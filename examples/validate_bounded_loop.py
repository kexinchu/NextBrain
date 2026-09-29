"""SYSTEM VALIDATION — NOT SCIENTIFIC EVIDENCE.

Run against a NEW local directory. Optional --machine selects an existing SSH alias;
this executes only a tiny CPU fixture, never GPU research or server cleanup.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

from researchos.policy import Policy
from researchos.service import ResearchOS
from researchos.ssh import import_config, probe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--machine', default='local')
    parser.add_argument('--intelligence', action='store_true', help='Enable V0.3 research design contracts')
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    repo = root / 'repo'
    repo.mkdir()
    (repo / 'fixture.py').write_text(
        "import json,time\nfrom pathlib import Path\n"
        "p=Path('starts.txt')\np.write_text(p.read_text()+'x' if p.exists() else 'x')\n"
        "print('SYSTEM VALIDATION - NOT SCIENTIFIC EVIDENCE',flush=True)\n"
        "time.sleep(.2)\nPath('metrics.json').write_text(json.dumps({'value':7,'synthetic':True}))\n")
    for argv in [('init', '-q'), ('config', 'user.name', 'Synthetic validation'),
                 ('config', 'user.email', 'fixture@example.invalid'), ('add', '.'),
                 ('commit', '-qm', 'Harmless synthetic CPU fixture')]:
        subprocess.run(['git', '-C', str(repo), *argv], check=True, capture_output=True)
    plans = root / 'plans'
    plans.mkdir()
    (plans / 'fixture.md').write_text('---\nidea_id: LOOP-VALIDATION\ntitle: Synthetic loop validation\n---\nNOT SCIENTIFIC EVIDENCE\n')
    app = ResearchOS(root / 'catalog')
    app.scan(plans)
    project = app.decide('LOOP-VALIDATION', 'GO', 'validation-fixture', 'User-requested system validation')['id']
    workspace = app.workspace(project)
    envelope = {'schema_version': 1, 'project_id': project,
        'problem': 'Validate the bounded coordinator on harmless CPU fixtures',
        'boundary': 'Isolated synthetic jobs; no scientific claims or GPU work',
        'resource_budget': {'cpu_hours': 30 / 3600, 'gpu_hours': 0},
        'allowed_experiment_classes': ['system-validation'],
        'stop_conditions': ['Three total fixture jobs', 'Ten-second per-run timeout'],
        'non_goals': ['Scientific evidence', 'Server cleanup'], 'allowed_baselines': []}
    (workspace / 'PROJECT_ENVELOPE.md').write_text('---\n' + yaml.safe_dump(envelope) + '---\n')
    digest = Policy(app).envelope_draft(project)[1]
    approval = root / 'synthetic-approval.txt'
    approval.write_text('APPROVE envelope ' + digest + '\nExplicit task-authorized synthetic infrastructure validation only.\n')
    Policy(app).approve_envelope(project, digest, approval, 'validation-fixture')
    (workspace / 'autoresearch.yaml').write_text(yaml.safe_dump({'version': 1, 'commands': {
        'fixture': {'skill': 'experiment-loop', 'argv': ['python3', 'fixture.py'], 'timeout': 10}}}))
    app.add('hypothesis', project, {'id': 'H1', 'statement': 'Synthetic value reaches fixture threshold',
                                  'falsification_condition': 'Synthetic value below threshold',
                                  **({'hypothesis_type': 'PERFORMANCE'} if args.intelligence else {})})
    if args.intelligence:
        from researchos.intelligence import set_question
        set_question(app, project, {'id': 'Q1', 'question': envelope['problem'],
                                   'motivation_hypotheses': [], 'oracle_hypotheses': []})
    if args.machine != 'local':
        import_config(app.store, Path.home() / '.ssh/config')
        inventory = probe(app.store, args.machine)
        if inventory['data']['status'] != 'OK':
            raise RuntimeError('Remote unavailable: ' + json.dumps(inventory['data']))
        (root / 'inventory.json').write_text(json.dumps(inventory, indent=2))

    def cli(*argv):
        result = subprocess.run([sys.executable, '-m', 'researchos', '--home', str(app.root), *argv],
                                check=True, capture_output=True, text=True, env=os.environ.copy())
        return json.loads(result.stdout)

    uncertainty = root / 'uncertainty.json'
    uncertainty.write_text(json.dumps({'id': 'U1', 'question': 'Can the bounded execution path complete safely?',
        'related_hypotheses': ['H1'], 'importance': 'HIGH', 'why_it_matters': 'Infrastructure acceptance test'}))
    cli('uncertainty', 'add', project, '--file', str(uncertainty))
    candidates = []
    for i in range(4):
        spec = {'id': f'E{i}', 'hypothesis_id': 'H1', 'experiment_class': 'system-validation',
            'evidence_kind': 'SYSTEM_VALIDATION', 'prediction': {'value': {'min': 5, 'max': 10}},
            'metrics': ['value'], 'success_condition': 'value >= 5', 'falsification_condition': 'value < 5',
            'expected_artifacts': ['metrics.json', 'starts.txt'],
            'resource_requirement': {'cpu_only': True, 'gpu_required': False, 'gpu_count': 0},
            'environment_requirement': {'python_min': '3.10'}, 'command_name': 'fixture',
            'estimated_runtime': '0.2 seconds', 'dependencies': [], 'timeout': 10,
            'budget': {'cpu_hours': 10 / 3600, 'gpu_hours': 0, 'max_retries': 0},
            'data': {'identifiers': [], 'hashes': {}}, 'protocol': {'metric_file': 'metrics.json',
            'baselines': [], 'rules': [{'metric': 'value', 'success': {'op': '>=', 'value': 5},
                                       'falsification': {'op': '<', 'value': 5}}]}}
        candidates.append({'candidate_id': f'C{i}', 'uncertainty_id': 'U1', 'hypothesis_ids': ['H1'],
            'question': 'Can this isolated fixture complete once?', 'experiment_type': 'FEASIBILITY',
            'mode': 'EXPLORATION', 'expected_information': 'Execution, recovery and re-planning correctness only',
            'possible_outcomes': {k: {'interpretation': 'Synthetic system outcome only: ' + k,
                                     'uncertainty_status': 'UNCHANGED' if k == 'OPERATIONAL_FAILURE' else 'REDUCED'}
                for k in ('SUPPORTED', 'FALSIFIED', 'INCONCLUSIVE', 'OPERATIONAL_FAILURE')},
            'estimated_cost': 1, 'risk': 'Ten-second bounded CPU job', 'discrimination_power': .5,
            'expected_information_gain': .5, 'feasibility': 1, 'spec': spec, 'repo': str(repo),
            'machine': args.machine, 'replication_of': None})
    if args.intelligence:
        from researchos.reasoning_eval import fixture_candidate
        from researchos.intelligence import CYCLE_FIELDS
        for candidate in candidates:
            candidate['research'] = fixture_candidate(repo, {'id': candidate['spec']['id'],
                'hypothesis': 'H1', 'uncertainty': 'U1', 'type': 'FEASIBILITY',
                'strategy': 'MEASUREMENT', 'cheap': True})['research']
    proposal = root / 'proposals.json'
    proposal.write_text(json.dumps({'reasoning_summary': 'SYSTEM VALIDATION; curated fixture pool, no scientific reasoning.',
                                   'candidates': candidates, **({'reasoning_cycle': {k: 'Synthetic fixture only: ' + k for k in CYCLE_FIELDS}}
                                            if args.intelligence else {})}, indent=2))
    cli('planner', 'import', project, '--file', str(proposal))
    before = cli('next', project)
    assert before['ready'] and not app.store.list('executions', project)
    one = cli('advance', project, '--max-wall-time', '10m')
    assert len(one['run_ids']) == 1 and one['stop_reason'] == 'MAX_RUNS', one
    two = cli('advance', project, '--max-runs', '2', '--max-wall-time', '10m')
    assert len(two['run_ids']) == 2 and two['stop_reason'] == 'MAX_RUNS', two
    blocked = cli('advance', project, '--max-runs', '2')
    assert not blocked['run_ids'] and 'budget' in blocked['stop_reason'], blocked
    runs = app.store.list('executions', project)
    assert len(runs) == 3 and all(r['state'] == 'SUCCEEDED' for r in runs)
    with app.store.connect() as db:
        starts = db.execute("SELECT a.path FROM artifact_origins o JOIN artifacts a ON a.id=o.artifact_id "
                            "WHERE o.relative_path='code/starts.txt'").fetchall()
    assert len(starts) == 3 and all(Path(row[0]).read_text() == 'x' for row in starts)
    context = cli('planner', 'context', project)
    assert context['hypotheses'][0]['state'] == 'PROPOSED'
    assert all(json.loads(r['data'])['evidence_kind'] == 'SYSTEM_VALIDATION' for r in app.store.list('findings', project))
    report = {'label': 'SYSTEM VALIDATION — NOT SCIENTIFIC EVIDENCE', 'project': project,
              'machine': args.machine, 'single': one, 'bounded_two': two, 'budget_stop': blocked,
              'run_ids': [r['id'] for r in runs], 'duplicate_jobs': False,
              'finding_count': len(app.store.list('findings', project)),
              'plan_count': len(app.store.list('planner_decisions', project)),
              'budget': context['budget'], 'scientific_state': context['hypotheses'],
              'gpu_execution': False, 'intelligence_enabled': args.intelligence}
    (root / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
