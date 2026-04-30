"""Scaffold an Obsidian workspace for PhD knowledge management."""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from nextbrain.config import get_obsidian_vault_path, get_output_language
from nextbrain.tools.io import write_markdown


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _language() -> str:
    lang = get_output_language().strip().lower()
    return "zh" if lang == "zh" else "en"


def _dashboard_md(lang: str) -> str:
    if lang == "zh":
        return f"""---
title: "Research Home"
type: dashboard
created_at: {_today()}
updated_at: {_today()}
---

# Research Home

## 研究节奏

1. 用 `nextbrain record <url>` 把新论文收进系统。
2. 把跨论文的理解沉淀到 `Concepts/`。
3. 把课题目标、风险和下一步维护在 `Projects/`。
4. 每周在 `Syntheses/` 写一次综合复盘。

## 文件夹说明

- `Papers-*`：按论文类型自动生成的文献笔记
- `Idea/`：研究想法
- `Concepts/`：概念、方法、问题定义
- `Projects/`：具体课题、实验线、合作项目
- `Syntheses/`：周报、综述草稿、研究地图
- `Daily/`：每日研究日志
- `Research/`：主题追踪配置
- `Templates/`：模板

## 本周关注

- 主题 1：
- 主题 2：
- 主题 3：

## 固定检查项

- 今天新增了哪些值得保留的论文？
- 哪个概念需要独立成笔记？
- 哪个项目最值得推进？
- 本周应该写哪一份 synthesis？
"""

    return f"""---
title: "Research Home"
type: dashboard
created_at: {_today()}
updated_at: {_today()}
---

# Research Home

## Weekly Cadence

1. Capture new papers with `nextbrain record <url>`.
2. Distill cross-paper ideas into `Concepts/`.
3. Track active work, risks, and next moves in `Projects/`.
4. Write one synthesis each week in `Syntheses/`.

## Folder Guide

- `Papers-*`: auto-generated paper notes by taxonomy
- `Idea/`: research ideas
- `Concepts/`: concepts, methods, problem definitions
- `Projects/`: active research threads and experiments
- `Syntheses/`: weekly digests, survey drafts, research maps
- `Daily/`: daily research logs
- `Research/`: topic-tracking configs
- `Templates/`: reusable note templates

## Current Focus

- Theme 1:
- Theme 2:
- Theme 3:

## Review Prompts

- What new papers are worth keeping?
- Which concept deserves its own note?
- Which project should move next?
- What synthesis should I write this week?
"""


def _concept_template_md(lang: str) -> str:
    if lang == "zh":
        return """---
type: concept
title:
aliases:
tags:
projects:
---

# Definition

这个概念在你的研究语境里是什么意思？

# Why It Matters

它为什么重要？它影响了哪些研究问题、方法选择或评估方式？

# Key Distinctions

- 它和相邻概念有什么边界？
- 最容易混淆的点是什么？

# Linked Papers

- 

# My Current View

你目前怎么理解它？这个理解和文献共识一致吗，还是有自己的判断？

# Open Questions

- 还不清楚什么？
- 哪些论文能帮助澄清？
"""

    return """---
type: concept
title:
aliases:
tags:
projects:
---

# Definition

What does this concept mean in your research context?

# Why It Matters

Why is it important for your problem framing, method choices, or evaluation?

# Key Distinctions

- What boundaries separate it from nearby concepts?
- What is the most common confusion point?

# Linked Papers

- 

# My Current View

What is your current understanding, and where does it differ from the literature consensus?

# Open Questions

- What is still unclear?
- Which papers would help resolve it?
"""


def _project_template_md(lang: str) -> str:
    if lang == "zh":
        return """---
type: project
title:
status: active
tags:
---

# Objective

这个项目当前想回答什么问题？

# Why Now

为什么现在推进它？它和你的博士主线是什么关系？

# Core Hypothesis

当前最值得验证的假设是什么？

# Inputs

- 关键论文：
- 关键数据：
- 关键实验资源：

# Progress Log

- 

# Risks

- 最大技术风险：
- 最大研究风险：
- 最大时间风险：

# Next 3 Moves

1. 
2. 
3. 
"""

    return """---
type: project
title:
status: active
tags:
---

# Objective

What question is this project trying to answer right now?

# Why Now

Why is this worth pushing now, and how does it connect to your PhD arc?

# Core Hypothesis

What is the most valuable hypothesis to test next?

# Inputs

- Key papers:
- Key datasets:
- Key resources:

# Progress Log

- 

# Risks

- Biggest technical risk:
- Biggest research risk:
- Biggest time risk:

# Next 3 Moves

1. 
2. 
3. 
"""


def _weekly_synthesis_template_md(lang: str) -> str:
    if lang == "zh":
        return """---
type: synthesis
period:
projects:
tags:
---

# This Week In One Paragraph

用一小段话总结这周真正发生了什么。

# What I Read

- 哪几篇最重要？
- 哪一篇最改变你的判断？

# What I Learned

- 哪个概念更清楚了？
- 哪个方法更值得追？
- 哪个方向其实不值得继续投入？

# What Moved Forward

- 哪个项目推进了？
- 推进的证据是什么？

# Open Problems

- 当前最卡的点是什么？
- 哪些问题需要补文献、补实验、补交流？

# Next Week

1. 必做的一件事：
2. 最值得读的一类论文：
3. 最值得验证的一个假设：
"""

    return """---
type: synthesis
period:
projects:
tags:
---

# This Week In One Paragraph

Summarize what actually happened this week.

# What I Read

- Which papers mattered most?
- Which one changed your judgment the most?

# What I Learned

- Which concept became clearer?
- Which method became more promising?
- Which direction is probably not worth more time?

# What Moved Forward

- Which project advanced?
- What evidence shows progress?

# Open Problems

- What is still blocking you?
- Which gaps need more reading, experiments, or discussion?

# Next Week

1. One must-do item:
2. The most valuable kind of paper to read:
3. One hypothesis to validate:
"""


def _daily_template_md(lang: str) -> str:
    if lang == "zh":
        return """---
type: daily
date:
projects:
tags:
---

# Top 3 Priorities

1. 
2. 
3. 

# Reading Notes

- 今天看了什么？
- 哪一条值得迁移到概念笔记或项目笔记？

# Experiments And Work

- 做了什么？
- 结果是什么？

# Blockers

- 卡点是什么？
- 需要谁或什么来解？

# Migrate Before Ending The Day

- [ ] 迁移到 `Concepts/`
- [ ] 更新 `Projects/`
- [ ] 补进 `Syntheses/`
"""

    return """---
type: daily
date:
projects:
tags:
---

# Top 3 Priorities

1. 
2. 
3. 

# Reading Notes

- What did I read today?
- What should be migrated into a concept or project note?

# Experiments And Work

- What did I do?
- What happened?

# Blockers

- What is blocking progress?
- What would unblock it?

# Migrate Before Ending The Day

- [ ] Move key ideas into `Concepts/`
- [ ] Update `Projects/`
- [ ] Add to `Syntheses/`
"""


def _topics_example_yaml(lang: str) -> str:
    if lang == "zh":
        return """topics:
  - id: topic-1
    label: Topic 1
    goal: >
      用一句话说明这个主题为什么对你的博士主线重要。
    queries:
      - '"keyword phrase 1"'
      - '"keyword phrase 2" AND method'
    include_authors:
      - Author Name
    exclude_keywords:
      - benchmark only
      - workshop abstract
    sources:
      - arxiv
      - openalex
      - crossref
      - semantic_scholar
    priority: high

  - id: topic-2
    label: Topic 2
    goal: >
      最好是你未来 6 到 12 个月会持续追踪的方向。
    queries:
      - '"problem name"'
      - '"problem name" AND survey'
    include_authors: []
    exclude_keywords: []
    sources:
      - arxiv
      - openalex
    priority: medium
"""

    return """topics:
  - id: topic-1
    label: Topic 1
    goal: >
      Explain in one sentence why this theme matters for your PhD trajectory.
    queries:
      - '"keyword phrase 1"'
      - '"keyword phrase 2" AND method'
    include_authors:
      - Author Name
    exclude_keywords:
      - benchmark only
      - workshop abstract
    sources:
      - arxiv
      - openalex
      - crossref
      - semantic_scholar
    priority: high

  - id: topic-2
    label: Topic 2
    goal: >
      Prefer themes you expect to track for the next 6 to 12 months.
    queries:
      - '"problem name"'
      - '"problem name" AND survey'
    include_authors: []
    exclude_keywords: []
    sources:
      - arxiv
      - openalex
    priority: medium
"""


def scaffold_phd_workspace(
    vault_path: str | None = None,
    force: bool = False,
) -> Tuple[Path, List[Path], List[Path]]:
    """Create a PhD-oriented workspace structure inside an Obsidian vault."""
    vault = Path(vault_path or get_obsidian_vault_path()).expanduser()
    lang = _language()

    folders = [
        "Concepts",
        "Projects",
        "Syntheses",
        "Daily",
        "Dashboards",
        "Research",
        "Templates",
        "Explore",
    ]
    changed: List[Path] = []
    skipped: List[Path] = []

    for folder in folders:
        path = vault / folder
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            changed.append(path)

    files: Dict[str, str] = {
        "Dashboards/Research Home.md": _dashboard_md(lang),
        "Templates/Concept Note.md": _concept_template_md(lang),
        "Templates/Project Note.md": _project_template_md(lang),
        "Templates/Weekly Synthesis.md": _weekly_synthesis_template_md(lang),
        "Templates/Daily Research Log.md": _daily_template_md(lang),
        "Research/topics.example.yaml": _topics_example_yaml(lang),
    }

    for rel_path, content in files.items():
        path = vault / rel_path
        if path.exists() and not force:
            skipped.append(path)
            continue
        if path.suffix == ".md":
            write_markdown(path, content)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        changed.append(path)

    return vault, changed, skipped
