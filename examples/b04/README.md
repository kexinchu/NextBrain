# B-04 fixed-frontier oracle preparation

`frontier_oracle.py` audits recorded graph-search frontiers on one CPU thread using
the Python standard library. It does not build an index, produce traces, dispatch a
job, approve a protocol, or register scientific findings. Its report remains
`UNVERIFIED` until provenance and execution evidence are reviewed.

## Question and action

Given 16 already exposed candidates, choose **exactly two** full-vector reads.
Replace those two estimated squared L2 distances with exact distances, retain the
other estimates, and return the ten smallest mixed scores. All ties use vector ID.
The oracle enumerates all 120 subsets and maximizes Recall@10 against ground truth
computed over the same fixed database. The result is optimal only for this finite
snapshot problem. It does not reveal undiscovered graph nodes or change a path.

The output may contain candidates whose vectors were not read. A product requiring
exact scoring for every returned item needs a different protocol. Exactly two reads
is also different from at most two: refinement can reduce recall. The latter problem
would require enumerating 137 subsets and changing the matched controls.

## Protocol R1

- 128 dimensions, 64 calibration queries and 256 test queries, one snapshot per query.
- Freeze the complete source query pool before viewing any outcomes. Sort IDs by
  SHA256 of compact UTF-8 JSON `["b04-r1-split", query_id]`, then by ID. Select the
  first 320, assigning the first 64 to calibration. The CLI verifies the split within
  the supplied 320; an external manifest must verify selection from the full pool.
- Proposed producer: one frozen graph and quantizer, beam 32, snapshot after eight
  expansions, nearest 16 exposed candidates by estimated distance and ID. Record
  exposure order and graph indegree. A missing/short snapshot is a protocol failure;
  do not replace it after inspecting its ground truth. The producer is not included.
- Select the strongest control on calibration mean recall, with ties resolved in
  this order: distance, margin, fixed-width, topology, random. Keep it fixed on test.
- Compare the oracle with that control using paired query gains in percentage points,
  10,000 percentile bootstrap resamples, seed 20260929. Record Python version.
- A lower endpoint above 1 pp supports local headroom. An upper endpoint below 1 pp
  yields `STOP_ON_FROZEN_SAMPLE_ONLY`. Otherwise the result is `INCONCLUSIVE`.
  A degenerate bootstrap can miss rare gains; it is not a population upper bound.

The five controls see only estimated distances, vector IDs, exposure order, and
topology. Distance reads the two smallest estimates; margin reads the two closest
to the estimated tenth-place score; fixed-width reads the two earliest exposures;
topology reads the two highest indegrees. Random uses SHA256 of compact UTF-8 JSON
`["b04-r1-random", query_id, candidate_id]`, then candidate ID. Compact JSON means
`ensure_ascii=False, separators=(",", ":")`.

Report no-read recall, all-exact frontier recall, frontier GT coverage, every
control's read IDs, oracle read IDs and enumerated subset counts. Two 128D float32
reads cost 1,024 logical payload bytes per query. This omits physical bus/page costs.
Oracle truth acquisition and enumeration costs belong in total experiment costs;
they are not implementable using only two online reads.

## Input and provenance

Input is a single JSON object, capped at 16 MiB:

```text
schema_version: 1
distance: squared_l2
dimension: 128
budget: 2
provenance:
  dataset_sha256: <64 lowercase hex characters>
  graph_sha256: <64 lowercase hex characters>
  codes_sha256: <64 lowercase hex characters>
  protocol_sha256: <64 lowercase hex characters>
  producer_revision: <immutable producer version>
queries:
  - id: <string, globally unique across splits>
    split: calibration | test
    ground_truth: <10 distinct global vector IDs>
    candidates: <16 objects, each with id, estimate, exact, topology, exposure>
```

IDs and exposure ordinals are distinct nonnegative integers within a snapshot.
Distances are finite and nonnegative. Ground-truth ties must use `(exact_distance,
vector_id)`. The validator rejects contradictions between available exact distances
and GT membership; it cannot validate distances of unseen database vectors.

The input checksum is checked against a separately supplied digest. Other hashes
are declarations, **not verification of the underlying files**. Before a scientific
run, independently verify source URLs and use conditions, database/query IDs,
data/split/GT hashes, graph/quantizer commits and parameters, trace producer revision,
platform/dependencies, frozen protocol, and complete input hash. Subsetting a database
requires recomputing GT over that subset. The script contains no substitute dataset
or fabricated trace producer.

## Running and resource enforcement

The command interface is:

```text
python examples/b04/frontier_oracle.py --input <frozen-input.json> \
  --input-sha256 <verified-digest> --output <new-report.json>
```

The output path must be new. No correctness-only or smaller-sample CLI override exists.
The internal functions allow tiny fixtures for unit tests; those reports carry
`REFERENCE_CORRECTNESS_ONLY`. The CLI always enforces the R1 dimensions and counts.

The reviewed project envelope allows 2 cumulative CPU-hours, 0 GPU-hours, 16 GiB
memory and 5 GiB additional disk. This standalone analyzer is **not a resource
supervisor**. Bind the final immutable argv as a user-authorized named command and
use the execution layer's remaining-budget and resource controls before a real run.
Input bounds do not replace cumulative CPU, memory, or disk enforcement. Do not
copy this template into the command allowlist as if the user supplied concrete argv.

## Evidence status and closest work

This is measurement infrastructure. No real B-04 trace, novelty claim, free-running
search improvement, or CXL/RDMA performance result is included. Unit tests use
synthetic data solely for correctness. The full-system B-04 proposal still overlaps
prior work; abstract controls here are not replicas:

- [FaTRQ](https://arxiv.org/html/2601.09985v1) refines residual representations across
  memory tiers. Its residual actions and bytes differ from a full-vector read.
- [RED-ANNS §5.3](https://kay21s.github.io/RED-ANNS-VLDB2026.pdf) uses PQ distance
  pruning before remote node reads and asynchronous expansion. A fixed-budget
  distance ordering does not reproduce its threshold or adjacency transfers.
- [SymphonyQG](https://arxiv.org/html/2411.12229v1) combines graph search with
  quantization and implicit exact reranking. This analyzer omits its multi-center
  estimates, layout, and graph construction.

The next required artifact is a verified real trace producer and input manifest.
Only then can the named execution command and scientific preflight be completed.
