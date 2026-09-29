"""Version-bound envelopes, explicit scope changes, and deterministic resource selection."""
from __future__ import annotations

import json
import math
from pathlib import Path

from autoresearch.contracts import parse_contract, protocol_digest
from autoresearch.io import sha256_bytes, utc_stamp

from .service import required, uid
from .store import encoded


def positive(value, name, *, zero=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or (not zero and value == 0)):
        raise ValueError(f'{name} must be finite and {"nonnegative" if zero else "positive"}')
    return float(value)


def strings(value, name):
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ValueError(f'{name} must be a list of nonempty strings')
    return value


class Policy:
    def __init__(self, app):
        self.app, self.store = app, app.store

    def envelope_path(self, project):
        return self.app.workspace(project) / 'PROJECT_ENVELOPE.md'

    def envelope_draft(self, project):
        self.store.get('projects', project)
        data = parse_contract(self.envelope_path(project)).metadata
        required(data, ('problem', 'boundary', 'resource_budget', 'stop_conditions',
                        'non_goals', 'allowed_experiment_classes'))
        if data.get('schema_version') != 1 or data.get('project_id') != project:
            raise ValueError('envelope requires schema_version 1 and matching project_id')
        for key in ('problem', 'boundary'):
            if not isinstance(data[key], str):
                raise ValueError(f'{key} must be text')
        for key in ('stop_conditions', 'non_goals', 'allowed_experiment_classes'):
            strings(data[key], key)
        budget = data['resource_budget']
        if not isinstance(budget, dict):
            raise ValueError('resource_budget must be a mapping')
        for key in ('gpu_hours', 'cpu_hours'):
            positive(budget.get(key, 0), key, zero=True)
        if not any(budget.get(key, 0) > 0 for key in ('gpu_hours', 'cpu_hours')):
            raise ValueError('envelope must authorize some compute')
        if data.get('claim') and data.get('claim_status') != 'PROVISIONAL':
            raise ValueError('early claims must be explicitly PROVISIONAL')
        maturity = data.get('maturity_policy', {})
        if not isinstance(maturity, dict) or set(maturity) - {'independent_replications', 'allow_robust'}:
            raise ValueError('invalid maturity_policy')
        count = maturity.get('independent_replications', 1)
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 5:
            raise ValueError('independent_replications must be an integer from 1 to 5')
        if not isinstance(maturity.get('allow_robust', False), bool):
            raise ValueError('allow_robust must be boolean')
        return data, protocol_digest(data)

    def approve(self, project, kind, digest, message_file: Path, actor):
        # The CLI is a trusted single-user surface; it never treats --by as approval.
        # Preserve the exact explicit approval message, bound to the versioned object.
        message = message_file.read_text()
        required({'actor': actor}, ('actor',))
        if f'APPROVE {kind} {digest}' not in message.splitlines():
            raise ValueError(f'approval message must contain exactly: APPROVE {kind} {digest}')
        receipt = {'id': uid('APPROVAL'), 'project_id': project, 'kind': kind,
                   'object_digest': digest, 'message': message,
                   'message_digest': sha256_bytes(message.encode()), 'actor': actor,
                   'created_at': utc_stamp()}
        with self.store.connect() as db:
            db.execute('INSERT INTO object_approvals VALUES (?,?,?,?,?,?,?,?)', tuple(receipt.values()))
        return receipt

    def approve_envelope(self, project, digest, message_file, actor):
        data, actual = self.envelope_draft(project)
        if actual != digest:
            raise ValueError('envelope changed since review')
        state = self.store.get('projects', project)['state']
        if state not in {'ACTIVE', 'SCOPE_CHANGE_REQUESTED', 'BUDGET_EXHAUSTED'}:
            raise ValueError('project must be active or awaiting a versioned scope/budget decision')
        if state == 'SCOPE_CHANGE_REQUESTED':
            with self.store.connect() as db:
                pending = db.execute("SELECT 1 FROM scope_requests WHERE project_id=? AND state='PENDING'", (project,)).fetchone()
            if pending:
                raise ValueError('approve each versioned scope request before approving the revised envelope')
        if state == 'SCOPE_CHANGE_REQUESTED':
            with self.store.connect() as db:
                old = db.execute('SELECT e.digest FROM project_envelopes p JOIN envelopes e ON e.id=p.envelope_id WHERE p.project_id=?', (project,)).fetchone()
            if old and old['digest'] == digest:
                raise ValueError('scope change requires a revised envelope')
        receipt = self.approve(project, 'envelope', digest, message_file, actor)
        with self.store.connect() as db:
            envelope_id = project + ':' + digest
            db.execute('INSERT OR IGNORE INTO envelopes VALUES (?,?,?,?,?)',
                       (envelope_id, project, digest, encoded(data), utc_stamp()))
            db.execute('INSERT INTO project_envelopes VALUES (?,?) ON CONFLICT(project_id) '
                       'DO UPDATE SET envelope_id=excluded.envelope_id', (project, envelope_id))
            db.execute("UPDATE projects SET state='ACTIVE' WHERE id=?", (project,))
            db.execute("UPDATE scope_requests SET state='RESOLVED' WHERE project_id=? "
                       "AND state='APPROVED'", (project,))
        return receipt

    def current(self, project):
        data, digest = self.envelope_draft(project)
        with self.store.connect() as db:
            row = db.execute('SELECT e.digest FROM project_envelopes p JOIN envelopes e '
                             'ON e.id=p.envelope_id WHERE p.project_id=?', (project,)).fetchone()
            approved = db.execute("SELECT 1 FROM object_approvals WHERE project_id=? "
                                  "AND kind='envelope' AND object_digest=?", (project, digest)).fetchone()
        if not row or row['digest'] != digest or not approved:
            raise ValueError('current envelope requires explicit version-bound approval')
        return data, digest

    def scope_request(self, project, change):
        self.store.get('projects', project)
        required(change, ('category', 'reason', 'proposed_change'))
        if change['category'] not in {'question', 'claim', 'scope', 'budget', 'architecture',
                                     'evaluation_target', 'baselines', 'experiment_exception'}:
            raise ValueError('unknown scope-change category')
        digest = protocol_digest(change)
        record = {'id': uid('SCOPE'), 'project_id': project, 'data': encoded(change),
                  'digest': digest, 'state': 'PENDING', 'created_at': utc_stamp()}
        with self.store.connect() as db:
            db.execute('INSERT INTO scope_requests VALUES (?,?,?,?,?,?)', tuple(record.values()))
            db.execute("UPDATE projects SET state='SCOPE_CHANGE_REQUESTED' WHERE id=?", (project,))
        return record

    def approve_scope(self, request_id, digest, message_file, actor):
        row = self.store.get('scope_requests', request_id)
        if row['digest'] != digest or protocol_digest(json.loads(row['data'])) != digest:
            raise ValueError('scope request differs from reviewed version')
        receipt = self.approve(row['project_id'], 'scope', digest, message_file, actor)
        with self.store.connect() as db:
            db.execute("UPDATE scope_requests SET state='APPROVED' WHERE id=?", (request_id,))
        return receipt

    def scope_blockers(self, envelope, spec):
        blockers = []
        if spec.get('experiment_class') not in envelope['allowed_experiment_classes']:
            blockers.append('experiment class is outside the approved envelope')
        if spec.get('scope_change'):
            blockers.append('experiment explicitly requests a scope change')
        scope = spec.get('scope', {})
        if not isinstance(scope, dict):
            return blockers + ['scope must be a mapping']
        allowed_scope = {'problem', 'boundary', 'architecture', 'evaluation_target', 'claim'}
        if set(scope) - allowed_scope:
            blockers.append('unknown scope fields require explicit human review')
        for field in allowed_scope:
            if field in scope and scope[field] != envelope.get(field):
                blockers.append(f'{field} differs from approved envelope')
        baselines = spec.get('protocol', {}).get('baselines', [])
        if not set(baselines).issubset(set(envelope.get('allowed_baselines', []))):
            blockers.append('baseline set exceeds approved envelope')
        return blockers

    def decision(self, project, kind, detail):
        with self.store.connect() as db:
            db.execute('INSERT INTO policy_decisions VALUES (?,?,?,?,?)',
                       (uid('DECISION'), project, kind, encoded(detail), utc_stamp()))


def machine_capabilities(row):
    data = json.loads(row['data'])
    if data.get('status') != 'OK':
        return None
    if 'capabilities' in data:
        return data['capabilities']
    gpu_lines = data.get('inventory', {}).get('gpu', '').splitlines()
    gpus = []
    for index, line in enumerate(gpu_lines):
        parts = [part.strip() for part in line.split(',')]
        if len(parts) >= 2:
            try:
                gpus.append({'index': index, 'name': parts[0], 'vram_gb': float(parts[1]) / 1024,
                             'free_vram_gb': float(parts[3]) / 1024 if len(parts) > 3 else float(parts[1]) / 1024})
            except ValueError:
                continue
    return {'gpus': gpus, 'cpu': True}


def match_machine(requirement, machines):
    gpu_required = requirement.get('gpu_required', not requirement.get('cpu_only', True))
    if requirement.get('cpu_only') and gpu_required:
        raise ValueError('cpu_only conflicts with gpu_required')
    count = requirement.get('gpu_count', 1 if gpu_required else 0)
    if isinstance(count, bool) or not isinstance(count, int) or count < int(bool(gpu_required)):
        raise ValueError('invalid gpu_count')
    memory = positive(requirement.get('min_vram_gb', 0), 'min_vram_gb', zero=True)
    matches = []
    for machine in machines:
        caps = machine_capabilities(machine)
        if not caps:
            continue
        gpus = sorted((g for g in caps.get('gpus', []) if g['vram_gb'] >= memory and g.get('free_vram_gb', g['vram_gb']) >= memory),
                      key=lambda g: g['vram_gb'])
        if gpu_required and len(gpus) < count:
            continue
        selected = gpus[:count] if gpu_required else []
        rank = (sum(g['vram_gb'] for g in selected), 0 if machine['id'] == 'local' else 1,
                machine['id'])
        matches.append((rank, {'alias': machine['id'], 'gpu_indices': [g['index'] for g in selected],
                               'capabilities': caps}))
    if not matches:
        raise ValueError('no reachable machine satisfies the resource requirements')
    return min(matches, key=lambda item: item[0])[1]
