"""Bounded, offline full-vector refinement audit of recorded frontier snapshots.

This measures a fixed candidate set, not a graph-search or hardware upper bound.
Online selectors cannot access exact distances or ground truth. No job dispatch.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics


POLICIES = ('distance', 'margin', 'fixed-width', 'topology', 'random')
K = 10
MAX_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class Observable:
    id: int
    estimate: float
    topology: int
    exposure: int


def keyed_hash(namespace, *parts):
    return hashlib.sha256(json.dumps([namespace, *parts], ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def select(candidates: tuple[Observable, ...], budget: int, policy: str,
           query_id: str, seed: int) -> tuple[int, ...]:
    """Select unique reads using only information available before refinement."""
    if policy not in POLICIES:
        raise ValueError('unknown policy')
    ranked = sorted(candidates, key=lambda c: (c.estimate, c.id))
    threshold = ranked[K - 1].estimate
    if policy == 'margin':
        ranked = sorted(candidates, key=lambda c: (abs(c.estimate - threshold), c.id))
    elif policy == 'fixed-width':
        ranked = sorted(candidates, key=lambda c: (c.exposure, c.id))
    elif policy == 'topology':
        ranked = sorted(candidates, key=lambda c: (-c.topology, c.id))
    elif policy == 'random':
        ranked = sorted(candidates, key=lambda c: (
            keyed_hash('b04-r1-random', query_id, c.id), c.id))
    return tuple(c.id for c in ranked[:budget])


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def validate(data, *, r1=False):
    """Fail closed on mixed distance semantics, split overlap, and unbounded inputs."""
    if data.get('schema_version') != 1 or data.get('distance') != 'squared_l2':
        raise ValueError('schema_version 1 and squared_l2 required')
    if not _integer(data.get('dimension'), 1, 4096):
        raise ValueError('invalid dimension')
    if not _integer(data.get('budget'), 1, 2):
        raise ValueError('read budget must be 1 or 2')
    provenance = data.get('provenance', {})
    for key in ('dataset_sha256', 'graph_sha256', 'codes_sha256', 'protocol_sha256'):
        value = provenance.get(key, '')
        if (not isinstance(value, str) or len(value) != 64
                or any(c not in '0123456789abcdef' for c in value)):
            raise ValueError(f'missing or invalid {key}')
    if not isinstance(provenance.get('producer_revision'), str) or not provenance['producer_revision']:
        raise ValueError('producer_revision required')
    rows = data.get('queries')
    if not isinstance(rows, list) or not 4 <= len(rows) <= 1024:
        raise ValueError('4..1024 query snapshots required')
    seen, counts = set(), {'calibration': 0, 'test': 0}
    for row in rows:
        qid = row.get('id')
        if not isinstance(qid, str) or not qid or qid in seen:
            raise ValueError('query IDs must be unique across splits')
        seen.add(qid)
        if row.get('split') not in counts:
            raise ValueError('unknown query split')
        counts[row['split']] += 1
        gt = row.get('ground_truth', [])
        if (not isinstance(gt, list) or len(gt) != K
                or not all(_integer(v, 0, 2**63 - 1) for v in gt) or len(set(gt)) != K):
            raise ValueError('ten distinct global ground-truth IDs required')
        candidates = row.get('candidates', [])
        if not isinstance(candidates, list) or not K <= len(candidates) <= 16:
            raise ValueError('10..16 exposed candidates required')
        ids, exposures = set(), set()
        for c in candidates:
            cid = c.get('id')
            if not _integer(cid, 0, 2**63 - 1) or cid in ids:
                raise ValueError('candidate IDs must be distinct nonnegative integers')
            ids.add(cid)
            for key in ('estimate', 'exact'):
                x = c.get(key)
                if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
                    raise ValueError('finite nonnegative squared distances required')
            if not _integer(c.get('topology'), 0, 2**31 - 1):
                raise ValueError('nonnegative observable topology score required')
            exposure = c.get('exposure')
            if not _integer(exposure, 0, 2**31 - 1) or exposure in exposures:
                raise ValueError('distinct nonnegative exposure ordinals required')
            exposures.add(exposure)
        members = [(c['exact'], c['id']) for c in candidates if c['id'] in gt]
        outsiders = [(c['exact'], c['id']) for c in candidates if c['id'] not in gt]
        if members and outsiders and max(members) > min(outsiders):
            raise ValueError('exact distances contradict global ground truth and ID tie rule')
    if min(counts.values()) < 2:
        raise ValueError('each split requires at least two independent query IDs')
    if r1:
        if (data['budget'] != 2 or data['dimension'] != 128
                or counts != {'calibration': 64, 'test': 256}
                or any(len(r['candidates']) != 16 for r in rows)):
            raise ValueError('R1 requires 128D, exactly 2 reads, 16 candidates, 64/256 queries')
        ordered = sorted(rows, key=lambda r: (keyed_hash('b04-r1-split', r['id']), r['id']))
        if any(r['split'] != ('calibration' if i < 64 else 'test')
               for i, r in enumerate(ordered)):
            raise ValueError('R1 query split must match frozen hash ordering')


def recall(row, reads):
    refined = set(reads)
    ranked = sorted(row['candidates'], key=lambda c: (
        c['exact'] if c['id'] in refined else c['estimate'], c['id']))
    return len({c['id'] for c in ranked[:K]} & set(row['ground_truth'])) / K


def evaluate(row, budget, seed):
    observables = tuple(Observable(c['id'], c['estimate'], c['topology'], c['exposure'])
                        for c in row['candidates'])
    reads = {p: select(observables, budget, p, row['id'], seed) for p in POLICIES}
    scores = {p: recall(row, choice) for p, choice in reads.items()}
    # Exactly B distinct reads, with stable tie-breaking on candidate IDs.
    choices = itertools.combinations(sorted(c.id for c in observables), budget)
    best = min(choices, key=lambda choice: (-recall(row, choice), choice))
    return {'id': row['id'], 'split': row['split'], 'baseline_reads': reads,
            'baseline_recall': scores, 'oracle_reads': best,
            'oracle_recall': recall(row, best), 'quantized_recall': recall(row, ()),
            'exact_frontier_recall': recall(row, [c.id for c in observables]),
            'candidate_coverage': len({c.id for c in observables} & set(row['ground_truth'])) / K,
            'subsets_enumerated': math.comb(len(observables), budget)}


def paired_interval(values, seed, resamples=10000):
    """Query-paired percentile bootstrap; not independent graph replication."""
    rng = random.Random(seed)
    n = len(values)
    means = sorted(statistics.fmean(values[rng.randrange(n)] for _ in range(n))
                   for _ in range(resamples))
    return [means[math.floor(.025 * (resamples - 1))],
            means[math.ceil(.975 * (resamples - 1))]]


def analyze(data, *, seed=20260929, r1=False):
    validate(data, r1=r1)
    rows = [evaluate(row, data['budget'], seed) for row in data['queries']]
    calibration = [r for r in rows if r['split'] == 'calibration']
    test = [r for r in rows if r['split'] == 'test']
    selected = min(POLICIES, key=lambda p: (
        -statistics.fmean(r['baseline_recall'][p] for r in calibration), POLICIES.index(p)))
    gains = [100 * (r['oracle_recall'] - r['baseline_recall'][selected]) for r in test]
    lower, upper = paired_interval(gains, seed)
    verdict = ('HEADROOM_IN_RESTRICTED_ACTION_SET' if lower > 1 else
               'STOP_ON_FROZEN_SAMPLE_ONLY' if upper < 1 else 'INCONCLUSIVE')
    return {'schema_version': 1, 'profile': 'B04-R1' if r1 else 'REFERENCE_CORRECTNESS_ONLY',
            'scope': 'fixed-frontier-exact-B-full-vector-refinement',
            'scientific_status': 'UNVERIFIED', 'hardware_measurement': False,
            'selected_baseline': selected, 'selection_split': 'calibration',
            'test_queries': len(test), 'calibration_queries': len(calibration),
            'read_budget': data['budget'], 'logical_payload_bytes_per_query':
            data['budget'] * 4 * data['dimension'], 'bootstrap_seed': seed,
            'bootstrap_resamples': 10000, 'oracle_gain_pp': statistics.fmean(gains),
            'oracle_gain_ci95_pp': [lower, upper], 'restricted_decision': verdict,
            'provenance': data['provenance'], 'queries': rows,
            'limitations': ['Conditional on supplied exposed frontier and trace producer.',
                           'Bootstrap may miss rare gains; no population upper bound.',
                           'No free-running search, global optimality, or CXL conclusion.',
                           'One graph/encoding does not establish independent replication.',
                           'Provenance declarations require external artifact verification.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--input-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    with args.input.open('rb') as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('input exceeds 16 MiB cap')
    digest = hashlib.sha256(raw).hexdigest()
    if digest != args.input_sha256:
        raise ValueError('input checksum mismatch')
    report = analyze(json.loads(raw), r1=True)
    report['input_sha256'] = digest
    report['analyzer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    import platform
    report['python_version'] = platform.python_version()
    with args.output.open('x') as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write('\n')


if __name__ == '__main__':
    main()
