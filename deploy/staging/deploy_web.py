"""Deploy only the web service of the existing site. No SQL/migration/seed writes."""
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path.home() / 'kant-moa'
RELEASE = Path(__file__).resolve().parents[2]
PUBLIC = 'https://letdown-kilometer-nutcase.ngrok-free.dev'


def command(args, *, env=None, data=None, timeout=60):
    result = subprocess.run(args, env=env, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + args[0])
    return result.stdout


def inspect(cid):
    return json.loads(command(['docker', 'inspect', cid]))[0]


def verify_web(base, video_path='/sources/tws.mp4'):
    request = urllib.request.Request(base + '/', headers={'ngrok-skip-browser-warning': 'true'})
    started = time.monotonic()
    first_video = None
    content = b''
    with urllib.request.urlopen(request, timeout=45) as response:
        assert response.status == 200
        while chunk := response.read1(16384):
            content += chunk
            if first_video is None and ('src="' + video_path + '"').encode() in content:
                first_video = round(time.monotonic() - started, 3)
    assert first_video is not None, 'Initial video missing'
    assert b'data-precedence="default"' not in content, 'Banner font still blocks streaming'
    with urllib.request.urlopen(base + '/login', timeout=30) as response:
        assert response.status == 200
    return {'homepage': 200, 'login': 200, 'first_video_html_seconds': first_video}


def verify_chat(base):
    request = urllib.request.Request(base + '/api/chat',
        data=json.dumps({'message': '이미 발송된 주문도 직접 취소할 수 있나요?', 'history': []}).encode(),
        headers={'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true'}, method='POST')
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.loads(response.read())
        assert response.status == 200 and isinstance(result.get('reply'), str) and result['reply'].strip(), 'AI reply missing'
    return {'status': 200, 'reply_characters': len(result['reply'])}


def main(*, require_kantbot=False):
    os.umask(0o077)
    active_path = ROOT / 'active-site.json'
    original_active = active_path.read_text()
    active = json.loads(original_active)
    base_release = Path(active['release']).resolve()
    assert base_release.parent == (ROOT / 'site-releases').resolve()
    manifest = json.loads((RELEASE / 'web-release.json').read_text())
    for name, expected in manifest['files']:
        assert hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() == expected
    hero_config = (RELEASE / 'src/components/home/heroVideos.ts').read_text(encoding='utf-8')
    initial_video = re.search(r'\btws:\s*\{\s*src:\s*"([^"]+)"', hero_config).group(1)
    assert initial_video.startswith(('/sources/', 'https://')) and initial_video.endswith('.mp4')
    # Reuse the deployed candidate's read-only DB snapshot. Importing does not run its main().
    spec = importlib.util.spec_from_file_location('snapshot', base_release / 'deploy/staging/site_candidate.py')
    snapshot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snapshot)
    env_file = Path(active['env_file'])
    env = {**os.environ, **dict(line.split('=', 1) for line in env_file.read_text().splitlines() if line)}
    assert env['SITE_PORT'] == '8022'
    base = ['docker', 'compose', '-p', active['project'], '--env-file', str(env_file),
            '-f', str(base_release / 'deploy/staging/compose.site.yml')]
    added_overrides = set()
    for key in ['api_override', 'web_override']:
        override_path = active.get(key)
        if override_path and override_path not in added_overrides:
            base += ['-f', override_path]
            added_overrides.add(override_path)
    ids = {service: command(base + ['ps', '-q', service], env=env).decode().strip()
           for service in ['api', 'web', 'gateway']}
    assert all(ids.values()) and all('\n' not in cid for cid in ids.values())
    api, old_web, gateway = (inspect(ids[service]) for service in ['api', 'web', 'gateway'])
    assert api['State']['Health']['Status'] == old_web['State']['Health']['Status'] == 'healthy'
    assert gateway['HostConfig']['PortBindings']['8080/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '8022'}]
    networks = set(api['NetworkSettings']['Networks']) & set(old_web['NetworkSettings']['Networks'])
    assert len(networks) == 1
    original_web_env = dict(item.split('=', 1) for item in old_web['Config']['Env'] if '=' in item)
    web_env = dict(original_web_env)
    if env.get('GEMINI_API_KEY'):
        web_env['GEMINI_API_KEY'] = env['GEMINI_API_KEY']
    if require_kantbot:
        assert web_env.get('GEMINI_API_KEY'), 'Server Gemini key required'
    assert web_env['API_INTERNAL_URL'] == 'http://api:8000'
    backup = ROOT / 'backups' / ('before-' + RELEASE.name)
    backup.mkdir(parents=True, exist_ok=False)
    (backup / 'active-site.json').write_text(original_active)
    command(['docker', 'tag', old_web['Image'], 'kant-moa-web:before-' + RELEASE.name.lower()])
    image = 'kant-moa-web:' + RELEASE.name.lower()
    print('Building web only; existing API and database retained', flush=True)
    with (RELEASE / 'build.log').open('wb') as log:
        built = subprocess.run(['docker', 'build', '-f', str(RELEASE / 'deploy/staging/Dockerfile.web'),
                                '--build-arg', 'NEXT_PUBLIC_API_URL=' + PUBLIC + '/api', '-t', image, str(RELEASE)],
                               stdout=log, stderr=subprocess.STDOUT, timeout=1800)
    assert built.returncode == 0, 'Web build failed; inspect protected server build.log'
    before = json.loads(command(['docker', 'exec', '-i', ids['api'], 'python', '-'], data=snapshot.SNAPSHOT))
    (backup / 'database-before.json').write_text(json.dumps(before, sort_keys=True))
    candidate_name = 'kant-web-check-' + RELEASE.name.lower()
    override = RELEASE / 'web.override.json'
    changed = False
    report = {'status': 'WEB_DEPLOY_FAILED', 'commit': manifest['commit'],
              'source_sha256': manifest['source_sha256'], 'release': str(RELEASE),
              'backup': str(backup), 'api_container_unchanged': None,
              'database_unchanged': None, 'rollback': None}
    try:
        args = ['docker', 'run', '-d', '--name', candidate_name, '--network', networks.pop(),
                '-p', '127.0.0.1::3000', '--label', 'kant.web.candidate=true']
        for key in web_env:
            args += ['-e', key]
        command(args + [image], env={**os.environ, **web_env})
        port = command(['docker', 'port', candidate_name, '3000/tcp']).decode().strip().rsplit(':', 1)[1]
        for attempt in range(20):
            try:
                report['candidate'] = verify_web('http://127.0.0.1:' + port, initial_video)
                break
            except Exception:
                if attempt == 19: raise
                time.sleep(1)
        if require_kantbot:
            report['candidate_chat'] = verify_chat('http://127.0.0.1:' + port)
        assert active_path.read_text() == original_active, 'Active deployment changed during build; candidate not promoted'
        print('Candidate web verified; replacing web service only', flush=True)
        compose_web_env = dict(web_env)
        if env.get('GEMINI_API_KEY'):
            # Resolve from site.env at runtime, never duplicate the new key in the override file.
            compose_web_env['GEMINI_API_KEY'] = '${GEMINI_API_KEY:?Set the server Gemini key}'
        override.write_text(json.dumps({'services': {'web': {'image': image, 'environment': compose_web_env}}}))
        compose = base + ['-f', str(override)]
        changed = True
        command(compose + ['up', '-d', '--no-deps', '--no-build', '--force-recreate',
                           '--wait', '--wait-timeout', '120', 'web'], env=env, timeout=180)
        # nginx resolves upstream IPs on load; reload after Docker replaces the web IP.
        command(['docker', 'exec', ids['gateway'], 'nginx', '-s', 'reload'])
        for attempt in range(10):
            try:
                report['public'] = verify_web(PUBLIC, initial_video)
                break
            except Exception:
                if attempt == 9: raise
                time.sleep(1)
        if require_kantbot:
            report['public_chat'] = verify_chat(PUBLIC)
        current_api = command(base + ['ps', '-q', 'api'], env=env).decode().strip()
        report['api_container_unchanged'] = current_api == ids['api'] and inspect(current_api)['Image'] == api['Image']
        assert report['api_container_unchanged']
        after = json.loads(command(['docker', 'exec', '-i', current_api, 'python', '-'], data=snapshot.SNAPSHOT))
        (RELEASE / 'database-after.json').write_text(json.dumps(after, sort_keys=True))
        report['database_unchanged'] = before == after
        assert report['database_unchanged'], 'DB activity detected; inspect snapshots, never restore DB automatically'
        active.update(web_override=str(override), web_release=str(RELEASE), web_commit=manifest['commit'])
        active_path.write_text(json.dumps(active, indent=2))
        report['status'] = 'WEB_DEPLOY_SUCCESS'
    except BaseException as error:
        report['error_type'] = type(error).__name__
        if changed:
            try:
                override.write_text(json.dumps({'services': {'web': {'image': old_web['Image'], 'environment': original_web_env}}}))
                command(base + ['-f', str(override), 'up', '-d', '--no-deps', '--no-build', '--force-recreate',
                                '--wait', '--wait-timeout', '120', 'web'], env=env, timeout=180)
                command(['docker', 'exec', ids['gateway'], 'nginx', '-s', 'reload'])
                active_path.write_text(original_active)
                report['rollback'] = 'PREVIOUS_WEB_RESTORED'
            except Exception as recovery_error:
                report['rollback'] = 'RECOVERY_REQUIRED'
                report['rollback_error_type'] = type(recovery_error).__name__
        raise
    finally:
        subprocess.run(['docker', 'rm', '-f', candidate_name], capture_output=True, timeout=45)
        (RELEASE / 'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
