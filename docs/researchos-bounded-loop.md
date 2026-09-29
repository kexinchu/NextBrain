# ResearchOS V0.2: bounded research planning

V0.2 adds a planner and coordinator above the existing frozen-experiment executor.
It does not replace execution, SSH recovery, named-command authorization, evidence hashing
or per-run retry limits. The package version remains 0.4.0; V0.2 names the ResearchOS milestone.

## Control flow

```text
Approved Project Envelope + durable evidence
                 ↓
Bounded research context (maximum 64 KiB)
                 ↓
ResearchReasoner → validated candidate proposals
                 ↓
Deterministic scope / dependency / resource / budget checks
                 ↓
Heuristic information-per-cost selection + durable Planner Decision
                 ↓
Freeze one experiment → existing Runs executor → Finding
                 ↓
Update uncertainty / hypothesis / confidence → controller decision
                 ↓
Re-plan from durable state, even at the final max-runs boundary
```

Research reasoning and policy are separate. The `ResearchReasoner.propose(context)` Python
interface can supply a new bounded proposal bundle each round. No model provider or API key
is required. The CLI's default `StoredReasoner` uses the latest schema-validated proposal
pool supplied by a human or conversation agent. It reevaluates eligibility and scores after
every result; it does not invent new research ideas or autonomously call an LLM. When that
pool cannot resolve the remaining question, execution stops for another proposal or review.
This is bounded autonomy over supplied research reasoning, not an unlimited autonomous scientist.

## Research state and memory

Hypothesis states are PROPOSED, ACTIVE, SUPPORTED, FALSIFIED, INCONCLUSIVE and BLOCKED.
New hypotheses default to PROPOSED; explicit initial lifecycle states are validated. Confidence
is separate: PRELIMINARY, REPLICATED or ROBUST, never a fabricated probability. Executor
failure changes no scientific belief. Falsification closes the affected branch and permits
other branches, unless an already approved project-level stop policy applies.

Uncertainties have OPEN, REDUCED, RESOLVED or BLOCKED states. Add one explicitly:

```yaml
id: U17
question: Does realistic prediction error erase the proposed benefit?
related_hypotheses: [H2, H3]
importance: HIGH
why_it_matters: The mechanism is impractical if benefit disappears at realistic error rates.
current_evidence: []
status: OPEN
threats_to_validity: [Workload representativeness]
```

```bash
researchos uncertainty add PROJECT --file uncertainty.yaml
researchos uncertainty list PROJECT
researchos planner context PROJECT
```

The context includes the approved envelope, all hypothesis evidence counts, bounded supporting
and contradicting Finding references, relevant recent Findings, claims, experiment dependencies,
operational failures, machine capabilities and remaining budget. Detailed lists start at 80
records and shrink to fit 64 KiB. Truncation is explicit. Earlier evidence still contributes to
hypothesis aggregates and the full research-state digest. Oversized irreducible records require
human curation. The database, not conversation history, is the source of truth.

## Candidate reasoning schema

`planner import PROJECT --file proposals.json` validates the whole bundle before persisting
it. The top level has exactly `reasoning_summary` and `candidates`. A pool has at most 16
candidates and at most four per uncertainty. Normally supply two to four alternatives for
an uncertainty; a singleton is allowed when only one justified option exists. The reasoning
summary should explain that restriction. No proposal may modify an envelope or approval.

Every candidate requires:

| Field | Meaning |
|---|---|
| `candidate_id`, `uncertainty_id`, `hypothesis_ids` | Valid project-local references |
| `question`, `expected_information`, `risk` | Research reasoning in plain text |
| `experiment_type` | MOTIVATION, FEASIBILITY, MECHANISM, DISCRIMINATION, PRIMARY, REPLICATION, SENSITIVITY, ABLATION, STRESS |
| `mode` | EXPLORATION or OPTIMIZATION |
| `possible_outcomes` | Interpretations for SUPPORTED, FALSIFIED, INCONCLUSIVE, OPERATIONAL_FAILURE |
| `estimated_cost` | Estimated normalized device/job minutes, not a monetary cost |
| `discrimination_power`, `expected_information_gain`, `feasibility` | Heuristic weights in (0, 1], not probabilities |
| `spec` | Existing V0.1 experiment fields plus explicit `evidence_kind` |
| `repo` | Absolute path to the clean local Git source repository |
| `machine` | Optional explicit alias affinity, otherwise null for smallest-fitting selection |
| `replication_of` | Original successful Run ID, otherwise null |

Each possible outcome has `interpretation` text and `uncertainty_status`. Scientific outcomes
may choose OPEN, REDUCED or RESOLVED; OPERATIONAL_FAILURE must use UNCHANGED. These interpretations
are frozen with the experiment before execution. The numeric protocol still determines the
scientific outcome; prose cannot overwrite measured comparisons.

The experiment `spec` reuses the [single-run schema](researchos-execution.md). Candidate IDs
and experiment IDs must be unique. Dependencies must already be registered experiments.
Only named commands authorized in `autoresearch.yaml` can execute. Candidate import neither
registers nor freezes the experiments; only the selected candidate is registered and frozen.
See [the executable validation example](../examples/validate_bounded_loop.py) for a complete
valid bundle. Its proposals are clearly labeled system fixtures.

## Selection and audit

```bash
researchos next PROJECT
researchos planner decisions PROJECT
```

`next` executes nothing. It creates a durable decision with context and digest, selected
uncertainty, competing candidates, component scores, rejected candidates and reasons, scope
checks and budget snapshot. The score is:

```text
importance × discrimination × expected information × feasibility × type weight
÷ max(estimated cost, timeout × devices × allowed attempts)
```

Costs are normalized to minutes. MECHANISM, DISCRIMINATION and REPLICATION get a modest 1.2
weight; others get 1. Optimization is blocked until a hypothesis has replicated support.
These values are an inspectable planning heuristic, not statistically calibrated information
gain. A human or reasoner supplies the scientific judgments; deterministic code enforces
permissions. Scope checks enforce declared fields/classes/baselines; they cannot prove the
semantic truth of arbitrary prose. Research review remains necessary.

The full state digest includes evidence, hypotheses, proposals, project/source revision,
approvals, machine inventory and named-command configuration, including records omitted from
the compact context. A stale decision cannot be admitted. Registration changes durable state,
so the coordinator re-plans and confirms the same selection after freezing, before creating a
Run. Pending Human Gate #2 review blocks readiness even when research evidence is unchanged.

## Bounded execution and recovery

```bash
researchos advance PROJECT                         # default max-runs=1, max-wall-time=1h
researchos advance PROJECT --max-runs 3 --max-wall-time 4h
researchos advance PROJECT --resume ADVANCE-ID
```

Bounds are 1–10 runs and a positive wall allowance up to 24 hours. Run timeout, retry limits,
project budgets, dependency evidence and scope approval remain enforced by V0.1. Runs execute
serially. The coordinator reserves enough remaining wall time for the next run and control
operations (2 seconds local, 90 seconds SSH headroom), checks again after preparation, and
bounds transport calls by the deadline. It never expands an existing advance's original
bounds on resume. CPU and GPU budget figures are conservative reservations, not measured
consumption, and remain charged after completion or failure.

The advance ID, deadline, planner decisions and linked runs are durable before dispatch.
LOST jobs produce RECOVERY_REQUIRED; no replacement is launched. Resume inspects the same
job through V0.1. Other unowned active runs block new advances. A crash between Run creation
and coordinator linking leaves an unowned CREATED run requiring explicit recovery/cancellation;
it cannot silently create a duplicate. Automatic retries are not added by the coordinator:
operational failure stops it, preserving the existing explicit `run retry` policy.

At a deadline, the coordinator requests cancellation and retains any outstanding job for
recovery. A small transport/cancellation handoff delay is possible; the worker's frozen
per-run timeout is independent of the coordinator. An unavailable host can prevent immediate
cancellation confirmation. This is reported as RECOVERY_REQUIRED, never as confirmed termination.
ResearchReasoner adapters are trusted application code and must implement their own bounded
provider calls; Python does not sandbox or preempt arbitrary adapter code.

## Controller, replication and confidence

After each completed run, a durable controller record returns CONTINUE, STOP_HYPOTHESIS,
STOP_PROJECT, ESCALATE_HUMAN or REPLICATE. Negative in-scope evidence does not automatically
open a human gate. A recommendation to stop the whole project, exhausted budget or necessary
scope change produces an explicit review. Stop recommendations do not silently pivot a project.

Promising scientific support starts as PRELIMINARY and requests replication. Supply a new
REPLICATION candidate referring to its original Run; it must test the same hypothesis and
numeric rules. Actual frozen command arguments, hashed inputs or machine must differ for it
to count as independent. Merely changing a declared seed label or waiting and rerunning the
same command is insufficient. A distinct execution configuration is evidence of variation,
not proof that the scientific experiment is causally independent; the human gate reviews that.

Independent positive replication promotes confidence to REPLICATED. Repeated identical
replication configurations do not increment the independent count. Confidence policy can be
set in the approved envelope:

```yaml
maturity_policy:
  independent_replications: 1  # integer 1–5
  allow_robust: false
```

ROBUST additionally requires positive sensitivity and ablation evidence and declared hashed
baselines, and must be explicitly enabled. Contradicting Findings remain visible and close
the hypothesis despite later positive evidence. Findings and assessments retain original/
replication Run links, variation and confidence basis. Machine promotion remains resource-driven;
4060 is never a mandatory predecessor to A6000.

## Human Gate #2 and paper workflow

```bash
researchos gate review PROJECT
# Human reviews the returned summary and digest, then supplies a message containing:
# APPROVE gate:FREEZE_STORY FULL-DIGEST
researchos gate approve GATE-ID --digest FULL-DIGEST --decision FREEZE_STORY \
  --message-file human-approval.txt --by reviewer
```

Actions are CONTINUE, STOP, PIVOT and FREEZE_STORY. The summary contains the original question,
hypothesis graph, Findings, replication, unexpected results, remaining uncertainties, compute
reservations/remaining budget, validity threats and suggested action. Approval binds the exact
summary and current research state. Stale evidence requires a new review. PIVOT opens a scope
request; it does not rewrite the envelope. FREEZE_STORY requires replicated scientific evidence
and only authorizes the existing paper workflow. It never writes or freezes `paper/STORY.md`.

An enabled ResearchOS project carries `.autoresearch/researchos.json`. Both `story-freeze`
round admission and the shared paper freeze primitive check the current Gate #2 approval.
The explicit ResearchOS handoff checks it too. Standalone legacy AutoResearch workspaces
without that marker retain their established contract workflow. Approval attribution still
assumes a trusted single-user account, as in V0.1.

## Synthetic evidence and server safety

Every planner candidate declares `evidence_kind: SCIENTIFIC` or `SYSTEM_VALIDATION`.
Validation Findings retain metrics and outcomes but never change scientific hypothesis or
uncertainty state, satisfy scientific dependencies, acquire scientific confidence or authorize
paper freezing. Explicit labels cannot detect a maliciously mislabeled dataset; fixture authors
must classify inputs correctly. The provided validation script always uses SYSTEM_VALIDATION.

SSH probing now records free VRAM and disk. Hosts below 1 GiB available disk are UNAVAILABLE;
missing disk evidence is INCOMPLETE. Neither state participates in selection. Before an advance
GPU dispatch, inventory is refreshed and selection rechecked. The worker verifies Python,
actual free/total GPU memory and free disk against the frozen allowance. Existing inventory
also records driver/CUDA and working-directory details; the source repository is a clean
hashed Git archive. No environment repair, dependency installation, credential changes,
trust changes, disk cleanup or output-directory redirection is performed. GPU resource
checks still do not provide cluster-wide exclusion or prove library compatibility.

## Reproducible infrastructure check

```bash
PYTHONPATH=src python examples/validate_bounded_loop.py \
  --root /tmp/unique-validation-directory --machine cloudsys01.engr.uconn.edu
```

This explicitly runs one tiny CPU job, then two more, then verifies budget rejection, no
duplicate starts, new Findings and plans, and unchanged scientific state. It requires a new
root directory and an existing reachable SSH alias. Omit `--machine` for local validation.
All output is **SYSTEM VALIDATION — NOT SCIENTIFIC EVIDENCE**.
