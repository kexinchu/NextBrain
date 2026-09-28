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
