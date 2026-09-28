# ResearchOS V0

ResearchOS adds a cross-project catalog to NextBrain. AutoResearch remains the execution
engine. Install with `python -m pip install .`; both `researchos` and `autoresearch` are
included. Python 3.11 or newer is required. No new runtime dependency is added beyond PyYAML.

## Scope

V0 supports plan ingestion, recorded human decisions, resumable project creation, contract
review, hypotheses, claims, immutable experiment specifications with dependencies, imported
run reports, findings, content-addressed artifacts, and machine inventory. It does not
schedule jobs, run experiment commands, promote work between GPUs, or merge candidate code.

The catalog defaults to `~/.local/share/researchos`. Use `RESEARCHOS_HOME` or the global
`--home PATH` option to select a different catalog. Keep this directory on a local filesystem.
SQLite is shared by projects; each project has its own AutoResearch workspace under
`<home>/projects/<project-id>/`. Private source snapshots and SSH inventory should not be
committed to Git. `.researchos/` is ignored for users who keep a local catalog in a checkout.
Back up the whole catalog, including `projects/` and `artifacts/`, while no command is writing.

## 1. Scan without approving

```bash
researchos scan --plans /path/to/Ideas/Research-Map/plans --source-root /path/to/Ideas
researchos inbox
```

Preferred plan format:

```yaml
---
idea_id: B-04
title: Quantization-aware graph search
---
```

A Markdown decision packet can contain multiple ``## 1. `B-04` Title`` sections. The scanner
also reads each candidate's Obsidian full-plan links from overview table rows. Linked
Markdown is included in the immutable source snapshot only when it stays under
`--source-root`. Links outside the root or missing on disk are recorded as unresolved;
execution readiness remains blocked. Linking is one level deep, not a recursive vault crawl.

Plain Markdown with an H1 gets a relative-path-derived ID. Add explicit `idea_id` frontmatter
if identity must survive renames. Duplicate IDs reject the whole scan. Content changes create
new revisions; scans never interpret upstream `pursue` labels as GO and never modify source
files. Previously approved snapshots and decisions remain intact. V0 does not automatically
archive candidates whose source files disappear.

## 2. Human Gate #1

```bash
researchos decide B-04 GO --by human --reason 'Investigate the prerequisite first'
researchos decide B-07 HOLD --by human --reason 'Waiting for workload access'
researchos decide B-09 DROP --by human --reason 'Outside current scope'
researchos decide B-03 NEEDS_WORK --by human --reason 'Define a measurable kill criterion'
```

Only GO creates a project. The result includes its ID. Repeating the same decision is
idempotent. HOLD/DROP/NEEDS_WORK pause an existing project without deleting its evidence.
A later GO can resume the same approved source revision; changed source requires a separate
revision workflow, which V0 deliberately does not automate.

Project creation first reserves a `PROVISIONING` database record, then materializes
`SOURCE_IDEA.md`, `RESEARCH_CONTRACT.md`, and an ordinary AutoResearch workspace. Only after
these succeed does it become `ACTIVE`. Repeat the same GO after an interrupted creation;
existing files are preserved and a modified source snapshot is rejected. ACTIVE means
admitted for refinement, not permitted to execute unrestricted experiments.

`--by` and `--reason` are audit fields in a single-user CLI, not an authentication system.
An agent must not invent a human approval; recording GO requires the user's actual decision.

## 3. Contract review

Fill in the project's `RESEARCH_CONTRACT.md`. Required fields include the question, claim,
baselines, variables, success/falsification conditions, an explicit abandonment result,
positive GPU-hour budget, target venue and contribution type. Placeholders do not pass.
These validators check structure; a human must judge scientific meaning and venue fit.
Refresh official venue guidance when actually conducting a venue-dependent research round.

```bash
researchos contract check PROJECT_ID
researchos contract approve PROJECT_ID --digest REVIEWED_SHA256 --by human --reason 'Reviewed'
```

GO and contract approval are separate. The authoritative approval is the database receipt
bound to the exact file hash; YAML approval flags cannot grant permission. Any file edit
invalidates the old approval. This contract is an intake specification. `paper/STORY.md`
remains the sole frozen scientific contract used by AutoResearch execution. ResearchOS never
updates that file or its freezes as a side effect of a catalog decision.

## 4. Hypotheses, experiments and findings

Use `researchos hypothesis|claim|experiment|run|finding add --project ID --file record.yaml`.
Each has a corresponding `list --project ID` command. IDs are unique within a record type
across the catalog; use project prefixes when needed. Records are append-only: identical
retries succeed, while changed content under an existing ID is rejected.

Example hypothesis:

```yaml
id: P1-H1
statement: The trace contains enough reuse to justify caching.
falsification_condition: Fewer than 5% of requests reuse eligible objects.
```

Example experiment specification (illustrative prediction, not a measured result):

```yaml
id: P1-E1
hypothesis_id: P1-H1
claim_ids: []
priority: 1
dependencies: []
estimated_runtime: 60s
resource_requirement: {gpu_model: RTX 4060, gpu_count: 1}
command_name: reuse-smoke
prediction: {reuse_fraction: '10–20%'}
metrics: [reuse_fraction]
success_condition: reuse_fraction > 5%
failure_condition: reuse_fraction <= 5%
expected_artifacts: [experiments/results/reuse.json]
```

Dependencies must reference existing experiments in the same project. Immutable nodes may
only depend on previously registered nodes, which prevents cycles. A changed protocol gets
a new experiment ID. Command names refer to human-authorized `experiment-loop` entries in the
project's `autoresearch.yaml`. Shell strings are rejected and no catalog command executes them.

```bash
researchos experiment ready P1-E1
researchos context PROJECT_ID
```

Readiness checks the active project, approved current contract, intact source snapshot,
source revision, authorized command and dependencies. `specification_ready` is only a
structural preparation check. It is not a smoke-test pass, hardware compatibility check,
budget reservation, or permission to bypass engine freezes. Remote execution is always
reported disabled in V0. Dependency completion requires executor-verified evidence; manually
imported PASS records do not automatically authorize successors.

A run report needs `id`, `experiment_id`, `status` (PASS/FAIL/INTERESTING/ERROR),
`provenance: manual-import`, `observed`, and `environment`. ResearchOS copies the experiment
prediction and protocol digest into the run, separately from observed values. V0 cannot
prove an imported prediction predates execution and labels every imported run UNVERIFIED.

```bash
researchos run add --project PROJECT_ID --file run.yaml
researchos artifact --run RUN_ID --file /path/to/result.json
```

Artifacts are copied to content-addressed storage with SHA-256 digests. A finding needs:

```yaml
id: P1-F1
experiment_id: P1-E1
run_ids: [P1-R1]
observation: Reuse was below the threshold in the imported trace.
magnitude: '2% (illustrative example)'
confidence: One imported trace; not independently verified.
supports: []
contradicts: []
unexpected: true
next_questions: [Does the production workload have a different reuse distribution?]
```

Finding claim links and run links must belong to the same project; run links must also match
the experiment. A contradiction records the evidence and sets the project to NEEDS_REVIEW.
Findings without evidence remain UNVERIFIED. Failure evidence is retained. `context` returns
the contract, hypotheses, claims, full experiment catalog, runs and all findings together.

## 5. Handoff to AutoResearch

S1–S4 can remain external. Prepare a schema-valid `idea-story` document (see
[contracts](contracts.md)) with a selected candidate. After reviewing that exact document:

```bash
researchos handoff PROJECT_ID --story /path/to/reviewed-story.md \
  --digest REVIEWED_STORY_SHA256 --by human --reason 'Accepted external S1–S4 review'
```

Handoff requires the current ResearchOS contract approval and unchanged approved source. The
engine's external-admission API validates the story, stages and promotes it with its existing
transaction allowlist, journals the explicit approval, and records the source/contract hashes.
Only an unused workspace can be admitted. It marks the idea origin as external human admission;
it does not fabricate scout/challenger rounds, freeze the story, or unlock implementation.
The existing story-freeze draft plus later exact-hash approval remains mandatory.

Continue using the normal AutoResearch host workflow in that project's workspace. A catalog
approval is never a replacement for `paper/STORY.md` approval, core-code freeze, authorized
check receipts or experiment protocol digests. Do not edit the intake contract to silently
revise an already frozen research story; changes require a separate human-reviewed revision.

## 6. Machine discovery

```bash
researchos ssh import --config ~/.ssh/config
researchos ssh list
researchos ssh probe GPU_ALIAS
researchos status
```

Import parses literal aliases and Includes locally, ignores wildcard-only entries and makes
no connection. Probe uses the existing alias and a fixed read-only inventory script for
hostname, GPUs/memory/driver, CUDA, Python, disk, Git, Docker and working directories.
It records success and failures. GPU identity comes from `nvidia-smi`, never alias names.

Probes are noninteractive, time-limited, and retain strict host-key checking. They do not
install software, delete experiments, copy credentials or update known hosts. V0 direct
probing disables proxy commands/jumps, forwarding, multiplexing and local commands; configs
with `Match exec` are rejected. Bastion-dependent machines need a future reviewed transport
adapter or a dedicated static config. Resolve changed host keys through a trusted channel;
do not disable checking to make a probe pass.

## Schema and next milestone

Schema version 1 uses `ideas`, `revisions`, `decisions`, `projects`, `approvals`, `hypotheses`,
`claims`, `experiments`, `dependencies`, `runs`, `artifacts`, `findings`, `machines`, and `probes`.
Foreign keys are enabled on every connection. Unsupported future schema versions are rejected.

V0.1 should add one isolated 4060 execution with a prediction recorded before dispatch,
executor receipts, artifact verification and interruption recovery. Then add resource/budget
reservations, A6000 promotion, replication and stop rules. Core changes return to the
implementation freeze workflow; scientific changes return to the human. A worktree alone
is not a scientific approval mechanism.
