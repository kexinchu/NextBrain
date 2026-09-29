"""Static SSH discovery and explicitly requested, bounded read-only inventory probes."""
from __future__ import annotations

import glob
import re
import shlex
import subprocess
from pathlib import Path

from autoresearch.io import utc_stamp

from .service import uid
from .store import Store, encoded

ALIAS = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')


def configuration(path: Path) -> tuple[list[str], list[str]]:
    aliases, hazards, visited = set(), set(), set()

    def read(current: Path):
        current = current.expanduser().resolve()
        if current in visited:
            return
        visited.add(current)
        for line in current.read_text().splitlines():
            parts = shlex.split(line, comments=True)
            if not parts:
                continue
            if '=' in parts[0]:
                key, value = parts[0].split('=', 1)
                parts = [key] + ([value] if value else []) + parts[1:]
            if len(parts) > 1 and parts[1] == '=':
                parts.pop(1)
            key, values = parts[0].lower(), parts[1:]
            if key == 'host':
                aliases.update(v for v in values if ALIAS.fullmatch(v))
            if key == 'match' and any(v.lower() == 'exec' for v in values):
                hazards.add('Match exec')
            if key == 'include':
                for value in values:
                    pattern = Path(value).expanduser()
                    if not pattern.is_absolute():
                        pattern = path.expanduser().parent / pattern
                    for included in sorted(glob.glob(str(pattern))):
                        read(Path(included))
    read(path)
    return sorted(aliases), sorted(hazards)


def import_config(store: Store, path: Path) -> list[dict]:
    path = path.expanduser().resolve(strict=True)
    aliases, hazards = configuration(path)
    with store.connect() as db:
        for alias in aliases:
            data = encoded({'discovery': 'static-config', 'gpu': 'UNKNOWN', 'hazards': hazards})
            db.execute('INSERT INTO machines VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                       'config_path=excluded.config_path,updated_at=excluded.updated_at',
                       (alias, str(path), data, utc_stamp()))
    return [{'alias': alias, 'hazards': hazards} for alias in aliases]


# Fixed inventory only; no model-supplied shell snippets or installation commands.
INVENTORY = r'''
printf '__ROS_HOSTNAME__\n'; hostname
printf '__ROS_GPU__\n'; nvidia-smi --query-gpu=name,memory.total,driver_version,memory.free --format=csv,noheader,nounits 2>/dev/null || true
printf '__ROS_CUDA__\n'; nvidia-smi 2>/dev/null | head -4; nvcc --version 2>/dev/null | tail -1
printf '__ROS_PYTHON__\n'; python3 --version 2>&1
printf '__ROS_DISK__\n'; df -Pk .
printf '__ROS_GIT__\n'; git --version 2>&1
printf '__ROS_DOCKER__\n'; docker --version 2>&1
printf '__ROS_DIRECTORIES__\n'; pwd; find . -maxdepth 1 -type d ! -name '.*' -print 2>/dev/null | head -30
'''


def probe(store: Store, alias: str) -> dict:
    if not ALIAS.fullmatch(alias):
        raise ValueError('invalid SSH alias')
    machine = store.get('machines', alias)
    path = Path(machine['config_path'])
    aliases, hazards = configuration(path)
    if alias not in aliases:
        raise ValueError('alias is no longer present in its SSH config')
    if hazards:
        raise ValueError('probe refuses config containing Match exec; use a static inventory config')
    argv = ['ssh', '-F', str(path), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
            '-o', 'ConnectionAttempts=1', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'PermitLocalCommand=no', '-o', 'ProxyCommand=none', '-o', 'ProxyJump=none',
            '-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'ClearAllForwardings=yes',
            '-o', 'UpdateHostKeys=no', '-o', 'AddKeysToAgent=no', '-o', 'Tunnel=no',
            '-o', 'RemoteCommand=none', '-o', 'ForwardAgent=no', '-o', 'ForwardX11=no', '-o', 'RequestTTY=no',
            alias, 'sh -s']
    try:
        result = subprocess.run(argv, input=INVENTORY, text=True, capture_output=True, timeout=30)
        data = {'status': 'OK' if result.returncode == 0 else 'UNREACHABLE',
                'exit_code': result.returncode, 'stderr': result.stderr[-4000:], 'inventory': {}}
        sections = re.split(r'__ROS_([A-Z]+)__\n', result.stdout)
        data['inventory'] = {sections[i].lower(): sections[i+1].strip()[:12000]
                             for i in range(1, len(sections)-1, 2)}
        gpu_lines = data['inventory'].get('gpu', '').splitlines()
        data['gpu_count'] = len(gpu_lines) if gpu_lines else None
        if data['status'] == 'OK' and not data['inventory'].get('hostname'):
            data['status'] = 'INCOMPLETE'
    except (subprocess.TimeoutExpired, OSError) as exc:
        data = {'status': 'UNREACHABLE', 'error': str(exc), 'inventory': {}}
    if data['status'] == 'OK':
        disk = data['inventory'].get('disk', '').splitlines()
        try:
            available = int(disk[-1].split()[3]) * 1024
            data['available_disk_bytes'] = available
            if available < 1024 ** 3:
                data.update(status='UNAVAILABLE', reason='Less than 1 GiB free disk; no automatic cleanup')
        except (ValueError, IndexError):
            data.update(status='INCOMPLETE', reason='Disk availability could not be verified')
    record = {'id': uid('PROBE'), 'machine_id': alias, 'data': encoded(data), 'created_at': utc_stamp()}
    with store.connect() as db:
        db.execute('INSERT INTO probes VALUES (?,?,?,?)', tuple(record.values()))
        db.execute('UPDATE machines SET data=?,updated_at=? WHERE id=?',
                   (encoded(data), record['created_at'], alias))
    return {**record, 'data': data}
