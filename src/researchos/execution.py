"""One resumable run at a time: durable intent, bounded attempts, receipts and evidence."""
from __future__ import annotations

import base64
import json
import math
import operator
from pathlib import Path

from autoresearch.config import ResearchConfig
from autoresearch.io import atomic_write, exclusive_lock, sha256_bytes, utc_stamp

from .freeze import verify_frozen
from .policy import Policy, match_machine
from .service import uid
from .store import encoded
from .transport import LocalTransport, SSHTransport, TransportError

TERMINAL = {'SUCCEEDED', 'FAILED_FINAL', 'TIMED_OUT', 'CANCELLED', 'FAILED_RETRYABLE'}
TRANSITIONS = {
    'CREATED': {'PREPARING', 'CANCELLED'},
    'PREPARING': {'DISPATCHED', 'LOST', 'FAILED_RETRYABLE', 'FAILED_FINAL', 'CANCELLED'},
    'DISPATCHED': {'RUNNING', 'COLLECTING', 'LOST'},
    'RUNNING': {'COLLECTING', 'LOST'},
    'COLLECTING': {'SUCCEEDED', 'FAILED_FINAL', 'FAILED_RETRYABLE', 'TIMED_OUT', 'CANCELLED', 'LOST'},
    'LOST': {'DISPATCHED', 'RUNNING', 'COLLECTING', 'FAILED_RETRYABLE', 'FAILED_FINAL'},
    'FAILED_RETRYABLE': {'PREPARING', 'FAILED_FINAL', 'CANCELLED'},
}
COMPARATORS = {'<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge, '==': operator.eq}


class Runs:
    def __init__(self, app, transport_factory=None):
        self.app, self.store, self.policy = app, app.store, Policy(app)
        self.transport_factory = transport_factory
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO machines VALUES (?,?,?,?)',
                       ('local', '', encoded({'status': 'OK', 'capabilities': {'cpu': True, 'gpus': []}}),
                        utc_stamp()))

    def _event(self, db, run_id, state, detail):
        db.execute('INSERT INTO run_events VALUES (?,?,?,?,?)',
                   (uid('EVENT'), run_id, state, encoded(detail), utc_stamp()))

    def _state(self, run_id, target, detail=None, receipt=None, failure=None):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM executions WHERE id=?', (run_id,)).fetchone()
            if row['state'] != target and target not in TRANSITIONS.get(row['state'], set()):
                raise ValueError(f'illegal run transition {row["state"]} -> {target}')
            db.execute('UPDATE executions SET state=?,updated_at=?,receipt=COALESCE(?,receipt),'
                       'failure=? WHERE id=?', (target, utc_stamp(), encoded(receipt) if receipt else None,
                                               encoded(failure) if failure else None, run_id))
            self._event(db, run_id, target, detail or {})

    def latest_freeze(self, experiment):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM experiment_freezes WHERE experiment_id=? '
                             'ORDER BY revision DESC LIMIT 1', (experiment,)).fetchone()
        if row is None:
            raise ValueError('experiment must be frozen before creating a run')
        return dict(row)

    def dependency_blockers(self, spec, project):
        blockers = []
        for dependency in spec.get('dependencies', []):
            with self.store.connect() as db:
                rows = db.execute('SELECT f.data FROM executions e JOIN findings_from_runs fr '
                                  'ON fr.run_id=e.id JOIN findings f ON f.id=fr.finding_id '
                                  "WHERE e.project_id=? AND e.experiment_id=? AND e.state='SUCCEEDED'",
                                  (project, dependency)).fetchall()
            if not any(json.loads(r['data']).get('outcome') == 'SUPPORTED' for r in rows):
                blockers.append('dependency lacks supported executor evidence: ' + dependency)
        with self.store.connect() as db:
            hypothesis = db.execute('SELECT state FROM hypothesis_states WHERE hypothesis_id=?',
                                    (spec['hypothesis_id'],)).fetchone()
        with self.store.connect() as db:
            prior = db.execute('SELECT f.data FROM findings_from_runs m JOIN findings f ON f.id=m.finding_id JOIN executions e ON e.id=m.run_id WHERE e.experiment_id=? ORDER BY f.rowid DESC LIMIT 1', (spec.get('experiment_id', spec['id']),)).fetchone()
        with self.store.connect() as db:
            exhausted = db.execute(
                "SELECT 1 FROM executions WHERE experiment_id=? AND state='FAILED_FINAL' "
                'AND attempt>=max_retries LIMIT 1',
                (spec.get('experiment_id', spec['id']),)).fetchone()
        if exhausted:
            blockers.append('experiment exhausted retries; revise the experiment before a new run')
        if prior and json.loads(prior['data']).get('outcome') == 'INCONCLUSIVE':
            blockers.append('experiment lacks discriminating evidence; revise its protocol')
        if hypothesis and hypothesis['state'] == 'FALSIFIED':
            blockers.append('hypothesis has already been falsified')
        return blockers

    def readiness(self, experiment_id):
        blockers = []
        selected = None
        try:
            freeze = self.latest_freeze(experiment_id)
            spec = verify_frozen(self.app, freeze)
            project = freeze['project_id']
            self.app.verify_source(project)
            envelope, digest = self.policy.current(project)
            if digest != spec['envelope_digest']:
                blockers.append('envelope approval changed after freeze')
            blockers += self.policy.scope_blockers(envelope, spec)
            blockers += self.dependency_blockers(spec, project)
            if self.store.get('projects', project)['state'] != 'ACTIVE':
                blockers.append('project is not active')
            command = ResearchConfig(self.app.workspace(project)).command(
                spec['command']['name'], 'experiment-loop')
            if list(command.argv) != spec['command']['argv'] or command.timeout < spec['timeout']:
                blockers.append('command authorization changed')
            selected = match_machine(spec['resource_requirement'], self.store.list('machines'))
            attempts = spec['budget']['max_retries'] + 1
            gpu = spec['timeout'] * len(selected['gpu_indices']) / 3600 * attempts
            cpu = spec['timeout'] / 3600 * attempts if not selected['gpu_indices'] else 0
            with self.store.connect() as db:
                total = db.execute('SELECT COALESCE(SUM(reserved_gpu_hours),0), '
                                   'COALESCE(SUM(reserved_cpu_hours),0) FROM executions WHERE project_id=?',
                                   (project,)).fetchone()
            if (gpu + total[0] > envelope['resource_budget'].get('gpu_hours', 0) + 1e-12
                    or cpu + total[1] > envelope['resource_budget'].get('cpu_hours', 0) + 1e-12):
                blockers.append('project compute budget exhausted')
        except (ValueError, OSError) as exc:
            blockers.append(str(exc))
        return {'experiment_id': experiment_id, 'specification_ready': not blockers,
                'dispatch_ready': not blockers, 'blockers': blockers, 'selected_machine': selected,
                'remote_execution_enabled': True, 'automatic_dispatch': False}

    def create(self, experiment_id, machine=None):
        freeze = self.latest_freeze(experiment_id)
        spec = verify_frozen(self.app, freeze)
        project = freeze['project_id']
        self.app.verify_source(project)
        envelope, digest = self.policy.current(project)
        if digest != spec['envelope_digest']:
            raise ValueError('experiment was frozen under a different envelope')
        blockers = self.policy.scope_blockers(envelope, spec) + self.dependency_blockers(spec, project)
        if blockers:
            self.policy.decision(project, 'BLOCKED', {'blockers': blockers})
            raise ValueError('; '.join(blockers))
        command = ResearchConfig(self.app.workspace(project)).command(spec['command']['name'],
                                                                      'experiment-loop')
        if list(command.argv) != spec['command']['argv'] or command.timeout < spec['timeout']:
            raise ValueError('named command authorization changed after freezing')
        machines = self.store.list('machines')
        if machine:
            machines = [row for row in machines if row['id'] == machine]
        selected = match_machine(spec['resource_requirement'], machines)
        retry = spec['budget']['max_retries']
        gpu_hours = spec['timeout'] * len(selected['gpu_indices']) / 3600 * (retry + 1)
        cpu_hours = spec['timeout'] / 3600 * (retry + 1) if not selected['gpu_indices'] else 0
        run_id = uid('RUN')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = db.execute('SELECT state FROM projects WHERE id=?', (project,)).fetchone()[0]
            if state != 'ACTIVE':
                raise ValueError('project is not active: ' + state)
            active = db.execute("SELECT r.data FROM executions e JOIN runs r ON r.id=e.id WHERE e.machine_alias=? AND e.state NOT IN ('SUCCEEDED','FAILED_FINAL','TIMED_OUT','CANCELLED')", (selected['alias'],)).fetchall()
            if any(set(selected['gpu_indices']) & set(json.loads(row['data'])['selection']['gpu_indices']) for row in active):
                raise ValueError('selected GPUs are already reserved by another catalog run')
            # Reserve the full worst-case allowance, including retries. Reservations are
            # conservatively charged permanently; a lost host cannot release budget twice.
            total = db.execute('SELECT COALESCE(SUM(reserved_gpu_hours),0),'
                               'COALESCE(SUM(reserved_cpu_hours),0) FROM executions WHERE project_id=?',
                               (project,)).fetchone()
            budget = envelope['resource_budget']
            blocked = (total[0] + gpu_hours > budget.get('gpu_hours', 0) + 1e-12
                       or total[1] + cpu_hours > budget.get('cpu_hours', 0) + 1e-12)
            if blocked:
                db.execute('INSERT INTO policy_decisions VALUES (?,?,?,?,?)',
                           (uid('DECISION'), project, 'BUDGET_BLOCKED', encoded({
                               'requested_gpu_hours': gpu_hours, 'requested_cpu_hours': cpu_hours,
                               'reserved_gpu_hours': total[0], 'reserved_cpu_hours': total[1]}), utc_stamp()))
            else:
                # V0 runs remains the common evidence FK; executions adds the operational lifecycle.
                db.execute('INSERT INTO runs VALUES (?,?,?,?,?)',
                           (run_id, project, experiment_id, encoded({
                               'provenance': 'executor', 'experiment_digest': freeze['digest'],
                               'prediction': spec['prediction'], 'selection': selected}), utc_stamp()))
                db.execute('INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (run_id, project, experiment_id, freeze['id'], freeze['digest'],
                            selected['alias'], 'CREATED', 0, retry, gpu_hours, cpu_hours,
                            None, None, utc_stamp(), utc_stamp()))
                self._event(db, run_id, 'CREATED', {'selection': selected})
        if blocked:
            raise ValueError('project compute budget exhausted; budget-blocked decision recorded')
        return self.status(run_id)

    def status(self, run_id):
        row = self.store.get('executions', run_id)
        row['scientific_outcome'] = None
        with self.store.connect() as db:
            result = db.execute('SELECT f.data FROM findings_from_runs m JOIN findings f '
                                'ON f.id=m.finding_id WHERE m.run_id=?', (run_id,)).fetchone()
        if result:
            row['scientific_outcome'] = json.loads(result['data'])['outcome']
        for field in ('receipt', 'failure'):
            if row[field]:
                row[field] = json.loads(row[field])
        return row

    def _request(self, run):
        freeze = self.store.get('experiment_freezes', run['freeze_id'])
        spec = verify_frozen(self.app, freeze)
        selection = json.loads(self.store.get('runs', run['id'])['data'])['selection']
        return {'run_id': run['id'], 'job_id': run['id'] + '-attempt-' + str(run['attempt']),
                'experiment_digest': freeze['digest'], 'machine_alias': run['machine_alias'],
                'gpu_indices': selection['gpu_indices'], 'snapshot': spec,
                'archive_digest': spec['archive_digest']}

    def _transport(self, run):
        worker = self.app.root / 'frozen' / run['experiment_digest'] / 'worker.py'
        if self.transport_factory:
            return self.transport_factory(run, worker)
        if run['machine_alias'] == 'local':
            return LocalTransport(self.app.root / 'executor', worker)
        machine = self.store.get('machines', run['machine_alias'])
        return SSHTransport(run['machine_alias'], Path(machine['config_path']), worker)

    def _failure(self, run, kind, error, retryable=True):
        return {'failure_type': kind, 'stderr': str(error), 'exit_code': None,
                'retry_count': run['attempt'], 'machine': run['machine_alias'],
                'timestamp': utc_stamp(), 'partial_artifacts': [], 'retryable': retryable}

    def dispatch(self, run_id):
        with exclusive_lock(self.app.root / 'run-locks' / (run_id + '.lock'), timeout=60):
            run = self.store.get('executions', run_id)
            if run['state'] != 'CREATED':
                return self._recover(run_id)
            return self._launch(run)

    def _launch(self, run):
        # Recheck authorization at dispatch; envelopes can change after run creation.
        envelope, digest = self.policy.current(run['project_id'])
        request = self._request(run)
        if digest != request['snapshot']['envelope_digest']:
            raise ValueError('envelope approval changed before dispatch')
        if self.store.get('projects', run['project_id'])['state'] != 'ACTIVE':
            raise ValueError('project is not active')
        command = ResearchConfig(self.app.workspace(run['project_id'])).command(
            request['snapshot']['command']['name'], 'experiment-loop')
        if (list(command.argv) != request['snapshot']['command']['argv']
                or command.timeout < request['snapshot']['timeout']):
            raise ValueError('command authorization changed')
        self._state(run['id'], 'PREPARING')
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO run_attempts VALUES (?,?,?,?,?,?,?)',
                       (request['job_id'], run['id'], run['attempt'], 'PREPARING', None, None, None))
        root = self.app.root / 'frozen' / run['experiment_digest']
        payload = {'operation': 'prepare', 'job_id': request['job_id'], 'request': request,
                   'archive': base64.b64encode((root / 'code.tar').read_bytes()).decode(),
                   'worker': base64.b64encode((root / 'worker.py').read_bytes()).decode()}
        transport = self._transport(run)
        try:
            transport.call(payload)
            result = transport.call({'operation': 'launch', 'job_id': request['job_id']})
            self._accept_receipt(run, result)
        except TransportError as exc:
            # Launch may have succeeded. Only inspect can resolve uncertainty; never retry here.
            self._state(run['id'], 'LOST', failure=self._failure(run, 'TRANSPORT_DISCONNECT', exc))
        return self.status(run['id'])

    def _accept_receipt(self, run, result):
        receipt = result.get('receipt')
        if not receipt:
            self._state(run['id'], 'LOST', failure=self._failure(run, 'MISSING_RECEIPT', result))
            return
        if (receipt.get('run_id') != run['id']
                or receipt.get('experiment_digest') != run['experiment_digest']
                or receipt.get('job_id') != run['id'] + '-attempt-' + str(run['attempt'])):
            raise ValueError('executor receipt does not match immutable run identity')
        directory = self.app.root / 'receipts' / run['id']
        directory.mkdir(parents=True, exist_ok=True)
        # Persist the local receipt before marking dispatch successful.
        atomic_write(directory / f'{run["attempt"]}.json', encoded(receipt))
        current = self.store.get('executions', run['id'])['state']
        if current in {'PREPARING', 'LOST'}:
            self._state(run['id'], 'DISPATCHED', receipt=receipt)
        with self.store.connect() as db:
            db.execute('UPDATE run_attempts SET receipt=?,state=? WHERE run_id=? AND attempt=?',
                       (encoded(receipt), result['state'], run['id'], run['attempt']))

    def recover(self, run_id):
        with exclusive_lock(self.app.root / 'run-locks' / (run_id + '.lock'), timeout=60):
            return self._recover(run_id)

    def _recover(self, run_id):
        run = self.store.get('executions', run_id)
        if run['state'] == 'CREATED':
            return self.status(run_id)  # Recovery is never an implicit initial dispatch.
        if run['state'] in TERMINAL:
            if run['state'] == 'SUCCEEDED':
                self._interpret(run)  # Idempotently finish a crash-interrupted local finding write.
            return self.status(run_id)
        request = self._request(run)
        transport = self._transport(run)
        try:
            result = transport.call({'operation': 'inspect', 'job_id': request['job_id']})
        except TransportError as exc:
            self._state(run_id, 'LOST', failure=self._failure(run, 'NODE_UNAVAILABLE', exc))
            return self.status(run_id)
        if result['state'] == 'ABSENT':
            if run['receipt']:
                self._state(run_id, 'LOST', failure=self._failure(
                    run, 'REMOTE_STATE_MISSING', 'Remote state disappeared after receipt', False))
                return self.status(run_id)
            if not result.get('launch_claimed') and result.get('confirmed_dead'):
                try:
                    result = transport.call({'operation': 'seal', 'job_id': request['job_id']})
                except TransportError as exc:
                    self._state(run_id, 'LOST', failure=self._failure(run, 'SEAL_UNCONFIRMED', exc))
                    return self.status(run_id)
            if result.get('sealed'):
                target = 'FAILED_RETRYABLE' if run['attempt'] < run['max_retries'] else 'FAILED_FINAL'
                self._state(run_id, target, failure=self._failure(run, 'NOT_LAUNCHED', 'No remote job'))
                with self.store.connect() as db:
                    db.execute('UPDATE run_attempts SET state=?,completed_at=? WHERE run_id=? AND attempt=?',
                               (target, utc_stamp(), run_id, run['attempt']))
            else:
                self._state(run_id, 'LOST', failure=self._failure(run, 'AMBIGUOUS_LAUNCH', result, False))
            return self.status(run_id)
        self._accept_receipt(run, result)
        if result['state'] in {'RUNNING', 'DISPATCHED'}:
            self._state(run_id, 'RUNNING')
            return self.status(run_id)
        if not result.get('confirmed_dead') or result['state'] == 'LOST':
            if result.get('receipt'):
                try:
                    partial = transport.call({'operation': 'partial', 'job_id': request['job_id']})
                    self._collect(run, partial)
                except (TransportError, ValueError, OSError) as exc:
                    self.policy.decision(run['project_id'], 'PARTIAL_COLLECTION_FAILED',
                                         {'run_id': run_id, 'error': str(exc)})
            self._state(run_id, 'LOST', failure=self._failure(run, 'SUPERVISOR_LOST', result, False))
            return self.status(run_id)
        if result['state'] not in {'SUCCEEDED', 'FAILED_FINAL', 'TIMED_OUT', 'CANCELLED'}:
            raise ValueError('unknown executor state')
        self._state(run_id, 'COLLECTING')
        try:
            collection = transport.call({'operation': 'collect', 'job_id': request['job_id']})
            self._collect(run, collection)
        except (TransportError, ValueError, OSError) as exc:
            self._state(run_id, 'COLLECTING', failure=self._failure(run, 'ARTIFACT_TRANSFER', exc))
            return self.status(run_id)
        target = result['state']
        failure = None
        if target != 'SUCCEEDED':
            retryable = result.get('failure_type') in {'PROCESS_EXIT', 'PREPARATION_FAILURE', 'OOM'}
            if target == 'FAILED_FINAL' and retryable and run['attempt'] < run['max_retries']:
                target = 'FAILED_RETRYABLE'
            failure = self._failure(run, result.get('failure_type', 'PROCESS_EXIT'),
                                    result.get('error', ''), retryable)
            failure['exit_code'] = result.get('exit_code')
            failure['partial_artifacts'] = [a['path'] for a in collection['artifacts']]
            stderr = next((a for a in collection['artifacts'] if a['path'] == 'stderr.log'), None)
            if stderr:
                failure['stderr'] = base64.b64decode(stderr['content']).decode(errors='replace')[-8000:]
        with self.store.connect() as db:
            db.execute('UPDATE run_attempts SET state=?,failure=?,completed_at=? WHERE run_id=? AND attempt=?',
                       (target, encoded(failure) if failure else None, utc_stamp(), run_id, run['attempt']))
        self._state(run_id, target, failure=failure)
        if target == 'SUCCEEDED':
            self._interpret(run)
        return self.status(run_id)

    def _collect(self, run, collection):
        state = collection['state']
        if state.get('experiment_digest') != run['experiment_digest'] or state.get('run_id') != run['id']:
            raise ValueError('artifact collection belongs to a different run')
        for entry in collection['artifacts']:
            relative = Path(entry['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('escaping artifact path')
            content = base64.b64decode(entry['content'], validate=True)
            if sha256_bytes(content) != entry['sha256'] or len(content) != entry['size']:
                raise ValueError('artifact transport hash mismatch')
            target = self.app.root / 'artifacts' / entry['sha256']
            target.parent.mkdir(exist_ok=True)
            if target.is_symlink() or target.resolve() != target:
                raise ValueError('artifact store path must not be a symlink')
            if target.exists() and sha256_bytes(target.read_bytes()) != entry['sha256']:
                raise ValueError('existing artifact store content was modified')
            if not target.exists():
                temp = target.with_suffix('.tmp')
                temp.write_bytes(content)
                temp.replace(target)
            with self.store.connect() as db:
                existing = db.execute('SELECT a.digest FROM artifact_origins o JOIN artifacts a '
                                      'ON a.id=o.artifact_id WHERE o.run_id=? AND o.attempt=? '
                                      'AND o.relative_path=?', (run['id'], run['attempt'], entry['path'])).fetchone()
                if existing:
                    if existing['digest'] != entry['sha256']:
                        raise ValueError('previously collected artifact changed')
                    continue
                artifact_id = uid('ART')
                db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)',
                           (artifact_id, run['id'], str(target), entry['sha256'], utc_stamp()))
                db.execute('INSERT INTO artifact_origins VALUES (?,?,?,?)',
                           (run['id'], run['attempt'], entry['path'], artifact_id))
        directory = self.app.root / 'receipts' / run['id']
        directory.mkdir(parents=True, exist_ok=True)
        atomic_write(directory / f'{run["attempt"]}-manifest.json', encoded(collection['manifest']))

    def retry(self, run_id):
        with exclusive_lock(self.app.root / 'run-locks' / (run_id + '.lock'), timeout=60):
            run = self.store.get('executions', run_id)
            if run['state'] != 'FAILED_RETRYABLE' or run['attempt'] >= run['max_retries']:
                raise ValueError('retry policy does not permit another attempt')
            request = self._request(run)
            previous = self._transport(run).call({'operation': 'inspect', 'job_id': request['job_id']})
            if (not previous.get('confirmed_dead') or previous['state'] == 'SUCCEEDED'
                    or (previous.get('launch_claimed') and previous['state'] == 'ABSENT'
                        and not previous.get('sealed'))):
                raise ValueError('previous execution is not confirmed dead and non-completed')
            with self.store.connect() as db:
                db.execute('UPDATE executions SET attempt=attempt+1 WHERE id=?', (run_id,))
            return self._launch(self.store.get('executions', run_id))

    def cancel(self, run_id):
        with exclusive_lock(self.app.root / 'run-locks' / (run_id + '.lock'), timeout=60):
            run = self.store.get('executions', run_id)
            if run['state'] in {'CREATED', 'FAILED_RETRYABLE'}:
                self._state(run_id, 'CANCELLED')
            elif run['state'] not in TERMINAL:
                request = self._request(run)
                self._transport(run).call({'operation': 'cancel', 'job_id': request['job_id']})
            return self.status(run_id)

    def _interpret(self, run):
        with self.store.connect() as db:
            if db.execute('SELECT 1 FROM findings_from_runs WHERE run_id=?', (run['id'],)).fetchone():
                return
            artifacts = db.execute('SELECT o.relative_path,a.path,a.digest FROM artifact_origins o '
                                   'JOIN artifacts a ON a.id=o.artifact_id WHERE o.run_id=? AND o.attempt=?',
                                   (run['id'], run['attempt'])).fetchall()
        spec = verify_frozen(self.app, self.store.get('experiment_freezes', run['freeze_id']))
        metric_path = 'code/' + spec['protocol']['metric_file']
        metric = next((a for a in artifacts if a['relative_path'] == metric_path), None)
        measurement, inference, outcomes = {}, [], []
        if metric:
            content = Path(metric['path']).read_bytes()
            if sha256_bytes(content) != metric['digest']:
                raise ValueError('stored metrics artifact hash mismatch')
            try:
                measurement = json.loads(content, parse_constant=lambda value: None)
                if not isinstance(measurement, dict):
                    measurement = {}
            except ValueError:
                measurement = {}
        for rule in spec['protocol']['rules']:
            value = measurement.get(rule['metric'])
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                outcome = 'INCONCLUSIVE'
            else:
                success = COMPARATORS[rule['success']['op']](value, rule['success']['value'])
                falsified = COMPARATORS[rule['falsification']['op']](value, rule['falsification']['value'])
                outcome = ('SUPPORTED' if success and not falsified else
                           'FALSIFIED' if falsified and not success else 'INCONCLUSIVE')
            outcomes.append(outcome)
            inference.append({'metric': rule['metric'], 'rule': rule, 'outcome': outcome})
        outcome = ('INCONCLUSIVE' if 'INCONCLUSIVE' in outcomes else
                   'FALSIFIED' if 'FALSIFIED' in outcomes else 'SUPPORTED')
        finding_id = uid('FINDING')
        comparison = {}
        unexpected = []
        if isinstance(spec['prediction'], dict):
            for metric_name, predicted in spec['prediction'].items():
                observed = measurement.get(metric_name)
                comparison[metric_name] = {'prediction': predicted, 'observed': observed}
                if (isinstance(predicted, dict) and isinstance(observed, (int, float))
                        and not isinstance(observed, bool)):
                    low, high = predicted.get('min'), predicted.get('max')
                    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
                        unexpected.append(not low <= observed <= high)
        data = {'id': finding_id, 'run_ids': [run['id']], 'experiment_id': run['experiment_id'],
                'hypothesis_id': spec['hypothesis_id'], 'measurement': measurement,
                'inference': inference, 'outcome': outcome, 'prediction': spec['prediction'],
                'confidence': 'One executor-verified run; replication not established.',
                'supports': spec.get('claim_ids', []) if outcome == 'SUPPORTED' else [],
                'falsifies': [spec['hypothesis_id']] if outcome == 'FALSIFIED' else [],
                'prediction_vs_observation': comparison,
                'unexpected': any(unexpected) if unexpected else None, 'next_questions': ['Replication or in-scope follow-up'],
                'verification': 'EXECUTOR_VERIFIED', 'experiment_digest': run['experiment_digest'],
                'evidence': [dict(a) for a in artifacts]}
        with self.store.connect() as db:
            db.execute('INSERT INTO findings VALUES (?,?,?,?,?)',
                       (finding_id, run['project_id'], run['experiment_id'], encoded(data), utc_stamp()))
            db.execute('INSERT INTO findings_from_runs VALUES (?,?)', (run['id'], finding_id))
            db.execute('INSERT INTO hypothesis_states VALUES (?,?,?,?) ON CONFLICT(hypothesis_id) '
                       'DO UPDATE SET state=excluded.state,finding_id=excluded.finding_id,'
                       'updated_at=excluded.updated_at',
                       (spec['hypothesis_id'], outcome, finding_id, utc_stamp()))
        if outcome == 'INCONCLUSIVE':
            self.policy.decision(run['project_id'], 'NON_DISCRIMINATING_EVIDENCE', {'run_id': run['id']})
        if outcome == 'FALSIFIED':
            self.policy.decision(run['project_id'], 'HYPOTHESIS_STOPPED',
                                 {'hypothesis_id': spec['hypothesis_id'], 'run_id': run['id']})

            hypothesis = json.loads(self.store.get('hypotheses', spec['hypothesis_id'])['data'])
            envelope = json.loads(self.store.get('envelopes', run['project_id'] + ':' + spec['envelope_digest'])['data'])
            if hypothesis.get('critical') and envelope.get('stop_on_critical_falsification') is True:
                with self.store.connect() as db:
                    db.execute("UPDATE projects SET state='STOPPED' WHERE id=?", (run['project_id'],))
                self.policy.decision(run['project_id'], 'PROJECT_STOPPED',
                                     {'reason': 'Explicit envelope critical-hypothesis stop policy'})
