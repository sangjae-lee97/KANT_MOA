"""Web deploy success/rollback checks using only temporary files and fakes."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deploy_web', Path(__file__).with_name('deploy_web.py'))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def scenario(fail, shared_override=False, *, kantbot=False, ai_fail=False):
    with tempfile.TemporaryDirectory(prefix='kant-web-deploy-test-', dir=Path(__file__).resolve().parent) as folder:
        root = Path(folder).resolve()
        base_release = root / 'site-releases/base'; base_release.mkdir(parents=True)
        release = root / 'web-releases/new'; release.mkdir(parents=True)
        env = base_release / 'site.env'; env.write_text('SITE_PORT=8022\n' + ('GEMINI_API_KEY=synthetic-new-key\n' if kantbot else ''))
        active = {'release': str(base_release), 'env_file': str(env), 'project': 'fake-site'}
        active['api_override'] = str(root / 'internal-api.override.json')
        active['web_override'] = active['api_override'] if shared_override else str(root / 'previous-web.override.json')
        (root / 'active-site.json').write_text(json.dumps(active))
        (release / 'web-release.json').write_text(json.dumps({'files': [], 'commit': 'fake-commit', 'source_sha256': 'fake-digest'}))
        config = release / 'src/components/home/heroVideos.ts'
        config.parent.mkdir(parents=True)
        video_path = 'https://example.com/tws-original.mp4' if fail else '/sources/tws.versioned.mp4'
        config.write_text('tws: { src: "' + video_path + '" }')
        calls = []
        ai_calls = []
        def command(args, **kwargs):
            calls.append(args)
            if args[-3:-1] == ['ps', '-q']: return (args[-1] + '-id').encode()
            if args[:2] == ['docker', 'port']: return b'127.0.0.1:12345'
            if args[:2] == ['docker', 'run'] and kantbot:
                assert kwargs['env']['GEMINI_API_KEY'] == 'synthetic-new-key'
                assert 'synthetic-new-key' not in args
            if args[:2] == ['docker', 'exec'] and args[-1] == '-': return b'{"tables":{}}'
            return b''
        def inspect(cid):
            return {'Image': 'sha256:old-' + cid,
                    'State': {'Health': {'Status': 'healthy'}},
                    'Config': {'Env': ['API_INTERNAL_URL=http://api:8000'] + (['GEMINI_API_KEY=synthetic-old-key'] if kantbot else [])},
                    'NetworkSettings': {'Networks': {'fake-site_default': {}}},
                    'HostConfig': {'PortBindings': {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8022'}]}}}
        def verify(base, video_path):
            assert video_path == ('https://example.com/tws-original.mp4' if fail else '/sources/tws.versioned.mp4')
            if fail and base == deploy.PUBLIC: raise RuntimeError('simulated failure')
            return {'homepage': 200}
        def verify_ai(base):
            ai_calls.append(base)
            if ai_fail and base == deploy.PUBLIC:
                raise RuntimeError('simulated AI failure')
            return {'status': 200, 'reply_characters': 25}
        dummy_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _: None))
        with patch.object(deploy, 'ROOT', root), patch.object(deploy, 'RELEASE', release), \
             patch.object(deploy, 'command', command), patch.object(deploy, 'inspect', inspect), \
             patch.object(deploy, 'verify_web', verify), patch.object(deploy.time, 'sleep', lambda _: None), \
             patch.object(deploy, 'verify_chat', verify_ai), \
             patch.object(deploy.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
             patch.object(deploy.importlib.util, 'spec_from_file_location', return_value=dummy_spec), \
             patch.object(deploy.importlib.util, 'module_from_spec', return_value=SimpleNamespace(SNAPSHOT=b'fake-read-only')):
            try: deploy.main(require_kantbot=kantbot)
            except RuntimeError: assert fail or ai_fail
        report = json.loads((release / 'report.json').read_text())
        current = json.loads((root / 'active-site.json').read_text())
        if fail or ai_fail:
            assert report['rollback'] == 'PREVIOUS_WEB_RESTORED'
            assert current == active
            assert json.loads((release / 'web.override.json').read_text())['services']['web']['image'] == 'sha256:old-web-id'
            if kantbot:
                assert json.loads((release / 'web.override.json').read_text())['services']['web']['environment']['GEMINI_API_KEY'] == 'synthetic-old-key'
        else:
            assert report['status'] == 'WEB_DEPLOY_SUCCESS'
            assert report['api_container_unchanged'] and report['database_unchanged']
            assert current['web_commit'] == 'fake-commit'
            if kantbot:
                assert report['candidate_chat']['status'] == report['public_chat']['status'] == 200
                assert 'synthetic-new-key' not in (release / 'web.override.json').read_text()
        if kantbot:
            assert ai_calls
        updates = [args for args in calls if 'up' in args]
        assert updates and all(args[-1] == 'web' and '--no-deps' in args and '--no-build' in args for args in updates)
        assert all('down' not in args and 'stop' not in args for args in calls)
        assert current['api_override'] == active['api_override']
        compose_calls = [args for args in calls if args[:2] == ['docker', 'compose']]
        assert compose_calls and all(args.count(active['api_override']) == 1 for args in compose_calls)
        assert all(args.count(active['web_override']) == 1 for args in compose_calls)


for shared_override in [False, True]:
    scenario(False, shared_override)
    scenario(True, shared_override)
    scenario(False, shared_override, kantbot=True)
    scenario(False, shared_override, kantbot=True, ai_fail=True)
print('WEB_ONLY_SUCCESS_AND_ROLLBACK_CHECKS_PASSED')
