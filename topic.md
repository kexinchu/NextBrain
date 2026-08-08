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
