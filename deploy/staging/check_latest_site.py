"""Check latest-release verification and rollback compatibility without a server."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('latest_site', Path(__file__).with_name('deploy_latest_site.py'))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def scenario():
    key = 'synthetic-server-key-not-real'
    settings = {'settings': {'jwt_secret': 'synthetic-jwt'}}
    writes, commands, requests = [], [], []
    doc = {'paths': {name: {'post': {}} for name in ['/auth/password-reset/request', '/auth/password-reset/confirm']}}

    def get(base, path):
        requests.append(path)
        return json.dumps(doc).encode(), {}, 0.01

    candidate = SimpleNamespace(settings=lambda _: copy.deepcopy(settings), verify=lambda *_: {'homepage': 200},
        command=lambda args, *pos, **kw: commands.append(args), get=get,
        private_json=lambda path, value: writes.append(copy.deepcopy(value)))
    chat = SimpleNamespace(verify_chat=lambda _: {'status': 200})
    tool.configure(candidate, chat, key)
    enriched = candidate.settings('old-api')['settings']
    assert enriched['password_reset_demo'] is False and enriched['password_reset_expire_minutes'] == 15
    settings['settings']['password_reset_demo'] = True
    try:
        candidate.settings('unsafe-api')
    except AssertionError:
        pass
    else:
        raise AssertionError('Demo mode must never be enabled silently')
    settings['settings']['password_reset_demo'] = False
    config = {'services': {'api': {'environment': {'JWT_SECRET': 'synthetic-jwt'}},
                          'web': {'environment': {'GEMINI_API_KEY': key}}}}
    candidate.private_json(Path('runtime.override.json'), config)
    assert key not in json.dumps(writes[-1])
    assert config['services']['web']['environment']['GEMINI_API_KEY'] == key
    assert candidate.verify('http://candidate', 'client')['password_reset_api_registered']
    doc['paths'] = {}
    try:
        candidate.verify('http://bad-candidate', 'client')
    except AssertionError:
        pass
    else:
        raise AssertionError('New release without routes was accepted')
    # A restored old version has no new pages/API. Recovery must verify its old scope.
    rollback = tool.ROOT / 'internal-db-state' / tool.RELEASE.name / 'rollback.override.json'
    candidate.command(['docker', 'compose', '-f', str(rollback), 'up', 'api', 'web'])
    requests.clear()
    result = candidate.verify('http://restored-original', 'client')
    assert result['kantbot']['status'] == 200 and not requests
    assert commands


if __name__ == '__main__':
    scenario()
    print('LATEST_SITE_CHECKS_PASSED: demo-off guard, key preservation, new routes, old-version recovery')
