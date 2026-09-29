"""Choose one explainable candidate without freezing or dispatching anything."""
from __future__ import annotations

import json

from .policy import Policy, match_machine


def legacy_next(app, project):
    from .execution import Runs

    policy = Policy(app)
    try:
        envelope, _ = policy.current(project)
    except (ValueError, OSError) as exc:
        return {'project_id': project, 'candidate': None, 'requires_human_gate': True,
                'blockers': [str(exc)], 'will_execute': False}
    runs = Runs(app)
    candidates = []
    for row in app.store.list('experiments', project):
        spec = json.loads(row['data'])
        scope = policy.scope_blockers(envelope, spec)
        blockers = runs.dependency_blockers(spec, project)
        with app.store.connect() as db:
            completed = db.execute("SELECT 1 FROM executions WHERE experiment_id=? "
                                   "AND state IN ('SUCCEEDED','CREATED','PREPARING','DISPATCHED',"
                                   "'RUNNING','COLLECTING','LOST')", (row['id'],)).fetchone()
        if completed or 'hypothesis has already been falsified' in blockers:
            continue
        try:
            selected = match_machine(spec['resource_requirement'], app.store.list('machines'))
        except ValueError as exc:
            selected = None
            blockers.append(str(exc))
        with app.store.connect() as db:
            frozen = db.execute('SELECT 1 FROM experiment_freezes WHERE experiment_id=?',
                                (row['id'],)).fetchone()
        if frozen:
            blockers.extend(b for b in runs.readiness(row['id'])['blockers'] if b not in blockers)
        hypothesis = json.loads(app.store.get('hypotheses', spec['hypothesis_id'])['data'])
        candidate = {'experiment_id': row['id'], 'hypothesis_id': spec['hypothesis_id'],
                     'unresolved_uncertainty': hypothesis['statement'],
                     'information_value_reason': spec.get('information_value',
                        'Directly tests the stated hypothesis with predeclared criteria.'),
                     'priority': spec.get('priority', 100),
                     'estimated_runtime': spec.get('estimated_runtime'),
                     'gpu_hours_upper_bound': spec.get('budget', {}).get('gpu_hours'),
                     'required_capability': spec['resource_requirement'], 'selected_machine': selected,
                     'dependencies': spec.get('dependencies', []), 'prediction': spec['prediction'],
                     'success_condition': spec['success_condition'],
                     'falsification_condition': spec.get('falsification_condition', spec['failure_condition']),
                     'within_scope': not scope, 'requires_human_gate': bool(scope),
                     'blockers': scope + blockers, 'will_execute': False}
        candidates.append(candidate)
    if not candidates:
        return {'project_id': project, 'candidate': None, 'requires_human_gate': False,
                'reason': 'No eligible unresolved experiment; prepare an in-scope follow-up.',
                'will_execute': False}
    # Readiness first, then explicit scientific priority. No hidden learned scoring or giant queue.
    selected = min(candidates, key=lambda c: (bool(c['blockers']), c['requires_human_gate'],
                                              c['priority'], c['experiment_id']))
    state = app.store.get('projects', project)['state']
    if state != 'ACTIVE':
        selected['blockers'].append('project is ' + state)
        selected['requires_human_gate'] = state == 'SCOPE_CHANGE_REQUESTED'
    return {'project_id': project, 'candidate': selected,
            'requires_human_gate': selected['requires_human_gate'], 'will_execute': False}


def prepare_next(app, project):
    if app.store.list('uncertainties', project) or app.store.list('planner_proposals', project):
        from .planner import plan
        return plan(app, project)
    return legacy_next(app, project)
