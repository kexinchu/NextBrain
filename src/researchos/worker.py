"""Small dependency-free executor supervisor, copied unchanged to a run's isolated directory.

Supports POSIX local/SSH hosts, Python >=3.10. Never accepts a shell command: argv is the
frozen, named command authorized by the user. No process is relaunched by inspect/recover.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import platform
import signal
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

TERMINAL = {'SUCCEEDED', 'FAILED_FINAL', 'TIMED_OUT', 'CANCELLED', 'LOST'}


def write(path, data):
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    with temp.open('w') as stream:
        json.dump(data, stream, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def contained(root, relative):
    value = Path(relative)
    if value.is_absolute() or '..' in value.parts:
        raise ValueError('path escapes run directory')
    path = root / value
    if path.resolve() != path or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('symlink or escaping artifact path')
    return path


def alive(pid, request_path):
    # A process-held lock identifies this exact job without PID-reuse ambiguity or ps access.
    lock_path = request_path.parent / 'supervisor.lock'
    if not lock_path.exists():
        return False
    with lock_path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(stream, fcntl.LOCK_UN)
        return False


def inspect(root):
    state_path = root / 'state.json'
    receipt_path = root / 'receipt.json'
    if not state_path.exists():
        return {'state': 'ABSENT', 'receipt': None, 'confirmed_dead': True,
                'launch_claimed': (root / 'launch.claim').exists(),
                'sealed': (root / 'sealed.json').exists()}
    state = read(state_path)
    receipt = read(receipt_path) if receipt_path.exists() else None
    if state['state'] not in TERMINAL and not alive(state.get('supervisor_pid'), root / 'request.json'):
        if state.get('state') == 'DISPATCHED' and time.time() - state['updated_at'] < 10:
            return {**state, 'receipt': receipt, 'confirmed_dead': False}
        # It may have completed between reading state and checking the process lock.
        latest = read(state_path)
        if latest['state'] in TERMINAL:
            return {**latest, 'receipt': read(receipt_path) if receipt_path.exists() else receipt,
                    'confirmed_dead': True}
        # A dead supervisor may have orphaned a child. Never retry this ambiguous state.
        return {**state, 'state': 'LOST', 'receipt': receipt, 'confirmed_dead': False,
                'failure_type': 'SUPERVISOR_LOST'}
    return {**state, 'receipt': receipt, 'confirmed_dead': state['state'] in TERMINAL}


def launch(root):
    request = read(root / 'request.json')
    claim = root / 'launch.claim'
    try:
        claim.mkdir()
    except FileExistsError:
        return inspect(root)
    # Claim persists even if launcher crashes: at-most-once start, never a blind duplicate.
    with (root / 'supervisor.log').open('ab') as log:
        process = subprocess.Popen([sys.executable, str(root / 'worker.py'), 'supervise',
                                    str(root / 'request.json')], stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log, start_new_session=True, close_fds=True)
    # Supervisor owns state.json. Wait briefly for its durable receipt, but never spawn again.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if (root / 'receipt.json').exists():
            return inspect(root)
        if process.poll() is not None:
            break
        time.sleep(0.02)
    return {'state': 'LOST', 'confirmed_dead': False, 'launch_claimed': True,
            'failure_type': 'RECEIPT_NOT_YET_AVAILABLE', 'run_id': request['run_id']}


def extract_code(root, request):
    archive = root / 'code.tar'
    if digest(archive) != request['archive_digest']:
        raise ValueError('code archive digest mismatch')
    destination = root / 'code'
    destination.mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        for member in members:
            contained(destination, member.name)
            if not member.isfile() and not member.isdir():
                raise ValueError('code archive contains link or special file')
        for member in members:
            path = contained(destination, member.name)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('wb') as stream:
                    stream.write(tar.extractfile(member).read())
                path.chmod(member.mode & 0o755)
    for relative, expected in request['snapshot']['data']['hashes'].items():
        if digest(contained(destination, relative)) != expected:
            raise ValueError('dataset hash mismatch: ' + relative)


def stop_child(child):
    # Child owns a dedicated process group. Never target a shared host process group.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            pass
        if sig == signal.SIGTERM:
            try:
                child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    child.wait()


def inventory(root, request):
    paths = [root / name for name in ('receipt.json', 'environment.json', 'gpu.csv',
                                     'stdout.log', 'stderr.log', 'supervisor.log')]
    for relative in request['snapshot']['expected_artifacts']:
        path = contained(root / 'code', relative)
        paths.extend(sorted(path.rglob('*')) if path.is_dir() else [path])
    manifest, used, exceeded = [], 0, False
    limit = request['snapshot']['budget']['artifact_bytes']
    # Preserve control evidence before potentially large experiment results.
    for path in dict.fromkeys(paths):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        contained(root, relative)
        size = path.stat().st_size
        remaining = max(0, limit - used)
        if size > remaining:
            exceeded = True
            if remaining and path.name in ('stdout.log', 'stderr.log', 'supervisor.log'):
                partial = root / (path.name + '.partial')
                with path.open('rb') as stream:
                    partial.write_bytes(stream.read(min(65536, remaining)))
                kept = partial.stat().st_size
                used += kept
                manifest.append({'path': partial.name, 'sha256': digest(partial),
                                 'size': kept, 'truncated': True})
            continue
        used += size
        manifest.append({'path': relative, 'sha256': digest(path), 'size': size})
    write(root / 'artifact-manifest.json', {'artifacts': manifest, 'limit_exceeded': exceeded})
    return manifest


def supervise(request_path):
    root = request_path.parent
    request = read(request_path)
    spec = request['snapshot']
    started = time.time()
    receipt = {'run_id': request['run_id'], 'experiment_digest': request['experiment_digest'],
               'machine_alias': request['machine_alias'], 'remote_workdir': str(root),
               'remote_pid': None, 'supervisor_pid': os.getpid(), 'job_id': request['job_id'],
               'launch_command': spec['command']['argv'], 'code_commit': spec['code']['commit_sha'],
               'started_at': started, 'stdout_path': str(root / 'stdout.log'),
               'stderr_path': str(root / 'stderr.log'),
               'artifact_manifest_path': str(root / 'artifact-manifest.json')}
    state = {'state': 'RUNNING', 'supervisor_pid': os.getpid(), 'updated_at': started,
             'run_id': request['run_id'], 'experiment_digest': request['experiment_digest'],
             'started_at': started, 'exit_code': None, 'failure_type': None}
    write(root / 'receipt.json', receipt)
    write(root / 'state.json', state)
    child = None
    try:
        write(root / 'environment.json', {'python': sys.version, 'platform': platform.platform(),
                                         'hostname': platform.node(), 'pid': os.getpid(),
                                         'gpu_indices': request['gpu_indices']})
        if shutil.disk_usage(root).free < spec['budget']['disk_bytes']:
            raise ValueError('insufficient free disk for frozen run allowance')
        extract_code(root, request)
        required = spec['environment_requirement'].get('python_min', '3.10')
        if sys.version_info[:2] < tuple(int(n) for n in required.split('.')[:2]):
            raise ValueError('Python runtime does not meet requirement')
        if request['gpu_indices']:
            gpu = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.total,utilization.gpu,memory.used,memory.free',
                                  '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
            if gpu.returncode:
                raise ValueError('GPU inventory unavailable at dispatch')
            (root / 'gpu.csv').write_text(gpu.stdout)
            available = {}
            for line in gpu.stdout.splitlines():
                fields = line.split(',')
                index, memory = fields[:2]
                available[int(index)] = min(float(memory), float(fields[4])) / 1024
            required_memory = spec['resource_requirement'].get('min_vram_gb', 0)
            if any(available.get(index, -1) < required_memory for index in request['gpu_indices']):
                raise ValueError('selected GPU no longer meets frozen requirements')
        if time.time() - started >= spec['timeout']:
            state.update(state='TIMED_OUT', failure_type='WALL_CLOCK_TIMEOUT')
            return
        env = os.environ.copy()
        env['CUDA_VISIBLE_DEVICES'] = ','.join(str(i) for i in request['gpu_indices'])
        env['RESEARCHOS_RUN_ID'] = request['run_id']
        with (root / 'stdout.log').open('wb') as out, (root / 'stderr.log').open('wb') as err:
            child = subprocess.Popen(spec['command']['argv'], cwd=root / 'code', env=env,
                                     stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                     start_new_session=True)
            receipt['remote_pid'] = child.pid
            write(root / 'receipt.json', receipt)
            while child.poll() is None:
                state['updated_at'] = time.time()
                write(root / 'state.json', state)
                if (root / 'cancel.request').exists():
                    state.update(state='CANCELLED', failure_type='USER_CANCELLED')
                    stop_child(child)
                    break
                if time.time() - started >= spec['timeout']:
                    state.update(state='TIMED_OUT', failure_type='WALL_CLOCK_TIMEOUT')
                    stop_child(child)
                    break
                size = sum(p.stat().st_size for p in root.rglob('*')
                           if p.is_file() and not p.is_symlink())
                if size > spec['budget']['disk_bytes']:
                    state.update(state='FAILED_FINAL', failure_type='DISK_LIMIT')
                    stop_child(child)
                    break
                time.sleep(0.05)
            state['exit_code'] = child.wait()
            if state['state'] == 'RUNNING':
                state['state'] = 'SUCCEEDED' if child.returncode == 0 else 'FAILED_FINAL'
                if child.returncode != 0:
                    error_text = (root / 'stderr.log').read_text(errors='replace')[-8000:].lower()
                    state['failure_type'] = 'OOM' if 'out of memory' in error_text else 'PROCESS_EXIT'
            # Do not leave background descendants after a nominally completed command.
            stop_child(child)
    except Exception as exc:
        if child is not None and child.poll() is None:
            stop_child(child)
        state.update(state='FAILED_FINAL', failure_type='PREPARATION_FAILURE', error=str(exc))
        with (root / 'stderr.log').open('a') as stream:
            stream.write('\nSupervisor: ' + str(exc) + '\n')
    finally:
        try:
            inventory(root, request)
        except Exception as exc:
            state['collection_error'] = str(exc)
        state['finished_at'] = time.time()
        state['updated_at'] = time.time()
        write(root / 'state.json', state)


def collect(root):
    state = inspect(root)
    if state['state'] not in TERMINAL or not state.get('confirmed_dead'):
        raise ValueError('collection requires confirmed terminal execution')
    request = read(root / 'request.json')
    entries = inventory(root, request)
    result = []
    for entry in entries:
        path = contained(root, entry['path'])
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('artifact changed during collection')
        result.append({**entry, 'content': base64.b64encode(data).decode()})
    return {'state': state, 'artifacts': result,
            'manifest': read(root / 'artifact-manifest.json')}


def collect_partial(root):
    request = read(root / 'request.json')
    entries = inventory(root, request)
    prefix = 'partial-' + str(time.time_ns()) + '/'
    artifacts = []
    for entry in entries:
        path = contained(root, entry['path'])
        with path.open('rb') as stream:
            data = stream.read(request['snapshot']['budget']['artifact_bytes'])
        artifacts.append({'path': prefix + entry['path'], 'sha256': hashlib.sha256(data).hexdigest(),
                          'size': len(data), 'content': base64.b64encode(data).decode(),
                          'partial': True})
    return {'state': {'run_id': request['run_id'], 'experiment_digest': request['experiment_digest']},
            'artifacts': artifacts, 'manifest': {'partial': True, 'captured_at': time.time(),
                'artifacts': [{k: v for k, v in a.items() if k != 'content'} for a in artifacts]}}


def control(payload):
    # Both transports use this same protocol. No arbitrary host path is accepted remotely.
    request = payload.get('request')
    job = payload['job_id']
    if not job or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in job):
        raise ValueError('invalid job id')
    base = Path(payload.get('local_base') or Path.home() / '.local/share/researchos-executor').resolve()
    root = base / job
    if root.is_symlink():
        raise ValueError('run directory is a symlink')
    if payload['operation'] == 'prepare':
        root.mkdir(parents=True, exist_ok=True)
        previous = root / 'request.json'
        if previous.exists() and read(previous) != request:
            raise ValueError('job already prepared with a different request')
        if not previous.exists():
            archive = base64.b64decode(payload['archive'], validate=True)
            if hashlib.sha256(archive).hexdigest() != request['archive_digest']:
                raise ValueError('archive transfer failed hash verification')
            (root / 'code.tar').write_bytes(archive)
            worker = base64.b64decode(payload['worker'], validate=True)
            if hashlib.sha256(worker).hexdigest() != request['snapshot']['worker_digest']:
                raise ValueError('worker transfer failed hash verification')
            (root / 'worker.py').write_bytes(worker)
            write(previous, request)
        return {'state': 'PREPARED', 'remote_workdir': str(root)}
    if payload['operation'] == 'seal':
        root.mkdir(parents=True, exist_ok=True)
        try:
            (root / 'launch.claim').mkdir()
        except FileExistsError:
            return inspect(root)
        write(root / 'sealed.json', {'reason': 'Confirmed no job; block any delayed launch'})
        return inspect(root)
    if not root.exists():
        return {'state': 'ABSENT', 'receipt': None, 'confirmed_dead': True, 'launch_claimed': False}
    if payload['operation'] == 'launch':
        return launch(root)
    if payload['operation'] == 'inspect':
        return inspect(root)
    if payload['operation'] == 'partial':
        return collect_partial(root)
    if payload['operation'] == 'collect':
        return collect(root)
    if payload['operation'] == 'cancel':
        write(root / 'cancel.request', {'at': time.time()})
        return inspect(root)
    raise ValueError('unknown control operation')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'supervise':
        request_path = Path(sys.argv[2]).resolve()
        with (request_path.parent / 'supervisor.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            supervise(request_path)
    else:
        print(json.dumps(control(json.load(sys.stdin))))
