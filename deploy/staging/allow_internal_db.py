"""Allow only the current app network/user/database in the host PostgreSQL HBA.

Run as root on the school server with --apply. Does not redeploy services or
change database contents, passwords, listen addresses, or the public DB tunnel.
"""
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

PROJECT = 'kant-google-20261028t013909z-f5b11c9'
IMAGE = 'sha256:a34e86d460bf5beee30cc5982b28f7209677cb30e0866a29f4a00f7b9cf1c920'
GATEWAY = '172.22.0.1'
SUBNET = '172.22.0.0/16'
RULE = 'host "kant-moa" "kant-moa" ' + SUBNET + ' scram-sha-256'
MARKER = '# KANT MOA app-only internal DB access\n'

PROBE = r'''
import asyncio,json,time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from database import engine
async def main():
 assert engine.url.database=='kant-moa' and engine.url.username=='kant-moa'
 result={}
 internal=create_async_engine(engine.url.set(host='172.22.0.1',port=5432),connect_args={'timeout':4,'command_timeout':5})
 try:
  async with engine.connect() as reference:
   baseline=dict((await reference.execute(text("SELECT pg_backend_pid() AS pid, (SELECT backend_start::text FROM pg_stat_activity WHERE pid=pg_backend_pid()) AS session_start, (SELECT oid::text FROM pg_database WHERE datname=current_database()) AS database_oid, extract(epoch from pg_postmaster_start_time())::text AS server_start"))).mappings().one())
   result['identity']={k:baseline[k] for k in ['database_oid','server_start']}
   try:
    async with internal.connect() as connection:
     same=await connection.scalar(text('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE pid=:pid AND backend_start::text=:started AND datname=current_database() AND usename=current_user)'),{'pid':baseline['pid'],'started':baseline['session_start']})
     result['same_database_proven']=bool(same)
     samples=[]
     for _ in range(3):
      started=time.monotonic(); await connection.execute(text('SELECT 1')); samples.append(round((time.monotonic()-started)*1000,2))
     result['select_1_roundtrip_ms']=samples
   except Exception as error:
    causes=[]; current=error
    for _ in range(5):
     if current is None: break
     causes.append(current); current=getattr(current,'orig',None) or current.__cause__
    result['hba_rejected']=any('no pg_hba.conf entry' in str(e).lower() for e in causes)
    result['same_database_proven']=False
 finally:
  await internal.dispose(); await engine.dispose()
 print(json.dumps(result))
asyncio.run(main())
'''


def command(args, data=None):
    result = subprocess.run(args, input=data, capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Command failed: ' + args[0])
    return result.stdout.decode().strip()


def pg(sql):
    return command(['runuser', '-u', 'postgres', '--', 'psql', '-X', '-q', '-t', '-A',
                    '-p', '5432', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-c', sql])


def atomic_write(path, content, original_stat):
    descriptor, temporary = tempfile.mkstemp(prefix='.kant-moa-hba-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), stat.S_IMODE(original_stat.st_mode))
            os.fchown(stream.fileno(), original_stat.st_uid, original_stat.st_gid)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configure(path, backup, verify):
    original = path.read_bytes()
    metadata = path.stat()
    assert pg('SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL') == '0', 'Existing HBA has parse errors'
    assert not any(line.strip() == RULE.encode() for line in original.splitlines()), 'Rule already exists; inspect instead of duplicating it'
    proposed = MARKER.encode() + RULE.encode() + b'\n' + original
    backup.write_bytes(original)
    backup.chmod(0o600)
    changed = False
    try:
        assert path.read_bytes() == original, 'HBA changed during preparation'
        # Mark before replace so interruption immediately after replacement also rolls back.
        changed = True
        atomic_write(path, proposed, metadata)
        assert pg('SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL') == '0', 'New HBA has parse errors'
        assert pg('SELECT pg_reload_conf()') == 't', 'Configuration reload failed'
        result = None
        for _ in range(5):
            time.sleep(0.25)
            result = verify()
            if result.get('same_database_proven'):
                return result
        raise RuntimeError('Internal same-database verification failed')
    except BaseException:
        if changed:
            current = path.read_bytes()
            if current not in [original, proposed]:
                raise RuntimeError('HBA was concurrently changed; backup preserved for manual review')
            if current == proposed:
                atomic_write(path, original, metadata)
                assert pg('SELECT pg_reload_conf()') == 't', 'HBA restore reload failed'
        raise


def main():
    assert os.geteuid() == 0 and '--apply' in sys.argv, 'Requires sudo and --apply'
    os.umask(0o077)
    for signum in [signal.SIGTERM, signal.SIGHUP]:
        signal.signal(signum, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    lock = os.open('/run/lock/kant-moa-internal-hba.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    root = Path(pwd.getpwnam('kant').pw_dir) / 'kant-moa'
    active_path = root / 'active-site.json'
    original_active = active_path.read_bytes()
    active = json.loads(original_active)
    assert active['project'] == PROJECT, 'Deployment changed; refresh preflight'
    cid = command(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT,
                   '--filter', 'label=com.docker.compose.service=api'])
    assert cid and '\n' not in cid
    api = json.loads(command(['docker', 'inspect', cid]))[0]
    assert api['Image'] == IMAGE and api['State']['Health']['Status'] == 'healthy', 'API changed or unhealthy'
    networks = api['NetworkSettings']['Networks']
    assert len(networks) == 1
    network_name, connection = next(iter(networks.items()))
    assert connection['Gateway'] == GATEWAY
    network = json.loads(command(['docker', 'network', 'inspect', network_name]))[0]
    assert SUBNET in [entry.get('Subnet') for entry in network['IPAM']['Config']]
    assert ipaddress.ip_address(connection['IPAddress']) in ipaddress.ip_network(SUBNET)
    def probe():
        return json.loads(command(['docker', 'exec', '-i', '--workdir', '/app/src', cid, 'python', '-'], PROBE.encode()))
    before = probe()
    if before.get('same_database_proven'):
        print(json.dumps({'status': 'INTERNAL_DB_ALREADY_ACCESSIBLE', **before}))
        return
    assert before.get('hba_rejected'), 'Failure is not an HBA rejection; no change made'
    local_identity = json.loads(pg("SELECT json_build_object('database_oid',(SELECT oid::text FROM pg_database WHERE datname='kant-moa'),'server_start',extract(epoch from pg_postmaster_start_time())::text)"))
    assert before['identity'] == local_identity, 'Host PostgreSQL differs from active database'
    assert pg("SELECT rolcanlogin AND rolpassword LIKE 'SCRAM-SHA-256$%' FROM pg_authid WHERE rolname='kant-moa'") == 't', 'Existing SCRAM role required; passwords are not changed'
    path = Path(pg('SHOW hba_file')).resolve(strict=True)
    assert path.name == 'pg_hba.conf' and path.is_file()
    backup_dir = root / 'backups' / ('internal-hba-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup_dir.mkdir(mode=0o700)
    assert active_path.read_bytes() == original_active, 'Active deployment changed'
    assert command(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT,
                    '--filter', 'label=com.docker.compose.service=api']) == cid
    result = configure(path, backup_dir / 'pg_hba.conf.before', probe)
    print(json.dumps({'status': 'INTERNAL_DB_ACCESS_READY', 'rule': RULE, 'gateway': GATEWAY,
                      'backup': str(backup_dir), 'same_database_proven': result['same_database_proven'],
                      'select_1_roundtrip_ms': result['select_1_roundtrip_ms'],
                      'api_connection_changed': False, 'database_data_changed': False,
                      'hba_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        print(json.dumps({'status': 'INTERNAL_DB_ACCESS_FAILED', 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, AssertionError) else 'Check preflight and the protected backup; API connection was not changed'}))
        raise SystemExit(1)
