"""Experiment-specific, content-addressed snapshots independent of paper STORY freeze."""
from __future__ import annotations

import io
import json
import subprocess
import tarfile
from pathlib import Path

from autoresearch.config import ResearchConfig
from autoresearch.contracts import protocol_digest
from autoresearch.io import atomic_write, sha256_bytes, sha256_file, utc_stamp

from .policy import Policy, positive
from .service import required, uid
from .store import encoded


def git(repo, *argv, binary=False):
    result = subprocess.run(['git', '-C', str(repo), *argv], capture_output=True,
                            text=not binary, timeout=30)
    if result.returncode:
        raise ValueError('git snapshot failed: ' + (result.stderr.decode() if binary else result.stderr))
    return result.stdout if binary else result.stdout.strip()


def validate_protocol(spec):
    if spec.get('evidence_kind', 'SCIENTIFIC') not in {'SCIENTIFIC', 'SYSTEM_VALIDATION'}:
        raise ValueError('invalid evidence_kind')
    required(spec, ('prediction', 'protocol', 'environment_requirement', 'resource_requirement',
                    'timeout', 'budget'))
    protocol = spec['protocol']
    if not isinstance(protocol, dict):
        raise ValueError('protocol must be a mapping')
    required(protocol, ('metric_file', 'rules'))
    metric = Path(protocol['metric_file'])
    if metric.is_absolute() or '..' in metric.parts:
        raise ValueError('metric_file must be relative to the isolated code checkout')
    if protocol['metric_file'] not in spec['expected_artifacts']:
        raise ValueError('metric_file must be named in expected_artifacts')
    rules = protocol['rules']
    if not isinstance(rules, list) or not rules:
        raise ValueError('protocol rules must be a nonempty list')
    for rule in rules:
        required(rule, ('metric', 'success', 'falsification'))
        if rule['metric'] not in spec['metrics']:
            raise ValueError('interpretation rule references an undeclared metric')
        if rule['success'] == rule['falsification']:
            raise ValueError('experiment cannot produce discriminating evidence')
        for key in ('success', 'falsification'):
            predicate = rule[key]
            if predicate.get('op') not in ('<', '<=', '>', '>=', '=='):
                raise ValueError('invalid numeric comparison')
            value = predicate.get('value')
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError('comparison threshold must be numeric')
            import math
            if not math.isfinite(value):
                raise ValueError('comparison threshold must be finite')
    positive(spec['timeout'], 'timeout')
    if spec['timeout'] > 86400:
        raise ValueError('single-run timeout must not exceed 24 hours')
    if not isinstance(spec['environment_requirement'], dict):
        raise ValueError('environment_requirement must be a mapping')
    unknown = set(spec['environment_requirement']) - {'python_min'}
    if unknown:
        raise ValueError('unsupported environment requirements: ' + ', '.join(sorted(unknown)))
    resource = spec['resource_requirement']
    if not isinstance(resource.get('gpu_required'), bool):
        raise ValueError('gpu_required must be explicit boolean')
    count = resource.get('gpu_count', 1 if resource['gpu_required'] else 0)
    if (isinstance(count, bool) or not isinstance(count, int) or count < 0
            or (resource['gpu_required'] and count < 1)
            or (not resource['gpu_required'] and count != 0)
            or (resource['gpu_required'] and resource.get('cpu_only'))):
        raise ValueError('inconsistent GPU requirements')
    positive(resource.get('min_vram_gb', 0), 'min_vram_gb', zero=True)
    data = spec.get('data')
    if not isinstance(data, dict) or not isinstance(data.get('identifiers'), list) or not isinstance(
            data.get('hashes'), dict):
        raise ValueError('data requires explicit identifiers and hashes, even if empty for a fixture')


def freeze_experiment(app, experiment_id, repo: Path):
    row = app.store.get('experiments', experiment_id)
    project = row['project_id']
    if app.store.get('projects', project)['state'] != 'ACTIVE':
        raise ValueError('project is not active')
    policy = Policy(app)
    envelope, envelope_digest = policy.current(project)
    spec = json.loads(row['data'])
    spec.setdefault('falsification_condition', spec['failure_condition'])
    validate_protocol(spec)
    from .intelligence import admit_design
    admit_design(app, project, spec)
    blockers = policy.scope_blockers(envelope, spec)
    if blockers:
        raise ValueError('; '.join(blockers))
    repo = repo.expanduser().resolve(strict=True)
    if Path(git(repo, 'rev-parse', '--show-toplevel')).resolve() != repo:
        raise ValueError('code repo must name the git root')
    if git(repo, 'status', '--porcelain', '--untracked-files=normal'):
        raise ValueError('code repository must be clean before freezing')
    commit = git(repo, 'rev-parse', 'HEAD')
    archive = git(repo, 'archive', '--format=tar', commit, binary=True)
    if len(archive) > 32 * 1024 * 1024:
        raise ValueError('single-run code archive exceeds 32 MiB; external datasets are not staged')
    if any(line.startswith('160000 ') for line in git(repo, 'ls-files', '--stage').splitlines()):
        raise ValueError('submodule execution is not supported by this snapshot transport')
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for entry in tar.getmembers():
            path = Path(entry.name)
            if path.is_absolute() or '..' in path.parts or not (entry.isfile() or entry.isdir()):
                raise ValueError('unsafe archive entry or symlink')
        for path, digest in spec['data']['hashes'].items():
            try:
                member = tar.getmember(path)
            except KeyError as exc:
                raise ValueError('declared data input is not committed: ' + path) from exc
            if not member.isfile() or sha256_bytes(tar.extractfile(member).read()) != digest:
                raise ValueError('data hash differs from committed input: ' + path)
        for baseline in spec['protocol'].get('baselines', []):
            relative = spec['protocol'].get('baseline_artifacts', {}).get(baseline)
            if not relative or relative not in spec['data']['hashes']:
                raise ValueError('required baseline unavailable or unhashed: ' + baseline)
    command = ResearchConfig(app.workspace(project)).command(spec['command_name'], 'experiment-loop')
    if spec['timeout'] > command.timeout:
        raise ValueError('experiment timeout exceeds human-authorized command timeout')
    from . import worker
    worker_bytes = Path(worker.__file__).read_bytes()
    budget = dict(spec['budget'])
    budget.setdefault('max_retries', 0)
    if not isinstance(budget['max_retries'], int) or isinstance(budget['max_retries'], bool) or not (
            0 <= budget['max_retries'] <= 10):
        raise ValueError('max_retries must be an integer between 0 and 10')
    budget.setdefault('artifact_bytes', 8 * 1024 * 1024)
    budget.setdefault('disk_bytes', 256 * 1024 * 1024)
    for key in ('artifact_bytes', 'disk_bytes'):
        positive(budget[key], key)
    if budget['artifact_bytes'] > 64 * 1024 * 1024:
        raise ValueError('inline artifact transfer limit is 64 MiB')
    resource = spec['resource_requirement']
    count = resource.get('gpu_count', 1 if resource.get('gpu_required') else 0)
    gpu_hours = spec['timeout'] * count / 3600
    cpu_hours = spec['timeout'] / 3600
    if positive(budget.get('gpu_hours', 0), 'gpu_hours', zero=True) < gpu_hours:
        raise ValueError('run GPU-hour limit cannot cover the wall timeout and allocated GPUs')
    if positive(budget.get('cpu_hours', cpu_hours), 'cpu_hours', zero=True) < cpu_hours:
        raise ValueError('run CPU-hour limit cannot cover the wall timeout')
    snapshot = {**spec, 'experiment_id': experiment_id,
                'experiment_revision': spec.get('revision', 1), 'envelope_digest': envelope_digest,
                'code': {'repo': str(repo), 'commit_sha': commit, 'dirty': False},
                'command': {'name': command.name, 'argv': list(command.argv), 'timeout': command.timeout},
                'budget': budget, 'archive_digest': sha256_bytes(archive),
                'worker_digest': sha256_bytes(worker_bytes), 'created_at': utc_stamp()}
    if not isinstance(snapshot['experiment_revision'], int) or snapshot['experiment_revision'] < 1:
        raise ValueError('experiment revision must be a positive integer')
    # Repeated freezing of an unchanged revision is idempotent, including its original timestamp.
    with app.store.connect() as db:
        previous = db.execute('SELECT * FROM experiment_freezes WHERE experiment_id=? AND revision=?',
                              (experiment_id, snapshot['experiment_revision'])).fetchone()
    if previous:
        old = json.loads(previous['data'])
        snapshot['created_at'] = old['created_at']
        if protocol_digest(snapshot) != previous['digest']:
            raise ValueError('frozen revision is immutable; register a new experiment ID/revision')
        return dict(previous)
    digest = protocol_digest(snapshot)
    directory = app.root / 'frozen' / digest
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'code.tar').write_bytes(archive)
    (directory / 'worker.py').write_bytes(worker_bytes)
    atomic_write(directory / 'snapshot.json', encoded(snapshot))
    record = {'id': uid('FREEZE'), 'project_id': project, 'experiment_id': experiment_id,
              'revision': snapshot['experiment_revision'], 'digest': digest,
              'data': encoded(snapshot), 'created_at': snapshot['created_at']}
    with app.store.connect() as db:
        db.execute('INSERT INTO experiment_freezes VALUES (?,?,?,?,?,?,?)', tuple(record.values()))
    return record


def verify_frozen(app, freeze):
    snapshot = json.loads(freeze['data'])
    if protocol_digest(snapshot) != freeze['digest']:
        raise ValueError('frozen experiment was modified')
    root = app.root / 'frozen' / freeze['digest']
    for name, expected in [('code.tar', snapshot['archive_digest']),
                           ('worker.py', snapshot['worker_digest'])]:
        if sha256_file(root / name) != expected:
            raise ValueError('frozen artifact was modified: ' + name)
    if json.loads((root / 'snapshot.json').read_text()) != snapshot:
        raise ValueError('frozen snapshot file was modified')
    return snapshot
