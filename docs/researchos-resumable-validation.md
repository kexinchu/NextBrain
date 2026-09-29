# Resumable execution: implementation and validation

Validated September 28, 2026. Base: merged `origin/master` at `81f39f2` (PR #2).
Branch: `codex/researchos-resumable-run`. Work was isolated from the original checkout's
37 pre-existing changed files. Package version remains 0.4.0; this is not a release.

## 1. Architecture

Project Envelope approval authorizes a research boundary. A per-experiment immutable
snapshot authorizes exact execution. A durable Run precedes dispatch. The small local/SSH
transport runs the same dependency-free supervisor. Evidence collection and numeric
interpretation are separate from process success. No autonomous multi-run S7 loop was added.

## 2. Schema

SQLite v1 migrates additively to v2. New tables: `envelopes`, `project_envelopes`,
`object_approvals`, `scope_requests`, `hypothesis_states`, `experiment_freezes`, `executions`,
`run_attempts`, `run_events`, `policy_decisions`, `findings_from_runs`, `artifact_origins`.
Legacy rows remain intact. SQL triggers prevent changing snapshot rows and run identity.
Approval receipts bind exact messages and hashes to object versions.

## 3. Files

Added `src/researchos/{schema,policy,freeze,execution,transport,worker,next_experiment}.py`,
`tests/test_resumable_runs.py`, the execution guide and this report. Updated the service,
store, CLI, one superseded legacy test assertion, README and AGENTS guidance. The current
user instruction is appended to the immutable requirement journal and mirrored topic.
No source modules were deleted wholesale.

## 4. Obsolete paths

Removed the generic imported-Finding contradiction → project NEEDS_REVIEW transition.
The new executor no longer requires a paper-first contract/STORY freeze. Old contract,
handoff, manual import and AutoResearch paper workflows remain compatibility paths;
the documentation distinguishes their constraints. This avoids migrating old records by
silently treating them as verified executor evidence.

## 5. Run states

`CREATED → PREPARING → DISPATCHED → RUNNING → COLLECTING → SUCCEEDED`, with operational
`FAILED_RETRYABLE`, `FAILED_FINAL`, `TIMED_OUT`, `CANCELLED`, and uncertain `LOST` branches.
Transition checks, per-run locks, durable receipts and audit events enforce the lifecycle.
Retries are explicit attempts of the same Run and frozen experiment, within its fixed cap.

## 6. Scientific states

Only successful executions with collected evidence are interpreted. Numeric frozen rules
produce SUPPORTED, FALSIFIED or INCONCLUSIVE. Falsification closes that hypothesis;
project-level stopping requires an explicit approved critical-stop policy. Scope changes
require explicit versioned approval and a revised envelope. Operational failures produce
no falsification. Missing data remains inconclusive; identical protocol repeats are blocked.

## 7. Recovery

Recovery reconciles the same remote job and process-held supervisor lock. Lost SSH responses
do not cause duplicate launch. A confirmed unstarted attempt is sealed before retry, making
late requests harmless. Uncertain liveness retains LOST and budget. Interrupted transfers
resume collection without rerunning. Partial evidence can be snapshotted while liveness is
uncertain, but cannot be used to infer scientific support.

## 8. Timeout and budgets

The worker terminates process groups on timeout/cancel/disk limit. Artifact transfer has a
strict byte cap, including truncated logs. Disk use is polled rather than enforced by an OS
quota. Creation atomically reserves worst-case timeout × devices × allowed attempts within
the approved project budget; reservations are conservatively retained, including lost runs.
CPU units are wall-clock job-hours. Exhausted retries cannot be reset with a new Run for the
same specification. These limits are not an adversarial sandbox or a cluster-wide scheduler.

## 9. Artifacts and findings

SHA-256 checked content-addressed artifacts preserve attempt/path origins, log diagnostics,
environment, receipts and expected results. GPU execution records an initial utilization
and memory sample when available. Findings retain measurement, inference, outcome,
confidence explanation, supports/falsifies, unexpected flag, next questions, and prediction
versus observation. Confidence is bounded explanatory text, not a statistical estimate.

## 10. Resource choice and next experiment

CPU prefers local. GPU selection chooses the smallest inventoried device satisfying memory
and count; larger work may go directly to A6000. The 4060 is not a mandatory stage.
`next` returns one ranked existing candidate with uncertainty, prediction, criteria, cost,
dependencies, selected capability and blockers. It does not execute. GPU exclusivity is
limited to this catalog; independent jobs/catalogs can still contend for the same devices.

## 11. Verification

- `python -m pytest -q`: **84 passed**, including 28 new lifecycle/policy tests.
- `python -m ruff check .`: passed.
- `python -m build`: wheel and source distribution built successfully.
- `autoresearch doctor --release`: passed from the installed wheel outside the repository.
- `python -m autoresearch skills list`: passed.
- Installed-wheel `researchos status` reports schema 2; `run --help` exposes all operations.
- `git diff --check`: passed.

The new tests cover all 17 requested categories, plus SQLite migration, interrupted artifact
transfer, revoked commands, supervisor loss, cancellation, explicit critical-stop policy,
baseline/discrimination gates, delayed launch sealing, OOM semantics, partial snapshot
collection, capped truncated logs and exhausted-retry bypass prevention. Local execution
tests use real subprocesses; transport failures are injected around the same executor.

## 12. Server validation

A fresh cloudsys01 inventory reported Python 3.10.12, two RTX A6000 devices with 49140 MiB
each, driver 610.57.04 and CUDA compiler 11.5. A tiny isolated **CPU-only synthetic fixture**
was launched through real SSH. The test discarded the successful launch response, then
recovered the original job. The final worker produced:

- Run: `RUN-d72b093dfaeb4f12ad5e728480bed04f`.
- Observed states: `LOST → RUNNING → SUCCEEDED`.
- Exactly one start marker; no duplicate execution.
- Seven collected, hash-verified artifacts.
- Synthetic outcome SUPPORTED, explicitly not a research result.
- Code commit: `945e1defd16df8eb623b25976c63b3ca7b56edd5`.
- Experiment digest: `756d870a7b191d2b8d9d71032dfd325561a3452977052f18825b888ff58eda76`.
- Remote supervisor/child PIDs: 2620085 / 2620089.
- Isolated remote directory: `~/.local/share/researchos-executor/RUN-d72b093dfaeb4f12ad5e728480bed04f-attempt-0`.

Two earlier iterations of this same validation also succeeded in separate isolated
directories. No server dependencies, credentials, existing experiments or GPU allocations
were changed. This verifies SSH process recovery and collection; GPU execution itself has
not been validated. Detailed local validation receipt: `/private/tmp/resumable-server-validation-verified/report.json`.

## 13. 4060 connectivity

`kexin-server` resolves through the existing SSH configuration to `kexin@192.168.50.2`.
The fresh connection attempt failed with **No route to host**. No claim of 4060 execution
is made. Restore the LAN/VPN route and repeat `researchos ssh probe kexin-server` before
using it; changing authentication cannot repair this routing failure.

## 14. GitHub delivery

The focused branch is delivered as a PR against master. The final response contains its
URL. No automatic merge is performed. Required GitHub checks should pass before merge.

## 15. Next milestone

Restore 4060 reachability, approve one real research envelope and discriminating protocol,
then run one bounded experiment with evidence recovery. Use A6000 directly when the frozen
requirements exceed 4060 capacity; otherwise replicate/promote only after interpreting the
first run. Implement bounded S7 automation after that real single-run path is reliable.

Remaining limits: trusted single-user approval attribution, Python-minimum-only environment
validation, committed-file data snapshots, no remote dependency provisioning, no statistical
confidence engine, no global GPU scheduler and no interpretation of arbitrary prose stops.
