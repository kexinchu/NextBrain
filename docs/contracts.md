# Research artifact contracts

`story.md` and `paper/STORY.md` remain human-readable and directly editable. YAML
frontmatter gives the host enough structure to enforce candidate, source, claim, and
experiment identities.

```markdown
---
schema_version: 1
stage: idea-story
status: exploring
selected_candidate: null
target_venues: [OSDI, MLSys]
candidates:
  - id: I-001
    approach: cache-policy
    collision_risk: 0.8
    novelty_uncertainty: 0.7
    scope_risk: 0.4
    motivation_cost: 0.2
sources:
  - id: S-001
    title: Primary paper title
    url: https://example.org/paper
    kind: primary-paper
    checked_at: 2026-08-08
claims:
  - id: C-001
    statement: Narrow falsifiable statement.
    source_ids: [S-001]
    experiment_ids: [M-001]
experiments:
  - id: M-001
    kind: motivation
    claim_ids: [C-001]
    status: planned
---

# Research story

## Thesis
...
```

Idea stories require these sections: Thesis; Target venue and contribution type; Problem
and motivation; Scope and non-goals; Novelty and closest work; Design; Baselines;
Motivation tests; Predictions and kill criteria; Claims and evidence; Open issues. Active
target venues must be explicit; a retired venue cannot satisfy the contract.

The frozen paper contract changes `stage` to `paper-story`, selects one candidate, keeps
non-empty claims and experiments, and adds Experiment matrix and Human approval sections.
Each paper-stage experiment additionally requires non-empty `prediction`, `datasets`,
`baselines`, `metrics`, `scales`, `seeds`, `resource_budget`, `success_criteria`, and
`kill_criteria`. Experiment receipts carry the canonical SHA-256 `protocol_digest`, so a
result cannot silently claim a different protocol under the same experiment ID.

## Round evidence

Each conversation round writes `.autoresearch/transactions/<round-id>/evidence.json`:

```json
{
  "schema_version": 1,
  "round_id": "...",
  "message_file": "0001-....md",
  "artifacts": ["story.md"]
}
```

Skill-specific fields record subagent identities, sampled candidates, experiment cells,
claim preservation, citations, or review provenance. Deterministic check receipts also bind
the exact final staged-workspace digest; editing code or experiment output after a passing
check invalidates that receipt. Evidence is checked before staged files are promoted.
