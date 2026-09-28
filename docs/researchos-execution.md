# ResearchOS: one resumable experiment

This is the execution path after V0. It uses the existing catalog, project workspaces,
SSH inventory and named command authorization. The control package requires Python 3.11+;
the dependency-free POSIX worker supports Python 3.10+. There is no autonomous run loop.

## Three different decisions

| Event | Run | Scientific state | Project |
|---|---|---|---|
| OOM, nonzero exit, disconnect, timeout | Operational failure or LOST | No inference | Remains ACTIVE |
| Valid measurement meets frozen falsification rule | SUCCEEDED | FALSIFIED; close hypothesis branch | Remains ACTIVE unless an explicitly approved critical-stop policy applies |
| Missing or ambiguous measurements | SUCCEEDED | INCONCLUSIVE | Revise protocol before repeating it |
| Proposed question, claim, architecture, baseline, scope or budget change | No new dispatch | Retain existing evidence | SCOPE_CHANGE_REQUESTED until revised approval |

A frozen paper claim is a later writing milestone. Early execution needs an approved
**Project Envelope** and an immutable **experiment snapshot**, not `paper/STORY.md`.
Legacy `autoresearch` paper workflows and V0 imported records remain available.
An imported PASS or manual Finding does not satisfy a verified execution dependency.

## Approve an envelope

After `scan` and a human `decide ... GO`, edit
`<home>/projects/<project-id>/PROJECT_ENVELOPE.md`. YAML front matter:

```yaml
schema_version: 1
project_id: PROJECT-ID
problem: Determine whether mechanism X reduces work on workload Y
boundary: Fixed workload and implementation family
resource_budget:
  gpu_hours: 2
  cpu_hours: 1
stop_conditions: [Budget exhausted, Repeated inconclusive evidence]
non_goals: [New architecture, Paper novelty claim]
allowed_experiment_classes: [feasibility, comparison]
allowed_baselines: []
```

Optional `claim` must have `claim_status: PROVISIONAL`. Optional
`stop_on_critical_falsification: true` stops the project when a hypothesis explicitly
marked critical is falsified. Free-text stops document human intent; only implemented
machine-readable policies (budget, timeout, dependencies, critical flag, protocol outcomes)
are automatically enforced. Arbitrary prose is not a policy interpreter.

```bash
researchos envelope check PROJECT-ID
# A human reviews the returned digest and supplies an approval message containing:
# APPROVE envelope FULL-DIGEST
researchos envelope approve PROJECT-ID --digest FULL-DIGEST \
  --message-file /path/to/human-approval.txt --by reviewer
```

Receipts preserve the exact message, its hash, object digest, actor and timestamp. `--by`
is attribution, not authentication. This is a trusted single-user CLI, not a cryptographic
human-identity system. Agents must not fabricate a human approval message. Semantic changes
to the envelope invalidate approval. For a scope change, use `scope request PROJECT-ID
--file request.yaml` (`category`, `reason` and `proposed_change`), approve its digest with a message containing
`APPROVE scope FULL-DIGEST`, then approve a revised envelope. Approving only the request
does not resume the project. Existing freezes must be revised for the new envelope digest.

## Freeze an experiment

Register a hypothesis, then an experiment with `hypothesis add` and `experiment add`
(`--project PROJECT-ID --file FILE`). Example experiment YAML:

```yaml
id: E1
hypothesis_id: H1
experiment_class: feasibility
prediction: {value: {min: 5, max: 10}}
metrics: [value]
success_condition: value >= 5
falsification_condition: value < 5
expected_artifacts: [metrics.json]
resource_requirement: {cpu_only: true, gpu_required: false, gpu_count: 0}
environment_requirement: {python_min: '3.10'}
command_name: measure
estimated_runtime: 10 seconds
dependencies: []
data: {identifiers: [], hashes: {}}
timeout: 30
budget: {gpu_hours: 0, cpu_hours: 0.008334, max_retries: 1}
protocol:
  metric_file: metrics.json
  baselines: []
  rules:
    - metric: value
      success: {op: '>=', value: 5}
      falsification: {op: '<', value: 5}
```

The project `autoresearch.yaml` must already authorize the named argv and timeout:

```yaml
version: 1
commands:
  measure:
    skill: experiment-loop
    argv: [python3, experiment.py]
    timeout: 30
```

```bash
researchos experiment freeze E1 --repo /path/to/clean/git/repo
researchos experiment ready E1
researchos next PROJECT-ID
```

Freeze refuses dirty/untracked code, submodules, symlink archives, undeclared metrics,
identical success/falsification predicates and unbacked baselines. Baseline names require
`protocol.baseline_artifacts` entries referencing committed files in `data.hashes`.
External dataset identifiers can be recorded, but automatic external data staging is not
implemented; executable hashed inputs must be in the committed archive. Only `python_min`
is supported as an environment constraint; unsupported constraints are rejected.

The snapshot binds the approved envelope, prediction, protocol, thresholds, code commit,
archive hash, worker hash, input hashes, argv, resources, timeout and budget. It is stored
under `<home>/frozen/<digest>/`; SQL triggers protect its immutable row. Repeating the same
freeze is idempotent. A changed experiment needs a new registered specification/ID.
`next` ranks eligible registered experiments by readiness and explicit priority, returns
one candidate with its uncertainty, cost, dependencies and gate status, and executes nothing.
It does not invent experiments or estimate information gain with an LLM.

## Run and recover

```bash
researchos run create E1                 # persists Run ID and reserves budget first
researchos run dispatch RUN-ID           # explicit single launch
researchos run status RUN-ID             # local durable view
researchos run recover RUN-ID            # inspect executor and resume collection
researchos run retry RUN-ID              # explicit, bounded operational retry
researchos run cancel RUN-ID
```

```text
CREATED -> PREPARING -> DISPATCHED -> RUNNING -> COLLECTING -> SUCCEEDED
                         |             |           |
                         +------------ LOST -------+  (inspect, never blind relaunch)
Operational terminals: FAILED_RETRYABLE, FAILED_FINAL, TIMED_OUT, CANCELLED
```

Each attempt has a stable executor job ID. Atomic launch claims prevent duplicates. The
remote supervisor owns a file lock and survives the SSH client; PID alone is not proof
of liveness. Receipts on both sides bind Run ID, experiment digest, machine, job directory,
PIDs, argv, code commit, start time, log paths and manifest path. A lost launch response is
reconciled against that same job. If an unstarted job can be confirmed, recovery first
seals the old launch claim so a delayed request cannot race a retry. Ambiguous or vanished
remote state remains LOST with its reservation; an orphan process is never assumed dead.
`recover` on CREATED never dispatches. Repeating `dispatch` never starts another attempt.

A retry keeps the same Run ID and experiment digest, increments the attempt, and requires
confirmed prior termination plus an available retry allowance. Timeout/cancellation and
uncertain liveness cannot be automatically retried. Exhausted retries also block creating
a fresh Run for the same specification; revise the experiment instead. A transfer failure stays COLLECTING;
recovery copies artifacts again without reexecuting the experiment. Partial evidence is
retained on failures and, when reachable, as immutable snapshots even under uncertain
supervisor liveness. No Finding is inferred from partial operational evidence.

## Resources and limits

`ssh import`, `ssh probe ALIAS` and `ssh list` manage the existing inventory. CPU-only work
prefers the local executor. GPU work selects the smallest inventoried device meeting
`gpu_count` and `min_vram_gb`; a large requirement can go directly to A6000. There is no
mandatory 4060 stage or automatic promotion. An unreachable GPU host is not replaced by
CPU for a GPU-required experiment. At dispatch, the worker checks actual selected GPU
capacity and restricts `CUDA_VISIBLE_DEVICES`.

The catalog reserves worst-case wall-clock GPU-hours (timeout × GPU count × all allowed
attempts), or wall-clock CPU job-hours, before launch. These conservative reservations are
not refunded, including failures and LOST runs. CPU job-hours are not summed core-hours.
An explicit envelope budget revision can grant more budget. GPU reservations coordinate
this catalog only; they do not exclude unrelated jobs or other independent catalogs.

Timeout terminates the job process group and collects bounded evidence. Disk use is polled
(default 256 MiB) and artifact transfer capped (default 8 MiB, maximum 64 MiB). These are
operational limits, not kernel quotas or protection against an adversarial executable.
Transient overshoot is possible. Named commands run with the user's OS permissions.
The worker does not install dependencies or create containers; the named executable must
already exist on the target. SSH uses existing static configuration and host keys, without
changing credentials or enabling forwarding.

## Evidence and findings

Collection checks artifact identity, bytes, size and SHA-256 before storing content-addressed
objects. Origins preserve Run ID, attempt and relative path; repeated collection is
idempotent. Logs, environment, receipt, an initial GPU utilization/memory sample when GPUs are requested, expected results and the manifest remain traceable.
Successful execution alone is not scientific support. The interpreter reads the frozen
numeric JSON metric file and applies the predeclared rules. Missing or ambiguous values
produce INCONCLUSIVE. Findings separate measurement from inference and include prediction
versus observation, unexpected-result flag where numeric intervals are available, evidence
hashes, supported/falsified hypotheses and a bounded confidence explanation. This does not
estimate statistical confidence or scientific novelty.

Keep the full catalog on one local filesystem and back it up when idle. Schema v1 migrates
additively to v2. Operational events, attempts, approval messages and policy decisions are
retained; legacy data is preserved. See [validation](researchos-resumable-validation.md).
