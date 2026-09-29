"""Bounded, evidence-derived research context. No conversation history is authoritative."""
from __future__ import annotations

import json
from collections import Counter

from autoresearch.contracts import protocol_digest
from autoresearch.io import sha256_file, utc_stamp, write_json

from .policy import Policy, strings
from .service import identifier, required
from .store import encoded

HYPOTHESIS_STATES = {'PROPOSED', 'ACTIVE', 'SUPPORTED', 'FALSIFIED', 'INCONCLUSIVE', 'BLOCKED'}
UNCERTAINTY_STATES = {'OPEN', 'REDUCED', 'RESOLVED', 'BLOCKED'}


def enable(app, project):
    # This marker makes the downstream paper freeze guard consult the catalog gate.
    write_json(app.workspace(project) / '.autoresearch' / 'researchos.json',
               {'catalog': str(app.root), 'project_id': project})


def add_uncertainty(app, project, data):
    if not isinstance(data, dict) or set(data) - {
            'id', 'question', 'related_hypotheses', 'importance', 'current_evidence', 'status',
            'why_it_matters', 'threats_to_validity'}:
        raise ValueError('invalid uncertainty schema')
    required(data, ('id', 'question', 'related_hypotheses', 'importance', 'why_it_matters'))
    identifier(data['id'])
    if not all(isinstance(data[k], str) and data[k].strip() for k in ('question', 'why_it_matters')):
        raise ValueError('uncertainty question and explanation must be text')
    if data['importance'] not in {'HIGH', 'MEDIUM', 'LOW'}:
        raise ValueError('invalid uncertainty importance')
    hypotheses = strings(data['related_hypotheses'], 'related_hypotheses')
    if not hypotheses:
        raise ValueError('uncertainty requires hypotheses')
    for h in hypotheses:
        app.same_project('hypotheses', h, project)
    for f in strings(data.get('current_evidence', []), 'current_evidence'):
        app.same_project('findings', f, project)
    state = data.get('status', 'OPEN')
    if state not in UNCERTAINTY_STATES:
        raise ValueError('invalid uncertainty status')
    with app.store.connect() as db:
        db.execute('INSERT INTO uncertainties VALUES (?,?,?,?,?)',
                   (data['id'], project, encoded(data), state, utc_stamp()))
    enable(app, project)
    return app.store.get('uncertainties', data['id'])


def scientific(finding):
    return (finding.get('verification') == 'EXECUTOR_VERIFIED'
            and finding.get('evidence_kind', 'SCIENTIFIC') == 'SCIENTIFIC')


def build_context(app, project, limit=80):
    envelope, envelope_digest = Policy(app).current(project)
    tables = ('hypotheses', 'claims', 'experiments', 'executions', 'findings', 'uncertainties',
              'research_assessments', 'planner_proposals', 'scope_requests', 'object_approvals')
    rows = {table: app.store.list(table, project) for table in tables}
    rows['object_approvals'] = [r for r in rows['object_approvals'] if not r['kind'].startswith('gate:')]
    machines = app.store.list('machines')
    project_row = app.store.get('projects', project)
    with app.store.connect() as db:
        states = {r['hypothesis_id']: dict(r) for r in db.execute(
            'SELECT s.* FROM hypothesis_states s JOIN hypotheses h ON h.id=s.hypothesis_id '
            'WHERE h.project_id=?', (project,))}
    config = app.workspace(project) / 'autoresearch.yaml'
    # Full-state digest includes omitted records, approvals, authorizations and operational state.
    digest = protocol_digest({'rows': rows, 'machines': machines, 'project': project_row,
                              'hypothesis_states': states, 'envelope': envelope_digest,
                              'source_revision': app.store.get('ideas', project_row['idea_id'])['current_revision'],
                              'command_config': sha256_file(config) if config.exists() else None})
    findings = [json.loads(r['data']) for r in rows['findings']]
    assessments = {r['id']: json.loads(r['data']) for r in rows['research_assessments']}
    hypotheses = []
    for row in rows['hypotheses']:
        h = json.loads(row['data'])
        relevant = [f for f in findings if f.get('hypothesis_id') == row['id'] and scientific(f)]
        positive = [f['id'] for f in relevant if f.get('outcome') == 'SUPPORTED']
        negative = [f['id'] for f in relevant if f.get('outcome') == 'FALSIFIED']
        confidence = 'PRELIMINARY'
        levels = {'PRELIMINARY': 0, 'REPLICATED': 1, 'ROBUST': 2}
        if positive:
            confidence = max((assessments.get(f, {}).get('confidence', 'PRELIMINARY')
                              for f in positive), key=lambda v: levels.get(v, 0))
        state = states.get(row['id'], {}).get('state', h.get('state', 'PROPOSED'))
        if state not in HYPOTHESIS_STATES:
            state = 'PROPOSED'
        # A contradiction cannot be erased by a later positive result.
        if negative:
            state = 'FALSIFIED'
        hypotheses.append({'id': row['id'], 'statement': h['statement'], 'state': state,
                           'critical': h.get('critical', False), 'confidence': confidence,
                           'supporting_findings': positive[-limit:], 'contradicting_findings': negative[-limit:],
                           'evidence_counts': dict(Counter(f.get('outcome') for f in relevant)),
                           'open_uncertainties': [r['id'] for r in rows['uncertainties']
                              if r['status'] in {'OPEN', 'REDUCED'} and row['id'] in
                              json.loads(r['data'])['related_hypotheses']]})
    reserved = {key: sum(r['reserved_' + key] for r in rows['executions'])
                for key in ('gpu_hours', 'cpu_hours')}
    context = {'project_id': project, 'project_state': project_row['state'],
               'research_state_digest': digest, 'envelope': envelope,
               'hypotheses': hypotheses[:limit], 'hypothesis_counts': dict(Counter(h['state'] for h in hypotheses)),
               'uncertainties': [{**json.loads(r['data']), 'status': r['status']}
                                 for r in rows['uncertainties'][:limit]],
               'findings': [{k: f.get(k) for k in ('id', 'hypothesis_id', 'experiment_id', 'outcome',
                            'measurement', 'inference', 'unexpected', 'verification', 'evidence_kind')}
                            for f in findings[-limit:]],
               'claims': [json.loads(r['data']) for r in rows['claims'][:limit]],
               'experiments': [{'id': r['id'], 'hypothesis_id': r['hypothesis_id'],
                    'dependencies': json.loads(r['data']).get('dependencies', [])}
                    for r in rows['experiments'][-limit:]],
               'completed_experiments': [r['experiment_id'] for r in rows['executions']
                                         if r['state'] == 'SUCCEEDED'][-limit:],
               'operational_failures': [{k: r[k] for k in ('id', 'experiment_id', 'state', 'failure')}
                    for r in rows['executions'] if r['state'] in
                    {'FAILED_RETRYABLE', 'FAILED_FINAL', 'TIMED_OUT', 'CANCELLED', 'LOST'}][-limit:],
               'machines': [{'id': r['id'], **json.loads(r['data'])} for r in machines[:limit]],
               'budget': {'reserved': reserved, 'remaining': {k: max(0, envelope['resource_budget'].get(k, 0) - v)
                                                             for k, v in reserved.items()},
                          'accounting': 'Conservative reservations; not measured compute consumption'},
               'truncated': {k: len(v) - limit for k, v in rows.items() if len(v) > limit}}
    # Hard prompt size cap: never silently feed an unbounded database to a reasoner.
    if len(encoded(context).encode()) > 65536:
        if limit > 5:
            return build_context(app, project, limit // 2)
        raise ValueError('research context exceeds 64 KiB; human curation required')
    return context
