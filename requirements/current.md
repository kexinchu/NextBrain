---
schema_version: 1
source_digest: 7c2ed5482e8b704f6f0e7cd4d8821be2bf4517c9a96552ce10e5e0b1fba11c63
covered_messages:
- 0001-20260808T051800.798506Z.md
- 0002-20260808T051801.363439Z.md
- 0003-20260808T051801.527089Z.md
- 0004-20260808T053259.264853Z.md
- 0005-20260808T054141.223178Z.md
- 0006-20260808T151658.785847Z.md
- 0007-20260808T175907.076512Z.md
---

# 当前约束（覆盖 0001-0007）

- [0001] 将旧项目整体替换为可由 pip 安装和调用的 auto-research repo；借鉴优秀开源工具，但保留人为控制。流程拆为六个 skills：双独立 sub-agent 交替的 idea scout/challenger loop、人工参与的 story freeze、不得改论文的 implementation loop、不得改论文和 core 的 experiment loop、按目标会议与近一年录用论文逐章优化但不改变科学内容的 writing、只输出审稿意见的 venue review。每条对 agents 的原话必须独立记录；每轮重读需求并检查漂移。
- [0002] 研究 topic 由一个 Markdown 文档指向，该文档同步记录 session 要求；idea-loop 的可读、可人工修改输出固定为 `story.md`。
- [0003] 六个 skills 必须能在 GPT/Claude/Cursor 对话中使用，并继承该对话当前选择的模型，不能暗中换后台模型。
- [0004] 必须从性能与能力角度评估这些 skills 是否满足需要，并明确优化项与证据边界。
- [0005] 实施全部已识别的 P0、P1、P2 优化；不得用本地测试冒充真实客户端或科研质量证据。
- [0006] 研究领域以 systems 和 AI infrastructure 为主；主要目标会议包括 SOSP、FAST、OSDI、ATC、EuroSys、MLSys，也兼顾 ICLR、NIPS、AAAI、DAC。工具应规范会议别名、识别会议状态变化，并按不同 venue community 的真实 contribution type 评估 idea、写作与审查，不能只替换叙事标签。
- [0007] 将当前完整 AutoResearch rewrite 提交到 GitHub，形成可追踪的 Git 历史和远端审查入口。
