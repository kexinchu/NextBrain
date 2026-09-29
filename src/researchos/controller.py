"""Evidence maturity, independent replication, and explicit human decisions."""
from __future__ import annotations

import json
from pathlib import Path

from autoresearch.contracts import protocol_digest
from autoresearch.io import utc_stamp

from .policy import Policy
from .research_state import build_context, scientific
from .service import uid
from .store import encoded


def gate_summary(app, project, reason, suggested_action='CONTINUE'):
    context = build_context(app, project)
    digest = context['research_state_digest']
    with app.store.connect() as db:
        existing = db.execute('SELECT * FROM maturity_gates WHERE project_id=? AND state_digest=? '
                              'AND action IS NULL', (project, digest)).fetchone()
    if existing:
        return dict(existing)
    data = {'original_question': context['envelope']['problem'], 'reason': reason,
            'hypothesis_graph': context['hypotheses'], 'strongest_findings': context['findings'],
            'replication_status': [json.loads(r['data']) for r in app.store.list('research_assessments', project)[-40:]],
            'unexpected_results': [f for f in context['findings'] if f['unexpected']],
            'remaining_uncertainties': [u for u in context['uncertainties'] if u['status'] in {'OPEN', 'REDUCED'}],
            'compute': context['budget'], 'suggested_action': suggested_action,
            'threats_to_validity': list(dict.fromkeys(
                t for u in context['uncertainties'] for t in u.get('threats_to_validity', []))) or
                ['Replication coverage and workload representativeness need human review.'],
            'research_state_digest': digest}
    from .intelligence import active, research_review
    if active(app, project):
        data['research_review'] = research_review(app, project, context)
    record = {'id': uid('GATE2'), 'project_id': project, 'state_digest': digest,
              'digest': protocol_digest(data), 'data': encoded(data), 'action': None,
              'approval_id': None, 'created_at': utc_stamp()}
    with app.store.connect() as db:
        db.execute("UPDATE maturity_gates SET action='SUPERSEDED' WHERE project_id=? AND action IS NULL", (project,))
        db.execute('INSERT INTO maturity_gates VALUES (?,?,?,?,?,?,?,?)', tuple(record.values()))
    return record


def approve_gate(app, gate_id, digest, action, message_file, actor):
    aliases = {'CONTINUE_EXPLORATION': 'CONTINUE', 'FOCUS_MECHANISM': 'CONTINUE',
               'REPLICATE': 'CONTINUE', 'EXPAND_EVALUATION': 'CONTINUE',
               'STOP_PROJECT': 'STOP', 'REQUEST_SCOPE_CHANGE': 'PIVOT'}
    requested_action = action
    action = aliases.get(action, action)
    if action not in {'CONTINUE', 'PIVOT', 'STOP', 'FREEZE_STORY'}:
        raise ValueError('invalid Human Gate #2 action')
    row = app.store.get('maturity_gates', gate_id)
    if row['action'] or row['digest'] != digest or protocol_digest(json.loads(row['data'])) != digest:
        raise ValueError('gate is already decided or digest changed')
    current = build_context(app, row['project_id'])
    if current['research_state_digest'] != row['state_digest']:
        raise ValueError('gate evidence is stale; generate a fresh review')
    if action == 'FREEZE_STORY' and not any(
            h['state'] == 'SUPPORTED' and h['confidence'] in {'REPLICATED', 'ROBUST'}
            for h in current['hypotheses']):
        raise ValueError('FREEZE_STORY requires replicated scientific evidence')
    if action == 'FREEZE_STORY':
        from .intelligence import active, research_review
        if active(app, row['project_id']) and not research_review(app, row['project_id'], current)['paper_ready']:
            raise ValueError('claim-specific evidence maturity or research debt blocks paper readiness')
    receipt = Policy(app).approve(row['project_id'], 'gate:' + requested_action, digest, message_file, actor)
    with app.store.connect() as db:
        db.execute('UPDATE maturity_gates SET action=?,approval_id=? WHERE id=?', (action, receipt['id'], gate_id))
        if action == 'STOP':
            db.execute("UPDATE projects SET state='STOPPED' WHERE id=?", (row['project_id'],))
    if action == 'PIVOT':
        Policy(app).scope_request(row['project_id'], {'category': 'question',
            'reason': 'Human Gate #2 approved preparing a pivot',
            'proposed_change': 'Human must define and approve a revised envelope before execution.'})
    return app.store.get('maturity_gates', gate_id)


def require_story_gate(app, project):
    context = build_context(app, project)
    with app.store.connect() as db:
        row = db.execute("SELECT 1 FROM maturity_gates WHERE project_id=? AND action='FREEZE_STORY' "
                         'AND state_digest=? AND approval_id IS NOT NULL',
                         (project, context['research_state_digest'])).fetchone()
    if not row:
        raise ValueError('Human Gate #2 must explicitly approve FREEZE_STORY for current evidence')


def check_workspace_story_gate(workspace):
    marker = Path(workspace) / '.autoresearch' / 'researchos.json'
    if marker.exists():
        from .service import ResearchOS
        data = json.loads(marker.read_text())
        require_story_gate(ResearchOS(Path(data['catalog'])), data['project_id'])


def independent(app, run, original):
    old = app.store.get('executions', original)
    if old['project_id'] != run['project_id'] or old['state'] != 'SUCCEEDED':
        return []
    a = json.loads(app.store.get('experiment_freezes', old['freeze_id'])['data'])
    b = json.loads(app.store.get('experiment_freezes', run['freeze_id'])['data'])
    axes = []
    if old['machine_alias'] != run['machine_alias']:
        axes.append('machine')
    if a['command']['argv'] != b['command']['argv']:
        axes.append('command arguments (for example seed or workload slice)')
    if a['data']['hashes'] != b['data']['hashes']:
        axes.append('hashed input subset')
    # Time passing and declared seed metadata alone are deliberately insufficient.
    return axes


def after_run(app, run_id):
    run = app.store.get('executions', run_id)
    project = run['project_id']
    with app.store.connect() as db:
        previous = db.execute('SELECT data FROM controller_decisions WHERE id=?', ('CONTROL:' + run_id,)).fetchone()
        found = db.execute('SELECT f.* FROM findings_from_runs m JOIN findings f ON f.id=m.finding_id '
                           'WHERE m.run_id=?', (run_id,)).fetchone()
    if previous:
        return json.loads(previous['data'])
    action, reason, gate = 'CONTINUE', 'Operational failure changes no scientific belief.', None
    if found:
        finding = json.loads(found['data'])
        spec = json.loads(app.store.get('experiment_freezes', run['freeze_id'])['data'])
        planning = spec.get('planning', {})
        original = planning.get('replication_of')
        axes = independent(app, run, original) if original else []
        real = scientific(finding)
        confidence = 'PRELIMINARY' if real else 'SYSTEM_VALIDATION'
        envelope, _ = Policy(app).current(project)
        maturity = envelope.get('maturity_policy', {})
        minimum = maturity.get('independent_replications', 1)
        if isinstance(minimum, bool) or not isinstance(minimum, int) or not 1 <= minimum <= 5:
            raise ValueError('independent_replications must be an integer from 1 to 5')
        assessments = [json.loads(r['data']) for r in app.store.list('research_assessments', project)]
        related = [a for a in assessments if a['hypothesis_id'] == spec['hypothesis_id']
                   and a['scientific'] and a['finding_id'] != found['id']]
        positive = real and finding['outcome'] == 'SUPPORTED'
        original_finding = None
        if original:
            with app.store.connect() as db:
                source = db.execute('SELECT f.data FROM findings_from_runs m JOIN findings f ON f.id=m.finding_id '
                                    'WHERE m.run_id=?', (original,)).fetchone()
            original_finding = json.loads(source['data']) if source else None
        independent_positive = bool(positive and axes and original_finding and scientific(original_finding)
                                    and original_finding['outcome'] == 'SUPPORTED')
        fingerprint = protocol_digest({'machine': run['machine_alias'], 'argv': spec['command']['argv'],
                                       'inputs': spec['data']['hashes']})
        variants = {a.get('variation_fingerprint') for a in related if a['independent_positive']}
        if independent_positive:
            variants.add(fingerprint)
        independent_count = len(variants)
        if positive and independent_count >= minimum:
            confidence = 'REPLICATED'
            types = {a['experiment_type'] for a in related if a['outcome'] == 'SUPPORTED'} | {planning.get('experiment_type')}
            if (maturity.get('allow_robust', False) is True and 'SENSITIVITY' in types
                    and 'ABLATION' in types and spec['protocol'].get('baselines')):
                confidence = 'ROBUST'
        assessment = {'finding_id': found['id'], 'run_id': run_id, 'hypothesis_id': spec['hypothesis_id'],
                      'scientific': real, 'outcome': finding['outcome'], 'confidence': confidence,
                      'original_run': original, 'replication_runs': [run_id] if original else [],
                      'variation': axes, 'variation_fingerprint': fingerprint, 'independent_positive': independent_positive,
                      'experiment_type': planning.get('experiment_type'),
                      'interpretation': planning.get('possible_outcomes', {}).get(finding['outcome'])}
        finding['confidence_basis'] = finding.get('confidence_basis', finding.get('confidence'))
        finding['confidence'] = confidence
        finding['replication'] = {'original_run': original, 'replication_runs': [run_id] if original else [],
                                  'variation': axes, 'independent_positive': independent_positive}
        with app.store.connect() as db:
            db.execute('UPDATE findings SET data=? WHERE id=?', (encoded(finding), found['id']))
            if original_finding:
                lineage = original_finding.setdefault('replication', {'original_run': None, 'replication_runs': []})
                lineage['replication_runs'] = list(dict.fromkeys(lineage['replication_runs'] + [run_id]))
                db.execute('UPDATE findings SET data=? WHERE id=?',
                           (encoded(original_finding), original_finding['id']))
            db.execute('INSERT OR IGNORE INTO research_assessments VALUES (?,?,?,?)',
                       (found['id'], project, encoded(assessment), utc_stamp()))
            if real and planning.get('uncertainty_id'):
                uncertainty = db.execute('SELECT data FROM uncertainties WHERE id=?',
                                         (planning['uncertainty_id'],)).fetchone()
                if uncertainty:
                    udata = json.loads(uncertainty['data'])
                    udata['current_evidence'] = list(dict.fromkeys(udata.get('current_evidence', []) + [found['id']]))
                    db.execute('UPDATE uncertainties SET data=? WHERE id=?',
                               (encoded(udata), planning['uncertainty_id']))
                interpretation = planning['possible_outcomes'][finding['outcome']]
                db.execute('UPDATE uncertainties SET status=? WHERE id=? AND project_id=?',
                           (interpretation['uncertainty_status'], planning['uncertainty_id'], project))
                if positive and confidence == 'PRELIMINARY':
                    db.execute("UPDATE uncertainties SET status='REDUCED' WHERE id=?",
                               (planning['uncertainty_id'],))
        from .intelligence import observe_finding
        observe_finding(app, run, found['id'])
        if not real:
            reason = 'SYSTEM VALIDATION — NOT SCIENTIFIC EVIDENCE; scientific state unchanged.'
        elif finding['outcome'] == 'FALSIFIED':
            action, reason = 'STOP_HYPOTHESIS', 'Frozen scientific criteria falsified this hypothesis; other branches remain eligible.'
        elif positive and confidence == 'PRELIMINARY':
            action, reason = 'REPLICATE', 'Promising single result needs independent confirmation.'
        elif positive and confidence in {'REPLICATED', 'ROBUST'}:
            action, reason = 'ESCALATE_HUMAN', 'Replicated evidence merits Human Gate #2 maturity review.'
            gate = gate_summary(app, project, reason, 'FREEZE STORY')
        else:
            reason = 'Evidence is inconclusive; request a discriminating in-scope follow-up.'
    if app.store.get('projects', project)['state'] == 'STOPPED':
        action, reason = 'STOP_PROJECT', 'Explicit approved project stop policy triggered.'
        gate = gate_summary(app, project, reason, 'STOP')
    if app.store.get('projects', project)['state'] == 'SCOPE_CHANGE_REQUESTED':
        action, reason = 'ESCALATE_HUMAN', 'Project scope change requires a revised approval.'
        gate = gate_summary(app, project, reason, 'PIVOT')
    decision = {'id': 'CONTROL:' + run_id, 'project_id': project, 'run_id': run_id,
                'action': action, 'reason': reason, 'gate_id': gate['id'] if gate else None}
    with app.store.connect() as db:
        db.execute('INSERT OR IGNORE INTO controller_decisions VALUES (?,?,?,?)',
                   (decision['id'], project, encoded(decision), utc_stamp()))
    return decision
