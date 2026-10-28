"""Server-only key entry and web rollout, preserving the active internal DB route."""
import fcntl
from getpass import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path.home() / 'kant-moa'
RELEASE = Path(__file__).resolve().parents[2]
COMMIT = '0d31221cdd260617552204a46ccd7c0f33feead9'
ACTIVE_SHA = '8154a507e173b03f9f82fb5016bc66ec0a291e30436da0f8569e82a74766918e'
API_ID = '8e38a1cf4850105d9ecdc384728beafe693ae890bdae9b0b710e7de2cb58513b'


def atomic_env(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.site-env-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def normalize_key(value):
    value = value.strip().lstrip('\ufeff').strip()
    # Some terminals wrap pasted input in bracketed-paste markers.
    if value.startswith('\x1b[200~') and value.endswith('\x1b[201~'):
        value = value[6:-6].strip()
    assignment = re.fullmatch(r'(?:export\s+)?(?:GEMINI_API_KEY|\$env:GEMINI_API_KEY)\s*=\s*(.*)', value)
    if assignment:
        value = assignment.group(1).strip()
    if len(value) >= 2 and value[0] in {'\"', "'"} and value[-1] == value[0]:
        value = value[1:-1].strip()
    # Auth keys are opaque and may contain dots (AQ.*); validate safe env syntax only.
    assert re.fullmatch(r'[A-Za-z0-9._-]{20,4096}', value), 'Invalid API key format; value not saved'
    return value


def read_key():
    for _ in range(3):
        try:
            return normalize_key(getpass('Gemini API key (hidden; paste then Enter): '))
        except AssertionError:
            print('입력 형식을 확인해주세요. API 키 값 또는 GEMINI_API_KEY=값을 다시 붙여넣어 주세요. 입력은 화면에 보이지 않습니다.', flush=True)
    raise AssertionError('Invalid API key format after 3 attempts; value not saved')


def key_environment(original, key):
    assert re.fullmatch(r'[A-Za-z0-9._-]{20,4096}', key), 'Invalid API key format; value not saved'
    lines = [line for line in original.decode().splitlines() if not line.startswith('GEMINI_API_KEY=')]
    return ('\n'.join(lines) + '\nGEMINI_API_KEY=' + key + '\n').encode()


def command(args, data=None):
    result = subprocess.run(args, input=data, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError('Server preflight failed: ' + args[0])
    return result.stdout


def main():
    os.umask(0o077)
    assert sys.stdin.isatty(), 'Interactive SSH terminal required; key entry stopped'
    lock = os.open(ROOT / '.internal-db-deploy.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    active_path = ROOT / 'active-site.json'
    original_active = active_path.read_bytes()
    assert hashlib.sha256(original_active).hexdigest() == ACTIVE_SHA, 'Active deployment changed; rerun preflight'
    active = json.loads(original_active)
    manifest = json.loads((RELEASE / 'web-release.json').read_bytes())
    assert manifest['commit'] == COMMIT
    for name, digest in manifest['files']:
        assert hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() == digest, 'Release hash mismatch'
    api = json.loads(command(['docker', 'inspect', API_ID]))[0]
    assert api['State']['Running'] and api['State']['Health']['Status'] == 'healthy'
    assert api['Config']['Labels']['com.docker.compose.project'] == active['project']
    check = b'''import asyncio,json
import asyncpg
from database import engine
async def main():
 assert engine.url.host=='172.22.0.1' and engine.url.port==5432 and engine.url.database=='kant-moa'
 con=await asyncpg.connect(engine.url.render_as_string(hide_password=False).replace('postgresql+asyncpg://','postgresql://',1))
 try:
  async with con.transaction(readonly=True):
   assert await con.fetchval("SELECT array_agg(version_num ORDER BY version_num) FROM alembic_version")==['4c726d1a91ab']
   assert await con.fetchval("SELECT to_regclass('public.order_shipments') IS NOT NULL")
  print(json.dumps({'revision':'4c726d1a91ab','internal_database':True}))
 finally: await con.close();await engine.dispose()
asyncio.run(main())
'''
    result = json.loads(command(['docker', 'exec', '-i', '--workdir', '/app/src', API_ID, 'python', '-'], check))
    assert result['internal_database']
    print('Shipping revision and active internal DB verified. No DB writes will run.', flush=True)
    env_file = Path(active['env_file'])
    original_env = env_file.read_bytes()
    key = read_key()
    updated_env = key_environment(original_env, key)
    del key
    assert active_path.read_bytes() == original_active
    backup = ROOT / 'backups' / ('before-kantbot-key-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    (backup / 'site.env').write_bytes(original_env)
    atomic_env(env_file, updated_env)
    del updated_env
    try:
        spec = importlib.util.spec_from_file_location('web_rollout', RELEASE / 'deploy/staging/deploy_web.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print('Server key saved privately; building and verifying web only', flush=True)
        module.main(require_kantbot=True)
    except BaseException:
        report_path = RELEASE / 'report.json'
        report = json.loads(report_path.read_bytes()) if report_path.exists() else {}
        if report.get('rollback') != 'RECOVERY_REQUIRED':
            atomic_env(env_file, original_env)
            print('Previous server environment restored; inspect private release report', flush=True)
        else:
            print('RECOVERY_REQUIRED: environment retained for manual recovery; key values hidden', flush=True)
        raise
    print(json.dumps({'status': 'KANTBOT_WEB_DEPLOY_SUCCESS', 'commit': COMMIT,
                      'server_environment_backup': str(backup), 'release': str(RELEASE),
                      'shipping_revision': '4c726d1a91ab'}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        print(json.dumps({'status': 'KANTBOT_WEB_DEPLOY_STOPPED', 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, AssertionError) else 'Inspect private server report. Key values are never printed.'}), flush=True)
        raise SystemExit(1)
