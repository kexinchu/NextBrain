# Capability and client evaluation

Local unit tests establish deterministic state behavior; they do not establish model or
client quality. Release readiness therefore has two separate gates.

## Local gate

```bash
python -m pytest
ruff check src tests
autoresearch doctor --release
autoresearch eval --release
```

The adversarial suite covers stale message binding, role alternation, independent agent
IDs, exact story approval, staged promotion, quarantine recovery, authorized test receipts,
post-check mutation rejection, same-stat content tampering, transaction rollback,
experiment protocol/matrix coverage, contradiction reporting, and new review artifacts.

## Real-client matrix

Run every skill in GPT/Codex, Claude, and Cursor with the intended model: 18 cells total.
For each cell preserve a Markdown transcript or screenshot bundle containing:

- client and exact model selection;
- explicit skill invocation and discovered skill version;
- bound message filename and requirements digest;
- transaction and evidence paths;
- terminal decision and promoted artifacts;
- any expected negative gate.

Record it:

```bash
autoresearch e2e record --client <gpt|claude|cursor> --skill <skill> \
  --model <exact-model> --status pass --evidence <artifact>
```

`autoresearch e2e status` verifies that the evidence file still matches its recorded hash.
`autoresearch doctor --release --require-e2e` stays red until all 18 cells have current pass
receipts.

## Research-quality benchmarks

Client execution success is not scientific quality. Evaluate the following on a seeded set
of topics with expert-labelled collisions and kill criteria:

- message capture rate and requirement-drift rate;
- prior-art collision recall and false novelty acceptance;
- challenger catches per sampled candidate and literature-query budget;
- motivation-test decision accuracy and cost;
- claim/source/experiment linkage completeness;
- implementation check pass rate without paper changes;
- contradiction-report recall without core/story mutation;
- writing claim-preservation rate;
- reviewer blocker agreement with an expert review;
- elapsed time, input tokens, tool calls, and compute per accepted idea.

Do not combine local code checks, real-client E2E, and research-quality benchmark results
into one undifferentiated score.
