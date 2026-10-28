"""Exercise backup ordering and stop conditions without any server or DB access."""
import copy
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('shipping_rollout', Path(__file__).with_name('apply_shipping_migration.py'))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def scenario(*, backup_ok=True, revision=None, migration_ok=True, backup_only=False, same_database=True):
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
        root = Path(folder)
        release = root / 'release'
        (release / 'deploy/staging').mkdir(parents=True)
        (release / 'deploy/staging/site_candidate.py').write_text("SNAPSHOT=b'snapshot'\n")
        active_bytes = json.dumps({'project': 'test-only', 'release': str(release)}).encode()
        (root / 'active-site.json').write_bytes(active_bytes)
        env = ['DATABASE_URL=postgresql+asyncpg://kant-moa:local-test@172.22.0.1:5432/kant-moa']
        events, descriptors = [], []
        state = {'revision': revision or tool.PARENT}
        identity = {'database': 'kant-moa', 'database_oid': '42', 'server_start': '123.0'}
        before = {'tables': {'products': {'count': 2, 'sha256': 'unchanged'},
                              'alembic_version': {'count': 1, 'sha256': 'parent'}}, 'sequences': []}

        def command(args, **kwargs):
            if args[:3] == ['docker', 'ps', '-q']:
                return args[-1].split('=')[-1].encode()
            if args[:2] == ['docker', 'inspect']:
                return json.dumps([{'Id': args[-1], 'Config': {'Env': env},
                                    'State': {'Running': True, 'Health': {'Status': 'healthy'}}}]).encode()
            if args[0] == 'pg_restore':
                events.append('verify-backup')
                return b'valid backup'
            if 'alembic' in args:
                assert events == ['dump', 'verify-backup'], 'Migration ran before backup verification'
                events.append('upgrade')
                if not migration_ok:
                    raise RuntimeError('simulated transactional upgrade failure')
                state['revision'] = tool.TARGET
                return b''
            raise AssertionError('Unexpected command')

        def dump(args, **kwargs):
            if args[0] == 'psql':
                assert kwargs['env']['PGHOST'] == '127.0.0.1'
                host = identity if same_database else {**identity, 'database_oid': '999'}
                return SimpleNamespace(returncode=0, stdout=json.dumps(host).encode(), stderr=b'')
            assert args[0] == 'pg_dump'
            events.append('dump')
            kwargs['stdout'].write(b'test-backup')
            return SimpleNamespace(returncode=0 if backup_ok else 1,
                                   stderr=b'pg_dump: error: no pg_hba.conf entry. private-sentinel')

        def query(cid, script):
            if script == tool.CHECK:
                return {'revisions': [state['revision']], 'shipment': state['revision'] == tool.TARGET,
                        'identity': identity, 'migration_sha256': tool.MIGRATION_SHA}
            result = copy.deepcopy(before)
            if state['revision'] == tool.TARGET:
                result['tables']['alembic_version']['sha256'] = 'target'
                result['tables']['order_shipments'] = {'count': 0, 'sha256': 'empty'}
            return result

        fake_lock = SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda fd, mode: descriptors.append(fd))
        try:
            with patch.dict(sys.modules, {'fcntl': fake_lock}), patch.object(os, 'O_NOFOLLOW', 0, create=True), \
                 patch.object(tool, 'ROOT', root), patch.object(tool, 'EXPECTED_ACTIVE', tool.hashlib.sha256(active_bytes).hexdigest()), \
                 patch.object(tool, 'command', command), patch.object(tool, 'python_in_api', query), \
                 patch.object(tool.subprocess, 'run', dump):
                try:
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        tool.main(backup_only=backup_only)
                except (AssertionError, RuntimeError):
                    assert not (backup_ok and migration_ok and revision is None and same_database)
                else:
                    assert backup_ok and migration_ok and revision is None and same_database
        finally:
            for fd in descriptors:
                os.close(fd)
        if not same_database:
            assert events == [], 'Different localhost DB must stop before backup or upgrade'
        elif revision is not None:
            assert events == [], 'Unexpected parent must stop before backup or upgrade'
        elif not backup_ok:
            assert events == ['dump'], 'Failed backup must stop before upgrade'
            assert 'PG_HBA_REJECTED' in output.getvalue()
            assert 'private-sentinel' not in output.getvalue()
            assert next((root / 'backups').glob('*/pg_dump.stderr')).read_bytes().endswith(b'private-sentinel')
        elif backup_only:
            assert events == ['dump', 'verify-backup'], 'Backup-only must never upgrade'
            assert 'SHIPPING_BACKUP_VERIFIED' in output.getvalue()
        else:
            assert events == ['dump', 'verify-backup', 'upgrade']


if __name__ == '__main__':
    scenario()
    scenario(backup_ok=False)
    scenario(revision='unexpected-parent')
    scenario(migration_ok=False)
    scenario(backup_only=True)
    scenario(same_database=False)
    for message, expected in [(b'pg_dump: aborting because of server version mismatch', 'PG_DUMP_VERSION_MISMATCH'),
                              (b'password authentication failed', 'PASSWORD_AUTH_FAILED'),
                              (b'permission denied for table example', 'BACKUP_PERMISSION_DENIED')]:
        assert tool.backup_failure(message) == expected
    print('SHIPPING_ROLLOUT_CHECKS_PASSED: localhost identity/mismatch, backup ordering/failure, private diagnostics, backup-only, wrong parent, upgrade failure')
