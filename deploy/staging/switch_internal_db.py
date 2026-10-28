"""Promote an already-verified internal-DB candidate; restore images on failure."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

ROOT = Path.home() / 'kant-moa'
RELEASE = ROOT / 'internal-releases/internal-20261028T023408Z-9aa5138'
SOURCE_SHA256 = '754a96c75f5918e97a262aad1af0a77f8ddd244311d238799e34bbb893b53dcc'
COMMIT = '9aa513889060ab39dd07d836c21fb03f271c95b7'


def atomic_bytes(path, data):
    descriptor, name = tempfile.mkstemp(prefix='.kant-active-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def compose_base(active):
    base_release = Path(active['release']).resolve()
    assert base_release.parent == (ROOT / 'site-releases').resolve()
    result = ['docker', 'compose', '-p', active['project'], '--env-file', active['env_file'],
              '-f', str(base_release / 'deploy/staging/compose.site.yml')]
    added = set()
    for key in ['api_override', 'web_override']:
        path = active.get(key)
        if path and path not in added:
            result += ['-f', path]
            added.add(path)
    return result


def mount_identity(container):
    return sorted((m['Destination'], m['Source'], m['RW']) for m in container['Mounts'])


def original_mounts(container):
    assert all(m.get('Type', 'bind') == 'bind' for m in container['Mounts']), 'Non-bind mounts need review'
    return [{'type': 'bind', 'source': m['Source'], 'target': m['Destination'],
             'read_only': not m['RW'], 'bind': {'create_host_path': False}} for m in container['Mounts']]


def resolved_mounts(service):
    return sorted((m['target'], m['source'], not m.get('read_only', False)) for m in service.get('volumes', []))


def verify_retry(module, base, client_id):
    for attempt in range(3):
        try:
            return module.verify(base, client_id)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1)


def promote(module, state_dir, saved, ready):
    active_path = ROOT / 'active-site.json'
    original_active = active_path.read_bytes()
    assert hashlib.sha256(original_active).hexdigest() == saved['active_bytes_sha256'], 'Active deployment changed after candidate checks'
    active = json.loads(original_active)
    assert active == saved['active']
    base = compose_base(active)
    ids = saved['ids']
    for service, cid in ids.items():
        actual = module.command(base + ['ps', '-q', service]).decode().strip()
        assert actual and '\n' not in actual, 'Expected one operating service: ' + service
        current = module.inspect(actual)
        assert current['Id'] == saved[service]['Id'], 'Operating service changed: ' + service + ' (full container IDs differ)'
        assert current['State']['Running'] and current['Image'] == saved[service]['Image']
    assert module.inspect(ids['gateway'])['HostConfig']['PortBindings']['8080/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '8022'}]
    client_id = saved['original_settings']['settings']['google_client_id']
    candidate_api = module.inspect(saved['names']['api'])
    candidate_web = module.inspect(saved['names']['web'])
    assert candidate_api['State']['Running'] and candidate_web['State']['Running']
    assert module.inspect(saved['images']['api'])['Id'] == candidate_api['Image']
    assert module.inspect(saved['images']['web'])['Id'] == candidate_web['Image']
    expected_settings = {**saved['original_settings']['settings'], 'database_url': saved['api_env']['DATABASE_URL']}
    candidate_settings = module.settings(saved['names']['api'])['settings']
    assert all(candidate_settings.get(key) == value for key, value in expected_settings.items())
    print('Rechecking candidate and current database; operating services retained', flush=True)
    verify_retry(module, ready['candidate_url'], client_id)
    before = module.snapshot(ids['api'])
    assert module.snapshot(saved['names']['api']) == before, 'Current candidate database differs'
    module.private_json(state_dir / 'database-before-switch.json', before)
    web_env = {**saved['web_env'], 'API_INTERNAL_URL': 'http://api:8000'}
    override = state_dir / 'runtime.override.json'
    rollback = state_dir / 'rollback.override.json'
    module.private_json(override, {'services': {
        'api': {'image': candidate_api['Image'], 'environment': saved['api_env'], 'volumes': original_mounts(saved['api'])},
        'web': {'image': candidate_web['Image'], 'environment': web_env}}})
    old_api_env = module.effective_environment(saved['api'], saved['original_settings']['settings'])
    old_api_env['DATABASE_URL'] = saved['original_settings']['database_url']
    old_web_env = dict(row.split('=', 1) for row in saved['web']['Config']['Env'] if '=' in row)
    module.private_json(rollback, {'services': {
        'api': {'image': saved['api']['Image'], 'environment': old_api_env, 'volumes': original_mounts(saved['api'])},
        'web': {'image': saved['web']['Image'], 'environment': old_web_env}}})
    (state_dir / 'active-site.before.json').write_bytes(original_active)
    suffix = RELEASE.name.lower()
    for service in ['api', 'web']:
        module.command(['docker', 'tag', saved[service]['Image'], 'kant-moa-' + service + ':before-' + suffix])
    current_compose = base + ['-f', str(override)]
    resolved = json.loads(module.command(current_compose + ['config', '--format', 'json']))
    assert resolved['services']['api']['environment']['DATABASE_URL'] == saved['api_env']['DATABASE_URL']
    assert resolved['services']['api']['environment']['JWT_SECRET'] == old_api_env['JWT_SECRET']
    assert resolved['services']['web']['environment']['API_INTERNAL_URL'] == 'http://api:8000'
    assert resolved['services']['api']['restart'] == resolved['services']['web']['restart'] == 'unless-stopped'
    assert resolved_mounts(resolved['services']['api']) == mount_identity(saved['api']), 'Resolved asset/upload mounts differ'
    assert resolved_mounts(resolved['services']['web']) == mount_identity(saved['web']), 'Resolved web mounts differ'
    report = {'status': 'INTERNAL_DB_DEPLOY_FAILED', 'application_commit': COMMIT,
              'source_sha256': SOURCE_SHA256, 'release': str(RELEASE), 'backup': str(state_dir),
              'rollback': None, 'phase': 'prepared'}
    changed = False
    promoted_bytes = None
    try:
        assert active_path.read_bytes() == original_active, 'Operating state changed before switch'
        changed = True
        report['phase'] = 'replace-api-web'
        print('Replacing only API and web with verified images; same DB, original mounts retained', flush=True)
        module.command(current_compose + ['up', '-d', '--no-deps', '--no-build', '--force-recreate',
                       '--wait', '--wait-timeout', '120', 'api', 'web'], timeout=180)
        module.command(['docker', 'exec', ids['gateway'], 'nginx', '-s', 'reload'])
        current_api = module.command(current_compose + ['ps', '-q', 'api']).decode().strip()
        current_web = module.command(current_compose + ['ps', '-q', 'web']).decode().strip()
        assert current_api and '\n' not in current_api and current_web and '\n' not in current_web
        api, web = module.inspect(current_api), module.inspect(current_web)
        assert api['Image'] == candidate_api['Image'] and web['Image'] == candidate_web['Image']
        assert mount_identity(api) == mount_identity(saved['api']), 'Original assets/uploads mounts differ'
        assert mount_identity(web) == mount_identity(saved['web']), 'Original web mounts differ'
        actual_settings = module.settings(current_api)['settings']
        assert all(actual_settings.get(key) == value for key, value in expected_settings.items()), 'Runtime/auth settings differ'
        assert module.internal_url(actual_settings['database_url']) == actual_settings['database_url']
        current_gateway = module.command(current_compose + ['ps', '-q', 'gateway']).decode().strip()
        assert current_gateway and '\n' not in current_gateway
        assert module.inspect(current_gateway)['Id'] == saved['gateway']['Id'], 'Gateway container changed'
        report['phase'] = 'verify-operating-site'
        print('Verifying internal and public site, Google config, protected APIs and DB fingerprint', flush=True)
        report['internal'] = verify_retry(module, 'http://127.0.0.1:8022', client_id)
        report['public'] = verify_retry(module, module.PUBLIC, client_id)
        after = module.snapshot(current_api)
        module.private_json(state_dir / 'database-after-switch.json', after)
        assert before == after, 'Database activity detected; never restore DB automatically'
        assert active_path.read_bytes() == original_active, 'Active pointer changed during switch'
        active.update(web_override=str(override), api_override=str(override),
                      web_release=str(RELEASE), web_commit=COMMIT,
                      runtime_main_release=str(RELEASE), runtime_main_commit=COMMIT,
                      internal_db_gateway=module.GATEWAY, previous_active_backup=str(state_dir / 'active-site.before.json'))
        promoted_bytes = json.dumps(active, indent=2).encode()
        atomic_bytes(active_path, promoted_bytes)
        report.update(status='INTERNAL_DB_DEPLOY_SUCCESS', phase='complete', same_database_proven=True,
                      database_snapshot_unchanged=True, authentication_settings_preserved=True,
                      gateway_container_unchanged=True, internal_db_gateway=module.GATEWAY)
    except BaseException as error:
        report['error_type'] = type(error).__name__
        if isinstance(error, AssertionError):
            report['reason'] = str(error)
        if changed:
            try:
                assert active_path.read_bytes() in [original_active, promoted_bytes], 'Another deployment changed the pointer; manual recovery required'
                restore = base + ['-f', str(rollback)]
                module.command(restore + ['up', '-d', '--no-deps', '--no-build', '--force-recreate',
                               '--wait', '--wait-timeout', '120', 'api', 'web'], timeout=180)
                module.command(['docker', 'exec', ids['gateway'], 'nginx', '-s', 'reload'])
                verify_retry(module, 'http://127.0.0.1:8022', client_id)
                atomic_bytes(active_path, original_active)
                report['rollback'] = 'PREVIOUS_API_WEB_RESTORED'
            except BaseException as restore_error:
                report['rollback'] = 'MANUAL_RECOVERY_REQUIRED'
                report['rollback_error_type'] = type(restore_error).__name__
        raise
    finally:
        module.private_json(state_dir / 'switch-report.json', report)
        print(json.dumps(report), flush=True)
    # Candidate containers are disposable. Cleanup failure does not undo a verified deployment.
    for name in reversed(list(saved['names'].values())):
        try:
            result = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=30)
            if result.returncode:
                print('CANDIDATE_CLEANUP_PENDING: ' + name, flush=True)
        except (OSError, subprocess.TimeoutExpired):
            print('CANDIDATE_CLEANUP_PENDING: ' + name, flush=True)
    return report


def main():
    os.umask(0o077)
    for signum in [signal.SIGTERM, signal.SIGHUP]:
        signal.signal(signum, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    lock = os.open(ROOT / '.internal-db-deploy.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    ready = json.loads((RELEASE / 'report.json').read_text())
    manifest = json.loads((RELEASE / 'internal-release.json').read_text())
    assert ready['status'] == 'INTERNAL_SITE_CANDIDATE_READY'
    assert ready['database_snapshot_unchanged'] and ready['same_database_proven'] and ready['authentication_settings_preserved']
    assert ready['application_commit'] == manifest['application_commit'] == COMMIT
    assert ready['source_sha256'] == manifest['source_sha256'] == SOURCE_SHA256
    for name, digest in manifest['files']:
        assert hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() == digest
    state_dir = Path(ready['state_dir']).resolve()
    assert state_dir == ROOT / 'internal-db-state' / RELEASE.name
    saved = json.loads((state_dir / 'state.json').read_text())
    spec = importlib.util.spec_from_file_location('internal_candidate', RELEASE / 'deploy/staging/internal_db_candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    promote(module, state_dir, saved, ready)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        print(json.dumps({'status': 'INTERNAL_SWITCH_STOPPED', 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, AssertionError) else 'See protected switch-report.json; no automatic DB restore'}), flush=True)
        raise SystemExit(1)
