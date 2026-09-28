---
name: experiment-loop
description: Execute every frozen experiment-matrix cell in staging, preserve provenance, and force a report on contradictions.
version: 0.4.0
model: inherit
---

# Experiment loop

Use the current conversation model; never call another model API or `autoresearch run`.
Record the exact user instruction and begin an `experimenter` round bound to its latest
message file.

Read the prompt, frozen story, and frozen core code. Edit staged `experiments/scripts/` and
write new artifacts under staged `experiments/results/`. Existing results are read-only and
are not copied into the transaction. The paper and `code/core/` are never writable.

Run only a human-authorized command from `autoresearch.yaml` using
`autoresearch host check <round-id> <experiment-command-name>`. Preserve raw stdout,
stderr, failures, dataset/baseline/config/seed/scale/resource metadata, and source versions.
Do not extrapolate missing cells or turn local smoke evidence into a full-scale result.

The evidence manifest must list logical artifacts and `experiment_cells`. Every cell has
the exact frozen experiment ID, status (`completed`, `failed`, `skipped`, or
`contradiction`), result paths, configuration digest, claim IDs, and the SHA-256
`protocol_digest` of its canonical frozen experiment mapping. `satisfied` requires exact
coverage of all frozen experiment IDs plus a successful authorized command whose workspace
digest matches the final staged contents. Any `contradiction` forces `report`; identify the
frozen claim, prediction, observation, confounders checked, and required human decision.
Never edit the paper or core code to make results agree.
