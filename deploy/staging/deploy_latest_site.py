"""Roll out reviewed main using the existing candidate and rollback machinery."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal

ROOT = Path.home() / 'kant-moa'
RELEASE = Path(__file__).resolve().parents[2]
COMMIT = 'e0c7ad8f3f0d551d4b849fa513db34acffcda0a0'
ACTIVE_SHA = '1bc7715b4b091b247d21709ef874ca6bca9ab45393efec58b6e998932e1452e2'
API_IMAGE = 'sha256:3840773235ccd68706de45bd713f40f23805f0a3c9cf0aa4607fa71813c9288f'
WEB_IMAGE = 'sha256:b9372ff635a4779a3f8f5f20ba77030e0625bddd3581c7997cd5ac94af00fac0'
NETWORK = 'kant-google-20261028t013909z-f5b11c9_default'
PROJECT = 'kant-google-20261028t013909z-f5b11c9'
GATEWAY = '172.22.0.1'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure(candidate, chat, site_key):
    """Extend verification, including the old-version rollback verification path."""
    original_settings = candidate.settings
    original_verify = candidate.verify
    original_command = candidate.command
    original_write = candidate.private_json
    verify_new = [True]
    rollback_file = ROOT / 'internal-db-state' / RELEASE.name / 'rollback.override.json'

    def settings(cid):
        value = original_settings(cid)
        value['settings'].setdefault('password_reset_demo', False)
        value['settings'].setdefault('password_reset_expire_minutes', 15)
        assert value['settings']['password_reset_demo'] is False, 'Password-reset demo mode must remain disabled'
        return value

    def command(args, *positional, **kwargs):
        if 'up' in args and str(rollback_file) in args:
            verify_new[0] = False
        return original_command(args, *positional, **kwargs)

    def write(path, value):
        if path.name in {'runtime.override.json', 'rollback.override.json'}:
            value = copy.deepcopy(value)
            web = value['services']['web']['environment']
            assert web.get('GEMINI_API_KEY') == site_key, 'Existing Gemini setting differs; do not replace it'
            web['GEMINI_API_KEY'] = '${GEMINI_API_KEY:?Preserve the existing server key}'
        original_write(path, value)

    def verify(base, client_id):
        result = original_verify(base, client_id)
        if verify_new[0]:
            for path in ['/forgot-password', '/reset-password']:
                candidate.get(base, path)
            doc = json.loads(candidate.get(base, '/api/openapi.json')[0])
            for path in ['/auth/password-reset/request', '/auth/password-reset/confirm']:
                assert 'post' in doc['paths'].get(path, {}), 'New password-reset API missing'
            result.update(password_reset_pages=200, password_reset_api_registered=True, password_reset_demo=False)
        result['kantbot'] = chat.verify_chat(base)
        return result

    candidate.settings = settings
    candidate.command = command
    candidate.private_json = write
    candidate.verify = verify


def main():
    import fcntl
    os.umask(0o077)
    for signum in [signal.SIGTERM, signal.SIGHUP]:
        signal.signal(signum, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    lock = os.open(ROOT / '.internal-db-deploy.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    active_bytes = (ROOT / 'active-site.json').read_bytes()
    assert hashlib.sha256(active_bytes).hexdigest() == ACTIVE_SHA, 'Operating deployment changed; rerun preflight'
    active = json.loads(active_bytes)
    assert active['project'] == PROJECT
    manifest = json.loads((RELEASE / 'internal-release.json').read_bytes())
    assert manifest['application_commit'] == COMMIT
    for name, digest in manifest['files']:
        assert hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() == digest, 'Release source mismatch'
    candidate = load('latest_candidate', 'internal_db_candidate.py')
    switch = load('latest_switch', 'switch_internal_db.py')
    chat = load('latest_chat_check', 'deploy_web.py')
    candidate.RELEASE = RELEASE
    candidate.PROJECT = PROJECT
    candidate.NETWORK = NETWORK
    candidate.GATEWAY = GATEWAY
    candidate.EXPECTED_API_IMAGE = API_IMAGE
    switch.ROOT = ROOT
    switch.RELEASE = RELEASE
    switch.COMMIT = COMMIT
    switch.SOURCE_SHA256 = manifest['source_sha256']
    ids = {}
    for service in ['api', 'web']:
        cid = candidate.command(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT,
                                 '--filter', 'label=com.docker.compose.service=' + service]).decode().strip()
        assert cid and '\n' not in cid
        ids[service] = cid
        assert candidate.inspect(cid)['Image'] == {'api': API_IMAGE, 'web': WEB_IMAGE}[service], 'Operating image changed'
    env_lines = Path(active['env_file']).read_text().splitlines()
    keys = [line.split('=', 1)[1].strip().strip('\"\'') for line in env_lines if line.startswith('GEMINI_API_KEY=')]
    assert keys and keys[-1], 'Existing Gemini key missing; do not rotate or request a new key'
    web_env = dict(line.split('=', 1) for line in candidate.inspect(ids['web'])['Config']['Env'] if '=' in line)
    assert web_env.get('GEMINI_API_KEY') == keys[-1]
    check = b'''import asyncio,json
import asyncpg
from database import engine
async def main():
 assert engine.url.host=='172.22.0.1' and engine.url.port==5432 and engine.url.database=='kant-moa'
 con=await asyncpg.connect(engine.url.render_as_string(hide_password=False).replace('postgresql+asyncpg://','postgresql://',1))
 try:
  async with con.transaction(readonly=True):
   assert await con.fetchval('SELECT array_agg(version_num ORDER BY version_num) FROM alembic_version')==['4c726d1a91ab']
  print(json.dumps({'revision':'4c726d1a91ab','internal_database':True}))
 finally: await con.close();await engine.dispose()
asyncio.run(main())
'''
    checked = json.loads(candidate.command(['docker', 'exec', '-i', '--workdir', '/app/src', ids['api'], 'python', '-'], check))
    assert checked['internal_database']
    configure(candidate, chat, keys[-1])
    print('Building latest main candidate; existing DB, key and uploads retained. No migration or seed runs.', flush=True)
    candidate.main()
    ready = json.loads((RELEASE / 'report.json').read_bytes())
    assert ready['status'] == 'INTERNAL_SITE_CANDIDATE_READY'
    state_dir = Path(ready['state_dir']).resolve()
    assert state_dir == ROOT / 'internal-db-state' / RELEASE.name
    saved = json.loads((state_dir / 'state.json').read_bytes())
    report = switch.promote(candidate, state_dir, saved, ready)
    assert report['status'] == 'INTERNAL_DB_DEPLOY_SUCCESS'
    print(json.dumps({'status': 'LATEST_MAIN_DEPLOY_SUCCESS', 'application_commit': COMMIT,
                      'source_sha256': manifest['source_sha256'], 'release': str(RELEASE),
                      'backup': str(state_dir), 'password_reset_demo': False,
                      'database_unchanged': report['database_snapshot_unchanged'],
                      'authentication_settings_preserved': report['authentication_settings_preserved'],
                      'gateway_container_unchanged': report['gateway_container_unchanged']}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        print(json.dumps({'status': 'LATEST_MAIN_DEPLOY_STOPPED', 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, AssertionError) else 'Inspect protected candidate/switch report; no automatic DB restore.'}), flush=True)
        raise SystemExit(1)
