"""Schema-validated research proposals, separate from deterministic admission and scoring."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from autoresearch.config import ResearchConfig
from autoresearch.io import utc_stamp

from .execution import Runs
from .freeze import validate_protocol
from .policy import Policy, match_machine, positive, strings
from .research_state import build_context, enable
from .service import identifier, required, uid
from .store import encoded

TYPES = {'MOTIVATION', 'FEASIBILITY', 'MECHANISM', 'DISCRIMINATION', 'PRIMARY',
         'REPLICATION', 'SENSITIVITY', 'ABLATION', 'STRESS'}
OUTCOMES = {'SUPPORTED', 'FALSIFIED', 'INCONCLUSIVE', 'OPERATIONAL_FAILURE'}


class ResearchReasoner(Protocol):
    def propose(self, context: dict) -> dict:
        """Return a small proposal bundle; never execute tools or modify the envelope."""


def validate_bundle(app, project, bundle):
    if not isinstance(bundle, dict) or set(bundle) != {'reasoning_summary', 'candidates'}:
        raise ValueError('planner output requires only reasoning_summary and candidates')
    if not isinstance(bundle['reasoning_summary'], str) or not bundle['reasoning_summary'].strip():
        raise ValueError('reasoning_summary is required')
    candidates = bundle['candidates']
    if not isinstance(candidates, list) or len(candidates) > 16:
        raise ValueError('candidate pool must be bounded to 16 (at most four per uncertainty)')
    seen, experiments, groups = set(), set(), {}
    for c in candidates:
        if not isinstance(c, dict) or set(c) != {
                'candidate_id', 'uncertainty_id', 'hypothesis_ids', 'question', 'experiment_type',
                'mode', 'expected_information', 'possible_outcomes', 'estimated_cost', 'risk',
                'discrimination_power', 'expected_information_gain', 'feasibility', 'spec', 'repo',
                'machine', 'replication_of'}:
            raise ValueError('invalid candidate schema or unknown planner field')
        required(c, ('candidate_id', 'uncertainty_id', 'question', 'expected_information', 'risk', 'repo'))
        identifier(c['candidate_id'])
        if c['candidate_id'] in seen:
            raise ValueError('duplicate candidate ID')
        seen.add(c['candidate_id'])
        groups[c['uncertainty_id']] = groups.get(c['uncertainty_id'], 0) + 1
        if groups[c['uncertainty_id']] > 4:
            raise ValueError('at most four candidates per uncertainty')
        for key in ('question', 'expected_information', 'risk', 'repo'):
            if not isinstance(c[key], str):
                raise ValueError(key + ' must be text')
        u = json.loads(app.same_project('uncertainties', c['uncertainty_id'], project)['data'])
        if c['experiment_type'] not in TYPES or c['mode'] not in {'EXPLORATION', 'OPTIMIZATION'}:
            raise ValueError('invalid experiment type or research mode')
        hypotheses = strings(c['hypothesis_ids'], 'hypothesis_ids')
        if not hypotheses or not set(hypotheses).issubset(u['related_hypotheses']):
            raise ValueError('candidate hypotheses must relate to its uncertainty')
        for h in hypotheses:
            app.same_project('hypotheses', h, project)
        outcomes = c['possible_outcomes']
        if not isinstance(outcomes, dict) or set(outcomes) != OUTCOMES:
            raise ValueError('possible_outcomes must interpret all scientific and operational outcomes')
        for outcome, interpretation in outcomes.items():
            if not isinstance(interpretation, dict) or set(interpretation) != {'interpretation', 'uncertainty_status'}:
                raise ValueError('invalid possible-outcome interpretation')
            if not isinstance(interpretation['interpretation'], str) or not interpretation['interpretation'].strip():
                raise ValueError('outcome interpretation must be text')
            allowed = {'UNCHANGED'} if outcome == 'OPERATIONAL_FAILURE' else {'REDUCED', 'RESOLVED', 'OPEN'}
            if interpretation['uncertainty_status'] not in allowed:
                raise ValueError('operational failure cannot alter scientific uncertainty')
        for key in ('discrimination_power', 'expected_information_gain', 'feasibility'):
            if not 0 < positive(c[key], key) <= 1:
                raise ValueError('heuristic components must be in (0,1]')
        positive(c['estimated_cost'], 'estimated_cost')
        spec = c['spec']
        if not isinstance(spec, dict):
            raise ValueError('candidate requires an experiment specification')
        required(spec, ('id', 'hypothesis_id', 'prediction', 'metrics', 'success_condition',
                        'falsification_condition', 'expected_artifacts', 'estimated_runtime',
                        'command_name', 'experiment_class', 'evidence_kind'))
        identifier(spec['id'])
        if spec['id'] in experiments:
            raise ValueError('candidate experiment IDs must be unique')
        experiments.add(spec['id'])
        if spec['hypothesis_id'] not in hypotheses or 'command' in spec:
            raise ValueError('invalid experiment hypothesis or raw command')
        if spec['evidence_kind'] not in {'SCIENTIFIC', 'SYSTEM_VALIDATION'}:
            raise ValueError('explicit evidence_kind required')
        validate_protocol(spec)
        for dep in strings(spec.get('dependencies', []), 'dependencies'):
            app.same_project('experiments', dep, project)
        if not Path(c['repo']).is_absolute():
            raise ValueError('repo must be an absolute local path')
        if c['machine'] is not None and not isinstance(c['machine'], str):
            raise ValueError('machine must be an alias or null')
        if c['replication_of']:
            original = app.same_project('executions', c['replication_of'], project)
            old = json.loads(app.store.get('experiment_freezes', original['freeze_id'])['data'])
            if (c['experiment_type'] != 'REPLICATION' or original['state'] != 'SUCCEEDED'
                    or old['hypothesis_id'] != spec['hypothesis_id']
                    or old['protocol']['rules'] != spec['protocol']['rules']
                    or old.get('evidence_kind', 'SCIENTIFIC') != spec['evidence_kind']):
                raise ValueError('replication must confirm the same hypothesis and frozen criteria')
        elif c['experiment_type'] == 'REPLICATION':
            raise ValueError('replication requires original_run')
    # JSON round trip prevents adapters from retaining mutable aliases; rejects NaN.
    return json.loads(encoded(bundle))


def import_proposals(app, project, bundle):
    bundle = validate_bundle(app, project, bundle)
    record = {'id': uid('PROPOSAL'), 'project_id': project, 'data': encoded(bundle), 'created_at': utc_stamp()}
    with app.store.connect() as db:
        db.execute('INSERT INTO planner_proposals VALUES (?,?,?,?)', tuple(record.values()))
    enable(app, project)
    return record


class StoredReasoner:
    """Curated agent/human research reasoning; each round reevaluates a pool, never a queue."""
    def __init__(self, app, project):
        self.app, self.project = app, project

    def propose(self, context):
        rows = self.app.store.list('planner_proposals', self.project)
        if not rows:
            return {'reasoning_summary': 'No research proposals supplied; request a bounded proposal bundle.',
                    'candidates': []}
        return json.loads(rows[-1]['data'])


def effective_spec(candidate):
    return {**candidate['spec'], 'planning': {k: candidate[k] for k in
            ('candidate_id', 'uncertainty_id', 'hypothesis_ids', 'question', 'mode', 'experiment_type',
             'possible_outcomes', 'expected_information', 'replication_of')}}


def candidate_check(app, project, candidate, context):
    spec = effective_spec(candidate)
    policy, runs = Policy(app), Runs(app)
    scope = policy.scope_blockers(context['envelope'], spec)
    blockers = scope + runs.dependency_blockers(spec, project)
    if context['project_state'] != 'ACTIVE':
        blockers.append('project is not ACTIVE')
    with app.store.connect() as db:
        pending = db.execute('SELECT 1 FROM maturity_gates WHERE project_id=? AND action IS NULL',
                             (project,)).fetchone()
        if pending:
            blockers.append('Human Gate #2 approval pending')
        paper = db.execute("SELECT action FROM maturity_gates WHERE project_id=? ORDER BY rowid DESC LIMIT 1",
                           (project,)).fetchone()
        if paper and paper['action'] == 'FREEZE_STORY':
            blockers.append('Human Gate #2 authorized the downstream paper workflow')
        existing = db.execute('SELECT data FROM experiments WHERE id=?', (spec['id'],)).fetchone()
        attempted = db.execute('SELECT 1 FROM executions WHERE experiment_id=?', (spec['id'],)).fetchone()
    if attempted:
        blockers.append('experiment already attempted; recover existing run or revise proposal')
    if existing:
        normalized = {**spec, 'failure_condition': spec['falsification_condition']}
        if json.loads(existing['data']) != normalized:
            blockers.append('experiment ID already binds a different specification')
    machine = None
    try:
        command = ResearchConfig(app.workspace(project)).command(spec['command_name'], 'experiment-loop')
        if command.timeout < spec['timeout']:
            blockers.append('timeout exceeds command authorization')
        rows = app.store.list('machines')
        if candidate['machine']:
            rows = [r for r in rows if r['id'] == candidate['machine']]
        machine = match_machine(spec['resource_requirement'], rows)
        attempts = spec['budget'].get('max_retries', 0) + 1
        gpu = len(machine['gpu_indices']) * spec['timeout'] / 3600 * attempts
        cpu = spec['timeout'] / 3600 * attempts if not gpu else 0
        if any(v > context['budget']['remaining'][k] + 1e-12 for k, v in [('gpu_hours', gpu), ('cpu_hours', cpu)]):
            blockers.append('project compute budget exhausted')
    except ValueError as exc:
        blockers.append(str(exc))
    established = any(h['state'] == 'SUPPORTED' and h['confidence'] in {'REPLICATED', 'ROBUST'}
                      for h in context['hypotheses'])
    if candidate['mode'] == 'OPTIMIZATION' and not established:
        blockers.append('explore the mechanism before optimization')
    if any(h['state'] in {'FALSIFIED', 'BLOCKED'} and h['id'] in candidate['hypothesis_ids']
           for h in context['hypotheses']):
        blockers.append('candidate targets a closed hypothesis branch')
    return {'blockers': blockers, 'within_scope': not scope, 'machine': machine}


def plan(app, project, reasoner=None):
    Runs(app)  # Ensure the known local capability exists before computing a state digest.
    context = build_context(app, project)
    reasoner = reasoner or StoredReasoner(app, project)
    bundle = validate_bundle(app, project, reasoner.propose(context))
    if build_context(app, project)['research_state_digest'] != context['research_state_digest']:
        raise ValueError('research state changed during planning; re-plan')
    uncertainties = {u['id']: u for u in context['uncertainties'] if u['status'] in {'OPEN', 'REDUCED'}}
    scores = []
    for c in bundle['candidates']:
        if c['uncertainty_id'] not in uncertainties:
            continue
        check = candidate_check(app, project, c, context)
        u = uncertainties[c['uncertainty_id']]
        components = {'importance': {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}[u['importance']],
                      **{k: c[k] for k in ('discrimination_power', 'expected_information_gain', 'feasibility')},
                      'normalized_cost': max(c['estimated_cost'], c['spec']['timeout'] / 60
                          * max(1, c['spec']['resource_requirement'].get('gpu_count', 0))
                          * (c['spec']['budget'].get('max_retries', 0) + 1)),
                      'type_weight': 1.2 if c['experiment_type'] in {'MECHANISM', 'DISCRIMINATION', 'REPLICATION'} else 1}
        score = (components['importance'] * components['discrimination_power'] *
                 components['expected_information_gain'] * components['feasibility'] *
                 components['type_weight'] / components['normalized_cost'])
        scores.append({'candidate': c, 'score': score, 'components': components, **check})
    ready = [s for s in scores if not s['blockers']]
    selected = max(ready, key=lambda s: (s['score'], s['candidate']['candidate_id'])) if ready else None
    # Only expose the small competing set for the selected uncertainty; retain rejected scores in audit.
    uncertainty = selected['candidate']['uncertainty_id'] if selected else None
    decision = {'project_id': project, 'research_state_digest': context['research_state_digest'],
                'context': context, 'selected_uncertainty': uncertainty,
                'candidate_experiments': [s['candidate']['candidate_id'] for s in scores
                                          if s['candidate']['uncertainty_id'] == uncertainty],
                'selected_experiment': selected['candidate']['spec']['id'] if selected else None,
                'selected': selected, 'selection_scores': scores,
                'reasoning_summary': bundle['reasoning_summary'],
                'selection_explanation': 'Heuristic information/discrimination per conservative runtime cost; not a probability.',
                'rejected_candidates': [{'candidate_id': s['candidate']['candidate_id'],
                    'reason': s['blockers'] or ['Lower information/cost score']} for s in scores if s is not selected],
                'scope_check': all(s['within_scope'] for s in scores),
                'budget_snapshot': context['budget'], 'will_execute': False,
                'ready': selected is not None, 'created_at': utc_stamp()}
    decision['id'] = uid('PLAN')
    with app.store.connect() as db:
        db.execute('INSERT INTO planner_decisions VALUES (?,?,?,?,?)',
                   (decision['id'], project, context['research_state_digest'], encoded(decision), decision['created_at']))
    return decision


def assert_fresh(app, decision):
    current = build_context(app, decision['project_id'])['research_state_digest']
    with app.store.connect() as db:
        pending = db.execute('SELECT 1 FROM maturity_gates WHERE project_id=? AND action IS NULL',
                             (decision['project_id'],)).fetchone()
    if pending:
        raise ValueError('Human Gate #2 approval pending')
    if current != decision['research_state_digest']:
        raise ValueError('stale planner decision; re-plan against current durable state')
