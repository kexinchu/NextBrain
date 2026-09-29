"""Explicit human decisions and append-only research evidence. Never runs experiment commands."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import yaml

from autoresearch.config import ResearchConfig
from autoresearch.contracts import parse_contract, protocol_digest
from autoresearch.freeze import FreezeGuard
from autoresearch.io import atomic_write, exclusive_lock, sha256_bytes, sha256_file, utc_stamp
from autoresearch.journal import UserMessageJournal
from autoresearch.venues import resolve_venue
from autoresearch.workspace import ResearchWorkspace

from .plans import identifier, scan_plans
from .store import Store, encoded


def uid(prefix: str) -> str:
    return prefix + '-' + uuid.uuid4().hex


def required(data: dict, fields: tuple[str, ...]) -> None:
    for field in fields:
        value = data.get(field)
        if value is None or value == '' or value == [] or value == {}:
            raise ValueError(f'missing {field}')
        if isinstance(value, str) and value.strip().lower() in {'', 'tbd', 'todo', 'unknown', '...'}:
            raise ValueError(f'{field} is a placeholder')


def id_list(data: dict, key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise ValueError(f'{key} must be a list of IDs')
    if len(value) != len(set(value)):
        raise ValueError(f'{key} contains duplicates')
    return [identifier(v) for v in value]


class ResearchOS:
    def __init__(self, root: Path):
        self.store = Store(root)
        self.root = self.store.root

    def scan(self, plans: Path, source_root: Path | None = None) -> list[dict]:
        records = scan_plans(plans, source_root)
        with self.store.connect() as db:
            for item in records:
                snapshot = encoded({'title': item['title'], **item['snapshot']})
                # Identity excludes source filename, so explicitly identified plans can move.
                content = {k: v for k, v in json.loads(snapshot).items() if k != 'source_path'}
                digest = sha256_bytes((item['id'] + encoded(content)).encode())
                db.execute('INSERT INTO ideas VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                           'title=excluded.title,current_revision=excluded.current_revision,'
                           'updated_at=excluded.updated_at',
                           (item['id'], item['title'], digest, 'INBOX', utc_stamp()))
                db.execute('INSERT OR IGNORE INTO revisions VALUES (?,?,?,?)',
                           (digest, item['id'], snapshot, utc_stamp()))
        return self.inbox()

    def inbox(self) -> list[dict]:
        result = self.store.list('ideas')
        projects = {p['idea_id']: p for p in self.store.list('projects')}
        for item in result:
            project = projects.get(item['id'])
            item['project_id'] = project['id'] if project else None
            item['source_changed'] = bool(project and project['revision_id'] != item['current_revision'])
        return result

    def workspace(self, project_id: str) -> Path:
        identifier(project_id)
        path = self.root / 'projects' / project_id
        # Reject a replaced workspace or ancestor symlink before writing.
        if path.resolve() != path:
            raise ValueError('project workspace must not be a symlink')
        return path

    def decide(self, idea_id: str, decision: str, actor: str, reason: str) -> dict:
        if decision not in {'GO', 'HOLD', 'DROP', 'NEEDS_WORK'}:
            raise ValueError('invalid human decision')
        required({'actor': actor, 'reason': reason}, ('actor', 'reason'))
        project_id = None
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            idea = db.execute('SELECT * FROM ideas WHERE id=?', (idea_id,)).fetchone()
            if idea is None:
                raise ValueError('unknown idea')
            project = db.execute('SELECT * FROM projects WHERE idea_id=?', (idea_id,)).fetchone()
            if decision == 'GO' and project and project['state'] in {'SCOPE_CHANGE_REQUESTED', 'STOPPED'}:
                raise ValueError('scope or stop gate requires version-bound approval, not another GO')
            if decision == 'GO' and project and project['revision_id'] != idea['current_revision']:
                raise ValueError('source changed after GO; explicit project revision is required')
            previous = db.execute('SELECT * FROM decisions WHERE idea_id=? ORDER BY rowid DESC LIMIT 1',
                                  (idea_id,)).fetchone()
            if (previous and previous['value'] == decision
                    and previous['revision_id'] == idea['current_revision']
                    and previous['actor'] == actor and previous['reason'] == reason):
                decision_id = previous['id']
            else:
                decision_id = uid('D')
                db.execute('INSERT INTO decisions VALUES (?,?,?,?,?,?,?)',
                           (decision_id, idea_id, idea['current_revision'], decision, actor,
                            reason, utc_stamp()))
            db.execute('UPDATE ideas SET decision=? WHERE id=?', (decision, idea_id))
            if decision == 'GO' and not project:
                project_id = uid('P')
                db.execute('INSERT INTO projects VALUES (?,?,?,?,?,?,?)',
                           (project_id, idea_id, idea['current_revision'], decision_id,
                            'PROVISIONING', None, utc_stamp()))
            elif project:
                project_id = project['id']
                if decision != 'GO':
                    db.execute('UPDATE projects SET state=? WHERE id=?', (decision, project_id))
                elif project['state'] != 'PROVISIONING':
                    db.execute("UPDATE projects SET state='ACTIVE' WHERE id=?", (project_id,))
        if project_id is None:
            return self.store.get('decisions', decision_id)
        if decision == 'GO':
            self.provision(project_id)
        return self.store.get('projects', project_id)

    def provision(self, project_id: str) -> None:
        identifier(project_id)
        with exclusive_lock(self.root / 'locks' / f'{project_id}.lock'):
            self._provision(project_id)

    def _provision(self, project_id: str) -> None:
        project = self.store.get('projects', project_id)
        path = self.workspace(project_id)
        source = self.store.get('revisions', project['revision_id'])
        snapshot = json.loads(source['snapshot'])
        source_text = '# Source idea (approved snapshot)\n\n' + encoded(snapshot) + '\n'
        path.mkdir(parents=True, exist_ok=True)
        source_path = path / 'SOURCE_IDEA.md'
        if source_path.exists() and source_path.read_text() != source_text:
            raise ValueError('approved source snapshot has been modified')
        if not source_path.exists():
            atomic_write(source_path, source_text)
        contract_path = path / 'RESEARCH_CONTRACT.md'
        if not contract_path.exists():
            contract = {'schema_version': 1, 'research_id': project_id, 'title': snapshot['title'],
                        'status': 'DRAFT', 'core_question': None, 'primary_claim': None,
                        'baseline': [], 'independent_variables': [], 'dependent_variables': [],
                        'success_conditions': [], 'falsification_conditions': [],
                        'abandonment_result': None, 'compute_budget': {'gpu_hours': None},
                        'target_venue': None, 'contribution_type': None,
                        'human_gate': {'project_approved': True, 'contract_approved': False}}
            atomic_write(contract_path, '---\n' + yaml.safe_dump(contract, allow_unicode=True,
                         sort_keys=False) + '---\n\n# Research contract\n\n'
                         'What result would make us abandon this idea?\n')
        envelope_path = path / 'PROJECT_ENVELOPE.md'
        if not envelope_path.exists():
            envelope = {'schema_version': 1, 'project_id': project_id, 'problem': None,
                        'boundary': None, 'resource_budget': {'gpu_hours': 0, 'cpu_hours': 0},
                        'stop_conditions': [], 'non_goals': [], 'allowed_experiment_classes': []}
            atomic_write(envelope_path, '---\n' + yaml.safe_dump(envelope, sort_keys=False)
                         + '---\n\n# Project Envelope\n')
        ResearchWorkspace(path).init()
        journal = UserMessageJournal(path)
        if not journal.files():
            journal.add('ResearchOS project admission (not scientific contract approval).\n'
                        + encoded(self.store.get('decisions', project['decision_id']))
                        + '\nSource revision: ' + project['revision_id'], source='researchos')
        with self.store.connect() as db:
            db.execute("UPDATE projects SET state='ACTIVE' WHERE id=? AND state='PROVISIONING'",
                       (project_id,))

    def contract(self, project_id: str) -> tuple[dict, str]:
        self.store.get('projects', project_id)
        path = self.workspace(project_id) / 'RESEARCH_CONTRACT.md'
        data = parse_contract(path).metadata
        required(data, ('research_id', 'title', 'core_question', 'primary_claim', 'baseline',
                        'independent_variables', 'dependent_variables', 'success_conditions',
                        'falsification_conditions', 'abandonment_result', 'compute_budget',
                        'target_venue', 'contribution_type'))
        if data.get('schema_version') != 1:
            raise ValueError('contract schema_version must be 1')
        for field in ('title', 'core_question', 'primary_claim', 'abandonment_result',
                      'target_venue', 'contribution_type'):
            if not isinstance(data[field], str):
                raise ValueError(f'{field} must be text')
        if data['research_id'] != project_id:
            raise ValueError('contract belongs to another project')
        for field in ('baseline', 'independent_variables', 'dependent_variables',
                      'success_conditions', 'falsification_conditions'):
            if not isinstance(data[field], list) or not all(isinstance(v, str) and v.strip()
                                                          for v in data[field]):
                raise ValueError(f'{field} requires a non-empty string list')
        budget = data['compute_budget']
        hours = budget.get('gpu_hours') if isinstance(budget, dict) else None
        if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not 0 < hours < 1e9:
            raise ValueError('compute_budget.gpu_hours must be finite and positive')
        resolve_venue(data['target_venue'])
        return data, sha256_file(path)

    def approve_contract(self, project_id: str, digest: str, actor: str, reason: str) -> dict:
        required({'actor': actor, 'reason': reason}, ('actor', 'reason'))
        project = self.store.get('projects', project_id)
        if project['state'] != 'ACTIVE':
            raise ValueError('project is not active')
        _, actual = self.contract(project_id)
        if actual != digest:
            raise ValueError('contract digest differs from the reviewed draft')
        approval = {'id': uid('A'), 'project_id': project_id, 'digest': digest,
                    'actor': actor, 'reason': reason, 'created_at': utc_stamp()}
        with self.store.connect() as db:
            db.execute('INSERT INTO approvals VALUES (?,?,?,?,?,?)', tuple(approval.values()))
            db.execute('UPDATE projects SET contract_digest=? WHERE id=?', (digest, project_id))
        return approval

    def same_project(self, table: str, record_id: str, project_id: str) -> dict:
        row = self.store.get(table, record_id)
        if row['project_id'] != project_id:
            raise ValueError(f'{record_id} belongs to another project')
        return row

    def add(self, kind: str, project_id: str, data: dict) -> dict:
        table = {'hypothesis': 'hypotheses', 'claim': 'claims', 'experiment': 'experiments',
                 'run': 'runs', 'finding': 'findings'}[kind]
        self.store.get('projects', project_id)
        if not isinstance(data, dict):
            raise ValueError('record must be a mapping')
        record_id = identifier(data.get('id'))
        data = dict(data)
        dependencies = []
        if kind in {'hypothesis', 'claim'}:
            required(data, ('statement',))
            if not isinstance(data['statement'], str):
                raise ValueError('statement must be text')
            if kind == 'claim':
                from .intelligence import MATURITY
                if not isinstance(data.get('maturity_requirements', []), list) or any(not isinstance(v, str) or v not in MATURITY for v in data.get('maturity_requirements', [])):
                    raise ValueError('invalid claim maturity requirements')
                for h in id_list(data, 'hypothesis_ids'):
                    self.same_project('hypotheses', h, project_id)
            if kind == 'hypothesis':
                required(data, ('falsification_condition',))
                from .intelligence import HYPOTHESIS_TYPES
                if data.get('hypothesis_type', 'UNCLASSIFIED') not in HYPOTHESIS_TYPES | {'UNCLASSIFIED'}:
                    raise ValueError('invalid hypothesis_type')
                from .research_state import HYPOTHESIS_STATES
                if data.get('state', 'PROPOSED') not in HYPOTHESIS_STATES:
                    raise ValueError('invalid hypothesis lifecycle state')
        elif kind == 'experiment':
            if 'falsification_condition' in data and 'failure_condition' not in data:
                data['failure_condition'] = data['falsification_condition']
            required(data, ('hypothesis_id', 'prediction', 'metrics', 'success_condition',
                            'failure_condition', 'expected_artifacts', 'resource_requirement',
                            'estimated_runtime', 'command_name'))
            self.same_project('hypotheses', data['hypothesis_id'], project_id)
            if 'command' in data:
                raise ValueError('use a pre-authorized command_name, not a shell command')
            dependencies = id_list(data, 'dependencies')
            for dependency in dependencies:
                if dependency == record_id:
                    raise ValueError('self dependency')
                self.same_project('experiments', dependency, project_id)
            # Immutable specifications may depend only on existing nodes: cycles cannot form.
            for claim_id in id_list(data, 'claim_ids'):
                self.same_project('claims', claim_id, project_id)
            if not isinstance(data['resource_requirement'], dict):
                raise ValueError('resource_requirement must be a mapping')
            if not isinstance(data['command_name'], str):
                raise ValueError('command_name must be text')
            for field in ('metrics', 'expected_artifacts'):
                if not isinstance(data[field], list) or not all(
                        isinstance(v, str) and v.strip() for v in data[field]):
                    raise ValueError(f'{field} must be a non-empty string list')
            for artifact in data['expected_artifacts']:
                if Path(artifact).is_absolute() or '..' in Path(artifact).parts:
                    raise ValueError('expected artifact paths must stay inside the workspace')
        elif kind == 'run':
            required(data, ('experiment_id', 'status', 'provenance', 'observed', 'environment'))
            experiment = self.same_project('experiments', data['experiment_id'], project_id)
            if data['status'] not in {'PASS', 'FAIL', 'INTERESTING', 'ERROR'}:
                raise ValueError('invalid run status')
            # V0 imports external run reports. It cannot certify that prediction preceded execution.
            if data['provenance'] != 'manual-import':
                raise ValueError('V0 supports only manual-import runs')
            data['verification'] = 'UNVERIFIED'
            data['experiment_digest'] = experiment['digest']
            data['prediction'] = json.loads(experiment['data'])['prediction']
        else:
            required(data, ('experiment_id', 'observation', 'magnitude', 'confidence'))
            if not isinstance(data.get('unexpected'), bool):
                raise ValueError('unexpected must be boolean')
            if not isinstance(data.get('next_questions'), list):
                raise ValueError('next_questions must be a list')
            self.same_project('experiments', data['experiment_id'], project_id)
            for run_id in id_list(data, 'run_ids'):
                run = self.same_project('runs', run_id, project_id)
                if run['experiment_id'] != data['experiment_id']:
                    raise ValueError('finding run belongs to another experiment')
            for field in ('supports', 'contradicts'):
                for claim_id in id_list(data, field):
                    self.same_project('claims', claim_id, project_id)
            if set(data.get('supports', [])) & set(data.get('contradicts', [])):
                raise ValueError('finding cannot both support and contradict the same claim')
            data['verification'] = 'UNVERIFIED'
        with self.store.connect() as db:
            existing = db.execute(f'SELECT * FROM {table} WHERE id=?', (record_id,)).fetchone()
            if existing:
                if existing['project_id'] != project_id or existing['data'] != encoded(data):
                    raise ValueError('immutable record already exists; use a new ID for a revision')
                return dict(existing)
            if kind in {'hypothesis', 'claim'}:
                db.execute(f'INSERT INTO {table} VALUES (?,?,?,?)',
                           (record_id, project_id, encoded(data), utc_stamp()))
                if kind == 'hypothesis':
                    db.execute('INSERT INTO hypothesis_states VALUES (?,?,?,?)',
                               (record_id, data.get('state', 'PROPOSED'), None, utc_stamp()))
            elif kind == 'experiment':
                db.execute('INSERT INTO experiments VALUES (?,?,?,?,?,?)',
                           (record_id, project_id, data['hypothesis_id'], encoded(data),
                            protocol_digest(data), utc_stamp()))
                db.executemany('INSERT INTO dependencies VALUES (?,?)',
                               [(record_id, dep) for dep in dependencies])
            else:
                db.execute(f'INSERT INTO {table} VALUES (?,?,?,?,?)',
                           (record_id, project_id, data['experiment_id'], encoded(data), utc_stamp()))
                # Scientific negatives are evidence, not automatic project-scope escalation.
                # Only an explicit scope request changes the project-level human gate.
        return self.store.get(table, record_id)

    def artifact(self, run_id: str, source: Path) -> dict:
        self.store.get('runs', run_id)
        if not source.is_file() or source.is_symlink():
            raise ValueError('artifact must be a regular file')
        content = source.read_bytes()
        digest = sha256_bytes(content)
        target = self.root / 'artifacts' / digest
        target.parent.mkdir(exist_ok=True)
        if target.resolve() != target:
            raise ValueError('artifact path must not be a symlink')
        # Content-addressed storage; existing content is verified before reuse.
        if target.exists():
            if sha256_file(target) != digest:
                raise ValueError('stored artifact was modified')
        else:
            with target.open('xb') as stream:
                stream.write(content)
        record = {'id': uid('ART'), 'run_id': run_id, 'path': str(target),
                  'digest': digest, 'created_at': utc_stamp()}
        with self.store.connect() as db:
            db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)', tuple(record.values()))
        return record

    def verify_source(self, project_id: str) -> None:
        project = self.store.get('projects', project_id)
        snapshot = json.loads(self.store.get('revisions', project['revision_id'])['snapshot'])
        expected = '# Source idea (approved snapshot)\n\n' + encoded(snapshot) + '\n'
        source = self.workspace(project_id) / 'SOURCE_IDEA.md'
        if source.is_symlink() or source.read_text() != expected:
            raise ValueError('approved source snapshot has been modified')

    def readiness(self, experiment_id: str) -> dict:
        with self.store.connect() as db:
            frozen = db.execute('SELECT 1 FROM experiment_freezes WHERE experiment_id=?', (experiment_id,)).fetchone()
        if frozen:
            from .execution import Runs
            return Runs(self).readiness(experiment_id)
        experiment = self.store.get('experiments', experiment_id)
        project_id = experiment['project_id']
        project = self.store.get('projects', project_id)
        data = json.loads(experiment['data'])
        blockers = []
        if project['state'] != 'ACTIVE':
            blockers.append('project is ' + project['state'])
        try:
            self.verify_source(project_id)
            _, digest = self.contract(project_id)
            if digest != project['contract_digest']:
                blockers.append('current contract is not approved')
        except (ValueError, OSError) as exc:
            blockers.append(str(exc))
        try:
            ResearchConfig(self.workspace(project_id)).command(data['command_name'], 'experiment-loop')
        except (ValueError, OSError) as exc:
            blockers.append(str(exc))
        source = json.loads(self.store.get('revisions', project['revision_id'])['snapshot'])
        if source.get('unresolved_links'):
            blockers.append('approved source has unresolved document links')
        if self.store.get('ideas', project['idea_id'])['current_revision'] != project['revision_id']:
            blockers.append('upstream source changed; human review required')
        for dependency in data.get('dependencies', []):
            # Manual imports are never sufficient to authorize autonomous dependent execution.
            blockers.append(f'dependency {dependency} has no executor-verified completion in V0')
        return {'experiment_id': experiment_id, 'specification_ready': not blockers,
                'blockers': blockers, 'remote_execution_enabled': False}

    def handoff(self, project_id: str, story: Path, digest: str, actor: str, reason: str) -> dict:
        from autoresearch.admission import admit_external_idea

        from .controller import check_workspace_story_gate
        check_workspace_story_gate(self.workspace(project_id))
        project = self.store.get('projects', project_id)
        self.verify_source(project_id)
        _, contract_digest = self.contract(project_id)
        if project['state'] != 'ACTIVE' or contract_digest != project['contract_digest']:
            raise ValueError('handoff requires an active project and approved current contract')
        idea = self.store.get('ideas', project['idea_id'])
        if idea['current_revision'] != project['revision_id']:
            raise ValueError('upstream source changed; review before handoff')
        return admit_external_idea(self.workspace(project_id), story, digest, actor=actor,
                                   reason=reason, provenance={
                                       'project_id': project_id, 'idea_id': project['idea_id'],
                                       'source_revision': project['revision_id'],
                                       'decision_id': project['decision_id'],
                                       'contract_digest': contract_digest})

    def context(self, project_id: str) -> dict:
        if self.store.list('uncertainties', project_id):
            from .research_state import build_context
            return build_context(self, project_id)
        project = self.store.get('projects', project_id)
        path = self.workspace(project_id)
        return {'project': project, 'workspace': str(path),
                'research_contract': (path / 'RESEARCH_CONTRACT.md').read_text(),
                'project_envelope': (path / 'PROJECT_ENVELOPE.md').read_text()
                    if (path / 'PROJECT_ENVELOPE.md').exists() else None,
                'executions': self.store.list('executions', project_id),
                **{table: self.store.list(table, project_id) for table in
                   ('hypotheses', 'claims', 'experiments', 'runs', 'findings')},
                'execution': 'Use the approved Project Envelope and experiment-specific freeze for '
                             'single-run execution. Paper STORY approval is a later, separate gate. '
                             'Legacy contract/handoff commands remain compatibility tools.'}

    def status(self) -> dict:
        from .store import TABLES
        projects = []
        for row in self.store.list('projects'):
            path = self.workspace(row['id'])
            frozen = {}
            for name in ('paper-story', 'core-code'):
                try:
                    FreezeGuard(path).verify(name)
                    frozen[name] = 'verified'
                except (ValueError, RuntimeError, OSError) as exc:
                    frozen[name] = str(exc)
            projects.append({**row, 'workspace': str(path), 'engine_freezes': frozen})
        return {'schema_version': 4, 'counts': {t: len(self.store.list(t)) for t in sorted(TABLES)},
                'projects': projects, 'remote_execution_enabled': True,
                'execution_mode': 'explicit single-run dispatch or bounded advance (default max_runs=1)'}
