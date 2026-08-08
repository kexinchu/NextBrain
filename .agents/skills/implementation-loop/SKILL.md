---
name: implementation-loop
description: Implement the frozen design in a transaction workspace and require a successful human-authorized small-test command before freezing core code.
version: 0.3.0
model: inherit
---

# Implementation loop

Use the current GPT/Codex, Claude, or Cursor model. Never call another model API or
`autoresearch run`.

Record the exact current user message, then run:

```text
autoresearch host begin --skill implementation-loop --role implementer \
  --message-file <latest-message>
```

Read the prompt and complete frozen `paper/STORY.md`. Edit only staged `code/core/`,
`code/tests/`, and `experiments/scripts/support/` under `transaction_workspace`. Never edit
the main workspace or paper. Make one reviewable step with fixed seeds, tiny fixtures,
explicit failure states, and reusable checks. Supporting probes cannot redefine the idea,
design, metrics, claims, or experiment protocol.

Write `evidence.json` with the bound round/message, and list every logical staged artifact.
Run only a command already authorized by the human in `autoresearch.yaml`:

```text
autoresearch host check <round-id> <implementation-command-name>
```

Complete with `continue` for an intermediate step. Use `report` if implementation requires
a scientific change or a test falsifies a premise. Use `satisfied` only when substantive
core code and tests exist and at least one authorized check for this round has exit code 0.
The successful check receipt must match the final staged content digest; any edit after the
check requires running it again. The host then promotes the transaction and freezes
`code/core/`. Merely creating a test file or claiming that it passed is insufficient.
