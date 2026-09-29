"""Scientific reasoning contracts and policy. No execution or model-provider privileges."""
from __future__ import annotations

import json
import math

from autoresearch.contracts import protocol_digest
from autoresearch.io import utc_stamp

from .policy import Policy, strings
from .research_state import scientific
from .service import identifier, uid
from .store import encoded

HYPOTHESIS_TYPES = {'EXISTENCE', 'MECHANISM', 'CAUSAL', 'PERFORMANCE', 'BOUNDARY', 'GENERALIZATION'}
RELATIONS = {'SUPPORTS', 'CONTRADICTS', 'DEPENDS_ON', 'ALTERNATIVE_TO', 'EXPLAINS', 'REFINES'}
NODE_TABLES = {'question': 'research_questions', 'hypothesis': 'hypotheses', 'uncertainty': 'uncertainties',
               'experiment': 'experiments', 'finding': 'findings', 'claim': 'claims'}
STRATEGIES = {'MEASUREMENT', 'CONTROLLED_INTERVENTION', 'ORACLE', 'COUNTERFACTUAL', 'ABLATION',
              'STRESS_TEST', 'TRACE_ANALYSIS', 'MICROBENCHMARK', 'END_TO_END', 'REPLICATION'}
VALUE_FIELDS = {'decision_relevance', 'uncertainty_reduction', 'discrimination_power',
                'downstream_unlock_value', 'feasibility', 'compute_cost', 'implementation_cost', 'execution_risk'}
CYCLE_FIELDS = {'observe', 'current_belief', 'uncertain', 'competing_explanations',
                'change_our_mind', 'cheapest_decisive_experiment', 'predicted_outcomes'}
DEBTS = {'MISSING_BASELINE', 'UNREPLICATED_CENTRAL_RESULT', 'UNEXPLAINED_ANOMALY',
         'WORKLOAD_REALISM', 'WEAK_MOTIVATION', 'MISSING_SENSITIVITY', 'MEASUREMENT_INSTABILITY',
         'LITERATURE_CHECK_REQUIRED'}
MATURITY = {'MOTIVATION', 'PRELIMINARY', 'REPLICATED', 'MECHANISM_ISOLATED', 'BOUNDARY', 'END_TO_END'}


def text_fields(data, fields):
    for key in fields:
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(key + ' requires substantive text')


def active(app, project):
    return bool(app.store.list('research_questions', project))


def set_question(app, project, data):
    if not isinstance(data, dict) or set(data) != {'id', 'question', 'motivation_hypotheses', 'oracle_hypotheses'}:
        raise ValueError('invalid research question schema')
    identifier(data['id'])
    envelope, _ = Policy(app).current(project)
    if data['question'] != envelope['problem']:
        raise ValueError('core question must match the approved envelope; request scope change')
    for key in ('motivation_hypotheses', 'oracle_hypotheses'):
        for h in strings(data[key], key):
            app.same_project('hypotheses', h, project)
    with app.store.connect() as db:
        db.execute('INSERT INTO research_questions VALUES (?,?,?,?)',
                   (data['id'], project, encoded(data), utc_stamp()))
    return app.store.get('research_questions', data['id'])


def node(app, project, value):
    if not isinstance(value, dict) or set(value) != {'kind', 'id'} or value['kind'] not in NODE_TABLES:
        raise ValueError('invalid typed graph node')
    app.same_project(NODE_TABLES[value['kind']], value['id'], project)
    return value['kind'] + ':' + value['id']


def add_edge(app, project, data):
    if not isinstance(data, dict) or set(data) != {'source', 'target', 'relation', 'reason'}:
        raise ValueError('invalid question graph edge schema')
    source, target = node(app, project, data['source']), node(app, project, data['target'])
    text_fields(data, ('reason',))
    if data['relation'] not in RELATIONS or source == target:
        raise ValueError('invalid relation or self edge')
    if data['relation'] == 'DEPENDS_ON':
        edges = [json.loads(r['data']) for r in app.store.list('research_edges', project)]
        adjacency = {}
        for e in edges:
            if e['relation'] == 'DEPENDS_ON':
                a, b = e['source'], e['target']
                adjacency.setdefault(a['kind'] + ':' + a['id'], []).append(b['kind'] + ':' + b['id'])
        pending, visited = [target], set()
        while pending:
            current = pending.pop()
            if current == source:
                raise ValueError('dependency graph cannot contain cycles')
            if current not in visited:
                visited.add(current)
                pending.extend(adjacency.get(current, []))
    key = 'EDGE-' + protocol_digest({'project': project, **data})
    with app.store.connect() as db:
        db.execute('INSERT OR IGNORE INTO research_edges VALUES (?,?,?,?)', (key, project, encoded(data), utc_stamp()))
    return app.store.get('research_edges', key)


def add_debt(app, project, data, key=None):
    if not isinstance(data, dict) or set(data) != {'kind', 'severity', 'reason', 'hypothesis_ids', 'finding_ids'}:
        raise ValueError('invalid research debt schema')
    if data['kind'] not in DEBTS or data['severity'] not in {'HIGH', 'MEDIUM', 'LOW'}:
        raise ValueError('invalid debt kind/severity')
    text_fields(data, ('reason',))
    for field, table in [('hypothesis_ids', 'hypotheses'), ('finding_ids', 'findings')]:
        for value in strings(data[field], field):
            app.same_project(table, value, project)
    key = key or uid('DEBT')
    with app.store.connect() as db:
        db.execute('INSERT OR IGNORE INTO research_debt VALUES (?,?,?,?,?)',
                   (key, project, encoded(data), 'OPEN', utc_stamp()))
    return app.store.get('research_debt', key)


def validate_research(app, project, bundle, *, check_cycle=True):
    if not active(app, project):
        return
    cycle = bundle.get('reasoning_cycle')
    if check_cycle and (not isinstance(cycle, dict) or set(cycle) != CYCLE_FIELDS):
        raise ValueError('V0.3 requires the explicit research reasoning cycle')
    if check_cycle:
        text_fields(cycle, CYCLE_FIELDS)
    groups = {}
    for c in bundle['candidates']:
        r = c.get('research')
        if not isinstance(r, dict) or set(r) != {'strategy', 'cheap_falsification', 'falsification_exemption',
                'value', 'prediction', 'competing_hypotheses', 'central', 'challenger'}:
            raise ValueError('candidate requires a V0.3 research design')
        if r['strategy'] not in STRATEGIES or not isinstance(r['central'], bool) or not isinstance(r['cheap_falsification'], bool):
            raise ValueError('invalid research strategy or flags')
        if not isinstance(r['value'], dict) or set(r['value']) != VALUE_FIELDS or any(
                v not in {'HIGH', 'MEDIUM', 'LOW'} for v in r['value'].values()):
            raise ValueError('value components must be ordinal HIGH/MEDIUM/LOW')
        prediction = r['prediction']
        if not isinstance(prediction, dict) or set(prediction) != {'expected', 'mechanism', 'boundary', 'surprising_result', 'falsification'}:
            raise ValueError('prediction requires mechanism, boundary, surprise and falsification')
        text_fields(prediction, ('mechanism', 'boundary', 'surprising_result', 'falsification'))
        if not isinstance(prediction['expected'], dict) or not prediction['expected']:
            raise ValueError('prediction requires expected metric directions')
        for metric, expectation in prediction['expected'].items():
            if metric not in c['spec']['metrics'] or not isinstance(expectation, dict) or set(expectation) != {'direction', 'range'}:
                raise ValueError('prediction references undeclared metric or invalid expectation')
            if expectation['direction'] not in {'increase', 'decrease', 'unchanged'}:
                raise ValueError('invalid predicted direction')
            interval = expectation['range']
            if interval is not None and (not isinstance(interval, list) or len(interval) != 2 or
                    any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in interval)
                    or interval[0] > interval[1]):
                raise ValueError('prediction range must be finite ordered values or null')
        for h in strings(r['competing_hypotheses'], 'competing_hypotheses'):
            app.same_project('hypotheses', h, project)
        for h in c['hypothesis_ids']:
            ht = json.loads(app.same_project('hypotheses', h, project)['data']).get('hypothesis_type')
            if ht not in HYPOTHESIS_TYPES:
                raise ValueError('V0.3 requires typed hypotheses')
            if ht in {'MECHANISM', 'CAUSAL'} and r['strategy'] in {'END_TO_END', 'MICROBENCHMARK'}:
                raise ValueError('correlated performance alone does not test mechanism/causality')
        if c['experiment_type'] == 'ORACLE' and r['strategy'] != 'ORACLE':
            raise ValueError('ORACLE requires an explicit oracle strategy')
        if r['challenger'] is not None and not isinstance(r['challenger'], dict):
            raise ValueError('invalid challenger record')
        if r['central'] or c['experiment_type'] == 'PRIMARY':
            challenge = r['challenger']
            fields = {'prompt_role', 'alternative_explanation', 'confounder', 'strong_baseline',
                      'falsification_test', 'mechanism_measurement', 'verdict'}
            if not isinstance(challenge, dict) or set(challenge) != fields:
                raise ValueError('central experiment requires independently prompted challenger record')
            text_fields(challenge, fields)
            if challenge['prompt_role'] != 'challenger' or challenge['verdict'] not in {'PASS', 'REVISE'}:
                raise ValueError('invalid challenger role/verdict')
        groups.setdefault(c['uncertainty_id'], []).append(r)
    for group in groups.values() if check_cycle else ():
        if not any(r['cheap_falsification'] for r in group):
            if not all(isinstance(r['falsification_exemption'], str) and r['falsification_exemption'].strip() for r in group):
                raise ValueError('consider a cheap falsification candidate or explain why inappropriate')


def research_blockers(app, project, c, context):
    if not active(app, project):
        return []
    blockers = []
    targets = {('hypothesis', h) for h in c['hypothesis_ids']} | {('experiment', c['spec']['id'])}
    # Full durable graph/premises are checked even when the model context was truncated.
    for row in app.store.list('uncertainties', project):
        u = json.loads(row['data'])
        if row['status'] != 'RESOLVED' and row['id'] != c['uncertainty_id']:
            if any((n['kind'], n['id']) in targets for n in u.get('blocks', [])):
                blockers.append('blocking uncertainty: ' + row['id'])
    with app.store.connect() as db:
        states = {r['hypothesis_id']: r['state'] for r in db.execute(
            'SELECT s.* FROM hypothesis_states s JOIN hypotheses h ON h.id=s.hypothesis_id WHERE h.project_id=?', (project,))}
    established = {json.loads(r['data']).get('hypothesis_id') for r in app.store.list('findings', project)
                   if scientific(json.loads(r['data'])) and json.loads(r['data']).get('outcome') == 'SUPPORTED'}
    for h in c['hypothesis_ids']:
        if states.get(h) in {'FALSIFIED', 'BLOCKED'}:
            blockers.append('candidate targets a closed hypothesis branch: ' + h)
    dependencies = [json.loads(e['data']) for e in app.store.list('research_edges', project)]
    pending, visited = list(targets), set()
    while pending:
        target = pending.pop()
        if target in visited:
            continue
        visited.add(target)
        for e in dependencies:
            if e['relation'] == 'DEPENDS_ON' and (e['source']['kind'], e['source']['id']) == target:
                parent = e['target']
                if parent['kind'] == 'hypothesis' and (states.get(parent['id']) != 'SUPPORTED' or parent['id'] not in established):
                    blockers.append('upstream hypothesis not established: ' + parent['id'])
                if parent['kind'] == 'uncertainty' and app.store.get('uncertainties', parent['id'])['status'] != 'RESOLVED':
                    blockers.append('upstream uncertainty not resolved: ' + parent['id'])
                pending.append((parent['kind'], parent['id']))
    question = json.loads(app.store.list('research_questions', project)[0]['data'])
    complex_work = c['research']['value']['implementation_cost'] == 'HIGH' or c['mode'] == 'OPTIMIZATION'
    if complex_work:
        for h in question['motivation_hypotheses'] + question['oracle_hypotheses']:
            if states.get(h) != 'SUPPORTED' or h not in established:
                blockers.append('motivation/oracle opportunity not established: ' + h)
    if (c['research'].get('challenger') or {}).get('verdict') == 'REVISE':
        blockers.append('challenger requires revised experiment')
    for row in app.store.list('research_debt', project):
        d = json.loads(row['data'])
        if row['status'] == 'OPEN' and d['severity'] == 'HIGH' and (not d['hypothesis_ids'] or set(d['hypothesis_ids']) & set(c['hypothesis_ids'])):
            repair = {'UNREPLICATED_CENTRAL_RESULT': {'REPLICATION'}, 'UNEXPLAINED_ANOMALY': {'DISCRIMINATION', 'MECHANISM'},
                      'WEAK_MOTIVATION': {'MOTIVATION', 'ORACLE'}, 'MISSING_SENSITIVITY': {'SENSITIVITY', 'STRESS'},
                      'MISSING_BASELINE': {'DISCRIMINATION', 'PRIMARY'}, 'WORKLOAD_REALISM': {'MOTIVATION', 'STRESS'},
                      'MEASUREMENT_INSTABILITY': {'REPLICATION', 'DISCRIMINATION'}}
            if d['kind'] == 'LITERATURE_CHECK_REQUIRED' or c['experiment_type'] not in repair.get(d['kind'], set()):
                blockers.append('central research debt requires attention: ' + row['id'])
    return blockers


def ordinal_value(c, uncertainty):
    components = dict(c['research']['value'])
    upstream = bool(uncertainty.get('blocks'))
    urgency = uncertainty.get('decision_relevance', uncertainty['importance'])
    counts = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
    benefits = sum(counts[components[k]] for k in ('decision_relevance', 'uncertainty_reduction',
                                                  'discrimination_power', 'downstream_unlock_value', 'feasibility'))
    costs = sum(counts[components[k]] for k in ('compute_cost', 'implementation_cost', 'execution_risk'))
    margin = benefits - costs
    band = 'HIGH' if margin >= 8 else 'MEDIUM' if margin >= 4 else 'LOW'
    rank = (int(upstream), counts[urgency], counts[uncertainty.get('current_uncertainty', 'MEDIUM')],
            counts[uncertainty.get('risk_to_project', 'MEDIUM')], counts[band], int(c['research']['cheap_falsification']),
            counts[components['discrimination_power']], -counts[components['compute_cost']])
    return {'band': band, 'components': components, 'rank': rank, 'upstream': upstream,
            'explanation': 'Ordinal rubric: upstream blockers, decision relevance, benefit/cost band, then cheap falsification. Not calibrated information gain.'}


def classify_surprise(prediction, measurement, outcome):
    matches, missing = [], []
    for metric, expected in prediction['expected'].items():
        observed = measurement.get(metric)
        interval = expected['range']
        if interval is None or isinstance(observed, bool) or not isinstance(observed, (int, float)) or not math.isfinite(observed):
            missing.append(metric)
        else:
            matches.append(interval[0] <= observed <= interval[1])
    if matches and not any(matches) and outcome == 'FALSIFIED':
        label = 'STRONGLY_CONTRADICTORY'
    elif matches and not any(matches):
        label = 'SURPRISING'
    elif missing or not all(matches):
        label = 'PARTIALLY_EXPECTED'
    else:
        label = 'EXPECTED'
    return {'classification': label, 'unassessed_metrics': missing,
            'basis': 'Only defensible numeric ranges were compared; prose directions without baselines remain unassessed.'}


def observe_finding(app, run, finding_id):
    """Idempotent interpretation from frozen predictions, before the human maturity review."""
    if not active(app, run['project_id']):
        return
    project = run['project_id']
    note_id = 'INTERPRET-' + finding_id
    with app.store.connect() as db:
        if db.execute('SELECT 1 FROM intelligence_notes WHERE id=?', (note_id,)).fetchone():
            return
    finding = json.loads(app.store.get('findings', finding_id)['data'])
    spec = json.loads(app.store.get('experiment_freezes', run['freeze_id'])['data'])
    design = spec.get('research_design')
    if not design or not scientific(finding):
        return
    surprise = classify_surprise(design['prediction'], finding['measurement'], finding['outcome'])
    finding['surprise'] = surprise
    finding['unexpected'] = surprise['classification'] in {'SURPRISING', 'STRONGLY_CONTRADICTORY'}
    with app.store.connect() as db:
        db.execute('UPDATE findings SET data=? WHERE id=?', (encoded(finding), finding_id))
    new_uncertainty = None
    if finding['unexpected']:
        from .research_state import add_uncertainty
        new_uncertainty = 'U-surprise-' + finding_id
        with app.store.connect() as db:
            exists = db.execute('SELECT 1 FROM uncertainties WHERE id=?', (new_uncertainty,)).fetchone()
        if not exists:
            add_uncertainty(app, project, {'id': new_uncertainty,
                'question': 'Why did ' + finding_id + ' depart from its frozen expected metric ranges within the same experiment boundary?',
                'related_hypotheses': [spec['hypothesis_id']], 'importance': 'HIGH',
                'why_it_matters': 'Separate an in-scope alternative explanation from measurement instability.',
                'current_evidence': [finding_id], 'origin_finding': finding_id, 'status': 'OPEN'})
        add_debt(app, project, {'kind': 'UNEXPLAINED_ANOMALY', 'severity': 'HIGH',
            'reason': 'Unexpected range departure requires explanation; do not rewrite the prediction.',
            'hypothesis_ids': [spec['hypothesis_id']], 'finding_ids': [finding_id]}, 'DEBT-anomaly-' + finding_id)
    if design['central'] and finding['outcome'] == 'SUPPORTED':
        debt_id = 'DEBT-replication-' + spec['hypothesis_id']
        if finding['confidence'] == 'PRELIMINARY':
            add_debt(app, project, {'kind': 'UNREPLICATED_CENTRAL_RESULT', 'severity': 'HIGH',
                'reason': 'A central positive result needs independent confirmation.',
                'hypothesis_ids': [spec['hypothesis_id']], 'finding_ids': [finding_id]}, debt_id)
        elif finding['confidence'] in {'REPLICATED', 'ROBUST'}:
            with app.store.connect() as db:
                db.execute("UPDATE research_debt SET status='RESOLVED' WHERE id=?", (debt_id,))
    before = None
    with app.store.connect() as db:
        admission = db.execute('SELECT p.data FROM advance_runs a JOIN planner_decisions p ON p.id=a.decision_id WHERE a.run_id=?',
                               (run['id'],)).fetchone()
    if admission:
        before = json.loads(admission['data'])['context']['hypotheses']
    note = {'kind': 'RESULT_INTERPRETATION', 'run_id': run['id'], 'finding_id': finding_id,
            'question': spec.get('planning', {}).get('question'), 'belief_before': before,
            'critical_uncertainty': spec.get('planning', {}).get('uncertainty_id'),
            'experiment': spec['experiment_id'], 'prediction': design['prediction'],
            'observation': finding['measurement'], 'interpretation': surprise,
            'belief_after': finding['outcome'], 'new_uncertainty': new_uncertainty,
            'prediction_digest': protocol_digest(design['prediction'])}
    with app.store.connect() as db:
        db.execute('INSERT OR IGNORE INTO intelligence_notes VALUES (?,?,?,?,?)',
                   (note_id, project, finding_id, encoded(note), utc_stamp()))


def branch(app, project, data):
    """Admit one schema-checked sub-hypothesis/uncertainty under the unchanged envelope."""
    from .research_state import build_context
    allowed = {'finding_id', 'state_digest', 'envelope_digest', 'question_id', 'budget_delta',
               'parent_hypothesis', 'hypothesis', 'uncertainty', 'reason'}
    if not isinstance(data, dict) or set(data) != allowed:
        raise ValueError('invalid unexpected-result branch proposal')
    finding = json.loads(app.same_project('findings', data['finding_id'], project)['data'])
    if not scientific(finding):
        raise ValueError('synthetic/unverified results cannot branch scientific state')
    if finding.get('surprise', {}).get('classification') not in {'SURPRISING', 'STRONGLY_CONTRADICTORY'}:
        raise ValueError('unexpected-result branching requires a classified surprising finding')
    context = build_context(app, project)
    _, digest = Policy(app).current(project)
    question = app.store.list('research_questions', project)
    if (not question or data['question_id'] != question[0]['id'] or data['envelope_digest'] != digest
            or data['budget_delta'] != 0 or data['state_digest'] != context['research_state_digest']):
        raise ValueError('branch changes scope/budget or uses stale evidence; human scope review required')
    if context['project_state'] != 'ACTIVE':
        raise ValueError('project is not active')
    parent = json.loads(app.same_project('hypotheses', data['parent_hypothesis'], project)['data'])
    if finding.get('hypothesis_id') != data['parent_hypothesis']:
        raise ValueError('branch parent must be the observed hypothesis')
    text_fields(data, ('reason',))
    h, u = data['hypothesis'], data['uncertainty']
    if not isinstance(h, dict) or set(h) != {'id', 'statement', 'falsification_condition', 'hypothesis_type'}:
        raise ValueError('sub-hypothesis schema cannot import claims, approvals or execution instructions')
    identifier(h['id'])
    text_fields(h, ('statement', 'falsification_condition'))
    if h['hypothesis_type'] not in HYPOTHESIS_TYPES or h['statement'] == parent['statement']:
        raise ValueError('a branch must pose a distinct typed sub-hypothesis')
    if not isinstance(u, dict) or set(u) != {'id', 'question', 'importance', 'why_it_matters'}:
        raise ValueError('invalid branch uncertainty schema')
    identifier(u['id'])
    text_fields(u, ('question', 'why_it_matters'))
    if u['importance'] not in {'HIGH', 'MEDIUM', 'LOW'}:
        raise ValueError('invalid branch importance')
    u = {**u, 'related_hypotheses': [h['id']], 'current_evidence': [data['finding_id']],
         'origin_finding': data['finding_id'], 'status': 'OPEN'}
    edge = {'source': {'kind': 'hypothesis', 'id': h['id']},
            'target': {'kind': 'hypothesis', 'id': data['parent_hypothesis']}, 'relation': 'REFINES', 'reason': data['reason']}
    # Full validation precedes one transaction. No partial child remains after a rejected proposal.
    with app.store.connect() as db:
        db.execute('INSERT INTO hypotheses VALUES (?,?,?,?)', (h['id'], project, encoded(h), utc_stamp()))
        db.execute('INSERT INTO hypothesis_states VALUES (?,?,?,?)', (h['id'], 'PROPOSED', None, utc_stamp()))
        db.execute('INSERT INTO uncertainties VALUES (?,?,?,?,?)', (u['id'], project, encoded(u), 'OPEN', utc_stamp()))
        db.execute('INSERT INTO research_edges VALUES (?,?,?,?)', (uid('EDGE'), project, encoded(edge), utc_stamp()))
        db.execute('INSERT INTO intelligence_notes VALUES (?,?,?,?,?)',
                   (uid('BRANCH'), project, data['finding_id'], encoded({'kind': 'IN_SCOPE_BRANCH', **data}), utc_stamp()))
    return {'hypothesis_id': h['id'], 'uncertainty_id': u['id'], 'scope_changed': False, 'budget_changed': False}


def claim_maturity(app, project):
    assessments = [json.loads(r['data']) for r in app.store.list('research_assessments', project)]
    result = []
    for row in app.store.list('claims', project):
        claim = json.loads(row['data'])
        required_stages = claim.get('maturity_requirements', [])
        stages, evidence = set(), []
        for a in assessments:
            f = json.loads(app.store.get('findings', a['finding_id'])['data'])
            if not a['scientific'] or a['outcome'] != 'SUPPORTED':
                continue
            if row['id'] not in f.get('supports', []) and a['hypothesis_id'] not in claim.get('hypothesis_ids', []):
                continue
            evidence.append(a['finding_id'])
            stages.add('PRELIMINARY')
            if a['experiment_type'] == 'MOTIVATION':
                stages.add('MOTIVATION')
            if a['confidence'] in {'REPLICATED', 'ROBUST'}:
                stages.add('REPLICATED')
            run = app.store.get('executions', a['run_id'])
            design = json.loads(app.store.get('experiment_freezes', run['freeze_id'])['data']).get('research_design', {})
            if a['experiment_type'] in {'MECHANISM', 'DISCRIMINATION', 'ABLATION'} and design.get('strategy') in {'CONTROLLED_INTERVENTION', 'COUNTERFACTUAL', 'ABLATION'}:
                stages.add('MECHANISM_ISOLATED')
            if a['experiment_type'] in {'SENSITIVITY', 'STRESS'}:
                stages.add('BOUNDARY')
            if a['experiment_type'] == 'PRIMARY' and design.get('strategy') == 'END_TO_END':
                stages.add('END_TO_END')
        contradicted = any(a['scientific'] and a['outcome'] == 'FALSIFIED' and
                           (a['hypothesis_id'] in claim.get('hypothesis_ids', []) or row['id'] in
                            json.loads(app.store.get('findings', a['finding_id'])['data']).get('contradicts', [])) for a in assessments)
        result.append({'claim_id': row['id'], 'required': required_stages, 'established': sorted(stages),
                       'missing': sorted(set(required_stages) - stages), 'evidence': evidence,
                       'contradicted': contradicted,
                       'ready': bool(required_stages) and set(required_stages) <= stages and not contradicted})
    return result


def research_review(app, project, context):
    maturity = claim_maturity(app, project)
    debt = [{'id': r['id'], **json.loads(r['data'])} for r in app.store.list('research_debt', project) if r['status'] == 'OPEN']
    return {'original_beliefs': [json.loads(h['data']) for h in app.store.list('hypotheses', project)[:40]],
            'current_beliefs': context['hypotheses'], 'surprises': [f for f in context['findings'] if f.get('surprise')],
            'strongest_evidence': context['findings'], 'research_debt': debt, 'claim_maturity': maturity,
            'understanding_changes': context.get('recent_reasoning', []),
            'remaining_opportunity': context['uncertainties'], 'compute': context['budget'],
            'paper_ready': bool(maturity) and all(c['ready'] for c in maturity)
                           and not any(d['severity'] == 'HIGH' for d in debt),
            'available_actions': ['CONTINUE_EXPLORATION', 'FOCUS_MECHANISM', 'REPLICATE', 'EXPAND_EVALUATION',
                                  'STOP_PROJECT', 'REQUEST_SCOPE_CHANGE', 'FREEZE_STORY']}


def journal(app, project):
    lines = ['# Research journal', '', 'Derived from SQLite; this Markdown is not authoritative.', '']
    controllers = {json.loads(r['data']).get('run_id'): json.loads(r['data'])
                   for r in app.store.list('controller_decisions', project)}
    for i, row in enumerate(app.store.list('intelligence_notes', project), 1):
        data = json.loads(row['data'])
        lines += [f'## Iteration {i}', '']
        for key in ('question', 'belief_before', 'critical_uncertainty', 'experiment', 'prediction',
                    'observation', 'interpretation', 'belief_after', 'new_uncertainty'):
            lines += [key.replace('_', ' ').capitalize() + ': ' + encoded(data.get(key)), '']
        lines += ['Decision: ' + encoded(controllers.get(data.get('run_id'))), '']
    return '\n'.join(lines)


def trajectory(app, project):
    lines = ['# Research trajectory', '']
    with app.store.connect() as db:
        states = {r['hypothesis_id']: r['state'] for r in db.execute('SELECT * FROM hypothesis_states')}
    for row in app.store.list('hypotheses', project):
        lines.append(row['id'] + ' ' + states.get(row['id'], 'PROPOSED'))
        for f in app.store.list('findings', project):
            data = json.loads(f['data'])
            if data.get('hypothesis_id') == row['id']:
                label = data.get('outcome', 'UNVERIFIED') if scientific(data) else 'NOT SCIENTIFIC EVIDENCE'
                lines.append('  -> ' + f['experiment_id'] + ' -> ' + f['id'] + ' ' + label)
                for u in app.store.list('uncertainties', project):
                    if json.loads(u['data']).get('origin_finding') == f['id']:
                        lines.append('       -> ' + u['id'] + ' ' + u['status'])
    for row in app.store.list('research_edges', project):
        e = json.loads(row['data'])
        lines.append(e['source']['id'] + ' --' + e['relation'] + '--> ' + e['target']['id'])
    return '\n'.join(lines) + '\n'


def admit_design(app, project, spec):
    if not active(app, project):
        return
    from .research_state import build_context
    planning = spec.get('planning', {})
    if not {'hypothesis_ids', 'experiment_type', 'uncertainty_id', 'mode'} <= set(planning):
        raise ValueError('V0.3 execution requires a planned research design')
    hypotheses = strings(planning['hypothesis_ids'], 'hypothesis_ids')
    if spec['hypothesis_id'] not in hypotheses:
        raise ValueError('frozen hypothesis must match the research design')
    uncertainty = json.loads(app.same_project('uncertainties', planning['uncertainty_id'], project)['data'])
    if not set(hypotheses) <= set(uncertainty['related_hypotheses']):
        raise ValueError('research design must target the declared uncertainty')
    candidate = {**planning, 'spec': spec, 'research': spec.get('research_design')}
    validate_research(app, project, {'candidates': [candidate]}, check_cycle=False)
    blockers = research_blockers(app, project, candidate, build_context(app, project))
    if blockers:
        raise ValueError('; '.join(blockers))
