import json
import subprocess
from pathlib import Path

import pytest
import yaml

from researchos.cli import main
from researchos.plans import scan_plans
from researchos.service import ResearchOS
from researchos.ssh import configuration, import_config, probe


@pytest.fixture
def setup(tmp_path):
    plans = tmp_path / 'plans'
    plans.mkdir()
    (plans / 'idea.md').write_text('---\nidea_id: I1\ntitle: Cache reuse\n---\n# Cache\n')
    app = ResearchOS(tmp_path / 'catalog')
    app.scan(plans)
    project = app.decide('I1', 'GO', 'human', 'Test feasibility')
    return app, project['id'], plans


def hypothesis(app, project, name='H1'):
    return app.add('hypothesis', project, {'id': name, 'statement': 'Reuse exists',
                                          'falsification_condition': 'Reuse below 5%'})


def experiment(app, project, name='E1', dependencies=None):
    return app.add('experiment', project, {
        'id': name, 'hypothesis_id': 'H1', 'prediction': {'reuse': '10-20%'},
        'metrics': ['reuse'], 'success_condition': 'reuse > 5%',
        'failure_condition': 'reuse <= 5%', 'expected_artifacts': ['result.json'],
        'resource_requirement': {'gpu_model': 'RTX 4060', 'gpu_count': 1},
        'estimated_runtime': '60s', 'command_name': 'smoke', 'dependencies': dependencies or []})


def approve(app, project):
    path = app.workspace(project) / 'RESEARCH_CONTRACT.md'
    data = {'schema_version': 1, 'research_id': project, 'title': 'Cache reuse',
            'core_question': 'Does reuse reduce inference cost?', 'primary_claim': 'Reuse saves cost',
            'baseline': ['No cache'], 'independent_variables': ['cache capacity'],
            'dependent_variables': ['latency'], 'success_conditions': ['latency decreases 10%'],
            'falsification_conditions': ['overhead exceeds savings'],
            'abandonment_result': 'No net benefit on realistic traces',
            'compute_budget': {'gpu_hours': 1}, 'target_venue': 'MLSys',
            'contribution_type': 'systems'}
    path.write_text('---\n' + yaml.safe_dump(data) + '---\n# Contract\n')
    _, digest = app.contract(project)
    return app.approve_contract(project, digest, 'human', 'Reviewed protocol')


def test_repeated_scan_go_and_source_revision(setup):
    app, project, plans = setup
    app.scan(plans)
    assert app.decide('I1', 'GO', 'human', 'Test feasibility')['id'] == project
    assert len(app.store.list('decisions')) == 1
    source = (app.workspace(project) / 'SOURCE_IDEA.md').read_text()
    (plans / 'idea.md').write_text('---\nidea_id: I1\ntitle: New claim\n---\n# Changed\n')
    app.scan(plans)
    assert app.inbox()[0]['source_changed']
    with pytest.raises(ValueError, match='source changed'):
        app.decide('I1', 'GO', 'human', 'Approve changed source')
    assert (app.workspace(project) / 'SOURCE_IDEA.md').read_text() == source
    assert len(app.store.list('revisions')) == 2


def test_non_go_and_resume(setup):
    app, project, _ = setup
    for decision in ('HOLD', 'DROP', 'NEEDS_WORK'):
        assert app.decide('I1', decision, 'human', 'Review')['state'] == decision
    assert app.decide('I1', 'GO', 'human', 'Resume')['state'] == 'ACTIVE'
    assert len(app.store.list('projects')) == 1


def test_non_go_never_creates_project(tmp_path):
    plans = tmp_path / 'plans'
    plans.mkdir()
    (plans / 'idea.md').write_text('# Candidate')
    app = ResearchOS(tmp_path / 'db')
    idea = app.scan(plans)[0]['id']
    for decision in ('HOLD', 'DROP', 'NEEDS_WORK'):
        assert app.decide(idea, decision, 'human', 'Review')['value'] == decision
    assert app.store.list('projects') == []


def test_multi_candidate_packet_links_and_duplicates(tmp_path):
    plans = tmp_path / 'plans'
    plans.mkdir()
    (tmp_path / 'detail.md').write_text('# Details')
    packet = plans / 'packet.md'
    packet.write_text('# Tournament\n## 1. `B-04` First\n[[../detail]]\n'
                      '## 2. `B-09` Second\n[[../../outside]]\n')
    records = scan_plans(plans, tmp_path)
    assert [r['id'] for r in records] == ['B-04', 'B-09']
    assert len(records[0]['snapshot']['linked_documents']) == 1
    assert records[1]['snapshot']['unresolved_links'] == ['../../outside']
    (plans / 'duplicate.md').write_text('---\nidea_id: B-04\ntitle: Duplicate\n---\n')
    app = ResearchOS(tmp_path / 'db')
    with pytest.raises(ValueError, match='duplicate'):
        app.scan(plans, tmp_path)
    assert app.inbox() == []


def test_contract_approval_and_drift(setup):
    app, project, _ = setup
    with pytest.raises(ValueError, match='missing'):
        app.contract(project)
    approved = approve(app, project)
    assert app.store.get('projects', project)['contract_digest'] == approved['digest']
    hypothesis(app, project)
    experiment(app, project)
    workspace = app.workspace(project)
    (workspace / 'autoresearch.yaml').write_text(yaml.safe_dump({
        'version': 1, 'commands': {'smoke': {'skill': 'experiment-loop',
                                          'argv': ['python', '-m', 'pytest']}}}))
    assert app.readiness('E1')['specification_ready'] is True
    assert app.readiness('E1')['remote_execution_enabled'] is False
    path = workspace / 'RESEARCH_CONTRACT.md'
    path.write_text(path.read_text() + '\nChanged\n')
    assert not app.readiness('E1')['specification_ready']
    with pytest.raises(ValueError, match='digest'):
        app.approve_contract(project, approved['digest'], 'human', 'Old approval')
    # Project admission never pretends the AutoResearch story is frozen.
    assert not (workspace / 'paper/STORY.md').exists()
    assert not (workspace / '.autoresearch/workflow.json').exists()


def test_dag_and_immutable_specs(setup):
    app, project, _ = setup
    hypothesis(app, project)
    first = experiment(app, project)
    assert experiment(app, project)['id'] == first['id']
    with pytest.raises(ValueError, match='unknown'):
        experiment(app, project, 'E2', ['MISSING'])
    with pytest.raises(ValueError, match='self dependency'):
        experiment(app, project, 'E2', ['E2'])
    experiment(app, project, 'E2', ['E1'])
    with pytest.raises(ValueError, match='immutable'):
        experiment(app, project, 'E1', ['E2'])
    assert any('dependency E1' in b for b in app.readiness('E2')['blockers'])


def test_cross_project_and_malformed_input(setup):
    app, project, plans = setup
    hypothesis(app, project)
    (plans / 'other.md').write_text('---\nidea_id: I2\ntitle: Other\n---\n# Other')
    app.scan(plans)
    other = app.decide('I2', 'GO', 'human', 'Check')['id']
    with pytest.raises(ValueError, match='another project'):
        experiment(app, other)
    with pytest.raises(ValueError, match='invalid identifier'):
        hypothesis(app, project, '../../bad')
    with pytest.raises(ValueError, match='mapping'):
        app.add('claim', project, [])


def test_failure_evidence_and_contradiction_are_preserved(setup, tmp_path):
    app, project, _ = setup
    hypothesis(app, project)
    experiment(app, project)
    app.add('claim', project, {'id': 'C1', 'statement': 'Caching helps'})
    run = app.add('run', project, {'id': 'R1', 'experiment_id': 'E1', 'status': 'FAIL',
                                  'provenance': 'manual-import', 'observed': {'reuse': 0},
                                  'environment': {'host': 'fixture'}})
    assert json.loads(run['data'])['prediction'] == {'reuse': '10-20%'}
    output = tmp_path / 'result.json'
    output.write_text('{"reuse": 0}')
    artifact = app.artifact('R1', output)
    output.write_text('changed')
    assert Path(artifact['path']).read_text() == '{"reuse": 0}'
    finding = app.add('finding', project, {
        'id': 'F1', 'experiment_id': 'E1', 'run_ids': ['R1'], 'observation': 'No reuse',
        'magnitude': '0%', 'confidence': 'single trace', 'supports': [], 'contradicts': ['C1'],
        'unexpected': True, 'next_questions': []})
    assert json.loads(finding['data'])['verification'] == 'UNVERIFIED'
    assert app.store.get('projects', project)['state'] == 'ACTIVE'
    assert not app.readiness('E1')['specification_ready']
    assert len(app.context(project)['findings']) == 1


def test_provision_failure_is_resumable(tmp_path, monkeypatch):
    import researchos.service as service
    plans = tmp_path / 'plans'
    plans.mkdir()
    (plans / 'idea.md').write_text('---\nidea_id: I1\ntitle: Example\n---\n# Candidate')
    app = ResearchOS(tmp_path / 'db')
    app.scan(plans)
    original = service.ResearchWorkspace.init
    monkeypatch.setattr(service.ResearchWorkspace, 'init', lambda _: (_ for _ in ()).throw(
        OSError('injected disk failure')))
    with pytest.raises(OSError, match='disk failure'):
        app.decide('I1', 'GO', 'human', 'Test')
    assert app.store.list('projects')[0]['state'] == 'PROVISIONING'
    monkeypatch.setattr(service.ResearchWorkspace, 'init', original)
    project = app.decide('I1', 'GO', 'human', 'Test')
    assert project['state'] == 'ACTIVE'
    assert len(app.store.list('projects')) == len(app.store.list('decisions')) == 1


def test_modified_source_and_symlink_workspace_rejected(setup, tmp_path):
    app, project, _ = setup
    path = app.workspace(project)
    (path / 'SOURCE_IDEA.md').write_text('tampered')
    with pytest.raises(ValueError, match='snapshot'):
        app.provision(project)
    moved = tmp_path / 'moved'
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        app.provision(project)


def test_ssh_import_never_executes_and_probe_is_explicit(tmp_path, monkeypatch):
    config = tmp_path / 'config'
    config.write_text('Host gpu-a gpu-b *.example\n HostName example\n')
    app = ResearchOS(tmp_path / 'db')
    def forbidden(*args, **kwargs):
        raise AssertionError('discovery must never connect')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    assert len(import_config(app.store, config)) == 2
    def success(argv, **kwargs):
        assert argv[-2:] == ['gpu-a', 'sh -s']
        assert 'StrictHostKeyChecking=yes' in argv
        assert 'ProxyCommand=none' in argv
        assert kwargs['timeout'] == 30
        return subprocess.CompletedProcess(argv, 0,
             '__ROS_HOSTNAME__\nfixture\n__ROS_GPU__\nNVIDIA RTX A6000, 49140, 555\n', '')
    monkeypatch.setattr(subprocess, 'run', success)
    assert probe(app.store, 'gpu-a')['data']['status'] == 'OK'
    assert 'A6000' in json.loads(app.store.get('machines', 'gpu-a')['data'])['inventory']['gpu']
    with pytest.raises(ValueError):
        probe(app.store, '-oProxyCommand=bad')


def test_ssh_include_match_exec_and_failed_probe(tmp_path, monkeypatch):
    config = tmp_path / 'config'
    include = tmp_path / 'hosts'
    config.write_text('Include hosts\nHost=one\n')
    include.write_text('Host two\nMatch exec "echo unsafe"\n')
    assert configuration(config) == (['one', 'two'], ['Match exec'])
    app = ResearchOS(tmp_path / 'db')
    import_config(app.store, config)
    with pytest.raises(ValueError, match='Match exec'):
        probe(app.store, 'one')
    include.write_text('Host two\n')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 255, '',
                                                                                      'No route'))
    assert probe(app.store, 'one')['data']['status'] == 'UNREACHABLE'
    assert len(app.store.list('probes')) == 1


def test_cli_full_local_flow(tmp_path, capsys):
    home = tmp_path / 'home'
    plans = tmp_path / 'plans'
    plans.mkdir()
    (plans / 'idea.md').write_text('---\nidea_id: I1\ntitle: Test\n---\n# Test')
    def cli(*args):
        assert main(['--home', str(home), *args]) == 0
        return json.loads(capsys.readouterr().out)
    cli('scan', '--plans', str(plans))
    assert cli('inbox')[0]['id'] == 'I1'
    project = cli('decide', 'I1', 'GO', '--by', 'human', '--reason', 'fixture')['id']
    record = tmp_path / 'record.yaml'
    record.write_text('id: H1\nstatement: Reuse exists\nfalsification_condition: No reuse\n')
    cli('hypothesis', 'add', '--project', project, '--file', str(record))
    experiment(ResearchOS(home), project)
    record.write_text(yaml.safe_dump({'id': 'F1', 'experiment_id': 'E1',
        'observation': 'No measurement yet', 'magnitude': 'not measured',
        'confidence': 'unverified', 'unexpected': False, 'next_questions': ['Run smoke']}))
    cli('finding', 'add', '--project', project, '--file', str(record))
    assert cli('status')['counts']['findings'] == 1
    assert cli('context', project)['hypotheses']
    assert main(['--home', str(home), 'contract', 'check', project]) == 1


def test_packet_overview_links_are_in_source_snapshot(tmp_path):
    plans = tmp_path / 'plans'
    plans.mkdir()
    detail = tmp_path / 'details.md'
    detail.write_text('# Full plan')
    (plans / 'batch.md').write_text('# Batch\n| `B-1` | title | [[../details]] |\n'
                                  '## 1. `B-1` Candidate\nSummary\n')
    assert str(detail) in scan_plans(plans, tmp_path)[0]['snapshot']['linked_documents']


def test_explicit_handoff_admits_external_idea_but_preserves_story_gate(setup, tmp_path):
    from autoresearch.host import HostRoundManager
    from autoresearch.io import sha256_file
    from autoresearch.journal import UserMessageJournal
    from autoresearch.workflow import WorkflowError, WorkflowState
    from test_host import contract

    app, project, _ = setup
    approve(app, project)
    story = tmp_path / 'reviewed-idea.md'
    story.write_text(contract().replace('selected_candidate: null', 'selected_candidate: I-1'))
    digest = sha256_file(story)
    with pytest.raises(WorkflowError, match='digest'):
        app.handoff(project, story, 'wrong', 'human', 'Reviewed S1-S4')
    receipt = app.handoff(project, story, digest, 'human', 'Reviewed S1-S4')
    assert receipt['kind'] == 'external-human-admission'
    assert app.handoff(project, story, digest, 'human', 'Reviewed S1-S4') == receipt
    root = app.workspace(project)
    assert WorkflowState(root).load()['story']['status'] == 'idle'
    with pytest.raises(WorkflowError, match='frozen story'):
        WorkflowState(root).begin('test-only', 'implementation-loop', 'implementation', 'unused')
    # The ordinary engine accepts a real story-freeze round after explicit admission.
    latest = UserMessageJournal(root).latest().name
    started = HostRoundManager(root).begin('story-freeze', role='story-editor', message_file=latest)
    assert Path(started['transaction_workspace']).is_dir()
    assert not (root / 'paper/STORY.md').exists()
    with pytest.raises(WorkflowError, match='idle'):
        app.handoff(project, story, digest, 'human', 'Cannot change pending round')
