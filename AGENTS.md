# NextBrain repository rules

## ResearchOS experiment execution

Early research execution uses an approved `PROJECT_ENVELOPE.md` and an immutable per-experiment
snapshot. A final paper claim or `paper/STORY.md` is not an early-execution prerequisite.
Only dispatch named commands already authorized in `autoresearch.yaml`. Persist the Run ID
before dispatch; reconcile remote receipts before retrying. Never blindly relaunch LOST jobs.
Operational failure is not falsification. Valid falsification closes a hypothesis branch and
keeps the project active unless an approved critical-stop policy applies. Changes to scope,
question, claim, architecture, evaluation target, baselines or budget require digest-bound
human approval and a revised envelope. Never manufacture human approval messages.
See `docs/researchos-execution.md`. These rules govern the new ResearchOS path.

## Legacy paper workflow


This repository implements a human-directed research workflow. Before any research round:

1. Read every Markdown file in `requirements/messages/` in filename order.
2. Resolve `.autoresearch/active-topic.json` and read the referenced topic Markdown in full.
   It contains the direction and mirrored session requirements; also verify the immutable
   source messages under `requirements/messages/`.
3. Verify the relevant content-hash freeze in `.autoresearch/freezes/`.
4. Run `autoresearch host next` and follow its playbook. Do not invent a round ID or
   write `alignment.md`; `host complete` writes that report.
5. Prefer `host start --inbox <file>` to record the current message and infer the role.
   Complete or abort a pending round first. Write model artifacts only under the returned
   transaction workspace and create the returned evidence manifest.

Scientific boundaries:

- `paper/STORY.md` is the frozen scientific contract.
- `story.md` is the human-editable output of `idea-loop`; every idea round reads it first.
- `paper/manuscript/` is an editable expression layer; it cannot change the story.
- After implementation freeze, `code/core/` is immutable during experiments.
- Experiment agents may change `experiments/scripts/` and write results only.
- A contradiction between evidence and the frozen story must stop and be reported.
- Missing evidence stays missing. Do not infer numeric results or novelty from absence.
- Default to systems and AI-infrastructure venue profiles. Require an explicit frozen
  target venue and contribution type. Do not re-label a systems-only contribution as ML/AI
  novelty to target ICLR, NeurIPS, or AAAI, or as EDA novelty to target DAC.
- Treat USENIX ATC as historical after ATC '25, not as an active submission target. Refresh
  the selected venue's current official CFP, author guide, and review guidance each round.

Engineering boundaries:

- Keep workflow control, path permissions, hashes, and stop conditions in Python, not only
  in prompts.
- Agent-generated files must pass the orchestrator's allowlist and be promoted from a
  round transaction; direct main-workspace changes are quarantined and restored.
- Do not execute model-generated shell commands. Only user-supplied check/run commands may
  be executed by the orchestrator. Conversation rounds use named commands pre-authorized
  in `autoresearch.yaml`.
- Keep provider adapters small and optional; skills must remain vendor-neutral.

Verification:

```bash
python -m pytest
python -m build
python -m autoresearch skills list
```
