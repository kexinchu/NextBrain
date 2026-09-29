"""Synthetic fixtures validate the control plane, never scientific claims."""
import copy
import json

import pytest
import yaml

from test_resumable_runs import case as base_case, prepare, finish, approve  # noqa: F401
from researchos.advance import advance
from researchos.controller import after_run, approve_gate, gate_summary, require_story_gate
from researchos.execution import Runs
from researchos.freeze import freeze_experiment
from researchos.planner import (plan, import_proposals, validate_bundle, effective_spec, assert_fresh)
from researchos.research_state import add_uncertainty, build_context
from autoresearch.freeze import FreezeGuard


@pytest.fixture
def research(base_case):  # noqa: F811
    app, project, repo, _ = base_case
    spec = prepare(base_case)
    add_uncertainty(app, project, {'id': 'U1', 'question': 'Does the fixture discriminate?',
        'related_hypotheses': ['H1'], 'importance': 'HIGH', 'why_it_matters': 'Tests a decision boundary'})
    return base_case, spec


def candidate(research, name='E2', *, uncertainty='U1', hypothesis='H1', mode='EXPLORATION',
              kind='MECHANISM', evidence='SYSTEM_VALIDATION'):
    case, template = research
    spec = copy.deepcopy(template)
    spec.update(id=name, hypothesis_id=hypothesis, evidence_kind=evidence)
    return {'candidate_id': 'C-' + name, 'uncertainty_id': uncertainty, 'hypothesis_ids': [hypothesis],
        'question': 'Which frozen outcome occurs?', 'experiment_type': kind, 'mode': mode,
        'expected_information': 'Separate positive and negative fixture outcomes.',
        'possible_outcomes': {k: {'interpretation': v, 'uncertainty_status': 'UNCHANGED' if k == 'OPERATIONAL_FAILURE' else 'REDUCED'}
            for k, v in {'SUPPORTED': 'Supports the tested hypothesis', 'FALSIFIED': 'Falsifies it',
                         'INCONCLUSIVE': 'Insufficient evidence', 'OPERATIONAL_FAILURE': 'No scientific conclusion'}.items()},
        'estimated_cost': 1, 'risk': 'Small isolated fixture', 'discrimination_power': .8,
        'expected_information_gain': .8, 'feasibility': 1, 'spec': spec, 'repo': str(case[2]),
        'machine': None, 'replication_of': None}


def supply(research, candidates):
    case, _ = research
    return import_proposals(case[0], case[1], {'reasoning_summary': 'Fixture proposals test policy boundaries.',
                                             'candidates': candidates})


def execute(research, c):
    case, _ = research
    app, project, repo, _ = case
    validate_bundle(app, project, {'reasoning_summary': 'Fixture', 'candidates': [c]})
    app.add('experiment', project, effective_spec(c))
    freeze_experiment(app, c['spec']['id'], repo)
    runs = Runs(app)
    run_id = runs.create(c['spec']['id'])['id']
    runs.dispatch(run_id)
    finish(runs, run_id)
    return run_id, after_run(app, run_id)


def test_context_reads_multiple_findings_and_digest_changes(research):
    app, project, _, _ = research[0]
    before = build_context(app, project)
    r1, _ = execute(research, candidate(research))
    r2, _ = execute(research, candidate(research, 'E3'))
    context = build_context(app, project)
    assert len(context['findings']) == 2
    assert set(context['completed_experiments']) == {'E2', 'E3'}
    assert context['research_state_digest'] != before['research_state_digest']
    assert r1 != r2


def test_closed_hypothesis_excluded(research):
    app, project, _, _ = research[0]
    with app.store.connect() as db:
        db.execute("UPDATE hypothesis_states SET state='FALSIFIED' WHERE hypothesis_id='H1'")
    supply(research, [candidate(research)])
    assert plan(app, project)['selected'] is None


def test_exploration_outranks_premature_optimization(research):
    app, project, _, _ = research[0]
    optimization = candidate(research, 'E3', mode='OPTIMIZATION')
    optimization['expected_information_gain'] = 1
    supply(research, [candidate(research), optimization])
    decision = plan(app, project)
    assert decision['selected_experiment'] == 'E2'
    assert 'optimization' in str(decision['rejected_candidates'])


@pytest.mark.parametrize('field', ['possible_outcomes', 'envelope', 'feasibility'])
def test_malformed_agent_output_never_persisted(research, field):
    app, project, _, _ = research[0]
    c = candidate(research)
    if field == 'possible_outcomes':
        c.pop(field)
    elif field == 'envelope':
        c[field] = {'resource_budget': {'gpu_hours': 999}}
    else:
        c[field] = float('nan')
    before = (app.workspace(project) / 'PROJECT_ENVELOPE.md').read_bytes()
    with pytest.raises(ValueError):
        supply(research, [c])
    assert not app.store.list('planner_proposals', project)
    assert (app.workspace(project) / 'PROJECT_ENVELOPE.md').read_bytes() == before


def test_out_of_scope_rejected_and_gate_created(research):
    app, project, _, _ = research[0]
    c = candidate(research)
    c['spec']['experiment_class'] = 'new-architecture'
    supply(research, [c])
    assert plan(app, project)['selected'] is None
    result = advance(app, project)
    assert result['run_ids'] == []
    assert app.store.list('maturity_gates', project)


def test_budget_blocks_planning_and_stops_cleanly(research):
    app, project, _, envelope = research[0]
    envelope['resource_budget']['cpu_hours'] = .00001
    approve(app, project, envelope)
    supply(research, [candidate(research)])
    assert not plan(app, project)['ready']
    result = advance(app, project)
    assert result['state'] == 'STOPPED' and not result['run_ids']
    assert 'budget' in result['stop_reason']


def test_dependencies_block_without_executor_support(research):
    app, project, _, _ = research[0]
    c = candidate(research)
    c['spec']['dependencies'] = ['E1']
    supply(research, [c])
    assert 'dependency' in str(plan(app, project)['rejected_candidates'])


def test_resource_selection_skips_unavailable_4060(research):
    from researchos.store import encoded
    app, project, _, _ = research[0]
    with app.store.connect() as db:
        for name, status, memory in [('4060', 'UNREACHABLE', 8), ('A6000', 'OK', 48), ('big', 'OK', 80)]:
            db.execute('INSERT INTO machines VALUES (?,?,?,?)', (name, '', encoded({'status': status,
                'capabilities': {'gpus': [{'index': 0, 'vram_gb': memory}]}}), 'now'))
    c = candidate(research)
    c['spec']['resource_requirement'] = {'gpu_required': True, 'cpu_only': False, 'gpu_count': 1, 'min_vram_gb': 6}
    c['spec']['budget']['gpu_hours'] = 1
    supply(research, [c])
    assert plan(app, project)['selected']['machine']['alias'] == 'A6000'


def test_next_has_durable_audit_but_no_execution(research):
    from researchos.next_experiment import prepare_next
    app, project, _, _ = research[0]
    supply(research, [candidate(research)])
    decision = prepare_next(app, project)
    assert not decision['will_execute'] and not app.store.list('executions')
    saved = app.store.get('planner_decisions', decision['id'])
    assert json.loads(saved['data'])['selection_scores'][0]['components']['importance'] == 3


def test_advance_defaults_to_one_and_replans(research):
    app, project, _, _ = research[0]
    supply(research, [candidate(research), candidate(research, 'E3')])
    result = advance(app, project)
    assert result['state'] == 'STOPPED', result
    assert result['stop_reason'] == 'MAX_RUNS'
    assert len(result['run_ids']) == 1
    assert len(result['planner_decisions']) >= 3
    assert len(app.store.list('findings', project)) == 1


def test_max_three_never_runs_four(research):
    app, project, _, _ = research[0]
    supply(research, [candidate(research, 'E' + str(i)) for i in range(2, 6)])
    result = advance(app, project, max_runs=3)
    assert len(result['run_ids']) == 3, result
    assert len(set(result['run_ids'])) == 3
    assert len(app.store.list('findings', project)) == 3
    decisions = [json.loads(r['data']) for r in app.store.list('planner_decisions', project)]
    assert len({d['research_state_digest'] for d in decisions}) >= 4


def test_synthetic_finding_cannot_change_scientific_belief(research):
    app, project, _, _ = research[0]
    run, control = execute(research, candidate(research))
    assert 'NOT SCIENTIFIC EVIDENCE' in control['reason']
    assert Runs(app).status(run)['scientific_outcome'] is None
    assert build_context(app, project)['hypotheses'][0]['state'] == 'PROPOSED'
    assert app.store.get('uncertainties', 'U1')['status'] == 'OPEN'
    assert not app.store.list('maturity_gates', project)


def test_important_positive_requests_replication(research):
    app, project, _, _ = research[0]
    _, control = execute(research, candidate(research, evidence='SCIENTIFIC'))
    assert control['action'] == 'REPLICATE'
    assert build_context(app, project)['hypotheses'][0]['confidence'] == 'PRELIMINARY'


def test_identical_replication_is_not_independent(research):
    app, project, _, _ = research[0]
    run, _ = execute(research, candidate(research, evidence='SCIENTIFIC'))
    c = candidate(research, 'E3', kind='REPLICATION', evidence='SCIENTIFIC')
    c['replication_of'] = run
    _, control = execute(research, c)
    assert control['action'] == 'REPLICATE'
    assessment = json.loads(app.store.list('research_assessments', project)[-1]['data'])
    assert not assessment['independent_positive']


def test_independent_replication_triggers_maturity_gate(research):
    app, project, repo, _ = research[0]
    run, _ = execute(research, candidate(research, evidence='SCIENTIFIC'))
    config = app.workspace(project) / 'autoresearch.yaml'
    data = yaml.safe_load(config.read_text())
    data['commands']['alternate'] = {'skill': 'experiment-loop', 'argv': [__import__('sys').executable, 'experiment.py', '--seed=2'], 'timeout': 10}
    config.write_text(yaml.safe_dump(data))
    c = candidate(research, 'E3', kind='REPLICATION', evidence='SCIENTIFIC')
    c['spec']['command_name'] = 'alternate'
    c['replication_of'] = run
    _, control = execute(research, c)
    assert control['action'] == 'ESCALATE_HUMAN'
    gate = app.store.get('maturity_gates', control['gate_id'])
    message = repo.parent / 'human.txt'
    message.write_text('APPROVE gate:FREEZE_STORY ' + gate['digest'] + '\nFixture approval, not real research\n')
    approve_gate(app, gate['id'], gate['digest'], 'FREEZE_STORY', message, 'fixture')
    require_story_gate(app, project)


def test_story_freeze_requires_gate(research):
    app, project, _, _ = research[0]
    path = app.workspace(project) / 'paper' / 'STORY.md'
    path.parent.mkdir(exist_ok=True)
    path.write_text('Unapproved synthetic story')
    with pytest.raises(ValueError, match='Human Gate #2'):
        FreezeGuard(app.workspace(project)).create('paper-story', ['paper/STORY.md'])


def test_stale_planner_decision_cannot_execute(research):
    app, project, _, _ = research[0]
    supply(research, [candidate(research)])
    decision = plan(app, project)
    execute(research, candidate(research, 'E3'))
    with pytest.raises(ValueError, match='stale'):
        assert_fresh(app, decision)


def test_operational_failure_preserves_belief(research):
    case, _ = research
    app, project, _, _ = case
    spec = prepare(case, code='raise RuntimeError("synthetic failure")\n', name='E-error')
    research = (case, spec)
    _, control = execute(research, candidate(research, evidence='SCIENTIFIC'))
    assert control['action'] == 'CONTINUE'
    assert build_context(app, project)['hypotheses'][0]['state'] == 'PROPOSED'
    assert not app.store.list('research_assessments', project)


def test_falsification_continues_other_branch_without_gate(research):
    case, _ = research
    app, project, _, _ = case
    spec = prepare(case, code="from pathlib import Path\nPath('metrics.json').write_text('{\"value\":1}')\n", name='E-negative')
    research = (case, spec)
    app.add('hypothesis', project, {'id': 'H2', 'statement': 'Alternative', 'falsification_condition': 'Test fails'})
    add_uncertainty(app, project, {'id': 'U2', 'question': 'Alternative?', 'related_hypotheses': ['H2'],
                                 'importance': 'HIGH', 'why_it_matters': 'Independent branch'})
    supply(research, [candidate(research, evidence='SCIENTIFIC'),
                     candidate(research, 'E3', uncertainty='U2', hypothesis='H2', evidence='SCIENTIFIC')])
    result = advance(app, project, max_runs=2)
    assert len(result['run_ids']) == 2, result
    assert not app.store.list('maturity_gates', project)
    assert app.store.get('projects', project)['state'] == 'ACTIVE'


def test_wall_time_admission_stops_before_launch(research):
    app, project, _, _ = research[0]
    supply(research, [candidate(research)])
    result = advance(app, project, max_wall_time=.01)
    assert not result['run_ids']
    assert 'MAX_WALL_TIME' in result['stop_reason']


def test_scope_request_stops_advance(research):
    from researchos.policy import Policy
    app, project, _, _ = research[0]
    supply(research, [candidate(research)])
    Policy(app).scope_request(project, {'category': 'architecture', 'reason': 'Requires new mechanism',
                                      'proposed_change': 'Separate architecture'})
    result = advance(app, project)
    assert not result['run_ids'] and app.store.list('maturity_gates', project)


def test_context_is_bounded_and_retains_global_evidence_counts(research):
    app, project, _, _ = research[0]
    for i in range(5):
        execute(research, candidate(research, 'Many' + str(i), evidence='SCIENTIFIC'))
    context = build_context(app, project, limit=2)
    assert len(context['findings']) == 2
    assert context['hypotheses'][0]['evidence_counts']['SUPPORTED'] == 5
    assert context['truncated']['findings'] == 3


def test_synthetic_gate_cannot_authorize_story(research):
    app, project, repo, _ = research[0]
    execute(research, candidate(research))
    gate = gate_summary(app, project, 'Fixture')
    message = repo.parent / 'approval-gate.txt'
    message.write_text('APPROVE gate:FREEZE_STORY ' + gate['digest'])
    with pytest.raises(ValueError, match='replicated scientific'):
        approve_gate(app, gate['id'], gate['digest'], 'FREEZE_STORY', message, 'fixture')


def test_insufficient_disk_marks_remote_unavailable(research, monkeypatch, tmp_path):
    import subprocess
    from researchos.ssh import import_config, probe
    app = research[0][0]
    config = tmp_path / 'ssh-config'
    config.write_text('Host cloudsys02\n HostName example.invalid\n')
    import_config(app.store, config)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 0,
        '__ROS_HOSTNAME__\nfixture\n__ROS_DISK__\nFilesystem 1024-blocks Used Available Capacity Mounted on\n/dev/mock 1000000 999999 1 100% /\n', ''))
    result = probe(app.store, 'cloudsys02')
    assert result['data']['status'] == 'UNAVAILABLE'
    assert 'no automatic cleanup' in result['data']['reason']


def test_story_round_cannot_start_before_gate(research):
    from autoresearch.workflow import WorkflowState
    app, project, _, _ = research[0]
    workflow = WorkflowState(app.workspace(project))
    state = workflow.load()
    state['idea']['status'] = 'satisfied'
    workflow.save(state)
    with pytest.raises(ValueError, match='Human Gate #2'):
        workflow.begin('fixture-round', 'story-freeze', 'researcher', 'fixture-message')
    assert workflow.load()['pending_round'] is None


def test_reasoner_receives_fresh_context_each_round(research):
    app, project, _, _ = research[0]
    contexts = []
    class Reasoner:
        def propose(self, context):
            contexts.append(context)
            return {'reasoning_summary': 'Adapt candidate to accumulated evidence',
                    'candidates': [candidate(research, 'Adaptive' + str(len(context['findings'])))]}
    result = advance(app, project, max_runs=2, reasoner=Reasoner())
    assert len(result['run_ids']) == 2
    assert {len(c['findings']) for c in contexts} == {0, 1, 2}


def test_advance_resume_recovers_existing_job_without_duplicate(research):
    app, project, _, _ = research[0]
    supply(research, [candidate(research)])
    original = Runs(app)
    class LostOnce:
        def __init__(self):
            self.once = True
        def __getattr__(self, name):
            return getattr(original, name)
        def recover(self, run_id):
            if self.once:
                self.once = False
                return {**original.status(run_id), 'state': 'LOST'}
            return original.recover(run_id)
    first = advance(app, project, runs=LostOnce())
    assert first['state'] == 'RECOVERY_REQUIRED'
    resumed = advance(app, project, resume=first['id'])
    assert resumed['run_ids'] == first['run_ids']
    assert len(app.store.list('executions', project)) == 1
    assert resumed['stop_reason'] == 'MAX_RUNS'


def test_expired_advance_cannot_expand_original_bounds(research):
    app, project, _, _ = research[0]
    from researchos.store import encoded
    with app.store.connect() as db:
        db.execute('INSERT INTO advances VALUES (?,?,?,?,?)', ('expired', project, encoded({
            'max_runs': 1, 'deadline': 0, 'max_wall_time': 1, 'run_ids': [],
            'planner_decisions': [], 'controllers': [], 'stop_reason': None}), 'INTERRUPTED', 'now'))
    result = advance(app, project, max_runs=10, max_wall_time='24h', resume='expired')
    assert not result['run_ids'] and result['stop_reason'] == 'MAX_WALL_TIME'
    assert result['max_runs'] == 1


def test_supervisor_completion_during_inspection_is_not_lost(tmp_path, monkeypatch):
    from researchos import worker
    worker.write(tmp_path / 'state.json', {'state': 'RUNNING', 'updated_at': 0})
    def completed(*args):
        worker.write(tmp_path / 'state.json', {'state': 'SUCCEEDED', 'updated_at': 1})
        return False
    monkeypatch.setattr(worker, 'alive', completed)
    result = worker.inspect(tmp_path)
    assert result['state'] == 'SUCCEEDED' and result['confirmed_dead']


def test_frozen_snapshot_contains_predeclared_interpretations(research):
    app, project, _, _ = research[0]
    c = candidate(research)
    supply(research, [c])
    result = advance(app, project)
    row = app.store.get('executions', result['run_ids'][0])
    snapshot = json.loads(app.store.get('experiment_freezes', row['freeze_id'])['data'])
    assert snapshot['planning']['possible_outcomes'] == c['possible_outcomes']
    assert snapshot['evidence_kind'] == 'SYSTEM_VALIDATION'


def test_pending_gate_blocks_next_readiness(research):
    app, project, _, _ = research[0]
    supply(research, [candidate(research)])
    decision = plan(app, project)
    gate_summary(app, project, 'Maturity review')
    assert not plan(app, project)['ready']
    with pytest.raises(ValueError, match='Gate #2'):
        assert_fresh(app, decision)


def test_agent_output_cannot_reinterpret_operational_failure(research):
    c = candidate(research)
    c['possible_outcomes']['OPERATIONAL_FAILURE']['uncertainty_status'] = 'RESOLVED'
    with pytest.raises(ValueError, match='operational failure'):
        supply(research, [c])


def test_transport_deadline_rechecked_before_each_call(tmp_path, monkeypatch):
    from researchos.transport import LocalTransport, TransportError
    import time
    transport = LocalTransport(tmp_path, tmp_path / 'unused-worker')
    transport.deadline = time.time() - 1
    with pytest.raises(TransportError, match='deadline'):
        transport.call({'operation': 'inspect'})


def test_claim_scope_change_cannot_be_hidden_in_candidate(research):
    app, project, _, _ = research[0]
    c = candidate(research)
    c['spec']['scope'] = {'claim': 'New scientific claim outside envelope'}
    supply(research, [c])
    result = plan(app, project)
    assert not result['ready'] and not result['scope_check']


def test_missing_proposals_does_not_invent_project_stop(research):
    app, project, _, _ = research[0]
    result = advance(app, project)
    assert 'AWAITING_IN_SCOPE_PROPOSALS' in result['stop_reason']
    assert not app.store.list('maturity_gates', project)
    assert app.store.get('projects', project)['state'] == 'ACTIVE'
