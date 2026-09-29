"""Deterministic V0.3 contracts. All experimental data here are disposable fixtures."""
import copy
import json
from pathlib import Path

import pytest

from test_resumable_runs import case as base_case, prepare, finish  # noqa: F401
from test_bounded_loop import candidate
from autoresearch.contracts import protocol_digest
from researchos.controller import after_run
from researchos.execution import Runs
from researchos.freeze import freeze_experiment
from researchos.intelligence import (CYCLE_FIELDS, HYPOTHESIS_TYPES, RELATIONS, set_question, add_edge,
    add_debt, research_blockers, ordinal_value, classify_surprise, observe_finding,
    branch, research_review, claim_maturity, journal, trajectory)
from researchos.pilot import inspect_go
from researchos.planner import validate_bundle, effective_spec, import_proposals, plan
from researchos.policy import Policy
from researchos.reasoning_adapter import PromptedReasoner
from researchos.reasoning_eval import fixture_candidate, evaluate_cases
from researchos.research_state import add_uncertainty, build_context


@pytest.fixture
def intel(base_case):  # noqa: F811
    app, project, repo, envelope = base_case
    template = prepare(base_case)
    app.add('hypothesis', project, {'id': 'H2', 'hypothesis_type': 'MECHANISM',
        'statement': 'Fixture intervention explains the value', 'falsification_condition': 'No intervention effect'})
    set_question(app, project, {'id': 'Q1', 'question': envelope['problem'],
                               'motivation_hypotheses': [], 'oracle_hypotheses': []})
    add_uncertainty(app, project, {'id': 'U2', 'question': 'Does intervention affect fixture value?',
        'related_hypotheses': ['H2'], 'importance': 'HIGH', 'why_it_matters': 'Fixture discrimination'})
    c = candidate((base_case, template), hypothesis='H2', uncertainty='U2')
    c['research'] = fixture_candidate(repo, {'id': 'E2', 'hypothesis': 'H2', 'uncertainty': 'U2',
        'type': 'MECHANISM', 'strategy': 'CONTROLLED_INTERVENTION', 'cheap': True})['research']
    return app, project, repo, c


def bundle(c):
    return {'reasoning_summary': 'Fixture reasoning', 'reasoning_cycle': {k: 'Fixture ' + k for k in CYCLE_FIELDS},
            'candidates': [c]}


def run_fixture(intel, *, science=False, surprise=False):
    app, project, repo, c = intel
    c = copy.deepcopy(c)
    if science:
        # Test-only catalog marker exercises scientific interpretation. Never exported as real evidence.
        c['spec']['evidence_kind'] = 'SCIENTIFIC'
    if surprise:
        c['research']['prediction']['expected']['value']['range'] = [1, 2]
    validate_bundle(app, project, bundle(c))
    app.add('experiment', project, effective_spec(c))
    frozen = freeze_experiment(app, c['spec']['id'], repo)
    runs = Runs(app)
    rid = runs.create(c['spec']['id'])['id']
    runs.dispatch(rid)
    assert finish(runs, rid)['state'] == 'SUCCEEDED'
    after_run(app, rid)
    return rid, frozen


@pytest.mark.parametrize('relation', sorted(RELATIONS))
def test_graph_persists_typed_relationships(intel, relation):
    app, project, _, _ = intel
    edge = {'source': {'kind': 'hypothesis', 'id': 'H2'}, 'target': {'kind': 'question', 'id': 'Q1'},
            'relation': relation, 'reason': 'Fixture relation'}
    row = add_edge(app, project, edge)
    assert json.loads(row['data']) == edge
    assert add_edge(app, project, edge)['id'] == row['id']


@pytest.mark.parametrize('kind', sorted(HYPOTHESIS_TYPES))
def test_hypothesis_type_persists(intel, kind):
    app, project, _, _ = intel
    app.add('hypothesis', project, {'id': 'H-' + kind, 'hypothesis_type': kind,
        'statement': 'Typed fixture', 'falsification_condition': 'Negative control'})
    assert json.loads(app.store.get('hypotheses', 'H-' + kind)['data'])['hypothesis_type'] == kind


def test_dependencies_reject_cycles(intel):
    app, project, _, _ = intel
    edge = {'source': {'kind': 'hypothesis', 'id': 'H2'}, 'target': {'kind': 'hypothesis', 'id': 'H1'},
            'relation': 'DEPENDS_ON', 'reason': 'Premise'}
    add_edge(app, project, edge)
    with pytest.raises(ValueError, match='cycles'):
        add_edge(app, project, {**edge, 'source': edge['target'], 'target': edge['source']})


def test_competitors_and_outcome_interpretations(intel):
    app, project, _, c = intel
    c['research']['competing_hypotheses'] = ['H1']
    validate_bundle(app, project, bundle(c))
    assert set(c['possible_outcomes']) == {'SUPPORTED', 'FALSIFIED', 'INCONCLUSIVE', 'OPERATIONAL_FAILURE'}
    c['research']['competing_hypotheses'] = ['missing']
    with pytest.raises(ValueError):
        validate_bundle(app, project, bundle(c))


@pytest.mark.parametrize('mutation', ['cycle', 'prediction', 'type', 'mechanism', 'ordinal', 'challenger', 'cheap'])
def test_invalid_design_is_not_persisted(intel, mutation):
    app, project, _, c = intel
    b = bundle(c)
    if mutation == 'cycle':
        b.pop('reasoning_cycle')
    elif mutation == 'prediction':
        c['research']['prediction'].pop('falsification')
    elif mutation == 'type':
        c['hypothesis_ids'] = ['H1']
        c['spec']['hypothesis_id'] = 'H1'
    elif mutation == 'mechanism':
        c['research']['strategy'] = 'END_TO_END'
    elif mutation == 'ordinal':
        c['research']['value']['feasibility'] = .873421
    elif mutation == 'challenger':
        c['research']['central'] = True
        c['research']['challenger'] = None
    else:
        c['research']['cheap_falsification'] = False
    with pytest.raises(ValueError):
        import_proposals(app, project, b)
    assert not app.store.list('planner_proposals', project)


def test_blocking_uncertainty_enforced_outside_bounded_context(intel):
    app, project, _, c = intel
    add_uncertainty(app, project, {'id': 'U-block', 'question': 'Premise?', 'related_hypotheses': ['H1'],
        'importance': 'HIGH', 'why_it_matters': 'Must hold', 'blocks': [{'kind': 'hypothesis', 'id': 'H2'}]})
    assert 'U-block' in str(research_blockers(app, project, c, {}))
    app.add('experiment', project, effective_spec(c))
    with pytest.raises(ValueError, match='blocking uncertainty'):
        freeze_experiment(app, c['spec']['id'], intel[2])


def test_challenger_revise_and_debt_block(intel):
    app, project, _, c = intel
    c['research']['challenger']['verdict'] = 'REVISE'
    assert 'challenger' in str(research_blockers(app, project, c, {}))
    c['research']['challenger']['verdict'] = 'PASS'
    add_debt(app, project, {'kind': 'UNREPLICATED_CENTRAL_RESULT', 'severity': 'HIGH',
        'reason': 'Replicate first', 'hypothesis_ids': ['H2'], 'finding_ids': []})
    assert 'research debt' in str(research_blockers(app, project, c, {}))


def test_ordinal_value_and_record(intel):
    app, project, _, c = intel
    import_proposals(app, project, bundle(c))
    decision = plan(app, project)
    assert decision['selected']['score'] in {'HIGH', 'MEDIUM', 'LOW'}
    assert decision['reasoning_cycle'] == bundle(c)['reasoning_cycle']
    u = {'importance': 'HIGH'}
    assert ordinal_value(c, {**u, 'blocks': ['H']})['rank'] > ordinal_value(c, u)['rank']


@pytest.mark.parametrize(('measurement', 'outcome', 'expected'), [({'value': 8}, 'SUPPORTED', 'EXPECTED'),
    ({'value': 20}, 'SUPPORTED', 'SURPRISING'), ({'value': 0}, 'FALSIFIED', 'STRONGLY_CONTRADICTORY'),
    ({}, 'INCONCLUSIVE', 'PARTIALLY_EXPECTED')])
def test_surprise_does_not_rewrite_prediction(intel, measurement, outcome, expected):
    p = intel[3]['research']['prediction']
    before = protocol_digest(p)
    assert classify_surprise(p, measurement, outcome)['classification'] == expected
    assert protocol_digest(p) == before


def test_synthetic_findings_cannot_create_scientific_branch(intel):
    run_fixture(intel, surprise=True)
    app, project, _, _ = intel
    assert not app.store.list('intelligence_notes', project)
    assert not app.store.list('research_debt', project)
    assert 'NOT SCIENTIFIC EVIDENCE' in trajectory(app, project)


def test_scientific_interpretation_creates_uncertainty_once(intel):
    rid, _ = run_fixture(intel, science=True, surprise=True)
    app, project, _, _ = intel
    notes = app.store.list('intelligence_notes', project)
    assert len(notes) == 1
    note = json.loads(notes[0]['data'])
    assert note['interpretation']['classification'] == 'SURPRISING'
    assert app.store.get('uncertainties', note['new_uncertainty'])['status'] == 'OPEN'
    observe_finding(app, app.store.get('executions', rid), note['finding_id'])
    assert len(app.store.list('intelligence_notes', project)) == 1
    assert 'Prediction:' in journal(app, project)
    assert note['new_uncertainty'] in trajectory(app, project)
    frozen = json.loads(app.store.get('experiment_freezes', app.store.get('executions', rid)['freeze_id'])['data'])
    assert frozen['research_design']['prediction']['expected']['value']['range'] == [1, 2]


def test_prompted_adapter_uses_separate_challenger_call(intel):
    app, project, _, c = intel
    c['research']['central'] = True
    calls = []
    def provider(**kwargs):
        calls.append(kwargs)
        return bundle(c) if kwargs['role'] == 'planner' else c['research']['challenger']
    reasoner = PromptedReasoner(provider)
    decision = plan(app, project, reasoner)
    assert [a['role'] for a in calls] == ['planner', 'challenger']
    assert calls[0]['prompt'] != calls[1]['prompt']
    assert len(decision['reasoner_calls']) == 2


def test_real_pilot_requires_attributed_go(tmp_path):
    p = tmp_path / 'idea.md'
    p.write_text('---\nidea_id: I1\ndecision: pursue\n---\nGO is the next human decision.')
    assert inspect_go(tmp_path)['status'] == 'HUMAN_GATE_1_REQUIRED'
    p.write_text('---\nidea_id: I1\ndecision: GO\napproval:\n  actor: human\n  message: Explicit fixture approval\n---\n')
    result = inspect_go(tmp_path)
    assert result['status'] == 'PLANNING_ONLY' and not result['will_execute']


def test_offline_structural_cases_without_provider():
    result = evaluate_cases(Path(__file__).parents[1] / 'evaluations/research_planner_cases.json')
    assert result['passed'], result
    assert not result['external_model_used']
    c = next(c for c in result['cases'] if c['id'] == 'C')
    assert 'research debt' in str(c['policy_rejections'])


def test_question_cannot_change_envelope(intel):
    app, project, _, _ = intel
    with pytest.raises(ValueError, match='scope change'):
        set_question(app, project, {'id': 'Q2', 'question': 'A different problem',
                                   'motivation_hypotheses': [], 'oracle_hypotheses': []})


def test_branch_is_atomic_and_cannot_expand_budget(intel):
    run_fixture(intel, science=True, surprise=True)
    app, project, _, _ = intel
    finding = app.store.list('findings', project)[0]['id']
    proposal = {'finding_id': finding, 'state_digest': build_context(app, project)['research_state_digest'],
        'envelope_digest': Policy(app).current(project)[1], 'question_id': 'Q1', 'budget_delta': 0,
        'parent_hypothesis': 'H2', 'reason': 'Explain the in-scope range departure',
        'hypothesis': {'id': 'H3', 'statement': 'Fixture noise explains the departure',
            'falsification_condition': 'Departure persists under noise control', 'hypothesis_type': 'MECHANISM'},
        'uncertainty': {'id': 'U3', 'question': 'Is fixture noise responsible?', 'importance': 'HIGH',
                        'why_it_matters': 'Choose the appropriate control'}}
    for delta in [1, -1]:
        with pytest.raises(ValueError, match='scope/budget'):
            branch(app, project, {**proposal, 'budget_delta': delta})
    assert len(app.store.list('hypotheses', project)) == 2
    result = branch(app, project, proposal)
    assert not result['scope_changed'] and not result['budget_changed']
    with pytest.raises(ValueError, match='stale'):
        branch(app, project, proposal)


def test_claim_maturity_uses_mechanism_evidence_and_full_debt(intel):
    app, project, _, _ = intel
    app.add('claim', project, {'id': 'CL1', 'statement': 'Fixture mechanism', 'hypothesis_ids': ['H2'],
        'maturity_requirements': ['PRELIMINARY', 'MECHANISM_ISOLATED']})
    assert not claim_maturity(app, project)[0]['ready']
    run_fixture(intel, science=True)
    assert claim_maturity(app, project)[0]['ready']
    add_debt(app, project, {'kind': 'LITERATURE_CHECK_REQUIRED', 'severity': 'HIGH',
        'reason': 'Novelty unverified', 'hypothesis_ids': ['H2'], 'finding_ids': []})
    context = build_context(app, project)
    context['research_debt'] = []  # Deliberate model-context omission cannot bypass review.
    assert not research_review(app, project, context)['paper_ready']


def test_execution_rechecks_new_blockers_after_freeze(intel):
    app, project, repo, c = intel
    app.add('experiment', project, effective_spec(c))
    freeze_experiment(app, c['spec']['id'], repo)
    runs = Runs(app)
    rid = runs.create(c['spec']['id'])['id']
    add_debt(app, project, {'kind': 'LITERATURE_CHECK_REQUIRED', 'severity': 'HIGH',
        'reason': 'New prior-art question', 'hypothesis_ids': ['H2'], 'finding_ids': []})
    with pytest.raises(ValueError, match='research debt'):
        runs.create(c['spec']['id'])
    with pytest.raises(ValueError, match='research debt'):
        runs.dispatch(rid)


def test_empty_proposal_pool_stops_cleanly(intel):
    app, project, _, _ = intel
    decision = plan(app, project)
    assert decision['selected'] is None and decision['reasoning_cycle']


def test_supported_label_without_scientific_evidence_is_not_a_premise(intel):
    app, project, _, c = intel
    with app.store.connect() as db:
        db.execute("UPDATE hypothesis_states SET state='SUPPORTED' WHERE hypothesis_id='H1'")
    add_edge(app, project, {'source': {'kind': 'hypothesis', 'id': 'H2'},
        'target': {'kind': 'hypothesis', 'id': 'H1'}, 'relation': 'DEPENDS_ON', 'reason': 'Requires evidence'})
    assert 'upstream hypothesis not established' in str(research_blockers(app, project, c, {}))


def test_central_positive_creates_replication_debt_and_review(intel):
    app, project, _, c = intel
    c['research']['central'] = True
    run_fixture(intel, science=True)
    debt = app.store.list('research_debt', project)
    assert len(debt) == 1 and json.loads(debt[0]['data'])['kind'] == 'UNREPLICATED_CENTRAL_RESULT'
    review = research_review(app, project, build_context(app, project))
    assert not review['paper_ready'] and review['research_debt']


def test_gate_alias_binds_requested_action(intel, tmp_path):
    from researchos.controller import gate_summary, approve_gate
    app, project, _, _ = intel
    gate = gate_summary(app, project, 'Fixture human review')
    message = tmp_path / 'human-review.txt'
    message.write_text('APPROVE gate:REPLICATE ' + gate['digest'] + '\nSynthetic test receipt\n')
    result = approve_gate(app, gate['id'], gate['digest'], 'REPLICATE', message, 'fixture-human')
    assert result['action'] == 'CONTINUE'
    assert app.store.get('object_approvals', result['approval_id'])['kind'] == 'gate:REPLICATE'
