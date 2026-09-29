import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from researchos.execution import Runs
from researchos.freeze import freeze_experiment, verify_frozen
from researchos.next_experiment import prepare_next
from researchos.policy import Policy, match_machine
from researchos.service import ResearchOS
from researchos.transport import LocalTransport, TransportError


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def case(tmp_path):
    plans = tmp_path / 'plans'
    plans.mkdir()
    (plans / 'test.md').write_text('---\nidea_id: I1\ntitle: Executor fixture\n---\n# Fixture')
    app = ResearchOS(tmp_path / 'catalog')
    app.scan(plans)
    project = app.decide('I1', 'GO', 'test-fixture', 'Infrastructure validation')['id']
    envelope = {'schema_version': 1, 'project_id': project, 'problem': 'Validate executor',
                'boundary': 'Synthetic local tests only', 'resource_budget': {'gpu_hours': 1, 'cpu_hours': 1},
                'stop_conditions': ['Timeout or budget exhausted'], 'non_goals': ['Scientific results'],
                'allowed_experiment_classes': ['fixture'], 'allowed_baselines': []}
    approve(app, project, envelope)
    app.add('hypothesis', project, {'id': 'H1', 'statement': 'Fixture value reaches 5',
                                  'falsification_condition': 'Fixture value below 5'})
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.email', 'fixture@example.invalid')
    git(repo, 'config', 'user.name', 'ResearchOS test fixture')
    return app, project, repo, envelope


def approve(app, project, envelope):
    path = Policy(app).envelope_path(project)
    path.write_text('---\n' + yaml.safe_dump(envelope) + '---\n# Envelope\n')
    _, digest = Policy(app).envelope_draft(project)
    message = path.parent / 'approval.txt'
    message.write_text('APPROVE envelope ' + digest + '\nSynthetic fixture approval\n')
    Policy(app).approve_envelope(project, digest, message, 'test-fixture')
    return digest


def prepare(case, *, code=None, timeout=3, retries=0, name='E1', experiment_class='fixture', deps=None):
    app, project, repo, _ = case
    if code is None:
        code = "import json\nfrom pathlib import Path\nPath('metrics.json').write_text(json.dumps({'value': 8}))\nprint('fixture complete')\n"
    (repo / 'experiment.py').write_text(code)
    git(repo, 'add', '.')
    git(repo, 'commit', '--allow-empty', '-qm', 'Synthetic fixture')
    (app.workspace(project) / 'autoresearch.yaml').write_text(yaml.safe_dump({
        'version': 1, 'commands': {'fixture': {'skill': 'experiment-loop',
                                            'argv': [sys.executable, 'experiment.py'], 'timeout': 10}}}))
    spec = {'id': name, 'hypothesis_id': 'H1', 'experiment_class': experiment_class, 'priority': 1,
            'prediction': {'value': {'min': 5, 'max': 10}}, 'metrics': ['value'],
            'success_condition': 'value >= 5', 'failure_condition': 'value < 5',
            'falsification_condition': 'value < 5', 'expected_artifacts': ['metrics.json', 'started.txt'],
            'resource_requirement': {'cpu_only': True, 'gpu_required': False, 'gpu_count': 0},
            'environment_requirement': {'python_min': '3.10'}, 'command_name': 'fixture',
            'estimated_runtime': '1s', 'dependencies': deps or [], 'timeout': timeout,
            'budget': {'gpu_hours': 0, 'cpu_hours': timeout / 3600, 'max_retries': retries},
            'data': {'identifiers': [], 'hashes': {}},
            'protocol': {'metric_file': 'metrics.json', 'baselines': [], 'rules': [
                {'metric': 'value', 'success': {'op': '>=', 'value': 5},
                 'falsification': {'op': '<', 'value': 5}}]}}
    app.add('experiment', project, spec)
    if experiment_class == 'fixture':
        freeze_experiment(app, name, repo)
    return spec


def finish(runs, run_id):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        state = runs.recover(run_id)
        if state['state'] in {'SUCCEEDED', 'FAILED_FINAL', 'TIMED_OUT', 'CANCELLED', 'FAILED_RETRYABLE'}:
            return state
        time.sleep(0.05)
    runs.cancel(run_id)
    raise AssertionError('fixture run did not finish: ' + str(state))


def test_ids_unique_and_persist_before_any_executor_call(case):
    app, _, _, _ = case
    prepare(case)
    def factory(run, worker):
        assert app.store.get('executions', run['id'])['state'] in {'PREPARING', 'DISPATCHED', 'RUNNING',
                                                                  'COLLECTING', 'LOST'}
        assert json.loads(app.store.get('runs', run['id'])['data'])['experiment_digest'] == run['experiment_digest']
        return LocalTransport(app.root / 'executor', worker)
    runs = Runs(app, factory)
    ids = {runs.create('E1')['id'] for _ in range(5)}
    assert len(ids) == 5
    run_id = next(iter(ids))
    runs.dispatch(run_id)
    assert finish(runs, run_id)['state'] == 'SUCCEEDED'


def test_digest_and_prediction_immutable_after_dispatch(case):
    app, _, repo, _ = case
    prepare(case)
    runs = Runs(app)
    created = runs.create('E1')
    runs.dispatch(created['id'])
    (repo / 'experiment.py').write_text("raise RuntimeError('later edit')")
    result = finish(runs, created['id'])
    assert result['state'] == 'SUCCEEDED'
    assert result['experiment_digest'] == created['experiment_digest']
    finding = json.loads(app.store.list('findings')[0]['data'])
    assert finding['prediction'] == {'value': {'min': 5, 'max': 10}}
    assert finding['measurement'] == {'value': 8}
    freeze = app.store.get('experiment_freezes', result['freeze_id'])
    (app.root / 'frozen' / freeze['digest'] / 'worker.py').write_text('tampered')
    with pytest.raises(ValueError, match='modified'):
        verify_frozen(app, freeze)


def test_disconnect_recovery_finds_same_running_process_without_relaunch(case):
    app, _, _, _ = case
    prepare(case, code="import time,json\nfrom pathlib import Path\np=Path('started.txt')\np.write_text(p.read_text()+'x' if p.exists() else 'x')\ntime.sleep(0.8)\nPath('metrics.json').write_text(json.dumps({'value':8}))\n")
    launches = []
    class DropResponse:
        def __init__(self, worker):
            self.local = LocalTransport(app.root / 'executor', worker)
        def call(self, payload):
            reply = self.local.call(payload)
            if payload['operation'] == 'launch':
                launches.append(payload['job_id'])
                raise TransportError('simulated lost SSH response after launch')
            return reply
    runs = Runs(app, lambda run, worker: DropResponse(worker))
    run_id = runs.create('E1')['id']
    assert runs.dispatch(run_id)['state'] == 'LOST'
    recovered = runs.recover(run_id)
    assert recovered['state'] == 'RUNNING'
    pid = recovered['receipt']['supervisor_pid']
    assert runs.dispatch(run_id)['receipt']['supervisor_pid'] == pid
    assert finish(runs, run_id)['state'] == 'SUCCEEDED'
    assert len(launches) == 1
    assert (app.root / 'executor' / (run_id + '-attempt-0') / 'code/started.txt').read_text() == 'x'
    assert len(app.store.list('findings')) == 1


def test_timeout_and_partial_artifacts_survive(case):
    app, project, _, _ = case
    prepare(case, code="import time\nfrom pathlib import Path\nprint('before timeout',flush=True)\nPath('metrics.json').write_text('{\"value\":1}')\ntime.sleep(5)\n", timeout=0.3)
    runs = Runs(app)
    run_id = runs.create('E1')['id']
    runs.dispatch(run_id)
    result = finish(runs, run_id)
    assert result['state'] == 'TIMED_OUT'
    assert result['failure']['failure_type'] == 'WALL_CLOCK_TIMEOUT'
    assert app.store.list('findings') == []
    assert app.store.get('projects', project)['state'] == 'ACTIVE'
    assert any('before timeout' in Path(a['path']).read_text(errors='replace')
               for a in app.store.list('artifacts'))
    assert 'code/metrics.json' in result['failure']['partial_artifacts']


def test_bounded_retry_is_explicit_and_cannot_change_run_digest(case):
    app, project, _, _ = case
    prepare(case, code="import sys\nprint('failed fixture',file=sys.stderr)\nsys.exit(2)\n", retries=1)
    runs = Runs(app)
    original = runs.create('E1')
    runs.dispatch(original['id'])
    first = finish(runs, original['id'])
    assert first['state'] == 'FAILED_RETRYABLE'
    assert first['failure']['exit_code'] == 2
    assert first['failure']['retry_count'] == 0
    assert runs.recover(original['id'])['attempt'] == 0
    runs.retry(original['id'])
    last = finish(runs, original['id'])
    assert last['state'] == 'FAILED_FINAL'
    assert last['attempt'] == 1
    assert last['experiment_digest'] == original['experiment_digest']
    with pytest.raises(ValueError, match='retry policy'):
        runs.retry(original['id'])
    assert len(app.store.list('findings')) == 0
    assert app.store.get('projects', project)['state'] == 'ACTIVE'


def test_falsification_is_normal_progress_but_scope_change_is_human_gate(case):
    app, project, _, _ = case
    prepare(case, code="from pathlib import Path\nPath('metrics.json').write_text('{\"value\":1}')\n")
    runs = Runs(app)
    run_id = runs.create('E1')['id']
    runs.dispatch(run_id)
    result = finish(runs, run_id)
    assert result['state'] == 'SUCCEEDED'
    assert result['scientific_outcome'] == 'FALSIFIED'
    assert app.store.get('projects', project)['state'] == 'ACTIVE'
    finding = json.loads(app.store.list('findings')[0]['data'])
    assert finding['falsifies'] == ['H1']
    with pytest.raises(ValueError, match='falsified'):
        runs.create('E1')
    Policy(app).scope_request(project, {'category': 'question', 'reason': 'Evidence suggests pivot',
                                      'proposed_change': 'A different question'})
    assert app.store.get('projects', project)['state'] == 'SCOPE_CHANGE_REQUESTED'


def test_artifact_hashes_and_collect_are_idempotent(case):
    from autoresearch.io import sha256_file
    app, _, _, _ = case
    prepare(case)
    runs = Runs(app)
    run_id = runs.create('E1')['id']
    runs.dispatch(run_id)
    finish(runs, run_id)
    artifacts = app.store.list('artifacts')
    assert artifacts
    assert all(sha256_file(Path(a['path'])) == a['digest'] for a in artifacts)
    runs.recover(run_id)
    assert app.store.list('artifacts') == artifacts
    assert len(app.store.list('findings')) == 1


def test_next_refuses_scope_change_and_does_not_execute(case):
    app, project, _, _ = case
    prepare(case, experiment_class='large-production-sweep')
    result = prepare_next(app, project)
    assert result['requires_human_gate']
    assert not result['candidate']['within_scope']
    assert result['will_execute'] is False
    assert app.store.list('executions') == []


def test_smallest_valid_resource_selection():
    def machine(alias, sizes):
        return {'id': alias, 'data': json.dumps({'status': 'OK', 'capabilities': {
            'cpu': True, 'gpus': [{'index': i, 'vram_gb': size} for i, size in enumerate(sizes)]}})}
    machines = [machine('a6000', [48, 48]), machine('4060', [8]), machine('local', [])]
    assert match_machine({'cpu_only': True}, machines)['alias'] == 'local'
    assert match_machine({'gpu_required': True, 'min_vram_gb': 6}, machines)['alias'] == '4060'
    assert match_machine({'gpu_required': True, 'min_vram_gb': 20}, machines)['alias'] == 'a6000'
    assert match_machine({'gpu_required': True, 'gpu_count': 2}, machines)['gpu_indices'] == [0, 1]
    with pytest.raises(ValueError, match='no reachable'):
        match_machine({'gpu_required': True, 'min_vram_gb': 80}, machines)


def test_budget_reservation_prevents_new_dispatch(case):
    app, project, _, envelope = case
    envelope['resource_budget']['cpu_hours'] = 0.001
    approve(app, project, envelope)
    prepare(case, timeout=3)
    runs = Runs(app)
    runs.create('E1')
    with pytest.raises(ValueError, match='budget exhausted'):
        runs.create('E1')
    assert len(app.store.list('executions')) == 1
    assert app.store.list('policy_decisions')[-1]['kind'] == 'BUDGET_BLOCKED'


def test_approval_digest_invalidates_and_actor_label_is_not_approval(case):
    app, project, _, envelope = case
    path = Policy(app).envelope_path(project)
    message = path.parent / 'not-approval.txt'
    message.write_text('by human')
    digest = Policy(app).envelope_draft(project)[1]
    with pytest.raises(ValueError, match='APPROVE'):
        Policy(app).approve_envelope(project, digest, message, 'human')
    envelope['boundary'] = 'Changed scope'
    path.write_text('---\n' + yaml.safe_dump(envelope) + '---\n')
    with pytest.raises(ValueError, match='approval'):
        Policy(app).current(project)


def test_transfer_failure_can_recover_without_reexecution(case):
    app, _, _, _ = case
    prepare(case)
    failed = []
    class InterruptedCopy:
        def __init__(self, worker):
            self.local = LocalTransport(app.root / 'executor', worker)
        def call(self, payload):
            if payload['operation'] == 'collect' and not failed:
                failed.append(True)
                raise TransportError('artifact copy interrupted')
            return self.local.call(payload)
    runs = Runs(app, lambda run, worker: InterruptedCopy(worker))
    run_id = runs.create('E1')['id']
    runs.dispatch(run_id)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        state = runs.recover(run_id)
        if state['state'] == 'COLLECTING':
            break
        time.sleep(0.05)
    assert state['failure']['failure_type'] == 'ARTIFACT_TRANSFER'
    assert finish(runs, run_id)['state'] == 'SUCCEEDED'
    assert len(app.store.list('run_attempts')) == 1


def test_dirty_code_and_changed_authorization_block_dispatch(case):
    app, project, repo, _ = case
    prepare(case)
    (repo / 'untracked.txt').write_text('unreviewed')
    with pytest.raises(ValueError, match='clean'):
        freeze_experiment(app, 'E1', repo)
    runs = Runs(app)
    run_id = runs.create('E1')['id']
    config = app.workspace(project) / 'autoresearch.yaml'
    config.write_text('version: 1\ncommands: {}\n')
    with pytest.raises(ValueError, match='authorized command'):
        runs.dispatch(run_id)
    assert runs.status(run_id)['state'] == 'CREATED'


def test_cancellation_and_recovery_never_dispatch_created_run(case):
    app, _, _, _ = case
    prepare(case)
    runs = Runs(app)
    run_id = runs.create('E1')['id']
    assert runs.recover(run_id)['state'] == 'CREATED'
    assert not (app.root / 'executor').exists()
    assert runs.cancel(run_id)['state'] == 'CANCELLED'


def test_missing_metrics_are_inconclusive_not_falsified(case):
    app, _, _, _ = case
    prepare(case, code="print('no metrics')\n")
    runs = Runs(app)
    run_id = runs.create('E1')['id']
    runs.dispatch(run_id)
    result = finish(runs, run_id)
    assert result['state'] == 'SUCCEEDED'
    assert result['scientific_outcome'] == 'INCONCLUSIVE'
    assert app.store.list('policy_decisions')[-1]['kind'] == 'NON_DISCRIMINATING_EVIDENCE'


def test_scope_and_budget_changes_require_bound_request_then_envelope(case):
    app, project, _, envelope = case
    policy = Policy(app)
    request = policy.scope_request(project, {'category': 'budget', 'reason': 'More validation',
                                            'proposed_change': {'cpu_hours': 2}})
    envelope['resource_budget']['cpu_hours'] = 2
    with pytest.raises(ValueError, match='scope request'):
        approve(app, project, envelope)
    message = app.workspace(project) / 'scope-approval.txt'
    message.write_text('APPROVE scope ' + request['digest'])
    with pytest.raises(ValueError, match='reviewed'):
        policy.approve_scope(request['id'], 'wrong', message, 'test-fixture')
    policy.approve_scope(request['id'], request['digest'], message, 'test-fixture')
    approve(app, project, envelope)
    assert app.store.get('projects', project)['state'] == 'ACTIVE'
    assert app.store.get('scope_requests', request['id'])['state'] == 'RESOLVED'


def test_run_identity_is_guarded_in_database(case):
    import sqlite3
    app, _, _, _ = case
    prepare(case)
    run = Runs(app).create('E1')
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        with app.store.connect() as db:
            db.execute("UPDATE executions SET experiment_digest='other' WHERE id=?", (run['id'],))


def test_missing_baseline_and_nondiscriminating_rules_block_freeze(case):
    app, project, repo, envelope = case
    envelope['allowed_baselines'] = ['baseline-a']
    approve(app, project, envelope)
    spec = prepare(case)
    spec.update(id='E2')
    spec['protocol']['baselines'] = ['baseline-a']
    app.add('experiment', project, spec)
    with pytest.raises(ValueError, match='baseline unavailable'):
        freeze_experiment(app, 'E2', repo)
    spec.update(id='E3')
    spec['protocol']['baselines'] = []
    spec['protocol']['rules'][0]['falsification'] = spec['protocol']['rules'][0]['success']
    app.add('experiment', project, spec)
    with pytest.raises(ValueError, match='discriminating'):
        freeze_experiment(app, 'E3', repo)


def test_dead_supervisor_is_lost_and_never_blindly_retried(case):
    app, _, _, _ = case
    prepare(case)
    class LostSupervisor:
        def call(self, payload):
            if payload['operation'] == 'prepare':
                return {'state': 'PREPARED'}
            return {'state': 'LOST', 'receipt': None, 'confirmed_dead': False}
    runs = Runs(app, lambda run, worker: LostSupervisor())
    run_id = runs.create('E1')['id']
    assert runs.dispatch(run_id)['state'] == 'LOST'
    assert runs.recover(run_id)['state'] == 'LOST'
    with pytest.raises(ValueError, match='retry policy'):
        runs.retry(run_id)


def test_cancel_running_process_and_no_scientific_failure(case):
    app, project, _, _ = case
    prepare(case, code="import time\nprint('started',flush=True)\ntime.sleep(5)\n", timeout=8)
    runs = Runs(app)
    run_id = runs.create('E1')['id']
    runs.dispatch(run_id)
    runs.cancel(run_id)
    assert finish(runs, run_id)['state'] == 'CANCELLED'
    assert app.store.list('findings') == []
    assert app.store.get('projects', project)['state'] == 'ACTIVE'


def test_critical_hypothesis_stops_only_with_explicit_project_policy(case):
    app, project, _, envelope = case
    envelope['stop_on_critical_falsification'] = True
    approve(app, project, envelope)
    app.add('hypothesis', project, {'id': 'H-critical', 'statement': 'Critical premise',
                                  'falsification_condition': 'value below 5', 'critical': True})
    spec = prepare(case, code="from pathlib import Path\nPath('metrics.json').write_text('{\"value\":1}')\n")
    spec.update(id='E-critical', hypothesis_id='H-critical')
    app.add('experiment', project, spec)
    freeze_experiment(app, 'E-critical', case[2])
    runs = Runs(app)
    run_id = runs.create('E-critical')['id']
    runs.dispatch(run_id)
    assert finish(runs, run_id)['scientific_outcome'] == 'FALSIFIED'
    assert app.store.get('projects', project)['state'] == 'STOPPED'


def test_unavailable_node_preserves_run_and_budget(case):
    app, _, _, _ = case
    prepare(case, retries=1)
    class Offline:
        def call(self, payload):
            raise TransportError('host offline')
    runs = Runs(app, lambda run, worker: Offline())
    run = runs.create('E1')
    assert runs.dispatch(run['id'])['state'] == 'LOST'
    assert runs.recover(run['id'])['failure']['failure_type'] == 'NODE_UNAVAILABLE'
    assert len(app.store.list('executions')) == 1
    assert runs.status(run['id'])['reserved_cpu_hours'] == run['reserved_cpu_hours']


def test_legacy_v1_catalog_migrates_without_losing_imported_records(tmp_path):
    import sqlite3
    from researchos.store import SCHEMA
    root = tmp_path / 'legacy'
    root.mkdir()
    db = sqlite3.connect(root / 'researchos.sqlite3')
    db.executescript(SCHEMA)
    db.execute("INSERT INTO ideas VALUES ('I-old','Legacy','rev','INBOX','time')")
    db.execute('PRAGMA user_version=1')
    db.commit()
    db.close()
    app = ResearchOS(root)
    assert app.inbox()[0]['id'] == 'I-old'
    with app.store.connect() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 3
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_sealing_missing_job_prevents_delayed_duplicate_launch(case):
    app, _, _, _ = case
    prepare(case, retries=1)
    interrupted = []
    class FailBeforeLaunch:
        def __init__(self, worker):
            self.local = LocalTransport(app.root / 'executor', worker)
        def call(self, payload):
            if payload['operation'] == 'launch' and not interrupted:
                interrupted.append(payload.copy())
                raise TransportError('lost connection before launch was processed')
            return self.local.call(payload)
    runs = Runs(app, lambda run, worker: FailBeforeLaunch(worker))
    run_id = runs.create('E1')['id']
    assert runs.dispatch(run_id)['state'] == 'LOST'
    assert runs.recover(run_id)['state'] == 'FAILED_RETRYABLE'
    run = app.store.get('executions', run_id)
    transport = runs._transport(run)
    # A delayed launch request for the old attempt is now harmless, even after retry is allowed.
    delayed = transport.call(interrupted[0])
    assert delayed['state'] == 'ABSENT' and delayed['sealed']
    assert not (app.root / 'executor' / (run_id + '-attempt-0') / 'code').exists()
    runs.retry(run_id)
    assert finish(runs, run_id)['state'] == 'SUCCEEDED'
    assert len(app.store.list('executions')) == 1


def test_oom_is_operational_not_scientific(case):
    app, project, _, _ = case
    prepare(case, code="import sys\nprint('CUDA out of memory',file=sys.stderr)\nsys.exit(1)\n")
    runs = Runs(app)
    run_id = runs.create('E1')['id']
    runs.dispatch(run_id)
    result = finish(runs, run_id)
    assert result['failure']['failure_type'] == 'OOM'
    assert result['scientific_outcome'] is None
    assert app.store.get('projects', project)['state'] == 'ACTIVE'


def test_uncertain_supervisor_preserves_hashed_partial_evidence(case):
    app, _, _, _ = case
    prepare(case, code="import time\nprint('partial evidence',flush=True)\ntime.sleep(1)\nfrom pathlib import Path\nPath('metrics.json').write_text('{\"value\":8}')\n")
    uncertain = [False]
    class UncertainInspection:
        def __init__(self, worker):
            self.local = LocalTransport(app.root / 'executor', worker)
        def call(self, payload):
            result = self.local.call(payload)
            if payload['operation'] == 'inspect' and uncertain[0]:
                result.update(state='LOST', confirmed_dead=False)
            return result
    runs = Runs(app, lambda run, worker: UncertainInspection(worker))
    run_id = runs.create('E1')['id']
    runs.dispatch(run_id)
    uncertain[0] = True
    result = runs.recover(run_id)
    assert result['state'] == 'LOST' and result['scientific_outcome'] is None
    with app.store.connect() as db:
        origins = db.execute('SELECT relative_path FROM artifact_origins WHERE run_id=?', (run_id,)).fetchall()
    assert any(row[0].startswith('partial-') for row in origins)
    uncertain[0] = False
    assert finish(runs, run_id)['state'] == 'SUCCEEDED'


def test_artifact_limit_includes_truncated_logs(tmp_path):
    from researchos.worker import inventory
    (tmp_path / 'stdout.log').write_bytes(b'x' * 1000)
    (tmp_path / 'stderr.log').write_bytes(b'y' * 1000)
    manifest = inventory(tmp_path, {'snapshot': {'expected_artifacts': [],
                                                  'budget': {'artifact_bytes': 100}}})
    assert sum(entry['size'] for entry in manifest) <= 100
    assert manifest[0]['truncated']


def test_exhausted_retry_budget_cannot_be_reset_with_new_run(case):
    app, project, _, _ = case
    prepare(case, code='raise RuntimeError("fixture failure")\n')
    runs = Runs(app)
    run_id = runs.create('E1')['id']
    runs.dispatch(run_id)
    assert finish(runs, run_id)['state'] == 'FAILED_FINAL'
    with pytest.raises(ValueError, match='exhausted retries'):
        runs.create('E1')
    assert 'exhausted retries' in str(prepare_next(app, project)['candidate']['blockers'])
