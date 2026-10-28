"""Read-only inventory for moving the existing site to native systemd services.

Never starts containers, changes services, prints credentials, or executes SQL.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = Path.home() / 'kant-moa'


def run(args, timeout=15):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return -1, type(error).__name__


def runtime(name, args):
    path = shutil.which(name)
    if not path and name == 'uv':
        candidate = Path.home() / '.local/bin/uv'
        path = str(candidate) if candidate.is_file() else None
    if not path:
        return {'installed': False}
    code, output = run([path, *args])
    return {'installed': code == 0, 'path': path, 'version': output[:200]}


def directory(path):
    path = Path(path)
    try:
        return {'path': str(path), 'exists': path.is_dir(),
                'readable': os.access(path, os.R_OK | os.X_OK),
                'writable': os.access(path, os.W_OK | os.X_OK)}
    except OSError:
        return {'path': str(path), 'accessible': False}


def main():
    active = json.loads((ROOT / 'active-site.json').read_text())
    report = {'status': 'NATIVE_PREFLIGHT_OK', 'services_changed': False,
              'database_changed': False, 'containers_started': False,
              'active_web_commit': active.get('web_commit'),
              'free_disk_mb': shutil.disk_usage(ROOT).free // 1024 // 1024,
              'runtimes': {name: runtime(name, args) for name, args in [
                  ('python3', ['--version']), ('python3.13', ['--version']),
                  ('uv', ['--version']), ('node', ['--version']),
                  ('npm', ['--version']), ('nginx', ['-v']), ('psql', ['--version'])]}}
    report['sudo_noninteractive_available'] = run(['sudo', '-n', 'true'])[0] == 0
    report['services'] = {}
    for unit in ['kant-moa-api.service', 'kant-moa-ngrok.service', 'ngrok.service',
                 'nginx.service', 'postgresql.service']:
        _, output = run(['systemctl', 'show', unit, '--no-pager',
                         '--property=LoadState,ActiveState,SubState,UnitFileState,User,WorkingDirectory'])
        report['services'][unit] = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
    _, listeners = run(['ss', '-ltnH'])
    ports = {'5432', '8022', '8030', '8000', '3000', '18000', '13000', '18022'}
    report['relevant_listeners'] = [line for line in listeners.splitlines()
                                    if len(line.split()) > 3 and line.split()[3].rsplit(':', 1)[-1] in ports]
    report['existing_containers'] = {}
    # Inspect only the three already-running services. No docker run/exec/start/build.
    for service in ['api', 'web', 'gateway']:
        code, cid = run(['docker', 'ps', '-q', '--filter',
                         'label=com.docker.compose.project=' + active['project'],
                         '--filter', 'label=com.docker.compose.service=' + service])
        if code or not cid or '\n' in cid:
            report['existing_containers'][service] = {'metadata_available': False}
            continue
        code, output = run(['docker', 'inspect', cid])
        if code:
            report['existing_containers'][service] = {'metadata_available': False}
            continue
        item = json.loads(output)[0]
        env = dict(row.split('=', 1) for row in item['Config'].get('Env', []) if '=' in row)
        info = {'image_id': item['Image'], 'health': item['State'].get('Health', {}).get('Status'),
                'working_directory': item['Config'].get('WorkingDir'),
                'mounts': [{'target': m['Destination'], 'source': m['Source'], 'type': m['Type']}
                           for m in item.get('Mounts', [])]}
        if service == 'api':
            url = urllib.parse.urlsplit(env.get('DATABASE_URL', ''))
            info['database_target'] = {'host': url.hostname, 'port': url.port,
                                        'database': urllib.parse.unquote(url.path.lstrip('/'))}
            info['jwt_present'] = bool(env.get('JWT_SECRET'))
            for mount in item.get('Mounts', []):
                if mount['Destination'] in ['/app/assets', '/app/uploads']:
                    info.setdefault('file_directories', []).append(directory(mount['Source']))
        report['existing_containers'][service] = info
    report['source_directories'] = {}
    for label, path in [('api', active['release']), ('web', active.get('web_release', active['release']))]:
        path = Path(path)
        report['source_directories'][label] = {**directory(path),
            'backend_source': (path / 'backend/src/main.py').is_file(),
            'package_json': (path / 'package.json').is_file(),
            'public': (path / 'public').is_dir()}
    report['environment_file'] = {'exists': (ROOT / 'backend.env').is_file()}
    report['baseline_http'] = []
    for path in ['/health', '/api/products?size=1']:
        start = time.monotonic()
        try:
            with urllib.request.urlopen('http://127.0.0.1:8022' + path, timeout=15) as response:
                data = json.load(response)
                report['baseline_http'].append({'path': path, 'status': response.status,
                    'seconds': round(time.monotonic() - start, 3),
                    'public_products': data.get('total')})
        except Exception as error:
            report['baseline_http'].append({'path': path, 'error_type': type(error).__name__})
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
