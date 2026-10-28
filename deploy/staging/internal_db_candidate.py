"""Build a read-only localhost candidate on the current, DB-authorized network."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path.home() / 'kant-moa'
RELEASE = Path(__file__).resolve().parents[2]
GATEWAY = '172.22.0.1'
NETWORK = 'kant-google-20261028t013909z-f5b11c9_default'
PROJECT = 'kant-google-20261028t013909z-f5b11c9'
EXPECTED_API_IMAGE = 'sha256:a34e86d460bf5beee30cc5982b28f7209677cb30e0866a29f4a00f7b9cf1c920'
PUBLIC = 'https://letdown-kilometer-nutcase.ngrok-free.dev'

SETTINGS = b'''import json
from core.config import get_settings
from database import engine
print(json.dumps({'settings':get_settings().model_dump(mode='json'),'database_url':engine.url.render_as_string(hide_password=False)}))
'''
SNAPSHOT = b'''import asyncio,hashlib,json
import asyncpg
from database import engine
async def main():
 con=await asyncpg.connect(engine.url.render_as_string(hide_password=False).replace('postgresql+asyncpg://','postgresql://',1))
 try:
  async with con.transaction(isolation='repeatable_read',readonly=True):
   identity=dict(await con.fetchrow("SELECT current_database() AS database,(SELECT oid::text FROM pg_database WHERE datname=current_database()) AS database_oid,extract(epoch from pg_postmaster_start_time())::text AS server_start"))
   tables={}
   for row in await con.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"):
    name=row['tablename'];quoted='"'+name.replace('"','""')+'"'
    values=sorted(r['value'] for r in await con.fetch('SELECT row_to_json(t)::text AS value FROM public.'+quoted+' t'))
    tables[name]={'count':len(values),'sha256':hashlib.sha256(('\\n'.join(values)).encode()).hexdigest()}
   sequences=[dict(r) for r in await con.fetch("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")]
   print(json.dumps({'identity':identity,'tables':tables,'sequences':sequences},sort_keys=True))
 finally:await con.close();await engine.dispose()
asyncio.run(main())
'''


def command(args, data=None, timeout=90):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + args[0])
    return result.stdout


def inspect(cid):
    return json.loads(command(['docker', 'inspect', cid]))[0]


def private_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')
    path.chmod(0o600)


def settings(cid):
    return json.loads(command(['docker', 'exec', '-i', '--workdir', '/app/src', cid, 'python', '-'], SETTINGS))


def snapshot(cid):
    return json.loads(command(['docker', 'exec', '-i', '--workdir', '/app/src', cid, 'python', '-'], SNAPSHOT, timeout=120))


def internal_url(url):
    parsed = urllib.parse.urlsplit(url)
    assert urllib.parse.unquote(parsed.path.lstrip('/')) == 'kant-moa'
    assert urllib.parse.unquote(parsed.username or '') == 'kant-moa'
    assert parsed.scheme == 'postgresql+asyncpg' and '@' in parsed.netloc
    return urllib.parse.urlunsplit(parsed._replace(netloc=parsed.netloc.rsplit('@', 1)[0] + '@' + GATEWAY + ':5432'))


def effective_environment(container, effective):
    env = dict(row.split('=', 1) for row in container['Config']['Env'] if '=' in row)
    for key, value in effective.items():
        env[key.upper()] = value if isinstance(value, str) else json.dumps(value, separators=(',', ':'))
    return env


def write_env(path, values):
    assert all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) for key in values)
    assert all(isinstance(value, str) and not any(c in value for c in '\n\r\0') for value in values.values()), 'Multiline environment needs separate review'
    path.write_text(''.join(key + '=' + value + '\n' for key, value in values.items()), encoding='utf-8')
    path.chmod(0o600)


def get(base, path, expected=200):
    request = urllib.request.Request(base + path, headers={'ngrok-skip-browser-warning': 'true'})
    started = time.monotonic()
    try:
        response = urllib.request.urlopen(request, timeout=40)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        data = response.read()
        assert response.status == expected, 'Unexpected HTTP status: ' + path
        return data, response.headers, round(time.monotonic() - started, 3)


def verify(base, client_id):
    timings = {}
    for path in ['/health', '/api/health', '/', '/products', '/login', '/artists', '/api/docs']:
        _, _, timings[path] = get(base, path)
    products = json.loads(get(base, '/api/products?size=1')[0])
    assert products['total'] > 0
    first = products['items'][0]
    get(base, '/api/products/' + str(first['id']))
    if first['thumbnail_path']:
        assert first['thumbnail_path'].startswith(('/static/', '/uploads/'))
        image = urllib.parse.quote(first['thumbnail_path'], safe='/')
        assert get(base, '/api' + image)[0]
    doc = json.loads(get(base, '/api/openapi.json')[0])
    for path in ['/auth/google/config', '/auth/google', '/products', '/orders', '/admin/products', '/wishlist/ids']:
        assert path in doc['paths'], 'API route missing: ' + path
    assert doc['components']['securitySchemes']['OAuth2PasswordBearer']['flows']['password']['tokenUrl'] == 'auth/login'
    for path in ['/api/auth/me', '/api/orders', '/api/admin/products', '/api/wishlist/ids']:
        get(base, path, 401)
    google, headers, _ = get(base, '/api/auth/google/config')
    google = json.loads(google)
    assert client_id and google['client_id'] == client_id and google['nonce']
    cookie = headers.get('Set-Cookie', '').lower()
    assert 'httponly' in cookie and 'secure' in cookie and 'samesite=lax' in cookie
    return {'public_products': products['total'], 'api_paths': len(doc['paths']),
            'google_config_preserved': True, 'protected_api_without_token': 401, 'timings_seconds': timings}


def main():
    os.umask(0o077)
    manifest = json.loads((RELEASE / 'internal-release.json').read_text())
    for name, expected in manifest['files']:
        assert hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() == expected
    original_active = (ROOT / 'active-site.json').read_bytes()
    active = json.loads(original_active)
    assert active['project'] == PROJECT, 'Operating deployment changed; refresh preflight'
    ids = {}
    for service in ['api', 'web', 'gateway']:
        cid = command(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT,
                       '--filter', 'label=com.docker.compose.service=' + service]).decode().strip()
        assert cid and '\n' not in cid
        ids[service] = cid
    api, web, gateway = (inspect(ids[service]) for service in ['api', 'web', 'gateway'])
    assert api['Image'] == EXPECTED_API_IMAGE and api['State']['Health']['Status'] == 'healthy'
    assert web['State']['Health']['Status'] == 'healthy'
    assert NETWORK in api['NetworkSettings']['Networks']
    assert api['NetworkSettings']['Networks'][NETWORK]['Gateway'] == GATEWAY
    state_dir = ROOT / 'internal-db-state' / RELEASE.name
    state_dir.mkdir(parents=True, mode=0o700)
    original_settings = settings(ids['api'])
    assert original_settings['settings']['jwt_secret'] and original_settings['settings']['google_client_id']
    api_env = effective_environment(api, original_settings['settings'])
    api_env['DATABASE_URL'] = internal_url(original_settings['database_url'])
    web_env = dict(row.split('=', 1) for row in web['Config']['Env'] if '=' in row)
    suffix = RELEASE.name.replace('.', '-').lower()
    names = {service: 'kant-check-' + service + '-' + suffix for service in ['api', 'web', 'gateway']}
    web_env['API_INTERNAL_URL'] = 'http://' + names['api'] + ':8000'
    write_env(state_dir / 'api.env', api_env)
    write_env(state_dir / 'web.env', web_env)
    mounts = {m['Destination']: m for m in api['Mounts']}
    assert '/app/assets' in mounts and '/app/uploads' in mounts
    assert set(mounts) <= {'/app/assets', '/app/uploads'}, 'Additional API mounts need review'
    gateway_mount = next(m for m in gateway['Mounts'] if m['Destination'] == '/etc/nginx/conf.d/default.conf')
    proxy = Path(gateway_mount['Source']).read_text()
    assert 'http://api:8000' in proxy and 'http://web:3000' in proxy
    proxy = proxy.replace('http://api:8000', 'http://' + names['api'] + ':8000').replace('http://web:3000', 'http://' + names['web'] + ':3000')
    (state_dir / 'nginx.conf').write_text(proxy)
    images = {service: 'kant-moa-' + service + ':' + suffix for service in ['api', 'web']}
    saved = {'active': active, 'active_bytes_sha256': hashlib.sha256(original_active).hexdigest(),
             'ids': ids, 'api': api, 'web': web, 'gateway': gateway,
             'original_settings': original_settings, 'api_env': api_env, 'web_env': web_env,
             'names': names, 'images': images, 'manifest': manifest}
    private_json(state_dir / 'state.json', saved)
    report = {'status': 'INTERNAL_SITE_CANDIDATE_FAILED', 'application_commit': manifest['application_commit'],
              'source_sha256': manifest['source_sha256'], 'release': str(RELEASE), 'state_dir': str(state_dir),
              'operating_services_changed': False}
    try:
        for service in ['api', 'web']:
            report['phase'] = 'build-' + service
            print('Building internal DB candidate ' + service, flush=True)
            args = ['docker', 'build', '-f', str(RELEASE / ('deploy/staging/Dockerfile.' + service)), '-t', images[service]]
            if service == 'web':
                args += ['--build-arg', 'NEXT_PUBLIC_API_URL=' + PUBLIC + '/api']
            args += [str(RELEASE)]
            with (state_dir / ('build-' + service + '.log')).open('wb') as log:
                result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
            assert result.returncode == 0, 'Build failed; inspect protected candidate build log'
        report['phase'] = 'snapshot-before'
        before = snapshot(ids['api'])
        private_json(state_dir / 'database-before.json', before)
        args = ['docker', 'run', '-d', '--name', names['api'], '--network', NETWORK, '--env-file', str(state_dir / 'api.env')]
        for destination in ['/app/assets', '/app/uploads']:
            args += ['--mount', 'type=bind,source=' + mounts[destination]['Source'] + ',target=' + destination + ',readonly']
        report['phase'] = 'start-candidates'
        command(args + [images['api']])
        command(['docker', 'run', '-d', '--name', names['web'], '--network', NETWORK,
                 '--env-file', str(state_dir / 'web.env'), images['web']])
        command(['docker', 'run', '-d', '--name', names['gateway'], '--network', NETWORK,
                 '-p', '127.0.0.1::8080', '--mount',
                 'type=bind,source=' + str(state_dir / 'nginx.conf') + ',target=/etc/nginx/conf.d/default.conf,readonly', gateway['Image']])
        port = command(['docker', 'port', names['gateway'], '8080/tcp']).decode().strip().rsplit(':', 1)[1]
        assert port.isdigit()
        base = 'http://127.0.0.1:' + port
        for attempt in range(40):
            try:
                get(base, '/api/health')
                break
            except Exception:
                if attempt == 39:
                    raise
                time.sleep(1)
        report['phase'] = 'settings-and-database-verification'
        candidate_settings = settings(names['api'])
        expected_settings = {**original_settings['settings'], 'database_url': api_env['DATABASE_URL']}
        assert all(candidate_settings['settings'].get(key) == value for key, value in expected_settings.items()), 'Authentication/runtime settings differ'
        candidate_snapshot = snapshot(names['api'])
        assert candidate_snapshot == before, 'Candidate does not match original database snapshot'
        report['phase'] = 'http-verification'
        report['checks'] = verify(base, original_settings['settings']['google_client_id'])
        after = snapshot(ids['api'])
        private_json(state_dir / 'database-after.json', after)
        assert before == after, 'Database activity detected; do not promote without review'
        assert hashlib.sha256((ROOT / 'active-site.json').read_bytes()).hexdigest() == saved['active_bytes_sha256']
        assert all(inspect(cid)['State']['Running'] for cid in ids.values())
        report.update(status='INTERNAL_SITE_CANDIDATE_READY', same_database_proven=True,
                      database_snapshot_unchanged=True, authentication_settings_preserved=True,
                      candidate_url=base, phase='ready')
    except BaseException as error:
        report['error_type'] = type(error).__name__
        if isinstance(error, AssertionError):
            report['reason'] = str(error)
        for name in reversed(list(names.values())):
            logs = subprocess.run(['docker', 'logs', name], capture_output=True, timeout=30)
            (state_dir / (name + '.log')).write_bytes(logs.stdout + logs.stderr)
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=30)
        raise
    finally:
        private_json(RELEASE / 'report.json', report)
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        print(json.dumps({'status': 'INTERNAL_CANDIDATE_FAILED', 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, AssertionError) else 'Operating services retained; inspect protected candidate report'}), flush=True)
        raise SystemExit(1)
