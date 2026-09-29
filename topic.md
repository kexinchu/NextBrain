# Research topic

## Direction

Systems and AI infrastructure research. Primary active targets are SOSP, FAST, OSDI,
EuroSys, and MLSys. Secondary targets are ICLR, NeurIPS (including the user's NIPS alias),
AAAI, and DAC when the scientific contribution fits those communities. USENIX ATC is kept
as historical comparison/style context because the conference ended after ATC '25; it is
not an active new-submission target.

## Scope and hard exclusions

- Add ideas that must not be rediscovered or rephrased.

## Resources and limits

- Compute budget:
- Time budget:
- Allowed data:

## Success and kill criteria

- Success:
- Kill:

## Session requirements

Requirements recorded through `autoresearch message` and `autoresearch run` are mirrored
below. The immutable source records remain under `requirements/messages/`.

### Session requirement 0001

<!-- autoresearch-message:0001-20260808T051800.798506Z.md -->
- Recorded at: `20260808T051800.798506Z`
- Source: `user`
- Immutable record: [`0001-20260808T051800.798506Z.md`](requirements/messages/0001-20260808T051800.798506Z.md)

我要把这个工作铲掉；然后帮助我重新写成一个auto-research 的repo；里面帮助我记录一下skills （要求可以直接通过pip 安装并调用）；当然过程中需要借鉴学习其他开源的优秀auto-research 工具；整体上计划将auto-research拆分成几个skills

原则：我跟agents说的话，都需要单独记录在一个md文档中，且每一轮都需要确认没有偏移

idea 寻找： 这是一个loop，包含两个sub-agents, 一个agents 按照指定的方向/topic 寻找有前景的idea，并且支持做一些motivation test； 另一个agent 专门challenge，评估idea的 scope 和 novelty （需要sample and efficient）；这两个agents 会交替执行 in loop，并且再遇到问题/拿到满意idea之后 停下loop向我汇报。 注意每一轮都需要访问我的需要（markdown文件，确保没有偏移）

论文故事冻结 skill：结合idea 和 人为干预，先写出初稿，将论文，设计，实验方案固定下来

实现 skills loop：这个过程中不允许修改论文；在确保论文主要故事线/设计不变的情况下，实现代码 + 小规模测试； 注意每一轮都需要阅读论文，确保没有走偏，但是也允许做一些支持性的探索，但是不允许修改idea和设计。完成之后冻结代码实现

Exp loop： 实验skiils，不允许修改论文 和 核心代码，仅允许修改一些脚本，按照论文批量执行实验，导出结论，当遇到结论跟论文不一致的时候，报告给我

写作 skills：按照某一个会议的要求（学习过去一年被接收的相关论文，学习写作风格，按章节的优化写作，这个时候纯优化写作，不允许篡改冻结的论文初稿，但是需要一章一章的优化写作）

审查 skill： 按照会议要求审核论文，给出审稿意见

### Session requirement 0002

<!-- autoresearch-message:0002-20260808T051801.363439Z.md -->
- Recorded at: `20260808T051801.363439Z`
- Source: `user`
- Immutable record: [`0002-20260808T051801.363439Z.md`](requirements/messages/0002-20260808T051801.363439Z.md)

研究方向/topic 指向一个md 文档，同时该文档也记录我在session中提出的要求

idea-loop 输出到一个story.md 文档，方便阅读 + 修改

### Session requirement 0003

<!-- autoresearch-message:0003-20260808T051801.527089Z.md -->
- Recorded at: `20260808T051801.527089Z`
- Source: `user`
- Immutable record: [`0003-20260808T051801.527089Z.md`](requirements/messages/0003-20260808T051801.527089Z.md)

注意这些skills 需要能够在GPT/Claude/cursor对话框中被使用，并且能够以它们的模型为后台模型

### Session requirement 0004

<!-- autoresearch-message:0004-20260808T053259.264853Z.md -->
- Recorded at: `20260808T053259.264853Z`
- Source: `user`
- Immutable record: [`0004-20260808T053259.264853Z.md`](requirements/messages/0004-20260808T053259.264853Z.md)

现在 分析 + 评估 Skill 的性能/能力，是否满足需要？是否需要优化？

### Session requirement 0005

<!-- autoresearch-message:0005-20260808T054141.223178Z.md -->
- Recorded at: `20260808T054141.223178Z`
- Source: `user`
- Immutable record: [`0005-20260808T054141.223178Z.md`](requirements/messages/0005-20260808T054141.223178Z.md)

帮助我优化 P0, P1, P2

### Session requirement 0006

<!-- autoresearch-message:0006-20260808T151658.785847Z.md -->
- Recorded at: `20260808T151658.785847Z`
- Source: `user`
- Immutable record: [`0006-20260808T151658.785847Z.md`](requirements/messages/0006-20260808T151658.785847Z.md)

因为我是做系统 和 AI infra 相关的research的，targte 会议包含： SOSP/FAST/OSDI/ATC/EuroSys/MLSys 等会议；也会兼顾 ICLR/NIPS/AAAI/DAC 等会议，

### Session requirement 0007

<!-- autoresearch-message:0007-20260808T175907.076512Z.md -->
- Recorded at: `20260808T175907.076512Z`
- Source: `user`
- Immutable record: [`0007-20260808T175907.076512Z.md`](requirements/messages/0007-20260808T175907.076512Z.md)

帮助我提交到github，更新github历史

### Session requirement 0008

<!-- autoresearch-message:0008-20260928T210019.062759Z.md -->
- Recorded at: `20260928T210019.062759Z`
- Source: `user-supplied-researchos-requirements`
- Immutable record: [`0008-20260928T210019.062759Z.md`](requirements/messages/0008-20260928T210019.062759Z.md)

# Task: Continue Building ResearchOS V0 in NextBrain

You are continuing an existing project. Do **not** redesign the system from scratch. First inspect the repository, the supplied V0 implementation, and the local environment, then integrate and validate the implementation.

## 1. Repository

Main repository:

```text
~/Github/NextBrain
```

GitHub repository:

```text
git@github.com:kexinchu/NextBrain.git
```

Before modifying anything:

```bash
cd ~/Github/NextBrain
git status
git pull
```

Inspect the existing architecture carefully, especially:

```text
src/autoresearch/
tests/
.agents/skills/
.cursor/skills/
AGENTS.md
README.md
pyproject.toml
```

The existing NextBrain implementation already contains useful infrastructure such as:

- AutoResearch orchestrator
- contracts
- freeze gates
- experiment loop
- implementation loop
- evidence handling
- journals
- alignment checks
- agent skills
- tests

Preserve and reuse these capabilities whenever appropriate.

Do NOT replace the existing AutoResearch engine unnecessarily.

---

# 2. ResearchOS Goal

We are extending NextBrain into a personal **Research Operating System for systems / LLM infrastructure research**.

The upstream research workflow S1–S4 is already handled by other agents.

Candidate research plans are generated under:

```text
/Users/kexin.chu/Github/paper-manager/Ideas/Research-Map/plans/
```

ResearchOS starts at the **first Human Gate**.

The intended workflow is:

```text
S1-S4 external research agents
        │
        ▼
plans/
        │
        ▼
Human Gate #1
        │
        ├── DROP
        ├── HOLD
        ├── NEEDS_WORK
        │
        └── GO
             │
             ▼
        ResearchOS
             │
             ▼
S5 Hypothesis Refinement
             │
             ▼
S6 Experiment Design / DAG
             │
             ▼
S7 Autonomous Research Loop
             │
     ┌───────┼────────┐
     ▼       ▼        ▼
   RTX4060 A6000-1 A6000-2
     │       │        │
     └───────┼────────┘
             ▼
       Findings Memory
             │
             ▼
       Human Gate #2
```

The human remains responsible for major research decisions.

Agents should automate execution and evidence collection, not silently redefine the research question.

---

# 3. Existing ResearchOS V0

A ResearchOS V0 implementation has already been produced.

Locate the supplied directory/archive if available, likely named:

```text
NextBrain-ResearchOS-V0
```

or

```text
NextBrain-ResearchOS-V0.zip
```

Inspect it before implementing anything.

The V0 already targets:

- plan scanning
- idea registry
- SQLite database
- Human Gate decisions
- GO/HOLD/DROP/NEEDS_WORK
- project creation
- Research Contract creation
- hypothesis registry
- experiment registry
- Findings Memory
- SSH config discovery
- explicit SSH probing
- ResearchOS CLI
- tests

Previous validation reported:

```text
4/4 V0 tests passed
```

Do not assume this remains true after integration. Re-run all tests.

---

# 4. Architecture Principle

ResearchOS is the **cross-project control plane**.

Existing NextBrain AutoResearch remains the **research execution engine**.

Conceptually:

```text
ResearchOS
│
├── Idea Registry
├── Human Gates
├── Project Registry
├── Hypotheses
├── Experiment DAG
├── Runs
├── Findings Memory
├── Machine Registry
└── Scheduler
        │
        ▼
Existing NextBrain AutoResearch
        │
        ├── story freeze
        ├── implementation loop
        ├── experiment loop
        ├── evidence
        └── writing/review
```

Do not tightly couple SQLite state with individual experiment workspaces.

---

# 5. Research State Model

The core research objects should conceptually support:

```text
Idea
Project
Hypothesis
Claim
Experiment
Run
Finding
Artifact
Decision
Machine
```

The important relationship is:

```text
IDEA
 │
 ▼
HYPOTHESIS
 │
 ├── tested_by
 ▼
EXPERIMENT
 │
 ▼
RUN
 │
 ▼
FINDING
 │
 ├── supports CLAIM
 ├── contradicts CLAIM
 └── motivates new HYPOTHESIS
```

We are not merely building a job scheduler.

We are tracking:

```text
claim → hypothesis → experiment → evidence → conclusion
```

---

# 6. Human Gate

ResearchOS should scan:

```text
/Users/kexin.chu/Github/paper-manager/Ideas/Research-Map/plans/
```

and identify candidate ideas.

Human decisions:

```text
GO
HOLD
DROP
NEEDS_WORK
```

Only:

```text
GO
```

may initialize an active ResearchOS project.

A GO should create a durable project with at least:

```text
SOURCE_IDEA.md
RESEARCH_CONTRACT.md
```

and corresponding database records.

---

# 7. Research Contract

Each accepted project must have a falsifiable research contract.

At minimum capture:

```yaml
research_id:

title:

status: ACTIVE

core_question:

primary_claim:

baseline:

independent_variables:

dependent_variables:

success_conditions:

falsification_conditions:

compute_budget:

human_gate:
  approved: true
```

One mandatory question is:

```text
What result would make us abandon this idea?
```

If this cannot be answered meaningfully, the project should not enter unrestricted S7 experimentation.

---

# 8. S5 — Hypothesis Refinement

S5 should transform an accepted research idea into explicit falsifiable hypotheses.

Eventually the process should support adversarial roles such as:

```text
Researcher
Skeptic
Prior-Art Agent
Systems Reviewer
Experiment Agent
```

But do not overengineer multi-agent orchestration in V0.

The durable output matters more than the number of agents.

Example:

```text
H1:
The workload exhibits sufficient reuse skew.

H2:
Predicting reusable objects costs less than the resources saved.

H3:
The proposed mechanism improves the target latency metric.

H4:
The improvement persists under realistic workloads.
```

Each hypothesis should eventually map to one or more experiments.

---

# 9. S6 — Experiment DAG

Experiments must not be treated as one giant experiment_plan.md.

Represent dependencies explicitly.

Example:

```text
E0 workload characterization
        │
        ▼
E1 reuse distribution
        │
        ▼
E2 oracle experiment
        │
    ┌───┴───┐
    ▼       ▼
E3 policy  E4 sensitivity
    │
    ▼
E5 end-to-end
    │
    ▼
E6 ablation
```

Each experiment should eventually contain fields similar to:

```yaml
experiment_id:
hypothesis_id:
priority:
dependencies:

estimated_runtime:

resource_requirement:

command:

prediction:

metrics:

success_condition:

failure_condition:

expected_artifacts:
```

---

# 10. Prediction Before Execution

This is a critical ResearchOS rule.

Before an experiment runs, record a prediction.

Example:

```text
Prediction

TTFT: -15% to -25%
TPOT: approximately unchanged
memory usage: -20%
```

After execution:

```text
Observed

TTFT: -3%
TPOT: +8%
memory usage: -21%
```

Store both.

This allows ResearchOS to distinguish actual scientific learning from random hill climbing.

---

# 11. Findings Memory

Every meaningful experiment should produce a durable Finding.

Example:

```yaml
finding_id:

experiment_id:

observation:

magnitude:

confidence:

supports:

contradicts:

unexpected:

next_questions:
```

Future research decisions should read:

```text
Research Contract
+
Hypotheses
+
Experiment DAG
+
Findings Memory
```

They should NOT reason only from the most recent experiment.

---

# 12. Compute Environment

There are three remote GPU servers.

Expected resources:

```text
2 × servers with NVIDIA A6000
1 × server with NVIDIA RTX 4060
```

SSH aliases/configuration should be discoverable from:

```text
~/.ssh/config
```

Do not modify SSH credentials.

Do not print private keys or secrets.

Do not copy credentials into ResearchOS.

Use SSH aliases rather than hardcoded IP addresses.

---

# 13. Machine Roles

Default intended policy:

```text
RTX 4060
├── unit tests
├── smoke tests
├── debugging
├── tiny workloads
└── feasibility experiments

A6000 #1
├── primary experiments
├── profiling
└── medium-scale experiments

A6000 #2
├── replication
├── sweeps
├── ablation
└── parallel experiments
```

Typical promotion path:

```text
Experiment
    │
    ▼
local/unit test
    │
    ▼
4060 smoke test
    │
    ├── FAIL → stop/debug
    │
    ▼
A6000 primary experiment
    │
    ▼
A6000 replication / sweep
```

Do not immediately send every experiment to A6000.

---

# 14. SSH Safety

SSH config discovery must be side-effect free.

This:

```text
researchos ssh import
```

must only inspect configuration.

It must NOT automatically connect to every host.

Remote connection should require an explicit command such as:

```text
researchos ssh probe <alias>
```

Before making destructive remote changes, inspect the machine first.

For each candidate server, collect:

```text
hostname
GPU model
GPU count
GPU memory
CUDA/driver version
Python version
disk availability
git version
Docker availability
working directories
```

Do not delete or overwrite existing server experiments.

---

# 15. Git Isolation

Autonomous experiments must never freely modify the main working tree.

Longer term use:

```text
git worktree
```

or isolated experiment branches.

Conceptually:

```text
worktrees/
├── E0001/
├── E0002/
└── E0003/
```

Experiment outcomes:

```text
FAIL
→ preserve evidence
→ discard candidate code if appropriate

PASS
→ candidate merge

INTERESTING
→ branch into new hypothesis
```

Failed experiments are evidence and must not simply disappear.

---

# 16. S7 Auto-Research Loop

The eventual loop is:

```python
while budget_remaining:

    read_research_contract()
    read_findings_memory()
    inspect_experiment_dag()

    choose_highest_value_uncertainty()

    propose_one_change()

    record_prediction()

    run_cheapest_valid_experiment()

    collect_artifacts()

    compare_prediction_vs_observation()

    create_finding()

    decide:
        KEEP
        REJECT
        BRANCH
        ESCALATE_TO_HUMAN
```

Avoid large uncontrolled batches of simultaneous modifications.

Prefer one interpretable change per experiment whenever possible.

---

# 17. Stop Rules

ResearchOS must eventually support automatic stop/escalation rules.

Examples:

```text
STOP if:

critical hypothesis falsified

OR

multiple consecutive experiments provide negligible improvement

OR

remaining compute exceeds project budget

OR

novelty is invalidated by prior work

OR

results cannot be reproduced
```

Escalate to human when:

```text
major hypothesis revision required

unexpected result changes research direction

experiments contradict prior findings

large architecture change is required

research claim needs expansion or contraction
```

---

# 18. Immediate Task

Do NOT implement all future features at once.

First finish and validate **ResearchOS V0**.

Perform the following sequence.

### Step A — Inspect

Inspect:

```text
~/Github/NextBrain
```

and the supplied ResearchOS V0 implementation.

Compare the two.

Identify integration conflicts before modifying files.

### Step B — Integrate V0

Integrate ResearchOS into NextBrain cleanly.

Preserve existing AutoResearch functionality.

The CLI should support at least the equivalent of:

```bash
researchos scan
researchos inbox

researchos decide <idea> GO
researchos decide <idea> HOLD
researchos decide <idea> DROP
researchos decide <idea> NEEDS_WORK

researchos hypothesis ...
researchos experiment ...
researchos finding ...

researchos ssh import
researchos ssh probe <alias>

researchos status
```

Exact syntax may be improved if necessary, but keep the semantics.

### Step C — Tests

Run:

```bash
pytest
```

Run existing NextBrain tests AND ResearchOS tests.

Do not accept regressions.

Also run linting if configured.

### Step D — Local Functional Test

Use a temporary test plans directory.

Verify:

```text
plan appears
→ scan
→ inbox
→ GO
→ project created
→ DB records created
→ Research Contract created
→ hypothesis created
→ experiment created
→ finding created
```

### Step E — SSH Discovery

Inspect:

```text
~/.ssh/config
```

Identify the likely three GPU servers.

Do not guess server identity from alias names alone.

Explicitly probe candidate hosts.

Determine which machines contain:

```text
A6000
A6000
RTX 4060
```

Record the machine registry.

Do not make destructive remote changes.

### Step F — Report

Before implementing S7 remote execution, report:

```text
1. Files changed
2. Tests passed/failed
3. ResearchOS CLI status
4. SQLite schema status
5. Detected SSH hosts
6. GPU mapping
7. Environment differences across servers
8. Existing NextBrain components reused
9. Remaining V0 blockers
10. Recommended V0.1 implementation
```

---

# 19. Important Engineering Principles

Prioritize:

```text
auditability
reproducibility
falsifiability
failure preservation
human control
minimal hidden state
```

Avoid:

```text
agent self-reinforcement
silent hypothesis drift
unbounded GPU loops
automatic rewriting of claims after failed experiments
deleting negative results
modifying main branches during experiments
inventing experimental results
```

ResearchOS must clearly distinguish:

```text
prediction
measurement
inference
decision
```

These are not interchangeable.

---

# 20. Current Milestone

The immediate milestone is NOT "write a paper automatically."

The milestone is:

```text
Human GO
    ↓
ResearchOS project
    ↓
Research Contract
    ↓
Hypothesis
    ↓
Experiment specification
    ↓
4060 smoke-test-ready
    ↓
Finding recorded
```

Once this is reliable, proceed to V0.1:

```text
4060 execution
    ↓
A6000 promotion
    ↓
artifact collection
    ↓
prediction vs observation
    ↓
KEEP / REJECT / BRANCH
    ↓
next experiment
```

Start by inspecting the repository and V0 implementation. Make changes only after understanding the existing architecture. Continue autonomously through integration and testing, but stop and report before any destructive server operation or any architectural decision that would materially change the research workflow.

### Session requirement 0009

<!-- autoresearch-message:0009-20260928T210019.087726Z.md -->
- Recorded at: `20260928T210019.087726Z`
- Source: `user`
- Immutable record: [`0009-20260928T210019.087726Z.md`](requirements/messages/0009-20260928T210019.087726Z.md)

按顺序 帮助我完成代码开发，并提交github

### Session requirement 0010

<!-- autoresearch-message:0010-20260928T211508.569255Z.md -->
- Recorded at: `20260928T211508.569255Z`
- Source: `user`
- Immutable record: [`0010-20260928T211508.569255Z.md`](requirements/messages/0010-20260928T211508.569255Z.md)

1，环境 4060 的环境是 kexin\@192.168.50.2， 具体配置你在 ssh/config 中能找到
2，一些旧的 Nextbrain 逻辑可以不要了，因为已经过期了
3，流程中还有什么可以优化？

### Session requirement 0011

<!-- autoresearch-message:0011-20260928T233931.197018Z.md -->
- Recorded at: `20260928T233931.197018Z`
- Source: `user`
- Immutable record: [`0011-20260928T233931.197018Z.md`](requirements/messages/0011-20260928T233931.197018Z.md)

Continue from the current `master` of `kexinchu/NextBrain`.

PR #2 has already been merged. Do not rebuild ResearchOS V0. Start from the current implementation and refactor toward the first real autonomous execution loop.

The primary objective of this iteration is:

```text
One experiment
→ dispatched safely
→ uniquely identifiable
→ resumable after disconnect
→ bounded by timeout/budget
→ evidence automatically recovered
→ converted into a Finding
```

Do not prioritize multi-agent orchestration, paper writing, or large-scale scheduling yet.

## 1. First inspect current master

Before changing anything:

```bash
cd ~/Github/NextBrain
git status
git pull
git log --oneline -10
pytest
ruff check .
```

Inspect especially:

```text
src/researchos/
src/autoresearch/
tests/test_researchos.py
docs/researchos.md
docs/researchos-v0-validation.md
```

Preserve working V0 functionality unless the architecture below explicitly supersedes it.

---

# 2. Refactor result semantics

Current handling of contradictions is too coarse.

Do not use one generic `contradicts => NEEDS_REVIEW` transition.

Introduce three distinct outcome classes.

## A. Execution failure

Examples:

```text
process crash
OOM
SSH disconnect
node unavailable
timeout
missing dependency
artifact transfer failure
```

This is an operational result, not scientific evidence by itself.

Record:

```text
failure_type
exit_code
stderr
retry_count
machine
timestamp
partial_artifacts
```

Allow bounded retries according to policy.

Do not mark the research project as scientifically contradicted.

---

## B. Hypothesis falsification

A valid experiment may show that a hypothesis is false.

This is normal research progress.

Create a Finding such as:

```yaml
outcome: FALSIFIED
hypothesis_id: H3
evidence:
  ...
```

Then:

```text
close that hypothesis
or
activate another already-approved hypothesis
or
generate an in-scope follow-up experiment
```

Do NOT require human review merely because the result is negative.

---

## C. Research-scope change

Human review is required when evidence suggests changing any of:

```text
core research question
primary contribution claim
approved scope
compute budget
fundamental architecture
evaluation target
major baseline set
```

Represent this separately, e.g.:

```text
SCOPE_CHANGE_REQUESTED
```

Only this category should trigger project-level Human Gate escalation.

---

# 3. Refactor contract lifecycle

The current contract model freezes too much too early.

Replace the conceptual flow with:

```text
Human GO
    ↓
Project Envelope approved
    ↓
S5 hypothesis refinement
    ↓
S6 experiment design
    ↓
Experiment-specific freeze
    ↓
execution
    ↓
Finding
    ↓
continue within approved scope
    ↓
Evidence maturity gate
    ↓
Paper STORY freeze
```

The Human GO / Project Envelope should approve only:

```text
problem
research boundary
resource/compute budget
stop conditions
major non-goals
allowed experiment classes
```

Do not require a final paper claim at this point.

The project may contain a provisional claim, but it must be explicitly marked provisional.

---

# 4. Experiment Freeze

Before each run, create an immutable experiment snapshot.

It must include:

```yaml
experiment_id:
experiment_revision:
hypothesis_id:

prediction:
protocol:
metrics:
success_condition:
falsification_condition:

code:
  repo:
  commit_sha:
  dirty: false

data:
  identifiers:
  hashes:

environment_requirement:

resource_requirement:

timeout:

budget:

created_at:
```

Compute a deterministic digest for the entire frozen experiment specification.

Once dispatched, the same Run must always reference that digest.

Do not silently mutate prediction, metric definitions, or success criteria after execution starts.

---

# 5. Implement a real Run object

Every execution must have a unique Run ID.

Example:

```text
RUN-20260928-0017
```

A Run must persist before remote execution starts.

Minimum Run state machine:

```text
CREATED
    ↓
PREPARING
    ↓
DISPATCHED
    ↓
RUNNING
    ↓
COLLECTING
    ↓
SUCCEEDED
```

Operational failure branches:

```text
FAILED_RETRYABLE
FAILED_FINAL
TIMED_OUT
CANCELLED
LOST
```

Scientific interpretation must remain separate:

```text
SUPPORTED
FALSIFIED
INCONCLUSIVE
```

Do not encode scientific interpretation directly into process status.

---

# 6. Executor Receipt

When a run is dispatched, create a durable executor receipt.

It should include at least:

```yaml
run_id:
experiment_digest:

machine_alias:

remote_workdir:

remote_pid:
job_id:

launch_command:

code_commit:

started_at:

stdout_path:
stderr_path:

artifact_manifest_path:
```

The receipt must be written locally before considering dispatch successful.

If possible, also write a small receipt on the remote host.

---

# 7. Recovery after SSH disconnect

Implement:

```bash
researchos run status RUN_ID
researchos run recover RUN_ID
```

Recovery must NOT blindly relaunch the experiment.

It should first determine:

```text
Is remote process still alive?
Did it finish?
Did it fail?
Are artifacts present?
Was completion recorded remotely?
```

Only relaunch if policy explicitly permits it and the previous execution is confirmed dead/non-completed.

Prevent duplicate jobs.

---

# 8. Timeout and budget enforcement

Each Run must support:

```text
wall-clock timeout
maximum retry count
GPU-hour budget
optional disk/artifact limit
```

Timeout should result in:

```text
TIMED_OUT
```

not generic failure.

If project budget is exhausted:

```text
do not dispatch additional runs
```

Record a budget-blocked decision.

---

# 9. Preserve partial evidence

Even failed runs may generate useful information.

Always attempt to recover:

```text
stdout
stderr
metrics emitted before failure
partial result files
environment snapshot
GPU utilization logs if available
```

Hash collected artifacts.

Store them in the existing ResearchOS artifact store.

Do not delete them because the run failed.

---

# 10. First remote target

Prefer the RTX 4060 host when it becomes reachable:

```text
kexin@192.168.50.2
```

Use the SSH alias/config from:

```text
~/.ssh/config
```

Do not alter credentials or host keys automatically.

If the 4060 remains unreachable, do NOT block the entire implementation.

Use a local mock executor or a safe reachable A6000 host for executor validation, but clearly distinguish test execution from scientific results.

No destructive server cleanup.

---

# 11. Resource-aware execution

Do not hard-code:

```text
every experiment must pass through 4060
```

Introduce minimal resource matching.

Experiment requirements may include:

```yaml
resource:
  gpu_required: true
  min_vram_gb: 20
  gpu_count: 1
  cpu_only: false
```

Selection policy:

```text
CPU-only experiment
→ local if possible

small GPU experiment
→ smallest suitable GPU

requires >4060 capability
→ A6000 directly
```

4060 is the preferred cheap test machine, not a mandatory gate.

---

# 12. Add prepare-next-experiment

Add a higher-level command similar to:

```bash
researchos next PROJECT_ID
```

It should NOT automatically execute.

It should summarize:

```text
most important unresolved uncertainty

candidate next experiment

why this experiment has high information value

estimated runtime / GPU cost

required machine capability

dependencies satisfied / missing

prediction

success/falsification criteria

whether it stays inside approved project scope
```

Output one recommended next experiment, not a huge queue.

If scope change is required:

```text
requires_human_gate: true
```

---

# 13. Human approval must bind to versioned objects

Existing `--by human` is audit metadata, not real authorization.

For sensitive transitions, create explicit approval receipts bound to object digest/version.

Examples:

```text
Project Envelope approval
Experiment exception approval
Scope-change approval
Budget increase approval
```

An approval must become invalid if the approved object's digest changes.

Do not require approval for ordinary in-scope negative experimental results.

---

# 14. Evidence-to-Finding pipeline

After a successful or scientifically valid run:

```text
Run artifacts
    ↓
metrics extraction
    ↓
prediction vs observation
    ↓
scientific interpretation
    ↓
Finding
```

A Finding should distinguish:

```yaml
measurement:
inference:
outcome:
confidence:
supports:
falsifies:
unexpected:
next_questions:
```

Measurement and inference must remain separate fields.

---

# 15. Stop rules

Implement minimal automatic stop policy.

Examples:

```text
critical hypothesis falsified
project compute budget exhausted
max retry count exceeded
required baseline unavailable
experiment cannot produce discriminating evidence
```

Stopping one hypothesis is not necessarily stopping the entire project.

Project-level stop must be explicit.

---

# 16. Testing requirements

Add tests for at least:

1. run IDs are unique
2. run persisted before dispatch
3. experiment digest immutable after dispatch
4. SSH disconnect does not create duplicate run
5. recover finds an already-running process
6. recover collects finished artifacts
7. timeout produces TIMED_OUT
8. retry count enforced
9. execution failure does not mark hypothesis falsified
10. falsified hypothesis does not mark project NEEDS_REVIEW
11. scope-change request does require human gate
12. partial artifacts survive failure
13. artifact hashes stable
14. next-experiment refuses out-of-scope change
15. resource matching selects smallest valid machine
16. budget prevents new dispatch
17. approval invalidates when object digest changes

Run:

```bash
pytest
ruff check .
python -m build
autoresearch doctor --release
```

Do not accept regressions.

---

# 17. Git workflow

Create a focused branch, for example:

```text
codex/researchos-resumable-run
```

Keep commits logically separated where practical:

```text
refactor: separate execution and scientific outcomes

feat: add resumable run lifecycle

feat: add executor receipts and recovery

feat: add evidence collection

feat: add resource-aware next experiment

test: cover recovery and state transitions
```

Push the branch and open a PR.

Do not merge automatically unless all tests pass and the diff is internally consistent.

---

# 18. End-of-task report

Return:

```text
1. architecture changes
2. schema changes
3. files added/removed
4. obsolete paths/modules removed
5. run state machine
6. scientific outcome state machine
7. recovery behavior
8. timeout/budget behavior
9. artifact/evidence collection
10. resource selection behavior
11. tests
12. server validation performed
13. unresolved 4060 connectivity issue
14. PR URL
15. recommended next step
```

The next milestone after this task is:

```text
real single-run execution
→ automatic evidence recovery
→ A6000 promotion/replication
→ bounded S7 loop
```

Do not implement autonomous multi-run S7 loops until the single resumable run path is reliable.

### Session requirement 0012

<!-- autoresearch-message:0012-20260929T011802.716515Z.md -->
- Recorded at: `20260929T011802.716515Z`
- Source: `user`
- Immutable record: [`0012-20260929T011802.716515Z.md`](requirements/messages/0012-20260929T011802.716515Z.md)

# Task: ResearchOS V0.2 — Bounded Autonomous Research Loop

Continue development from the current `master` of:

```text
~/Github/NextBrain
```

Repository:

```text
git@github.com:kexinchu/NextBrain.git
```

PR #3 has been merged.

ResearchOS V0.1 already provides the trusted execution primitive:

```text
Frozen Experiment
    ↓
Unique Run
    ↓
Resource Selection
    ↓
Execution
    ↓
Recovery
    ↓
Artifact Collection
    ↓
Evidence
    ↓
Finding
```

Do NOT redesign this execution path.

The goal of V0.2 is to build the first **bounded autonomous research loop** on top of it.

The key question is:

> Given the current Project Envelope, hypotheses, experiment history, Findings Memory, available compute and remaining budget, what is the highest-value next experiment, and can ResearchOS execute a small bounded sequence of such experiments without silently changing the research question?

---

# 0. Before modifying code

Start from clean current master.

```bash
cd ~/Github/NextBrain

git status
git pull
git log --oneline -10

pytest
ruff check .
python -m build
autoresearch doctor --release
```

Inspect carefully:

```text
src/researchos/
src/autoresearch/
docs/researchos*.md
tests/test_researchos.py
tests/test_resumable_runs.py
```

Especially understand the current implementations of:

```text
next_experiment.py
execution.py
policy.py
freeze.py
transport.py
worker.py
store.py
schema.py
```

Do not duplicate existing functionality.

Create a focused branch such as:

```text
codex/researchos-bounded-loop
```

---

# 1. Core architecture

The intended V0.2 loop is:

```text
              Project Envelope
                     │
                     ▼
              Findings Memory
                     │
                     ▼
              Hypothesis State
                     │
                     ▼
        ┌── Research Planner ──┐
        │                      │
        ▼                      ▼
Candidate Experiments     Stop/Escalate
        │
        ▼
Experiment Selector
        │
        ▼
Scope / Policy Check
        │
        ▼
Freeze ONE Experiment
        │
        ▼
Existing V0.1 Executor
        │
        ▼
Evidence Collection
        │
        ▼
Finding
        │
        ▼
Update Research State
        │
        └───────────→ re-plan
```

The loop MUST re-plan after every completed experiment.

Do NOT generate an entire fixed experiment sequence and blindly execute it.

---

# 2. Research state must become explicit

Introduce or refine explicit hypothesis lifecycle states.

At minimum:

```text
PROPOSED
ACTIVE
SUPPORTED
FALSIFIED
INCONCLUSIVE
BLOCKED
```

Prefer keeping confidence separate from state.

For example:

```yaml
hypothesis_id: H3

state: ACTIVE

confidence:
  value: 0.55
  basis: qualitative

supporting_findings:
  - F0012

contradicting_findings:
  - F0018

open_uncertainties:
  - behavior under bursty workload
  - sensitivity to prediction error
```

Do NOT invent mathematically precise probabilities unless the evidence justifies them.

A qualitative or ordinal confidence representation is acceptable.

---

# 3. Findings Memory must drive planning

The planner must not reason only from:

```text
latest experiment
```

Before proposing the next experiment, construct a bounded Research Context containing:

```text
Project Envelope

Active hypotheses

Supported hypotheses

Falsified hypotheses

Relevant Findings

Existing claims

Completed experiments

Failed operational runs

Unresolved uncertainties

Available machines

Remaining budget

Existing experiment DAG/dependencies
```

Avoid dumping the entire historical database into an LLM prompt.

Create a compact structured context.

---

# 4. Introduce explicit Uncertainty objects

This is important.

ResearchOS should not choose experiments directly from hypotheses alone.

Represent unresolved research questions as first-class uncertainties.

Example:

```yaml
uncertainty_id: U17

project_id: P001

question:
  Does the proposed KV placement remain beneficial
  when reuse prediction precision falls below 70%?

related_hypotheses:
  - H2
  - H3

importance: HIGH

current_evidence:
  - F21
  - F24

status: OPEN
```

Suggested states:

```text
OPEN
REDUCED
RESOLVED
BLOCKED
```

The research loop should primarily ask:

> Which uncertainty is currently most decision-relevant?

not:

> Which parameter should we optimize next?

---

# 5. Candidate Experiment generation

For the highest-value uncertainty, generate a small bounded candidate set.

Default:

```text
2–4 candidate experiments
```

Not 20.

Each candidate should contain:

```yaml
candidate_id:

uncertainty_id:

hypothesis_ids:

question:

experiment_type:

expected_information:

possible_outcomes:

interpretation_by_outcome:

estimated_cost:

resource_requirement:

dependencies:

risk:

within_scope:
```

Critically, require:

```text
possible_outcomes
```

before execution.

Example:

```yaml
possible_outcomes:

  strong_positive:
    interpretation:
      supports H3

  neutral:
    interpretation:
      H3 remains uncertain

  negative:
    interpretation:
      falsifies H3

  operational_failure:
    interpretation:
      no scientific conclusion
```

This prevents post-hoc reinterpretation.

---

# 6. Experiment selection must optimize information value

Do NOT select experiments merely because they are likely to improve a metric.

The selector should reason approximately about:

```text
decision relevance
×
expected information gain
×
ability to distinguish hypotheses
÷
cost
```

A practical V0.2 heuristic is acceptable.

For example:

```text
score =
    uncertainty_importance
  × discrimination_power
  × expected_information_gain
  × feasibility
  ÷ normalized_cost
```

Do not pretend this is statistically exact.

The score is a planning heuristic.

Store the component values and explanation.

---

# 7. Distinguish exploration from optimization

ResearchOS must explicitly distinguish:

```text
EXPLORATION
```

from:

```text
OPTIMIZATION
```

Exploration asks:

```text
Is the phenomenon real?
Why does it happen?
Under what conditions?
Which hypothesis is correct?
```

Optimization asks:

```text
How much can we improve the metric?
What parameter is best?
```

Before the core mechanism is sufficiently established, prefer exploration.

Do not allow the system to spend dozens of experiments tuning parameters for a mechanism that may not matter.

---

# 8. Experiment types

Introduce useful semantic experiment types.

At minimum:

```text
MOTIVATION
FEASIBILITY
MECHANISM
DISCRIMINATION
PRIMARY
REPLICATION
SENSITIVITY
ABLATION
STRESS
```

These should influence planning.

For example:

```text
MOTIVATION
→ establish whether the problem matters

DISCRIMINATION
→ distinguish competing explanations

PRIMARY
→ test central claim

REPLICATION
→ test reproducibility

ABLATION
→ isolate mechanism

STRESS
→ determine validity boundary
```

---

# 9. Add researchos next

Upgrade:

```bash
researchos next PROJECT_ID
```

into a real planner.

Expected output should resemble:

```text
PROJECT
P001

CURRENT RESEARCH STATE
3 active hypotheses
1 supported
1 falsified

HIGHEST-VALUE UNCERTAINTY
U17

Question:
Does reuse prediction accuracy erase the benefit?

Why this matters:
If benefit disappears below realistic prediction accuracy,
the central mechanism is not practical.

CANDIDATE EXPERIMENTS
E31
E32
E33

SELECTED
E32

Reason:
Highest discrimination/cost ratio.

Expected runtime:
22 min

Machine:
cloudsys01 GPU0

Estimated GPU-hours:
0.37

Prediction:
...

Possible interpretations:
...

Scope:
WITHIN APPROVED ENVELOPE

Ready:
YES
```

`researchos next` MUST NOT execute anything.

---

# 10. Add researchos advance

Introduce:

```bash
researchos advance PROJECT_ID
```

and bounded mode:

```bash
researchos advance PROJECT_ID --max-runs 3
```

Default:

```text
max-runs = 1
```

Do NOT default to autonomous multi-run execution.

Each iteration:

```text
read state
    ↓
select uncertainty
    ↓
generate candidates
    ↓
select experiment
    ↓
scope check
    ↓
freeze experiment
    ↓
execute using V0.1
    ↓
collect evidence
    ↓
create Finding
    ↓
update hypothesis/uncertainty
    ↓
evaluate stop rules
    ↓
RE-PLAN
```

Never pre-dispatch multiple experiments.

---

# 11. Hard bounds

`advance` must obey all of:

```text
max_runs
max_wall_time
project GPU-hour budget
per-run timeout
retry limits
scope boundaries
machine availability
```

Suggested CLI:

```bash
researchos advance P001 \
  --max-runs 3 \
  --max-wall-time 4h
```

If any hard bound is reached:

```text
STOP CLEANLY
```

and record why.

---

# 12. Stop / Continue / Escalate controller

After every Finding, produce one explicit decision:

```text
CONTINUE
STOP_HYPOTHESIS
STOP_PROJECT
ESCALATE_HUMAN
REPLICATE
```

Examples:

### CONTINUE

Important uncertainty remains and an in-scope experiment can reduce it.

### STOP_HYPOTHESIS

Critical hypothesis has been falsified.

This does NOT necessarily stop the project.

### REPLICATE

Result is important enough that independent confirmation is required.

### STOP_PROJECT

Examples:

```text
core mechanism falsified
problem magnitude negligible
budget exhausted
all useful in-scope hypotheses exhausted
```

### ESCALATE_HUMAN

Required when:

```text
core question should change
claim scope should change
new architecture required
budget increase needed
new major baseline family required
project envelope must change
```

---

# 13. Replication policy

A single promising run must not automatically create a high-confidence Finding.

Important positive results should trigger replication.

Represent:

```text
original_run
replication_runs
```

Prefer variation in at least one of:

```text
seed
workload slice
machine
input subset
execution time
```

Do not treat:

```text
same command
same seed
same machine
```

as strong independent replication.

---

# 14. Finding confidence

Finding confidence should depend on evidence quality.

For example:

```text
PRELIMINARY
REPLICATED
ROBUST
```

or similar.

Do not use arbitrary numeric confidence unless justified.

Example progression:

```text
single primary run
→ PRELIMINARY

independent replication
→ REPLICATED

replication + sensitivity + relevant baselines
→ ROBUST
```

Keep this configurable.

---

# 15. Promotion semantics

Do not think of machines only as:

```text
4060 → A6000
```

Think of experiment maturity.

Example:

```text
FEASIBILITY
    ↓
PRIMARY
    ↓
REPLICATION
    ↓
SENSITIVITY / ABLATION
```

Machine selection should remain resource-driven.

For example:

```text
small feasibility
→ 4060 when available

large-model feasibility
→ A6000 directly

CPU analysis
→ local

replication
→ preferably another eligible GPU/server
```

---

# 16. 4060 must not block V0.2

Current known state:

```text
kexin-server
kexin@192.168.50.2
```

is still unreachable with:

```text
No route to host
```

Do not modify SSH credentials or trust configuration automatically.

Continue V0.2 development without it.

Use the reachable A6000 infrastructure for safe validation when necessary.

Clearly mark synthetic validation as:

```text
NOT SCIENTIFIC EVIDENCE
```

---

# 17. A6000 environment safety

Before real GPU execution, verify:

```text
Python runtime
CUDA runtime
driver
available GPU memory
available disk
experiment working directory
repository state
```

Known prior issue:

```text
cloudsys02 root filesystem was effectively full
```

Do not automatically clean it.

If insufficient disk remains:

```text
mark machine unavailable
```

with reason.

Do not silently redirect experiment output into unknown directories.

---

# 18. Human Gate #2

Introduce an explicit evidence maturity gate.

This is NOT triggered by every negative result.

Trigger it when:

```text
central mechanism has sufficient evidence

OR

project requires scope change

OR

research appears mature enough to define paper claims

OR

system recommends stopping project
```

Human Gate #2 should summarize:

```text
Original question

Current hypothesis graph

Supported hypotheses

Falsified hypotheses

Strongest Findings

Replication status

Unexpected results

Remaining uncertainties

Compute consumed

Compute remaining

Closest known threats to validity

Suggested action:
CONTINUE
PIVOT
STOP
FREEZE STORY
```

The system may suggest these actions.

It must not silently choose PIVOT or FREEZE STORY.

---

# 19. Paper Story remains downstream

Do NOT automatically write or freeze:

```text
paper/STORY.md
```

during ordinary S7 exploration.

Only after Human Gate #2 explicitly approves:

```text
FREEZE STORY
```

should the existing AutoResearch paper workflow become authoritative.

Target lifecycle:

```text
ResearchOS exploration
        ↓
Evidence maturity
        ↓
Human Gate #2
        ↓
FREEZE STORY
        ↓
AutoResearch paper pipeline
```

---

# 20. Planner implementation

Do not hard-code the entire planner as arbitrary Python heuristics.

Separate:

```text
deterministic policy
```

from:

```text
research reasoning
```

Deterministic code should enforce:

```text
budget
scope
dependencies
machine capability
run limits
approval validity
experiment freeze
artifact integrity
```

Research reasoning may propose:

```text
uncertainties
candidate experiments
expected information
interpretation
next questions
```

All agent-generated planner output must pass a schema validator before entering durable state.

---

# 21. Planner auditability

Every planning round should generate a durable Planner Decision record.

Example:

```yaml
planner_decision_id:

project_id:

research_state_digest:

selected_uncertainty:

candidate_experiments:

selected_experiment:

selection_scores:

reasoning_summary:

rejected_candidates:

scope_check:

budget_snapshot:

created_at:
```

This is important.

Later we should be able to ask:

> Why did ResearchOS choose experiment E32 instead of E31?

and reconstruct the answer.

---

# 22. Avoid context drift

Every planning iteration should derive a compact context from durable state.

Do NOT rely on an ever-growing conversation history.

Conceptually:

```text
SQLite / Findings
       ↓
Context Builder
       ↓
bounded research context
       ↓
Planner
       ↓
schema-validated decision
       ↓
durable DB state
```

The database is the source of truth.

The LLM conversation is not.

---

# 23. Tests

Add comprehensive tests.

At minimum test:

1. planner reads all relevant Findings, not only latest
2. falsified hypotheses excluded from ordinary next-step selection
3. unresolved high-importance uncertainty can outrank metric optimization
4. candidate experiment requires possible-outcome interpretations
5. out-of-scope experiment rejected
6. over-budget experiment rejected
7. experiment dependencies enforced
8. smallest valid machine selected
9. 4060 unavailability does not block valid A6000 experiment
10. `next` does not execute
11. `advance` default executes at most one run
12. `--max-runs 3` never executes a fourth
13. every run causes re-planning
14. hypothesis falsification can continue another branch
15. operational failure does not alter scientific belief
16. important positive result can trigger replication
17. identical rerun is not considered strong independent replication
18. scope change triggers Human Gate
19. negative in-scope result does not automatically trigger Human Gate
20. budget exhaustion cleanly stops loop
21. planner decisions are durable
22. planner state digest changes when evidence changes
23. stale planner decision cannot execute against newer state
24. malformed agent planner output rejected
25. Project Envelope cannot be modified by planner
26. paper STORY cannot be frozen without Human Gate #2
27. synthetic executor result cannot become scientific evidence accidentally

Run:

```bash
pytest
ruff check .
python -m build
autoresearch doctor --release
```

Do not accept regressions.

---

# 24. Real validation

After deterministic and synthetic tests pass:

Perform a safe bounded validation on a reachable server.

Do NOT yet run a costly research workload.

Validate:

```text
planner
→ next
→ freeze
→ one execution
→ collect
→ Finding
→ re-plan
```

Then test:

```text
advance --max-runs 2
```

using harmless synthetic experiments.

Confirm:

```text
exactly two or fewer runs
no duplicate jobs
Findings created
state changes
planner re-runs
budget changes
stop rule works
```

Clearly label these results:

```text
SYSTEM VALIDATION
NOT SCIENTIFIC EVIDENCE
```

---

# 25. Do not implement yet

Explicitly out of scope for V0.2:

```text
automatic paper writing

automatic paper STORY freeze

unbounded research loops

automatic Git merge

automatic Project Envelope modification

large multi-agent swarm

large hyperparameter search

automatic literature-derived scope expansion

venue optimization

review-score optimization
```

Do not add these merely because they are easy.

---

# 26. Cleanup

Now that ResearchOS is becoming the main research control plane, inspect old NextBrain paths.

Classify legacy components as:

```text
KEEP
REUSE
DEPRECATE
DELETE
```

Delete only components that are clearly superseded and have no active dependency.

Do NOT delete reusable infrastructure such as:

```text
evidence
journal
transactions
freeze primitives
alignment
artifact integrity
```

unless there is

### Session requirement 0013

<!-- autoresearch-message:0013-20260929T025706.273780Z.md -->
- Recorded at: `20260929T025706.273780Z`
- Source: `user`
- Immutable record: [`0013-20260929T025706.273780Z.md`](requirements/messages/0013-20260929T025706.273780Z.md)

# ResearchOS V0.3 — Research Intelligence + Real-Project Pilot

Continue from the current merged `master` of:

```text
~/Github/NextBrain
```

Repository:

```text
git@github.com:kexinchu/NextBrain.git
```

Previous milestones are complete.

ResearchOS already provides:

```text
S1-S4 external idea discovery
        ↓
Human Gate #1
        ↓
Project Envelope
        ↓
Hypotheses + Uncertainties
        ↓
Auditable Planner
        ↓
Candidate Experiments
        ↓
Experiment Freeze
        ↓
Bounded advance loop
        ↓
Recoverable execution
        ↓
Evidence / Findings
        ↓
Hypothesis updates
        ↓
Replication
        ↓
Human Gate #2
```

The previous implementation passed:

```text
121 tests
Ruff
build
installed CLI
release doctor
```

and completed real system validation on `cloudsys01`:

```text
1 run
→ 2 bounded runs
→ budget exhaustion
→ clean stop
```

with:

```text
3 Findings
10 planning records
no duplicate jobs
```

All were synthetic CPU validation and correctly excluded from scientific evidence.

Do NOT redesign these mechanisms.

---

# 1. Objective

The primary problem is no longer execution infrastructure.

The major remaining weakness is **research intelligence**.

ResearchOS can execute experiments reliably, but it must become better at:

```text
forming useful hypotheses

identifying decisive uncertainties

designing discriminating experiments

reasoning about expected outcomes before execution

interpreting unexpected results

deciding whether to replicate, branch, falsify, or escalate

distinguishing scientific progress from metric hill climbing
```

The goal of V0.3 is:

> Build a research-reasoning layer that proposes and evaluates experiments like a careful systems researcher, while leaving deterministic safety, execution, scope, budget, provenance and approvals to the existing ResearchOS control plane.

---

# 2. Architectural principle

Maintain a strict separation:

```text
              Research Intelligence
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
 Hypothesis       Experiment       Result
 Reasoning         Design       Interpretation
       │              │              │
       └──────────────┼──────────────┘
                      ▼
              Structured Proposal
                      │
                      ▼
             Deterministic ResearchOS
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
     scope          budget         policy
     check          check          check
       │
       └──────────────┼──────────────┘
                      ▼
                Experiment Freeze
                      │
                      ▼
                  Executor
```

The reasoning layer proposes.

The deterministic layer decides whether the proposal is admissible.

Never allow the reasoning model to bypass:

```text
scope
budget
approval
freeze
provenance
resource
artifact
execution
```

rules.

---

# 3. Introduce Research Question Graph

Flat hypotheses are not enough.

Represent the current scientific reasoning structure explicitly.

Add a Research Question Graph.

Conceptually:

```text
Core Question
     │
     ├── H1
     │    ├── U1
     │    └── U2
     │
     ├── H2
     │    └── U3
     │
     └── H3
          ├── U4
          └── U5
```

Support relationships such as:

```text
SUPPORTS
CONTRADICTS
DEPENDS_ON
ALTERNATIVE_TO
EXPLAINS
REFINES
```

Do not build a general-purpose graph database.

SQLite relational representation is sufficient.

The purpose is scientific traceability, not graph infrastructure.

---

# 4. Distinguish hypothesis classes

Introduce semantic hypothesis types.

At minimum:

```text
EXISTENCE
MECHANISM
CAUSAL
PERFORMANCE
BOUNDARY
GENERALIZATION
```

Examples:

```text
EXISTENCE:
Reuse skew exists in realistic workloads.

MECHANISM:
Reuse skew is caused by shared prefixes.

PERFORMANCE:
Selective placement reduces TTFT.

BOUNDARY:
The benefit disappears below 60% prediction precision.

GENERALIZATION:
The mechanism persists across model families.
```

Experiment design should depend on hypothesis type.

A performance benchmark is not automatically a valid test of a mechanism hypothesis.

---

# 5. Competing hypotheses

ResearchOS must explicitly support competing explanations.

Example:

```text
Observed:
TTFT improves.

Possible explanations:

H1:
HBF placement reduced transfer traffic.

H2:
Batch composition changed.

H3:
Cache hit rate changed for unrelated reasons.

H4:
Measurement noise.
```

The planner should prefer experiments that discriminate among plausible explanations.

Introduce explicit:

```text
competing_hypotheses
```

or graph relation:

```text
ALTERNATIVE_TO
```

Do not let the system immediately interpret a metric improvement as proof of the intended mechanism.

---

# 6. Research reasoning cycle

For each planning iteration, reasoning should follow:

```text
OBSERVE
   ↓
WHAT DO WE CURRENTLY BELIEVE?
   ↓
WHAT IS UNCERTAIN?
   ↓
WHAT ARE THE COMPETING EXPLANATIONS?
   ↓
WHAT RESULT WOULD CHANGE OUR MIND?
   ↓
WHAT IS THE CHEAPEST DECISIVE EXPERIMENT?
   ↓
PREDICT OUTCOMES
   ↓
EXECUTE
   ↓
COMPARE OBSERVATION TO PREDICTION
   ↓
UPDATE RESEARCH STATE
```

Make this structure explicit in planner records.

---

# 7. Improve uncertainty prioritization

Do not prioritize uncertainties only by static importance.

Consider:

```text
decision relevance
scientific importance
downstream dependency
current uncertainty
discrimination potential
cost to resolve
risk of invalidating project
```

Especially prioritize **upstream uncertainties**.

Example:

```text
U1:
Does the phenomenon exist?

U2:
Which scheduling policy is optimal?
```

U1 should dominate U2.

Do not optimize implementation details before establishing the premise.

---

# 8. Introduce blocking uncertainty

Allow uncertainties to block downstream work.

Example:

```text
U1: Is reuse sufficiently skewed?
    status = OPEN
    blocks = [H3, H4, E10-E30]
```

If U1 is unresolved:

```text
do not spend large compute optimizing placement policy
```

This should be enforced by planner policy.

---

# 9. Improve candidate experiment generation

For every important uncertainty, candidate generation should consider different experimental strategies.

Examples:

```text
measurement
controlled intervention
oracle experiment
counterfactual
ablation
stress test
trace analysis
microbenchmark
end-to-end benchmark
replication
```

Require at least one candidate to be a **cheap falsification attempt** when appropriate.

Ask:

> What is the cheapest experiment that could kill this hypothesis?

before:

> What is the full experiment proving it?

---

# 10. Introduce Oracle Experiments

Systems research often benefits from oracle upper bounds.

Support experiment type:

```text
ORACLE
```

Example:

```text
Before implementing a sophisticated reuse predictor:

Assume perfect reuse prediction.

Measure the maximum possible benefit.
```

If oracle improvement is negligible:

```text
STOP implementation work
```

This should be a preferred early-stage experiment when applicable.

---

# 11. Motivation gates

Before expensive implementation, require motivation evidence when relevant.

Conceptually:

```text
Problem magnitude
       ↓
Oracle opportunity
       ↓
Mechanism feasibility
       ↓
Prototype
       ↓
End-to-end evaluation
```

Planner should penalize:

```text
complex implementation
```

when:

```text
problem magnitude
```

or:

```text
oracle opportunity
```

has not been established.

---

# 12. Experiment value model

Refine the current heuristic.

Candidate value should conceptually consider:

```text
Value(E) =

decision_relevance
× uncertainty_reduction
× discrimination_power
× downstream_unlock_value
× feasibility

--------------------------------

compute_cost
× implementation_cost
× execution_risk
```

Do NOT claim mathematical precision.

Store components separately.

Example:

```yaml
decision_relevance: HIGH
uncertainty_reduction: HIGH
discrimination_power: MEDIUM
downstream_unlock_value: HIGH

compute_cost: LOW
implementation_cost: LOW
execution_risk: LOW
```

Then derive an ordinal ranking.

Avoid fake decimal precision such as:

```text
score = 0.873421
```

unless genuinely computed from calibrated quantities.

---

# 13. Prediction quality

Before execution, require more than:

```text
metric should improve
```

Prediction should include:

```text
direction
expected magnitude/range when defensible
mechanistic reason
boundary conditions
what outcome would surprise us
what outcome falsifies the hypothesis
```

Example:

```yaml
prediction:

  expected:
    TTFT:
      direction: decrease
      approximate_range: 10-20%

  mechanism:
    fewer repeated HBM transfers

  boundary:
    benefit should disappear when reuse < 1.2x

  surprising_result:
    TPOT increases >10%

  falsification:
    oracle placement improves TTFT <2%
```

---

# 14. Surprise detection

After execution, compare:

```text
prediction
vs
observation
```

Explicitly classify:

```text
EXPECTED
PARTIALLY_EXPECTED
SURPRISING
STRONGLY_CONTRADICTORY
```

A surprising result should not automatically be treated as failure.

It may create a new uncertainty.

Example:

```text
Expected:
TTFT improves.

Observed:
TTFT unchanged,
TPOT improves significantly.

→ create new uncertainty:
Why did TPOT improve instead?
```

---

# 15. Unexpected-result branching

Allow Findings to create:

```text
new in-scope uncertainty
```

or:

```text
new sub-hypothesis
```

without Human Gate if and only if:

```text
it remains inside Project Envelope
does not materially expand budget
does not change core research question
```

Example:

```text
Finding F31
    ↓
unexpected behavior
    ↓
U22
    ↓
H7
    ↓
cheap discrimination experiment
```

This is a core auto-research capability.

---

# 16. Anti-confirmation-bias mechanism

Before executing a central claim experiment, require a challenger pass.

The challenger should ask:

```text
What alternative explanation fits the same evidence?

What confounder could produce this result?

What baseline would make the proposed contribution disappear?

What experiment could falsify our preferred explanation?

Are we measuring the mechanism or merely correlated performance?
```

Store the challenge.

Do not require a separate LLM if the current reasoning adapter can produce an independently prompted challenger output.

---

# 17. Research debt

Introduce lightweight Research Debt tracking.

Examples:

```text
missing baseline

unreplicated central result

unexplained anomaly

unverified workload realism

weak motivation evidence

missing sensitivity test

measurement instability
```

Debt should affect planning.

Example:

```text
central result exists
but no replication

→ replication debt HIGH

→ prioritize replication
```

Do not allow dozens of new experiments while central research debt accumulates.

---

# 18. Evidence maturity

Define evidence maturity for major claims.

Example:

```text
LEVEL 0 — hypothesis only

LEVEL 1 — motivation evidence

LEVEL 2 — preliminary experiment

LEVEL 3 — replicated

LEVEL 4 — mechanism isolated

LEVEL 5 — sensitivity/boundary established

LEVEL 6 — end-to-end validated
```

Do not assume every claim needs every level.

Make maturity requirements claim-specific.

This will later drive paper readiness.

---

# 19. Human Gate #2 improvement

Upgrade Gate #2 into a research review rather than a simple status summary.

It should answer:

```text
What did we originally believe?

What do we believe now?

Which hypotheses survived?

Which were falsified?

What surprised us?

What is the strongest evidence?

What is still weak?

Which research debt remains?

What experiments changed our understanding most?

How much compute was consumed?

What is the remaining opportunity?

Is there enough evidence to define a paper story?
```

Suggested actions:

```text
CONTINUE_EXPLORATION
FOCUS_MECHANISM
REPLICATE
EXPAND_EVALUATION
STOP_PROJECT
REQUEST_SCOPE_CHANGE
FREEZE_STORY
```

Human makes the final Gate #2 decision.

---

# 20. Real-project pilot

After implementation and synthetic validation, perform the first real-project **planning pilot**.

Do NOT automatically launch expensive scientific experiments.

Use one existing research seed from the user's upstream plan directory:

```text
/Users/kexin.chu/Github/paper-manager/Ideas/Research-Map/plans/
```

Choose only an idea already marked GO.

If no real idea is GO:

```text
STOP
```

and report that Human Gate #1 is required.

Never convert upstream ranking/recommendation into GO automatically.

---

# 21. For the pilot, run S5/S6 deeply

For the selected GO project:

construct:

```text
Core Question

Project Envelope

Research Question Graph

Hypotheses

Competing Hypotheses

Uncertainties

Blocking Uncertainties

Candidate Experiments

Oracle Experiments

Motivation Tests

Expected Findings

Kill Criteria

Research Debt
```

Then run:

```text
researchos next PROJECT_ID
```

and inspect whether the selected experiment is scientifically sensible.

Do NOT execute it automatically yet unless it is:

```text
cheap
safe
within scope
within approved budget
and explicitly allowed by existing execution policy
```

For any substantial GPU experiment:

```text
prepare the frozen experiment
but stop before dispatch
```

and report it for review.

The objective is to test **research quality**, not GPU automation.

---

# 22. Add planner evaluation harness

This is important.

We need a way to determine whether ResearchOS is becoming a better researcher.

Create offline planner-evaluation cases.

Each case should contain:

```text
research state

hypotheses

findings

uncertainties

candidate experiments

known bad choices

expected reasoning properties
```

Examples:

### Case A

```text
Problem magnitude unknown.
Complex optimization available.
```

Expected:

```text
choose motivation measurement
NOT optimization
```

### Case B

```text
Oracle benefit ≈ 0.
```

Expected:

```text
stop implementation branch
```

### Case C

```text
Central result positive but unreplicated.
```

Expected:

```text
replicate
```

### Case D

```text
Two competing mechanisms explain result.
```

Expected:

```text
choose discrimination experiment
```

### Case E

```text
Unexpected result contradicts prediction.
```

Expected:

```text
create uncertainty
NOT rewrite prediction
```

---

# 23. Planner regression suite

Create a durable set of research-reasoning regression cases.

The test should verify structural properties rather than exact prose.

For example:

```text
selected experiment type
blocked experiment not selected
falsification candidate considered
replication triggered
scope escalation triggered
oracle gate respected
```

Do not test exact LLM wording.

---

# 24. Deterministic vs reasoning tests

Separate:

```text
deterministic unit tests
```

from:

```text
research reasoning evaluations
```

Deterministic CI must remain fully reproducible.

LLM/reasoning evaluations should be separately labeled and should not make ordinary CI flaky.

If an external reasoning model is unavailable:

```text
deterministic tests still pass
```

---

# 25. Context architecture

Do not send the entire database to the reasoning model.

Create a Research Context Builder.

Suggested output:

```yaml
project:
  question:
  envelope:

hypotheses:
  active:
  supported:
  falsified:

uncertainties:
  blocking:
  high_priority:

findings:
  central:
  recent:
  contradictory:

research_debt:

resources:

budget:

candidate_dependencies:
```

Bound context size.

Prefer scientific relevance over recency alone.

---

# 26. Research journal

Create a compact machine-generated research journal.

Each research iteration should append something equivalent to:

```text
Iteration 12

Question:
...

Belief before:
...

Critical uncertainty:
...

Experiment:
...

Prediction:
...

Observation:
...

Interpretation:
...

Belief after:
...

New uncertainty:
...

Decision:
...
```

This should be derived from structured DB state.

Do not make Markdown journal the source of truth.

SQLite remains authoritative.

---

# 27. Research trajectory visualization

Add a lightweight command:

```bash
researchos trajectory PROJECT_ID
```

It should show:

```text
H1 ACTIVE
 │
 E1
 │
 F1 SUPPORT
 │
 ├── U3
 │    │
 │    E4
 │    │
 │    F5 FALSIFY
 │
 H1 FALSIFIED

H2 ACTIVE
 │
 E2
 │
 F2 SUPPORT
 │
 E6 REPLICATION
 │
 F7 SUPPORT
 │
 H2 SUPPORTED
```

Plain text / Markdown output is sufficient.

Do NOT build a web dashboard.

---

# 28. No autonomous literature scope expansion yet

Research reasoning may identify:

```text
prior-art question
missing baseline
novelty concern
```

but V0.3 must not autonomously expand the Project Envelope based on newly discovered literature.

Instead create:

```text
LITERATURE_CHECK_REQUIRED
```

or Research Debt.

Literature intelligence will be a later stage.

---

# 29. Tests

Add tests for at least:

1. Research Question Graph relationships persist correctly
2. hypothesis types persist
3. competing hypotheses represented
4. blocking uncertainty blocks downstream optimization
5. existence/motivation experiment outranks premature optimization
6. oracle experiment can kill implementation branch
7. candidate includes outcome interpretations
8. prediction stores mechanism and falsification
