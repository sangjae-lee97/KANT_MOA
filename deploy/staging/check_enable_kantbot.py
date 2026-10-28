"""Check key registration, recovery and stale-deployment guards with synthetic data."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

fake_lock = SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda fd, mode: None)
with patch.dict(sys.modules, {'fcntl': fake_lock}):
    spec = importlib.util.spec_from_file_location('enable_kantbot', Path(__file__).with_name('enable_kantbot.py'))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)


def scenario(*, failure=False, stale=False, invalid=False, input_style='plain'):
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
        root = Path(folder)
        release = root / 'new-web'
        release.mkdir()
        (release / 'web-release.json').write_text(json.dumps({'commit': tool.COMMIT, 'files': []}))
        env_file = root / 'site.env'
        original = b'SITE_PORT=8022\nGEMINI_API_KEY=synthetic-prior-key-value\n'
        env_file.write_bytes(original)
        active_bytes = json.dumps({'project': 'test-only', 'env_file': str(env_file)}).encode()
        (root / 'active-site.json').write_bytes(active_bytes)
        key = 'synthetic-new-key-value-12345'
        inputs = {'plain': [key], 'assignment': ['GEMINI_API_KEY="' + key + '"'],
                  'retry': ['invalid key', 'export GEMINI_API_KEY=\'' + key + '\'']}[input_style]
        calls, descriptors = [], []
        tool.fcntl.flock = lambda fd, mode: descriptors.append(fd)

        def command(args, data=None):
            if args[:2] == ['docker', 'inspect']:
                return json.dumps([{'State': {'Running': True, 'Health': {'Status': 'healthy'}},
                                    'Config': {'Labels': {'com.docker.compose.project': 'test-only'}}}]).encode()
            assert args[:3] == ['docker', 'exec', '-i'] and data
            return b'{"revision":"4c726d1a91ab","internal_database":true}'

        def deploy(*, require_kantbot):
            assert require_kantbot and env_file.read_bytes().count(b'GEMINI_API_KEY=') == 1
            assert key.encode() in env_file.read_bytes()
            calls.append('deploy')
            if failure:
                (release / 'report.json').write_text(json.dumps({'rollback': 'PREVIOUS_WEB_RESTORED'}))
                raise RuntimeError('synthetic deploy failure')

        dummy_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _: None))
        output = io.StringIO()
        try:
            with patch.object(tool, 'ROOT', root), patch.object(tool, 'RELEASE', release), \
                 patch.object(tool, 'ACTIVE_SHA', 'stale' if stale else hashlib.sha256(active_bytes).hexdigest()), \
                 patch.object(tool, 'command', command), patch.object(tool.sys.stdin, 'isatty', return_value=True), \
                 patch.object(tool, 'getpass', side_effect=['invalid key'] * 3 if invalid else inputs), \
                 patch.object(os, 'O_NOFOLLOW', 0, create=True), \
                 patch.object(tool.importlib.util, 'spec_from_file_location', return_value=dummy_spec), \
                 patch.object(tool.importlib.util, 'module_from_spec', return_value=SimpleNamespace(main=deploy)), \
                 contextlib.redirect_stdout(output):
                try:
                    tool.main()
                except (AssertionError, RuntimeError):
                    assert failure or stale or invalid
                else:
                    assert not (failure or stale or invalid)
        finally:
            for fd in descriptors:
                os.close(fd)
        assert key not in output.getvalue()
        assert 'synthetic-prior-key-value' not in output.getvalue()
        if failure or stale or invalid:
            assert env_file.read_bytes() == original
        else:
            assert key.encode() in env_file.read_bytes()
        assert calls == ([] if stale or invalid else ['deploy'])


if __name__ == '__main__':
    scenario()
    scenario(failure=True)
    scenario(stale=True)
    scenario(invalid=True)
    scenario(input_style='assignment')
    scenario(input_style='retry')
    key = 'synthetic-new-key-value-12345'
    for value in [key, '"' + key + '"', "'" + key + "'", 'GEMINI_API_KEY=' + key,
                  'export GEMINI_API_KEY="' + key + '"', '$env:GEMINI_API_KEY = "' + key + '"',
                  '\x1b[200~' + key + '\x1b[201~', '\ufeff ' + key]:
        assert tool.normalize_key(value) == key
    auth_key = 'AQ.synthetic-auth-key-for-local-test-only-12345'
    assert tool.normalize_key(auth_key) == auth_key
    assert tool.normalize_key('GEMINI_API_KEY="' + auth_key + '"') == auth_key
    assert auth_key.encode() in tool.key_environment(b'SITE_PORT=8022\n', auth_key)
    for value in [auth_key + '\ninjected=value', auth_key + ' with space']:
        try:
            tool.normalize_key(value)
        except AssertionError:
            pass
        else:
            raise AssertionError('Unsafe multiline or whitespace key accepted')
    print('KANTBOT_KEY_CHECKS_PASSED: quoted/assignment/pasted input, retry, no secret output, failure restore, stale deployment, invalid key')
