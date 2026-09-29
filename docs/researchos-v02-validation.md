# ResearchOS V0.2 validation and delivery

Base: current master `78e6d81`, after merged PR #3. Branch:
`codex/researchos-bounded-loop`. Development used an isolated clean worktree; the original
checkout's 37 pre-existing changes were preserved. Initial master checks passed: 84 tests,
Ruff, package build and release doctor. Validation took place September 28–29, 2026.

## Delivered architecture

Four new modules provide the upper layer:

- `research_state.py`: explicit uncertainties and compact evidence-derived context.
- `planner.py`: strict proposal validation, pluggable research reasoning, deterministic
  admission/scoring, durable decisions and stale-state rejection.
- `controller.py`: ordinal confidence, replication lineage, stop/continue decisions and
  Human Gate #2 review/approval.
- `advance.py`: persisted, sequential, bounded coordination over the V0.1 executor.

SQLite v3 adds uncertainties, proposal/decision records, research assessments, controller
decisions, maturity gates, advances and Run associations. Existing catalogs migrate additively.
New hypotheses get explicit PROPOSED state; confidence remains separate. Possible-outcome
interpretations and the scientific/validation evidence label are frozen before execution.

The executor remains authoritative for subprocesses, receipts, retries, recovery and artifact
integrity. Integration adds a deadline-aware transport timeout, scientific isolation for
validation Findings, fresh GPU/disk admission checks and one concurrency fix: inspection now
rereads terminal state when the supervisor finishes between the initial state read and its
liveness check. This prevents a completed short task from being misclassified as LOST.

## Verification

Final verification:

- **121 tests passed**, including 37 V0.2 tests; all 84 baseline tests remain passing.
- Ruff and `git diff --check` passed.
- Source archive and wheel built successfully.
- Installed-wheel CLI acceptance passed outside the source tree: one run, then two runs,
  then budget rejection, with no duplicate jobs and no scientific state changes.
- Installed-wheel `autoresearch doctor --release` passed; skill listing passed.

The deterministic suite covers the 27 requested categories and additional failure boundaries:

| Requirement | Coverage |
|---|---|
| Findings Memory and changing state digest | Multiple Findings, older evidence aggregates and explicit context truncation |
| Closed branches and exploration priority | Falsified hypotheses excluded; premature optimization rejected |
| Validated agent output | Missing outcomes, unknown envelope fields, NaN scores and operational reinterpretation rejected before persistence |
| Scope/budget/dependencies/resources | Claim and architecture changes, unsupported dependencies, exhausted budgets, smallest valid GPU and offline 4060 fallback |
| `next` is non-executing | Durable audit with no Run created |
| Default and multi-run bounds | Default one, maximum three from four candidates, fresh reasoning after every result |
| Negative versus operational evidence | Other hypothesis branches continue; executor failure leaves scientific belief unchanged |
| Replication and confidence | Single positive asks for replication; identical execution is not independent; distinct configuration can trigger Gate #2 |
| Human gates and downstream paper | Scope/maturity review, stale decisions, pending-gate readiness, direct paper freeze and story-round admission checks |
| Synthetic isolation | Validation Findings cannot change scientific hypotheses, resolve uncertainty or authorize paper freezing |
| Coordinator recovery | Resume same linked job without duplicates; original deadlines/run limits cannot expand |
| Extra boundaries | Low disk unavailable, transport deadline per call, frozen outcome mappings, terminal-inspection race, missing proposals do not imply project stop |

An executable CLI acceptance fixture is checked in at
[`examples/validate_bounded_loop.py`](../examples/validate_bounded_loop.py). It exercises
`uncertainty add → planner import → next → advance → freeze → run → collect → Finding → re-plan`,
then verifies two-run and budget bounds. It also runs against an installed wheel outside the
source tree, avoiding accidental source-import success.

## Real SSH validation

**SYSTEM VALIDATION — NOT SCIENTIFIC EVIDENCE.**

Fresh cloudsys01 inventory:

- Python 3.10.12.
- Two RTX A6000 devices, 49140 MiB total each; sampled free memory 47951 / 47889 MiB.
- Driver 610.57.04; nvidia-smi CUDA UMD 13.3; nvcc compiler 11.5. These are distinct version
  reports, not a claim that arbitrary ML dependencies are compatible.
- About 485.8 GB available disk at probe time.
- Existing SSH configuration and host trust were reused without changes.

The remote validation ran only tiny CPU fixtures in newly allocated executor directories:

1. Default `advance` created exactly one run.
2. `advance --max-runs 2` created exactly two additional runs.
3. A further bounded advance created zero runs because the project budget was exhausted.
4. Every collected start marker contained exactly one `x`; no duplicate execution occurred.
5. Three Findings and ten Planner Decisions were recorded, including post-Finding replanning.
6. Conservative CPU reservation increased to 0.0083333333 job-hours; remaining allowance
   reached zero. This is the frozen timeout allowance, not measured CPU consumption.
7. Scientific hypothesis state remained PROPOSED. No GPU computation was requested.

Remote validation Run IDs:

```text
RUN-45881bbb21a544a194a77a573b853b12
RUN-a1f56af177b84235a1002d78796aa57e
RUN-3e86d29598354f6299a6bd84e25d06f2
```

Local receipt bundle: `/private/tmp/researchos-v02-remote-validation/report.json`.
The fixture uses frozen, clean Git source and the same named command for each isolated run.
The repeated commands intentionally test infrastructure; they are not independent scientific
replications. No server software, existing experiments, SSH credentials, known_hosts or
storage contents were repaired or cleaned.

4060 (`kexin-server`, `kexin@192.168.50.2`) was not required or used. The prior `No route to host`
condition was not re-probed during this milestone, so current 4060 reachability is unverified.
cloudsys02 was not used or cleaned. Its historical disk issue is addressed by a tested
unavailability rule, not by assuming the disk has recovered.

## Human gate and cleanup

No real research envelope, pivot, paper claim or STORY freeze was approved by these tests.
Approvals generated by fixtures are explicitly scoped to synthetic infrastructure validation.
Human Gate #2 actions require exact digest-bound messages; no automatic Git merge is added.

See [legacy classification](researchos-legacy-classification.md). The evidence, journal,
transaction, alignment, hashing, freeze and paper-workflow components remain reusable. No
complete module was deleted because active dependencies remain. The old `next` output is a
deprecated compatibility path for projects that have not registered uncertainties.

## Practical limits and next step

The default CLI uses the latest validated human/agent proposal pool. A Python reasoning adapter
can generate new candidates from each fresh context; no hidden LLM call or provider-specific
SDK is installed. Exhausted proposals pause the loop for new reasoning, rather than inventing
claims or expanding scope. Heuristic scores and configuration-based replication independence
are transparent aids, not guarantees of scientific quality.

Budgets remain conservative reservations, disk enforcement is polled, remote libraries are not
provisioned, and independent catalogs can contend for a GPU. A lost host may prevent immediate
cancellation confirmation. Uncertain work remains recoverable and never creates a replacement.

Next: review and merge the focused PR after CI, then approve a small real scientific envelope,
explicit uncertainty and two to four discriminating candidates. Validate one real workload and
its replication before raising run limits. Real GPU research and scientific discovery were not
part of this infrastructure validation.
