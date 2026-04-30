"""Daily and weekly research report generator.

Daily  (Mon–Sat): scan papers with created_at == today AND ingested_via == email
                  → LLM generates: what was read, key insights, research implications
                  → send email to user; skip if no new papers

Weekly (Sunday):  scan papers with created_at in last 7 days
                  → LLM generates: weekly synthesis of learning + implications
                  → always send (even if quiet week)
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple


# ── Note scanning ────────────────────────────────────────────────────────────

_FM_RE           = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_CREATED_RE      = re.compile(r"^created_at:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_INGESTED_VIA_RE = re.compile(r"^ingested_via:\s*(\w+)", re.MULTILINE)
_TITLE_RE        = re.compile(r'^title:\s*"?([^"\n]+)"?', re.MULTILINE)
_PTYPE_RE        = re.compile(r"^paper_type:\s*(.+?)\s*$", re.MULTILINE)
_FIRST_PARA_RE   = re.compile(r"^##\s+.+?\n+(.+?)(?=\n##\s|\Z)", re.MULTILINE | re.DOTALL)


def _read_fm(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
    except OSError:
        return ""
    m = _FM_RE.match(head)
    return m.group(1) if m else ""


def _first_section(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    body = _FM_RE.sub("", text, count=1)
    m = _FIRST_PARA_RE.search(body)
    if not m:
        return ""
    s = " ".join(m.group(1).split())
    return s[:300] + "…" if len(s) > 300 else s


def _papers_in_window(vault: Path, since: str, until: str) -> List[Tuple[str, str, str]]:
    """Return list of (title, paper_type, problem_snippet) for papers created in [since, until]."""
    results = []
    for md in vault.glob("Papers-*/*.md"):
        fm = _read_fm(md)
        if not fm:
            continue
        cm = _CREATED_RE.search(fm)
        if not cm:
            continue
        created = cm.group(1)
        if not (since <= created <= until):
            continue
        # For daily report, only count email-ingested papers
        if since == until:   # daily window
            vm = _INGESTED_VIA_RE.search(fm)
            if not vm or vm.group(1).strip() != "email":
                continue
        tm = _TITLE_RE.search(fm)
        pm = _PTYPE_RE.search(fm)
        title = tm.group(1).strip() if tm else md.stem
        ptype = pm.group(1).strip().strip('"\'') if pm else "Other"
        snippet = _first_section(md)
        results.append((title, ptype, snippet))
    return results


# ── Prompt templates ─────────────────────────────────────────────────────────

_DAILY_SYSTEM = """\
你是一个学术研究助理，帮助一位 ML systems 方向的 PhD 整理每日阅读收获。

风格要求：
- 语言：中文
- 语气：简洁、有洞察力、像和导师对话
- 避免逐篇复述，关注跨论文的共性与差异
- 重点突出对用户当前研究的潜在价值

输出格式（Markdown）：
## 今日新增论文 (N篇)
> 分主题一两句话概括整体

## 关键洞察
- 每条洞察跨越至少两篇论文

## 对我的 Research 的启发
- 具体可行的想法或需要关注的方向

## 值得精读
- 最多 3 篇，说明为什么值得深入
"""

_WEEKLY_SYSTEM = """\
你是一个学术研究助理，帮助一位 ML systems 方向的 PhD 完成每周学习复盘。

风格要求：
- 语言：中文
- 语气：有深度，像学术周报
- 纵向总结这一周的知识积累，找出趋势和空白
- 对下周的研究方向给出具体建议

输出格式（Markdown）：
## 本周概览
> 本周新增 N 篇，主要集中在哪些方向

## 主要研究趋势
（跨论文的共性趋势，不超过 4 条）

## 关键技术洞察
（值得记住的技术细节或新方法）

## 与我的 Research 的关联
（具体关联点，可以是支撑、挑战或新方向）

## 下周建议
（要精读的论文、要做的调研、可以尝试的实验方向）
"""


def _build_paper_list(papers: List[Tuple[str, str, str]]) -> str:
    lines = []
    for title, ptype, snippet in papers:
        lines.append(f"### [{ptype}] {title}")
        if snippet:
            lines.append(f"> {snippet}")
    return "\n".join(lines)


# ── Report generation ────────────────────────────────────────────────────────

def generate_daily_report(vault_path: Optional[str] = None) -> Optional[str]:
    """Generate daily report for today's email-ingested papers.
    Returns None if no new papers today."""
    from nextbrain.config import get_obsidian_vault_path
    from nextbrain.tools.llm import call_llm

    vault = Path(vault_path or get_obsidian_vault_path()).expanduser()
    today = datetime.now().strftime("%Y-%m-%d")
    papers = _papers_in_window(vault, today, today)

    if not papers:
        return None

    user_msg = f"今天是 {today}，共新增 {len(papers)} 篇论文：\n\n{_build_paper_list(papers)}"
    report = call_llm(_DAILY_SYSTEM, user_msg, max_tokens=1500)

    header = f"# 📚 每日论文日报 — {today}\n\n"
    return header + report


def generate_weekly_report(vault_path: Optional[str] = None) -> str:
    """Generate weekly report for the past 7 days. Always returns a report."""
    from nextbrain.config import get_obsidian_vault_path
    from nextbrain.tools.llm import call_llm

    vault = Path(vault_path or get_obsidian_vault_path()).expanduser()
    today = datetime.now()
    week_start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    week_end = today.strftime("%Y-%m-%d")

    papers = _papers_in_window(vault, week_start, week_end)

    if not papers:
        user_msg = f"本周（{week_start} 至 {week_end}）没有新增邮件论文，请基于这一情况写一份简短的周报，总结建议下周关注的方向。"
    else:
        user_msg = (
            f"本周（{week_start} 至 {week_end}）共新增 {len(papers)} 篇论文：\n\n"
            + _build_paper_list(papers)
        )

    report = call_llm(_WEEKLY_SYSTEM, user_msg, max_tokens=2000)

    iso_year, iso_week, _ = today.isocalendar()
    header = f"# 📊 每周研究周报 — {iso_year} 第{iso_week}周\n\n"
    return header + report
