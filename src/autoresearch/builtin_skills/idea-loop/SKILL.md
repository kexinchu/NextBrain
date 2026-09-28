---
name: idea-loop
description: Alternate two independent host-native agents under an enforced state machine, challenge a risk-stratified sample, and update story.md.
version: 0.4.0
model: inherit
---

# Idea loop

Use the model selected in this conversation. Never call another model API or
`autoresearch run`. The main conversation is the orchestrator and must delegate scout and
challenger to fresh host-native subagents. If independent delegation is unavailable, stop.

## Start a user turn

Save the exact current user message as a new `.autoresearch/inbox/*.md`, then run
`autoresearch --workspace . message --file <file> --source user`. Capture the returned
message filename. Never combine two messages.

Start the role required by `autoresearch host status`:

```text
autoresearch host begin --skill idea-loop --role <idea-scout|idea-challenger> \
  --message-file <latest-message> --max-rounds <N> --sample-size <K>
```

Read `prompt_path`. Read source requirements and prior `story.md` from the main workspace,
but write the proposed `story.md` only inside `transaction_workspace`. Direct edits to the
main workspace invalidate the round.

## Contract and roles

`story.md` must be readable Markdown with YAML frontmatter containing:

- `schema_version: 1`, `stage: idea-story`, `status`, `selected_candidate`, and a non-empty
  list of active `target_venues`;
- `candidates`: unique IDs plus `approach` and numeric 0..1 `collision_risk`,
  `novelty_uncertainty`, `scope_risk`, and `motivation_cost`;
- `sources`: unique IDs with title, URL, kind, and `checked_at`;
- `claims`: unique IDs, statements, `source_ids`, and `experiment_ids`;
- `experiments`: unique motivation-test IDs and `claim_ids`.

Use these exact `##` sections: Thesis; Target venue and contribution type; Problem and
motivation; Scope and non-goals; Novelty and closest work; Design; Baselines; Motivation
tests; Predictions and kill criteria; Claims and evidence; Open issues.

The scout searches primary papers, official proceedings, and repositories, proposes a
small falsifiable set, explicitly tests venue-family fit, and designs cheap motivation tests.
Systems and AI-infrastructure venues are the default; ICLR, NeurIPS, AAAI, or DAC require a
real contribution to their own community, not only a systems paper with renamed motivation.
The challenger reads the
generated `sample-plan.json` and reviews exactly that risk-stratified sample. It tests
collision, scope, baseline fairness, confounders, feasibility, and whether existing work
already solves the problem. Never infer novelty from a missing search result.

Write `evidence.json` at the path returned by `host begin`:

```json
{
  "schema_version": 1,
  "round_id": "<round-id>",
  "message_file": "<latest-message>",
  "artifacts": ["story.md"],
  "subagents": [{"role": "<round-role>", "agent_id": "<host-run-id>"}],
  "sampled_candidate_ids": []
}
```

For a challenger, `sampled_candidate_ids` must exactly match `sample-plan.json`, and its
`agent_id` must differ from the prior scout. Complete with `continue`, `satisfied`,
`blocked`, or `report`. The host enforces alternation, round budget, evidence, schema, and
promotion. Only a challenger may accept an idea. Stop immediately for collision, failed
motivation, infeasible resources, conflicts, or a surviving candidate needing human review.
