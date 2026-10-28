"""Isolated deployment/rollback checks. No DB, network or real Docker operations."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('switch_internal', Path(__file__).with_name('switch_internal_db.py'))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def scenario(failure=None, short_ids=False):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        base_release = root / 'site-releases/previous'
        base_release.mkdir(parents=True)
        release = root / 'internal-releases/verified'
        release.mkdir(parents=True)
        state_dir = root / 'state'
        state_dir.mkdir()
        active = {'project': 'test-site', 'release': str(base_release), 'env_file': str(base_release / 'site.env'),
                  'api_override': 'previous-api.json', 'web_override': 'previous-web.json'}
        active_path = root / 'active-site.json'
        original = json.dumps(active).encode()
        active_path.write_bytes(original)
        env = {'DATABASE_URL': 'postgresql+asyncpg://kant-moa:test@172.22.0.1:5432/kant-moa',
               'JWT_SECRET': 'preserved-test-secret', 'GOOGLE_CLIENT_ID': 'preserved-client'}
        old_settings = {'database_url': 'postgresql+asyncpg://kant-moa:test@public.example:12799/kant-moa',
                        'jwt_secret': env['JWT_SECRET'], 'google_client_id': env['GOOGLE_CLIENT_ID']}
        new_settings = {**old_settings, 'database_url': env['DATABASE_URL']}
        mounts = [{'Destination': '/app/assets', 'Source': '/original/assets', 'RW': False},
                  {'Destination': '/app/uploads', 'Source': '/original/uploads', 'RW': True}]
        def container(image, web=False):
            return {'Image': image, 'Id': image, 'State': {'Running': True}, 'Mounts': [] if web else mounts,
                    'Config': {'Env': ['API_INTERNAL_URL=http://api:8000'] if web else ['JWT_SECRET=' + env['JWT_SECRET']]},
                    'HostConfig': {'PortBindings': {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8022'}]}}}
        old_api, old_web, gateway = container('old-api'), container('old-web', True), container('gateway')
        new_api, new_web = container('new-api'), container('new-web', True)
        fixtures = {'api-old': old_api, 'web-old': old_web, 'gateway-old': gateway,
                    'api-new': new_api, 'web-new': new_web,
                    'candidate-api': new_api, 'candidate-web': new_web,
                    'candidate-api-tag': new_api, 'candidate-web-tag': new_web}
        fixtures.update({'api-short': old_api, 'web-short': old_web, 'gateway-short': gateway,
                         'api-foreign': container('different-container')})
        saved = {'active': active, 'active_bytes_sha256': hashlib.sha256(original).hexdigest(),
                 'ids': {'api': 'api-old', 'web': 'web-old', 'gateway': 'gateway-old'},
                 'api': old_api, 'web': old_web, 'gateway': gateway,
                 'names': {'api': 'candidate-api', 'web': 'candidate-web', 'gateway': 'candidate-gateway'},
                 'images': {'api': 'candidate-api-tag', 'web': 'candidate-web-tag'},
                 'original_settings': {'settings': old_settings, 'database_url': old_settings['database_url']},
                 'api_env': env, 'web_env': {'API_INTERNAL_URL': 'http://candidate-api:8000'}}
        if short_ids:
            saved['ids'] = {service: service + '-short' for service in ['api', 'web', 'gateway']}
        calls = []
        phase = [0]
        data = {'identity': 'same-database', 'tables': {'products': {'count': 389}}}
        def command(args, **kwargs):
            calls.append(args)
            if args[-3:-1] == ['ps', '-q']:
                service = args[-1]
                if failure == 'service_changed' and service == 'api':
                    return b'api-foreign'
                return ('gateway-old' if service == 'gateway' else service + ('-new' if phase[0] == 1 else '-old')).encode()
            if args[-3:] == ['config', '--format', 'json']:
                configured = json.loads((state_dir / 'runtime.override.json').read_text())
                for service in ['api', 'web']:
                    configured['services'][service]['restart'] = 'unless-stopped'
                return json.dumps(configured).encode()
            if 'up' in args:
                phase[0] = 2 if str(state_dir / 'rollback.override.json') in args else 1
                if failure == 'partial_replace' and phase[0] == 1:
                    raise RuntimeError('Simulated partial replacement')
            return b''
        def verify(base, client_id):
            assert client_id == env['GOOGLE_CLIENT_ID']
            if base == 'https://public.example':
                if failure == 'public_check':
                    raise RuntimeError('Simulated public failure')
                if failure == 'concurrent_pointer':
                    active_path.write_text('{"other_deployment":true}')
            return {'public_products': 387}
        def snapshot(cid):
            return {'identity': 'same-database', 'tables': {'products': {'count': 390}}} if failure == 'concurrent_data' and cid == 'api-new' else data
        def settings(cid):
            return {'settings': {**new_settings, **({'jwt_secret': 'changed-secret'} if failure == 'auth_change' and cid == 'api-new' else {})}}
        def private_json(path, value):
            path.write_text(json.dumps(value))
        module = SimpleNamespace(command=command, inspect=lambda cid: fixtures[cid],
            settings=settings, snapshot=snapshot, private_json=private_json,
            effective_environment=lambda container, values: {key.upper(): value for key, value in values.items()},
            internal_url=lambda url: url, verify=verify, PUBLIC='https://public.example', GATEWAY='172.22.0.1')
        with patch.object(deploy, 'ROOT', root), patch.object(deploy, 'RELEASE', release), \
             patch.object(deploy.time, 'sleep', lambda _: None), \
             patch.object(deploy.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
            try:
                deploy.promote(module, state_dir, saved, {'candidate_url': 'http://candidate.example'})
                assert failure is None
            except (RuntimeError, AssertionError):
                assert failure is not None
        updates = [args for args in calls if 'up' in args]
        if failure == 'service_changed':
            assert not updates and active_path.read_bytes() == original
            assert not (state_dir / 'switch-report.json').exists()
            return
        report = json.loads((state_dir / 'switch-report.json').read_text())
        assert all(args[-2:] == ['api', 'web'] and '--no-deps' in args and '--no-build' in args for args in updates)
        assert all('down' not in args and 'stop' not in args for args in calls)
        assert all(args[0] == 'docker' for args in calls)
        if failure is None:
            assert report['status'] == 'INTERNAL_DB_DEPLOY_SUCCESS'
            current = json.loads(active_path.read_text())
            assert current['internal_db_gateway'] == '172.22.0.1'
            assert current['api_override'] == current['web_override']
            assert len(updates) == 1
        elif failure == 'concurrent_pointer':
            assert report['rollback'] == 'MANUAL_RECOVERY_REQUIRED'
            assert json.loads(active_path.read_text()) == {'other_deployment': True}
            assert len(updates) == 1
        else:
            assert report['rollback'] == 'PREVIOUS_API_WEB_RESTORED'
            assert active_path.read_bytes() == original
            assert len(updates) == 2
            restored = json.loads((state_dir / 'rollback.override.json').read_text())['services']
            assert restored['api']['image'] == 'old-api' and restored['web']['image'] == 'old-web'
            assert restored['api']['environment']['JWT_SECRET'] == env['JWT_SECRET']
            assert restored['api']['environment']['DATABASE_URL'] == old_settings['database_url']
        assert data == {'identity': 'same-database', 'tables': {'products': {'count': 389}}}


for failure in [None, 'public_check', 'partial_replace', 'auth_change', 'concurrent_data', 'concurrent_pointer']:
    scenario(failure)
scenario(None, short_ids=True)
scenario('public_check', short_ids=True)
scenario('service_changed', short_ids=True)
print('INTERNAL_SWITCH_SUCCESS_ROLLBACK_AUTH_AND_CONCURRENT_CHANGE_CHECKS_PASSED')
