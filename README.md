# NextBrain AutoResearch

一个面向系统与机器学习研究的、**人为控制 + 可审计 + 有冻结边界**的 auto-research
工具箱。它不是让一个 agent 从头到尾自由改写所有内容，而是把科研流程拆成六个可通过 `pip`
安装、可在 GPT/Claude/Cursor 对话框直接触发的 skills，并由确定性 Python 状态机约束每轮读什么、
能改什么、需要什么证据、何时必须停下报告。当前对话中选中的模型就是后台模型；skills 不会偷偷调用第二个模型。

## 六个 skills

| Skill | 角色与循环 | 可修改内容 | 必须停止的情况 |
|---|---|---|---|
| `idea-loop` | 两个独立的宿主原生 sub-agent：scout 与 sampled challenger 交替 | `story.md` | 撞车、motivation test 失败、需求冲突、或 idea 通过全部 gate |
| `story-freeze` | idea + 人为干预 -> 科研合同 | `paper/STORY.md` | 设计/claim/实验矩阵仍有歧义 |
| `implementation-loop` | 实现 + 小规模测试 | `code/core/`、`code/tests/`、支持性 probes | 需要改 idea/设计，或小测证伪前提 |
| `experiment-loop` | 批量实验与结论导出 | `experiments/scripts/`、`experiments/results/` | 结果与冻结 prediction 不一致 |
| `section-writing` | 按会议逐章优化 | 单个 `paper/manuscript/<section>.md` | 好的写法需要改变科学内容 |
| `venue-review` | 按会议标准独立审查 | `reviews/` | 只审，不修改论文 |

默认研究域是 systems 与 AI infrastructure。Active primary venues 为 SOSP、FAST、OSDI、
EuroSys、MLSys；secondary venues 为 ICLR、NeurIPS、AAAI、DAC。输入 `NIPS` 会规范为
`NeurIPS`。USENIX ATC 已在 ATC '25 后结束，因此只保留为历史论文风格与比较 corpus，不能作为
新的 active submission target。会议规则、track、页数和审稿政策必须在每次 venue-dependent
round 中从当年官方来源刷新，不能依赖静态记忆。详见 [Venue profiles](docs/venues.md)。

## 安装到 GPT、Claude 和 Cursor

```bash
python -m pip install .
autoresearch --workspace /path/to/research init
cd /path/to/research
autoresearch install-skills --target all --scope project
```

安装结果：

```text
.agents/skills/       # GPT/ChatGPT desktop 与 Codex
.claude/skills/       # Claude Code
.cursor/skills/       # Cursor
```

然后直接在对应对话框选择或调用 `idea-loop`、`story-freeze` 等 skill。Codex 可使用
`$idea-loop` 或 `/skills`，Claude/Cursor 可使用 `/idea-loop`；GPT/ChatGPT desktop 在支持
skills 的界面使用 `@` 选择。六份 skill 都声明或明确要求继承当前会话模型，并禁止调用
`OpenAIAgent`、`CommandAgent`、模型 API 或 `autoresearch run`。OpenAI 客户端还会安装
`agents/openai.yaml` UI metadata，并默认要求显式调用。完整说明见
[Conversation hosts](docs/conversation-hosts.md)。

Cursor 的官方说明目前仍把 Agent Skills 标为 Nightly 功能；若稳定版没有发现 `.cursor/skills/`，需
在 Cursor 设置中切换到 Nightly 并重启。

如只安装一个客户端或安装到用户级目录：

```bash
autoresearch install-skills --target claude --scope project
autoresearch install-skills --target cursor --scope user
```

仓库还带有 `.codex-plugin/plugin.json`，可作为本地 Codex plugin bundle 使用。ChatGPT web
工作区的服务端发布仍需要该工作区对应的 plugin/skill 分发流程；`pip install` 本身不会把本地
文件发布到 ChatGPT web。

开发安装与测试：

```bash
pip install -e .

pip install -e ".[dev]"
```

安装后也可检查 skills：

```bash
autoresearch skills list
autoresearch skills show idea-loop
autoresearch venues list
autoresearch venues show NIPS  # returns canonical NeurIPS profile
```

## 对话原生工作流

### 1. 初始化，并逐条记录你对 agents 说的话

```bash
autoresearch --workspace ./demo init
# 编辑 ./demo/topic.md，写入研究方向、scope 和 kill criteria
autoresearch --workspace ./demo message "研究方向是 CXL + ANNS。"
autoresearch --workspace ./demo message "不要提出已有进行中的 Repair idea。"
autoresearch --workspace ./demo message --file ./long-requirement.md
```

每条消息都会成为独立文件：

```text
demo/requirements/messages/
├── 0001-<timestamp>.md
├── 0002-<timestamp>.md
└── 0003-<timestamp>.md
```

workspace 中的 `topic.md` 是 active topic 文档；`.autoresearch/active-topic.json` 保存它的路径。
每条 `message` 和 `run` directive 都会自动镜像进该文档的 `Session requirements`，同时保留上述
独立 Markdown 源记录。`.manifest.json` 保存每条历史消息的哈希；旧消息被改写时系统拒绝继续。
每轮 agent 调用前，系统读取完整 topic 文档、验证所有源消息并计算组合 SHA-256 digest；agent 必须回显该 digest，
结束后系统写 `runs/<round>/alignment.md`。如果调用期间需求发生变化，该轮自动变成 `report`，
需要基于新需求重跑。每个 `autoresearch run ...` 的科研参数也会先自动保存为一条独立 run
directive；使用 Python API 时，则由调用方在调用 skill 前执行 `UserMessageJournal.add(...)`。

长 session 可以维护经过覆盖检查的压缩视图。摘要必须显式引用每个 message ID；新增消息会立即让
旧摘要失效，系统自动回退到完整 topic：

```bash
autoresearch requirements update --file requirements-summary-draft.md
autoresearch requirements status
```

每次 skill 收到新的用户指令，都会先把原话写成新的 Markdown，再调用 `message --file`。
`host begin` 必须绑定返回的最新 message filename；状态机拒绝旧消息、重复 pending round、错误角色、
跳阶段、超出 round budget 或连续执行两个 scout。

`host begin` 返回独立的 `transaction_workspace`。模型只能在这里写拟议产物，同时生成
`evidence.json`。`host complete` 检查需求 digest、冻结哈希、artifact schema、证据和状态迁移后才把
文件原子提升到主 workspace。若模型直接修改主 workspace，系统把违规版本保存到 transaction 的
`quarantine/`，再恢复轮次开始前的内容。每轮报告保存在 `runs/<round-id>/alignment.md`。

`idea-loop` 会要求宿主启动两个全新的原生 sub-agent。Python 状态机会核对 agent ID、强制
scout/challenger 交替，并根据 collision risk、novelty uncertainty、scope risk、motivation cost
与 approach diversity 生成 challenger 的风险分层样本。宿主没有 sub-agent 能力时必须停下。

`story.md` 和 `paper/STORY.md` 使用人可读 Markdown + YAML frontmatter，机器验证 candidate、source、
claim 和 experiment ID 的引用关系；paper-stage 的每个实验还必须冻结 prediction、数据集、baseline、
metric、scale、seed、资源预算、成功阈值与 kill criteria。格式见
[Research contracts](docs/contracts.md)。

### 2. 预授权确定性命令

模型不能提供任意 shell command。用户在 `autoresearch.yaml` 中按名称授权精确 argv：

```yaml
commands:
  implementation-tests:
    skill: implementation-loop
    argv: [python, -m, pytest, code/tests]
    timeout: 3600
```

轮次中只能调用：

```bash
autoresearch host check <round-id> implementation-tests
```

实现冻结必须有当轮成功 check receipt，而且 receipt 的 workspace digest 必须等于最终 staged 内容；
check 后再改代码会使 receipt 失效。实验完成还必须覆盖冻结矩阵的全部 experiment ID，并提交与冻结
实验 mapping 匹配的 protocol digest。

### 3. Story 两阶段批准

第一轮 story draft 只能 `continue`。系统返回 draft digest 后，用户必须在后续消息中给出：

```text
APPROVE paper/STORY.md <exact-draft-digest>
```

记录这条新消息并执行 `host approve-story` 后，未改动的同一 draft 才能 `satisfied` 并冻结。

### 4. Workspace doctor、更新与 E2E gate

```bash
autoresearch client-skills status --target all
autoresearch client-skills update --target all
autoresearch client-skills uninstall --target cursor
autoresearch doctor
autoresearch eval
autoresearch eval --release
```

真实客户端测试通过后，把截图、日志或 Markdown 证据登记为不可替换的 digest receipt：

```bash
autoresearch e2e record --client claude --skill idea-loop \
  --model claude-model-name --status pass --evidence ./e2e/claude-idea.md

autoresearch doctor --require-e2e
autoresearch doctor --release --require-e2e
```

没有真实 E2E receipt 时，release gate 会保持失败，不能把本地测试冒充 GPT/Claude/Cursor 验证。

### 5. 可选的 legacy standalone adapter 模式（已弃用）

对话框之外，仍可以显式选择 command adapter。该兼容接口已弃用，不参与新的 host-native
能力保证；新工作流应使用 `host begin/check/complete`：

```bash
autoresearch --workspace ./demo run idea \
  --topic topic.md \
  --max-rounds 6 --sample-size 3 \
  --agent-command "my-research-agent --json"
```

`idea-scout` 负责文献搜索、问题潜力、baseline、motivation test 与 kill criteria；
`idea-challenger` 每轮只审核前 `sample-size` 个候选，控制开销。任一方发现需要人为决策的问题，
或 challenger 接受某个 idea，loop 立即停止。两个角色每轮都会读取当前 `story.md`，并把完整、
便于人工阅读的故事重新写回该文件；你可以直接修改它，再启动下一次 idea loop。

Agent command 的协议很小：完整 prompt 从 stdin 输入；stdout 返回一个 JSON object。格式见
[Architecture](docs/architecture.md)。这是可选兼容模式，不是对话 skills 的执行路径。

#### 5.1 冻结故事（legacy）

`idea-loop` 接受后，直接把可编辑的 `story.md` 转换为冻结科研合同：

```bash
autoresearch --workspace ./demo run story \
  --human-context "只承诺静态查询，不包含 online repair。" \
  --agent-command "my-research-agent --json"
```

包含 `--human-context` 的 run directive 会被单独记录为一条 Markdown。成功后生成
`.autoresearch/freezes/paper-story.json`；后续实现和实验每轮前后都会校验它。

#### 5.2 实现并冻结核心代码（legacy）

```bash
autoresearch --workspace ./demo run implement \
  --max-rounds 8 \
  --check-command "python -m pytest code/tests" \
  --agent-command "my-coding-agent --json"
```

只有你通过 `--check-command` 提供的命令会被执行；模型输出中的 shell 文本永远不会被自动执行。
当 agent 返回 `decision=satisfied`，系统冻结 `code/core/`。

#### 5.3 批量实验（legacy）

```bash
autoresearch --workspace ./demo run experiment \
  --max-rounds 12 \
  --run-command "python experiments/scripts/run_batch.py" \
  --agent-command "my-research-agent --json"
```

实验 skill 每轮都校验 story 与 core-code 两个 freeze。结论与 prediction 不一致时只能汇报，
不能改论文或核心代码。

#### 5.4 逐章写作与审稿（legacy）

```bash
autoresearch --workspace ./demo run write \
  --venue "OSDI" --section introduction \
  --accepted-corpus venue-corpus/osdi-2025 \
  --agent-command "my-research-agent --json"

autoresearch --workspace ./demo run review \
  --venue "OSDI" --venue-guide venue/osdi-review.md \
  --agent-command "my-research-agent --json"
```

写作只改变表达层 `paper/manuscript/`；`paper/STORY.md` 继续作为不可篡改的科学真值。

## 可选 OpenAI API adapter（仅 standalone 模式）

也可以不写 command adapter，直接使用可选 OpenAI backend：

```bash
export OPENAI_API_KEY=...
autoresearch --workspace ./demo run idea \
  --topic topic.md --openai-model gpt-5.6-terra
```

当前 adapter 使用 Responses API。它只服务显式的 `autoresearch run`；在 GPT/Claude/Cursor
对话框触发的六个 skills 不读取 API key，也不经过这个 adapter。

## 设计来源与区别

本项目研究了 Karpathy autoresearch、AI Scientist v1/v2、Agent Laboratory 与
AI-Research-SKILLs。具体借鉴点、风险边界和链接见 [prior-art.md](docs/prior-art.md)。核心区别是：
这里的禁止修改、停止条件与记录要求由 Python + 路径 allowlist + 内容哈希执行，而不只依赖 prompt。

## 当前范围

这是可以安装并在三类对话宿主中使用的第一版基础设施。它没有声称已经替你完成某个具体 idea
的文献检索、实现或大规模实验，也不会把本地 smoke test 当作论文证据。真实运行前，应配置
计算资源、检索源和 venue corpus，并确认所选对话宿主提供 skill 所需的工具与 sub-agent 能力。
