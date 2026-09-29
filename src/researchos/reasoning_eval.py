"""Offline structural reasoning evaluation. Disposable fixture catalogs; no execution or LLM calls."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from autoresearch.contracts import protocol_digest
from autoresearch.io import utc_stamp
from .intelligence import (CYCLE_FIELDS, add_debt, add_edge, set_question, classify_surprise, observe_finding)
from .planner import plan, import_proposals, validate_bundle
from .policy import Policy
from .research_state import add_uncertainty
from .service import ResearchOS
from .store import encoded


def fixture_candidate(root, item):
    spec = {'id': item['id'], 'hypothesis_id': item['hypothesis'], 'experiment_class': 'offline-fixture',
            'evidence_kind': 'SYSTEM_VALIDATION', 'prediction': {'value': {'min': 5, 'max': 10}},
            'metrics': ['value'], 'success_condition': 'value >= 5', 'falsification_condition': 'value < 5',
            'expected_artifacts': ['metrics.json'], 'resource_requirement': {'gpu_required': False, 'gpu_count': 0, 'cpu_only': True},
            'environment_requirement': {'python_min': '3.10'}, 'timeout': 3,
            'budget': {'cpu_hours': .01, 'gpu_hours': 0, 'max_retries': 0}, 'data': {'identifiers': [], 'hashes': {}},
            'command_name': 'fixture', 'estimated_runtime': '3s', 'dependencies': [],
            'protocol': {'metric_file': 'metrics.json', 'baselines': [], 'rules': [
                {'metric': 'value', 'success': {'op': '>=', 'value': 5}, 'falsification': {'op': '<', 'value': 5}}]}}
    return {'candidate_id': 'C-' + item['id'], 'uncertainty_id': item['uncertainty'],
            'hypothesis_ids': [item['hypothesis']], 'question': 'Offline policy fixture question',
            'experiment_type': item['type'], 'mode': item.get('mode', 'EXPLORATION'),
            'expected_information': 'Structural policy behavior only', 'risk': 'No execution permitted in evaluator',
            'possible_outcomes': {k: {'interpretation': 'Fixture interpretation: ' + k,
                'uncertainty_status': 'UNCHANGED' if k == 'OPERATIONAL_FAILURE' else 'REDUCED'}
                for k in ('SUPPORTED', 'FALSIFIED', 'INCONCLUSIVE', 'OPERATIONAL_FAILURE')},
            'estimated_cost': 1, 'discrimination_power': 1, 'expected_information_gain': 1, 'feasibility': 1,
            'spec': spec, 'repo': str(root), 'machine': None,
            'replication_of': 'R-fixture' if item['type'] == 'REPLICATION' else None,
            'research': {'strategy': item['strategy'], 'central': item['type'] == 'PRIMARY',
                'cheap_falsification': item['cheap'], 'falsification_exemption': '',
                'competing_hypotheses': item.get('competing', []),
                'value': {'decision_relevance': 'HIGH', 'uncertainty_reduction': 'HIGH',
                    'discrimination_power': 'HIGH', 'downstream_unlock_value': 'HIGH', 'feasibility': 'HIGH',
                    'compute_cost': 'LOW', 'implementation_cost': item.get('cost', 'LOW'), 'execution_risk': 'LOW'},
                'prediction': {'expected': {'value': {'direction': 'increase', 'range': [5, 10]}},
                    'mechanism': 'Fixture only: compare predicted value with an observed value',
                    'boundary': 'Disposable simulated state, not a real hypothesis',
                    'surprising_result': 'Value outside the declared interval', 'falsification': 'Value below five'},
                'challenger': {'prompt_role': 'challenger', 'alternative_explanation': 'Measurement noise',
                    'confounder': 'Batch composition', 'strong_baseline': 'Existing authorized control',
                    'falsification_test': 'Cheap negative control', 'mechanism_measurement': 'Direct intervention', 'verdict': 'PASS'}}}


def evaluate_case(case):
    # Simulated belief states are isolated from the user's catalog, not certified experimental evidence.
    with TemporaryDirectory(prefix='researchos-offline-eval-') as directory:
        root = Path(directory)
        plans = root / 'plans'
        plans.mkdir()
        (plans / 'case.md').write_text('---\nidea_id: EVAL\ntitle: Offline fixture\n---\nNOT SCIENTIFIC EVIDENCE\n')
        app = ResearchOS(root / 'catalog')
        app.scan(plans)
        project = app.decide('EVAL', 'GO', 'offline-fixture', 'Simulated evaluation state only')['id']
        envelope = {'schema_version': 1, 'project_id': project, 'problem': case['research_state'],
                    'boundary': 'Offline simulated fixture', 'resource_budget': {'cpu_hours': 1, 'gpu_hours': 0},
                    'allowed_experiment_classes': ['offline-fixture'], 'allowed_baselines': [],
                    'non_goals': ['Scientific claims', 'Execution'], 'stop_conditions': ['No execution']}
        path = app.workspace(project)
        (path / 'PROJECT_ENVELOPE.md').write_text('---\n' + yaml.safe_dump(envelope) + '---\n')
        digest = Policy(app).envelope_draft(project)[1]
        approval = root / 'fixture-approval'
        approval.write_text('APPROVE envelope ' + digest + '\nOFFLINE FIXTURE ONLY\n')
        Policy(app).approve_envelope(project, digest, approval, 'offline-fixture')
        (path / 'autoresearch.yaml').write_text(yaml.safe_dump({'version': 1, 'commands': {
            'fixture': {'skill': 'experiment-loop', 'argv': ['python3', 'nonexistent-do-not-execute.py'], 'timeout': 3}}}))
        for h in case['hypotheses']:
            app.add('hypothesis', project, {'id': h['id'], 'statement': 'SIMULATED ' + h['id'],
                'hypothesis_type': h['type'], 'state': h['state'], 'falsification_condition': 'Fixture comparison fails'})
        set_question(app, project, {'id': 'Q1', 'question': case['research_state'],
                                   'motivation_hypotheses': case['motivation'], 'oracle_hypotheses': case['oracle']})
        for u in case['uncertainties']:
            add_uncertainty(app, project, {'id': u['id'], 'question': 'Fixture uncertainty ' + u['id'],
                'related_hypotheses': [u['hypothesis']], 'importance': 'HIGH', 'why_it_matters': case['research_state'],
                'blocks': [{'kind': 'hypothesis', 'id': h} for h in u.get('blocks', [])]})
        for e in case['edges']:
            add_edge(app, project, {'source': {'kind': 'hypothesis', 'id': e['source']},
                'target': {'kind': 'hypothesis', 'id': e['target']}, 'relation': e['relation'], 'reason': 'Fixture relation'})
        for d in case['debts']:
            add_debt(app, project, {'kind': d['kind'], 'severity': 'HIGH', 'reason': 'Offline fixture debt',
                                   'hypothesis_ids': [d['hypothesis']], 'finding_ids': []})
        candidates = [fixture_candidate(root, item) for item in case['candidates']]
        # A simulated prior run enables reference validation; there is intentionally no executor receipt.
        if any(c['replication_of'] for c in candidates):
            spec = copy.deepcopy(candidates[0]['spec'])
            spec['id'] = 'E-prior'
            app.add('experiment', project, spec)
            with app.store.connect() as db:
                db.execute('INSERT INTO experiment_freezes VALUES (?,?,?,?,?,?,?)',
                           ('FROZEN-fixture', project, spec['id'], 1, 'fixture-digest', encoded(spec), utc_stamp()))
                db.execute('INSERT INTO runs VALUES (?,?,?,?,?)', ('R-fixture', project, spec['id'], '{}', utc_stamp()))
                db.execute('INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    ('R-fixture', project, spec['id'], 'FROZEN-fixture', 'fixture-digest', 'local', 'SUCCEEDED',
                     0, 0, 0, 0, None, None, utc_stamp(), utc_stamp()))
        bundle = {'reasoning_summary': case['research_state'], 'candidates': candidates,
                  'reasoning_cycle': {k: 'OFFLINE FIXTURE: ' + case['research_state'] for k in CYCLE_FIELDS}}
        rejected, accepted = {}, []
        for c in candidates:
            try:
                probe = copy.deepcopy(c)
                if not probe['research']['cheap_falsification']:
                    probe['research']['falsification_exemption'] = 'Evaluated alongside the full bundle cheap falsifier.'
                validate_bundle(app, project, {**bundle, 'candidates': [probe]})
                accepted.append(c)
            except ValueError as exc:
                rejected[c['spec']['id']] = str(exc)
        import_proposals(app, project, {**bundle, 'candidates': accepted})
        decision = plan(app, project)
        expected = case['expected']
        checks = {'selection': decision['selected_experiment'] == expected['selected'],
                  'bad_choices_excluded': decision['selected_experiment'] not in case['known_bad_choices'],
                  'cheap_falsification_considered': any(c['research']['cheap_falsification'] for c in candidates)}
        if expected.get('type'):
            checks['type'] = bool(decision['selected'] and decision['selected']['candidate']['experiment_type'] == expected['type'])
        if expected.get('blocked_reason'):
            checks['blocked_reason'] = expected['blocked_reason'] in encoded(decision['rejected_candidates'])
        surprise = None
        if 'observation' in case:
            prediction = candidates[0]['research']['prediction']
            before = protocol_digest(prediction)
            surprise = classify_surprise(prediction, case['observation'], case['outcome'])
            checks['surprise'] = surprise['classification'] == expected['surprise']
            # Feed simulated evidence to the production interpreter in this disposable catalog.
            # These rows are fixtures, never exported as executor-verified research evidence.
            spec = copy.deepcopy(candidates[0]['spec'])
            app.add('experiment', project, spec)
            spec.update(experiment_id=spec['id'], research_design=candidates[0]['research'],
                        planning={'question': case['research_state'], 'uncertainty_id': candidates[0]['uncertainty_id']})
            finding = {'id': 'F-surprise', 'hypothesis_id': spec['hypothesis_id'], 'measurement': case['observation'],
                'outcome': case['outcome'], 'verification': 'EXECUTOR_VERIFIED', 'evidence_kind': 'SCIENTIFIC',
                'confidence': 'PRELIMINARY'}
            with app.store.connect() as db:
                db.execute('INSERT INTO experiment_freezes VALUES (?,?,?,?,?,?,?)',
                    ('FROZEN-surprise', project, spec['id'], 1, 'fixture-digest', encoded(spec), utc_stamp()))
                db.execute('INSERT INTO findings VALUES (?,?,?,?,?)',
                    ('F-surprise', project, spec['id'], encoded(finding), utc_stamp()))
            observe_finding(app, {'id': 'R-surprise', 'project_id': project, 'freeze_id': 'FROZEN-surprise'}, 'F-surprise')
            checks['uncertainty_created'] = any(json.loads(u['data']).get('origin_finding') == 'F-surprise'
                                                for u in app.store.list('uncertainties', project))
            frozen_prediction = json.loads(app.store.get('experiment_freezes', 'FROZEN-surprise')['data'])['research_design']['prediction']
            checks['prediction_unchanged'] = before == protocol_digest(frozen_prediction)
        return {'id': case['id'], 'passed': all(checks.values()), 'checks': checks,
                'selected': decision['selected_experiment'], 'schema_rejections': rejected,
                'policy_rejections': decision['rejected_candidates'], 'surprise': surprise,
                'label': 'OFFLINE STRUCTURAL EVALUATION — NOT SCIENTIFIC EVIDENCE'}


def evaluate_cases(path):
    payload = json.loads(Path(path).read_text())
    results = [evaluate_case(case) for case in payload['cases']]
    return {'passed': all(r['passed'] for r in results), 'cases': results,
            'evaluation_kind': 'deterministic structural regression', 'external_model_used': False,
            'limitation': 'Checks control and reasoning contracts; does not measure an LLM research-quality gain.'}
