---
name: story-freeze
description: Draft and explicitly approve a schema-validated paper, design, and experiment contract before content-hash freezing it.
version: 0.4.0
model: inherit
---

# Paper story freeze

Use the current conversation model; never call another model API or `autoresearch run`.
This skill requires a challenger-accepted idea and always uses two separate user turns.

Record the exact current message with `autoresearch message --file ...`, then start:

```text
autoresearch host begin --skill story-freeze --role story-editor \
  --message-file <latest-message>
```

Read the returned prompt and main-workspace `story.md`. Write only the staged
`paper/STORY.md` under `transaction_workspace`. It uses the same structured frontmatter as
`story.md`, but sets `stage: paper-story`, selects exactly one candidate, and contains
non-empty claims, experiments, and active target venues. Preserve all source, claim,
experiment, and target-venue identities. Include all idea-story sections plus
`## Experiment matrix` and `## Human approval`.

The contract fixes thesis, scope, non-claims, design, assumptions, and claim-to-experiment
mapping. Every experiment mapping must encode non-empty `prediction`, `datasets`,
`baselines`, `metrics`, `scales`, `seeds`, `resource_budget`, `success_criteria`, and
`kill_criteria` fields. The validator rejects a paper story without this executable frozen
protocol. Do not strengthen claims to hide ambiguity.

Write the returned evidence path with schema version, round ID, message filename, and
`"artifacts": ["paper/STORY.md"]`. The first pass must complete with `continue`; the host
promotes the draft but does not freeze it.

Show the exact draft digest and unresolved choices to the user. Ask the user to approve with
the exact line `APPROVE paper/STORY.md <draft-digest>`. After receiving and recording that
later message, run:

```text
autoresearch host approve-story --message-file <approval-message>
```

Start a new story-editor round bound to that approval message. Do not change the approved
draft. Write evidence again and complete with `satisfied`. The host requires a matching
approval receipt for the unchanged draft digest before creating the paper-story freeze.
