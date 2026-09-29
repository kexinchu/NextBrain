"""Synthetic correctness checks only; not B-04 scientific evidence."""
import copy
import importlib.util
from pathlib import Path
import sys

import pytest


spec = importlib.util.spec_from_file_location('b04_frontier',
    Path(__file__).parents[1] / 'examples/b04/frontier_oracle.py')
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def fixture():
    candidates = [{'id': i, 'estimate': float(i), 'exact': float(i), 'topology': 0,
                   'exposure': i}
                  for i in range(12)]
    # Candidate 10 is a false negative under approximate scoring. Refining it repairs recall.
    candidates[10]['exact'] = .5
    return {'schema_version': 1, 'distance': 'squared_l2', 'dimension': 128, 'budget': 2,
            'provenance': {**{k: 'a' * 64 for k in (
                'dataset_sha256', 'graph_sha256', 'codes_sha256', 'protocol_sha256')},
                'producer_revision': 'SYNTHETIC-TEST-ONLY'},
            'queries': [{'id': str(i), 'split': 'calibration' if i < 2 else 'test',
                         'ground_truth': list(range(9)) + [10],
                         'candidates': copy.deepcopy(candidates)} for i in range(4)]}


def test_exact_restricted_oracle_and_byte_accounting():
    result = audit.analyze(fixture())
    for row in result['queries']:
        assert row['subsets_enumerated'] == 66
        assert row['oracle_recall'] == 1
        assert len(set(row['oracle_reads'])) == 2
        assert row['oracle_recall'] >= max(row['baseline_recall'].values())
    assert result['logical_payload_bytes_per_query'] == 1024
    assert result['scientific_status'] == 'UNVERIFIED'
    assert not result['hardware_measurement']


def test_no_truth_leakage_into_selectors_or_calibration_choice():
    original = fixture()
    changed = copy.deepcopy(original)
    for row in changed['queries']:
        for c in row['candidates']:
            c['exact'] = 1000 - c['id']
    for a, b in zip(original['queries'], changed['queries']):
        assert audit.evaluate(a, 2, 4)['baseline_reads'] == audit.evaluate(b, 2, 4)['baseline_reads']
    changed = copy.deepcopy(original)
    for row in changed['queries'][2:]:
        row['ground_truth'] = list(range(100, 110))
    assert audit.analyze(changed)['selected_baseline'] == audit.analyze(original)['selected_baseline']


@pytest.mark.parametrize('mutation', ['overlap', 'nan', 'budget', 'duplicate', 'checksum', 'split'])
def test_bad_trace_rejected(mutation):
    data = fixture()
    if mutation == 'overlap':
        data['queries'][3]['id'] = data['queries'][0]['id']
    elif mutation == 'nan':
        data['queries'][0]['candidates'][0]['estimate'] = float('nan')
    elif mutation == 'budget':
        data['budget'] = True
    elif mutation == 'duplicate':
        data['queries'][0]['candidates'][1]['id'] = 0
    elif mutation == 'checksum':
        data['provenance']['graph_sha256'] = 'unverified'
    else:
        data['queries'][0]['split'] = 'train'
    with pytest.raises(ValueError):
        audit.analyze(data)


def test_frontier_blind_spot_stays_missing():
    data = fixture()
    for row in data['queries']:
        row['ground_truth'] = list(range(100, 110))
    report = audit.analyze(data)
    assert report['oracle_gain_ci95_pp'] == [0, 0]
    assert all(row['candidate_coverage'] == 0 for row in report['queries'])
    assert report['restricted_decision'] == 'STOP_ON_FROZEN_SAMPLE_ONLY'


def test_cli_checksum_and_strict_profile(tmp_path):
    import hashlib
    import json
    src, dst = tmp_path / 'input.json', tmp_path / 'report.json'
    src.write_text(json.dumps(fixture()))
    args = ['--input', str(src), '--input-sha256', '0' * 64, '--output', str(dst)]
    with pytest.raises(ValueError, match='checksum'):
        audit.main(args)
    assert not dst.exists()
    args[3] = hashlib.sha256(src.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='R1 requires'):
        audit.main(args)
    assert not dst.exists()


def r1_fixture():
    data = fixture()
    row = data['queries'][0]
    row['candidates'].extend({'id': i, 'estimate': float(i), 'exact': float(i),
                              'topology': 0, 'exposure': i} for i in range(12, 16))
    data['queries'] = [dict(copy.deepcopy(row), id=str(i)) for i in range(320)]
    ordered = sorted(data['queries'], key=lambda r: audit.keyed_hash('b04-r1-split', r['id']))
    for i, r in enumerate(ordered):
        r['split'] = 'calibration' if i < 64 else 'test'
    return data


def test_strict_profile_and_split():
    data = r1_fixture()
    audit.validate(data, r1=True)
    for r in data['queries']:
        r['split'] = 'calibration' if r['split'] == 'test' else 'test'
    with pytest.raises(ValueError, match='R1 requires'):
        audit.validate(data, r1=True)
    data = r1_fixture()
    a = next(r for r in data['queries'] if r['split'] == 'test')
    b = next(r for r in data['queries'] if r['split'] == 'calibration')
    a['split'], b['split'] = b['split'], a['split']
    with pytest.raises(ValueError, match='hash ordering'):
        audit.validate(data, r1=True)


def test_contradictory_truth_rejected():
    data = fixture()
    data['queries'][0]['candidates'][11]['exact'] = 0
    with pytest.raises(ValueError, match='contradict'):
        audit.validate(data)


def test_exposure_order_and_reproducible_random_ignore_serialization_order():
    row = fixture()['queries'][0]
    reverse = dict(row, candidates=list(reversed(row['candidates'])))
    assert audit.evaluate(row, 2, 0)['baseline_reads'] == audit.evaluate(reverse, 2, 0)['baseline_reads']


def test_cli_full_profile_and_exclusive_output(tmp_path):
    import hashlib
    import json
    src, dst = tmp_path / 'trace.json', tmp_path / 'result.json'
    src.write_text(json.dumps(r1_fixture()))
    args = ['--input', str(src), '--input-sha256', hashlib.sha256(src.read_bytes()).hexdigest(),
            '--output', str(dst)]
    audit.main(args)
    report = json.loads(dst.read_text())
    assert report['profile'] == 'B04-R1'
    assert report['scientific_status'] == 'UNVERIFIED'
    assert report['test_queries'] == 256
    assert report['bootstrap_resamples'] == 10000
    assert all(r['subsets_enumerated'] == 120 for r in report['queries'])
    with pytest.raises(FileExistsError):
        audit.main(args)
