"""Back up the active DB and apply only the reviewed shipping revision."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit, unquote

ROOT = Path.home() / 'kant-moa'
EXPECTED_ACTIVE = '8154a507e173b03f9f82fb5016bc66ec0a291e30436da0f8569e82a74766918e'
PARENT = '3f21520f9615'
TARGET = '4c726d1a91ab'
MIGRATION_SHA = 'b1cee322dc958d9551f8608f0e002a497fead0bb2c97471d5aa6d6b56cf7a50c'
CHECK = b'''
import asyncio, hashlib, json, os
from pathlib import Path
import asyncpg
from database import engine
from sqlalchemy.engine import make_url
async def main():
 actual=engine.url.render_as_string(hide_password=False)
 assert make_url(actual)==make_url(os.environ['DATABASE_URL'])
 con=await asyncpg.connect(actual.replace('postgresql+asyncpg://','postgresql://',1))
 try:
  async with con.transaction(readonly=True):
   revisions=list(await con.fetchval('SELECT array_agg(version_num ORDER BY version_num) FROM alembic_version') or [])
   shipment=bool(await con.fetchval("SELECT to_regclass('public.order_shipments') IS NOT NULL"))
   identity=dict(await con.fetchrow("SELECT current_database() AS database,(SELECT oid::text FROM pg_database WHERE datname=current_database()) AS database_oid,extract(epoch from pg_postmaster_start_time())::text AS server_start"))
   migration=Path('/app/migrations/versions/4c726d1a91ab_add_order_shipments.py')
   print(json.dumps({'revisions':revisions,'shipment':shipment,'identity':identity,'migration_sha256':hashlib.sha256(migration.read_bytes()).hexdigest()}))
 finally: await con.close();await engine.dispose()
asyncio.run(main())
'''


def command(args, *, env=None, timeout=120):
    result = subprocess.run(args, capture_output=True, env=env, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + args[0])
    return result.stdout


def inspect(cid):
    return json.loads(command(['docker', 'inspect', cid]))[0]


def python_in_api(cid, script):
    result = subprocess.run(['docker', 'exec', '-i', '--workdir', '/app/src', cid, 'python', '-'],
                            input=script, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError('API DB check failed')
    return json.loads(result.stdout)


def prepare_guard(active_bytes, check):
    assert hashlib.sha256(active_bytes).hexdigest() == EXPECTED_ACTIVE, 'Active deployment changed; rerun preflight'
    assert check['revisions'] == [PARENT], 'Unexpected migration parent; do not run initial migrations'
    assert check['shipment'] is False, 'Shipment table already exists; review before continuing'
    assert check['migration_sha256'] == MIGRATION_SHA, 'Migration differs from reviewed code'


def compare_business(before, after):
    expected = {name: value for name, value in before['tables'].items() if name != 'alembic_version'}
    actual = {name: value for name, value in after['tables'].items()
              if name not in {'alembic_version', 'order_shipments'}}
    return expected == actual and before['sequences'] == after['sequences']


def backup_failure(stderr):
    message = stderr.decode('utf-8', errors='replace').lower()
    for fragment, reason in [
        ('server version mismatch', 'PG_DUMP_VERSION_MISMATCH'),
        ('server version:', 'PG_DUMP_VERSION_MISMATCH'),
        ('no pg_hba.conf entry', 'PG_HBA_REJECTED'),
        ('password authentication failed', 'PASSWORD_AUTH_FAILED'),
        ('permission denied', 'BACKUP_PERMISSION_DENIED'),
        ('connection refused', 'CONNECTION_REFUSED'),
        ('timeout', 'CONNECTION_TIMEOUT'),
        ('could not translate host name', 'HOSTNAME_UNRESOLVED'),
    ]:
        if fragment in message:
            return reason
    return 'BACKUP_COMMAND_FAILED'


def localhost_identity(pg_env):
    sql = "SELECT json_build_object('database',current_database(),'database_oid',(SELECT oid::text FROM pg_database WHERE datname=current_database()),'server_start',extract(epoch from pg_postmaster_start_time())::text)::text"
    result = subprocess.run(['psql', '-X', '--no-password', '--tuples-only', '--no-align', '--command', sql],
                            env=pg_env, capture_output=True, timeout=30)
    if result.returncode:
        raise AssertionError('Localhost backup route rejected: ' + backup_failure(result.stderr or b''))
    return json.loads(result.stdout)


def main(*, backup_only=False):
    import fcntl
    os.umask(0o077)
    lock = os.open(ROOT / '.internal-db-deploy.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    active_path = ROOT / 'active-site.json'
    active_bytes = active_path.read_bytes()
    active = json.loads(active_bytes)
    ids = {}
    for service in ['api', 'web', 'gateway']:
        value = command(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + active['project'],
                         '--filter', 'label=com.docker.compose.service=' + service]).decode().strip()
        assert value and '\n' not in value
        ids[service] = inspect(value)['Id']
    api = inspect(ids['api'])
    assert api['State'].get('Health', {}).get('Status') == 'healthy'
    env = dict(value.split('=', 1) for value in api['Config']['Env'] if '=' in value)
    url = urlsplit(env['DATABASE_URL'])
    assert (url.hostname, url.port, unquote(url.path.lstrip('/')), unquote(url.username or '')) == ('172.22.0.1', 5432, 'kant-moa', 'kant-moa')
    initial_check = python_in_api(ids['api'], CHECK)
    prepare_guard(active_bytes, initial_check)
    spec = importlib.util.spec_from_file_location('snapshot_only', Path(active['release']) / 'deploy/staging/site_candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = python_in_api(ids['api'], module.SNAPSHOT)
    backup = ROOT / 'backups' / ('before-shipping-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    (backup / 'active-site.json').write_bytes(active_bytes)
    (backup / 'database-before.json').write_text(json.dumps(before, sort_keys=True))
    pg_env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
    # pg_dump runs on the school server, not inside Docker. Its native DB route is loopback.
    pg_env.update(PGHOST='127.0.0.1', PGPORT=str(url.port), PGDATABASE=unquote(url.path.lstrip('/')),
                  PGUSER=unquote(url.username), PGPASSWORD=unquote(url.password or ''), PGCONNECT_TIMEOUT='10')
    pg_env['LC_ALL'] = 'C'
    assert localhost_identity(pg_env) == initial_check['identity'], 'Localhost is a different DB; backup and migration stopped'
    print('Localhost backup route verified against the active API DB; HBA unchanged', flush=True)
    dump = backup / 'kant-moa.dump'
    print('Backing up the existing DB; services retained', flush=True)
    with dump.open('xb') as stream:
        result = subprocess.run(['pg_dump', '--format=custom', '--no-owner', '--no-acl'],
                                env=pg_env, stdout=stream, stderr=subprocess.PIPE, timeout=180)
    if result.returncode or dump.stat().st_size == 0:
        # Keep raw diagnostics private on the server; never print credentials or SQL.
        stderr = result.stderr or b''
        (backup / 'pg_dump.stderr').write_bytes(stderr)
        report = {'status': 'SHIPPING_BACKUP_FAILED', 'reason': backup_failure(stderr),
                  'backup': str(backup), 'exit_code': result.returncode,
                  'dump_bytes': dump.stat().st_size, 'migration_started': False}
        (backup / 'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
        raise AssertionError('Backup failed; migration not started. See classified reason and private server log.')
    command(['pg_restore', '--list', str(dump)])
    if backup_only:
        print(json.dumps({'status': 'SHIPPING_BACKUP_VERIFIED', 'backup': str(backup),
                          'dump_bytes': dump.stat().st_size, 'migration_started': False,
                          'services_changed': False}), flush=True)
        return
    assert active_path.read_bytes() == active_bytes, 'Deployment changed before migration'
    assert inspect(ids['api'])['State']['Running']
    prepare_guard(active_bytes, python_in_api(ids['api'], CHECK))
    print('Backup verified; applying only 3f21520f9615 -> 4c726d1a91ab', flush=True)
    # Standard Alembic execution: PostgreSQL DDL and revision update share its transaction.
    command(['docker', 'exec', '--workdir', '/app', ids['api'], 'python', '-m', 'alembic',
             'upgrade', TARGET], timeout=120)
    final = python_in_api(ids['api'], CHECK)
    assert final['revisions'] == [TARGET] and final['shipment'] is True
    after = python_in_api(ids['api'], module.SNAPSHOT)
    (backup / 'database-after.json').write_text(json.dumps(after, sort_keys=True))
    assert active_path.read_bytes() == active_bytes, 'Deployment changed during migration'
    services_unchanged = all(inspect(cid)['State']['Running'] for cid in ids.values())
    report = {'status': 'SHIPPING_MIGRATION_SUCCESS', 'revision': TARGET, 'backup': str(backup),
              'existing_business_data_unchanged': compare_business(before, after),
              'services_unchanged': services_unchanged,
              'order_shipments_count': after['tables']['order_shipments']['count']}
    (backup / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
    # Concurrent user traffic may change business rows. Never restore the DB automatically.
    assert report['existing_business_data_unchanged'], 'Business data changed; inspect snapshots without restoring DB'


if __name__ == '__main__':
    try:
        main(backup_only='--backup-only' in sys.argv)
    except Exception as error:
        print(json.dumps({'status': 'SHIPPING_MIGRATION_STOPPED', 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, AssertionError) else 'Inspect protected backup; services retained. No automatic DB restore.'}))
        raise SystemExit(1)
