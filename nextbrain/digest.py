"""Weekly synthesis: turn the past N days of vault activity into a digest note.

Pulls:
  - Papers written in the last `--days` days (Papers-*/, Inbox/)
  - Idea/ notes touched in the same window

Asks the LLM to:
  1. Cluster papers by theme (using their titles + the upstream summary fields)
  2. Cross-reference each idea against the recent papers — which support, which
     challenge, which are unrelated
  3. Surface 3-5 open questions worth chasing this week
  4. Suggest "next reads" — gaps in the weekly haul

Output: <vault>/Syntheses/<YYYY-Www>-weekly.md  (ISO week so it's stable)
"""
from __future__ import annotations

import re
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from nextbrain import config


@dataclass
class _NoteSummary:
    path: Path
    title: str
    paper_type: str
    topics: List[str]
    one_liner: str       # first non-empty section after the heading
    is_idea: bool


_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_TITLE_RE = re.compile(r'^title:\s*"?([^"\n]+)"?', re.MULTILINE)
_TYPE_RE = re.compile(r"^type:\s*(\w+)", re.MULTILINE)
_PAPER_TYPE_RE = re.compile(r"^paper_type:\s*(.+?)\s*$", re.MULTILINE)
_TAGS_BLOCK_RE = re.compile(r"^tags:\s*\n((?:\s*-\s*.+\n?)+)", re.MULTILINE)
_UPSTREAM_RE = re.compile(r"^upstream_topic_scores:\s*\n((?:\s+\S+:\s*[\d.]+\n?)+)", re.MULTILINE)
_FIRST_SECTION_RE = re.compile(r"^##\s+\S.*?\n+(.+?)(?=\n##\s|\Z)", re.MULTILINE | re.DOTALL)


def _read_note(path: Path) -> Optional[_NoteSummary]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fm_m = _FM_RE.match(text)
    if not fm_m:
        return None
    fm = fm_m.group(1)
    title_m = _TITLE_RE.search(fm)
    type_m = _TYPE_RE.search(fm)
    ptype_m = _PAPER_TYPE_RE.search(fm)

    title = title_m.group(1).strip() if title_m else path.stem
    note_type = (type_m.group(1).strip() if type_m else "").lower()
    paper_type = ptype_m.group(1).strip().strip('"\'') if ptype_m else ""

    # Topics: tags + upstream slugs (best-effort)
    topics: List[str] = []
    tb = _TAGS_BLOCK_RE.search(fm)
    if tb:
        for line in tb.group(1).splitlines():
            line = line.strip()
            if line.startswith("-"):
                topics.append(line[1:].strip().strip('"\''))
    ub = _UPSTREAM_RE.search(fm)
    if ub:
        for ln in ub.group(1).splitlines():
            m = re.match(r"\s+(\S+):", ln)
            if m:
                topics.append(m.group(1))

    # First section body — typically "Problem"; trim aggressively
    body = text[fm_m.end():]
    sec_m = _FIRST_SECTION_RE.search(body)
    one_liner = ""
    if sec_m:
        one_liner = " ".join(sec_m.group(1).split())
    if len(one_liner) > 280:
        one_liner = one_liner[:277] + "..."

    return _NoteSummary(
        path=path, title=title, paper_type=paper_type,
        topics=list(dict.fromkeys(topics)),  # dedup, preserve order
        one_liner=one_liner,
        is_idea=(note_type == "idea"),
    )


def _gather_recent(vault: Path, days: int) -> Dict[str, List[_NoteSummary]]:
    """Return {'papers': [...], 'ideas': [...]} for notes touched in window."""
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    out = {"papers": [], "ideas": []}

    paper_iter = list(vault.glob("Papers-*/*.md")) + list(vault.glob("Inbox/*.md"))
    for md in paper_iter:
        try:
            mtime = datetime.fromtimestamp(md.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            continue
        ns = _read_note(md)
        if ns:
            out["papers"].append(ns)

    for md in vault.glob("Idea/**/*.md"):
        try:
            mtime = datetime.fromtimestamp(md.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            continue
        ns = _read_note(md)
        if ns:
            out["ideas"].append(ns)

    return out


def _format_for_llm(papers: List[_NoteSummary], ideas: List[_NoteSummary]) -> str:
    lines: List[str] = []
    lines.append(f"## NEW PAPERS THIS WEEK ({len(papers)})")
    for i, p in enumerate(papers, 1):
        topic_str = (", ".join(p.topics[:4])) if p.topics else p.paper_type
        lines.append(f"[P{i}] ({topic_str}) {p.title}")
        if p.one_liner:
            lines.append(f"     → {p.one_liner}")
    lines.append("")
    lines.append(f"## ACTIVE IDEAS ({len(ideas)})")
    for i, idea in enumerate(ideas, 1):
        lines.append(f"[I{i}] {idea.title}")
        if idea.one_liner:
            lines.append(f"     → {idea.one_liner}")
    return "\n".join(lines)


_SYSTEM_PROMPT = """\
You are a research assistant for a PhD student. Your job is to take their
recent paper-reading and idea-development activity and produce a weekly
synthesis that helps them see patterns, gaps, and next moves.

Be concrete and skeptical — surface tensions and unresolved questions.
Do not summarize each paper one by one (the user already has the notes).
Instead, look across them.

Output STRICT JSON with this shape:
{
  "themes": [
    {"name": "...", "papers": ["P1", "P3"], "what_unites": "...", "open_question": "..."},
    ...
  ],
  "idea_crossrefs": [
    {"idea": "I1", "supported_by": ["P2"], "challenged_by": [], "note": "..."},
    ...
  ],
  "open_questions": ["...", "..."],
  "suggested_next_reads": ["topic or paper-shaped query the user should chase", ...],
  "tldr": "one paragraph, max 100 words"
}

Rules:
- Reference papers/ideas by their bracketed IDs (P1, I2, ...).
- 2-4 themes, 3-5 open questions, up to 5 next reads.
- If papers don't cluster meaningfully, say so in tldr — don't invent themes.
- If there are no ideas, set "idea_crossrefs": [].
"""


def _render_markdown(week_label: str, payload: dict,
                     papers: List[_NoteSummary], ideas: List[_NoteSummary]) -> str:
    """Render the LLM JSON into a navigable Obsidian note with wikilinks."""
    pid_to_title = {f"P{i}": p.title for i, p in enumerate(papers, 1)}
    iid_to_title = {f"I{i}": idea.title for i, idea in enumerate(ideas, 1)}

    def link_ids(refs: List[str], lookup: Dict[str, str]) -> str:
        out = []
        for r in refs:
            t = lookup.get(r)
            out.append(f"[[{t}]]" if t else r)
        return ", ".join(out) if out else "—"

    lines = [
        "---",
        f"title: \"Weekly Digest {week_label}\"",
        "type: synthesis",
        f"created_at: {datetime.now().strftime('%Y-%m-%d')}",
        f"updated_at: {datetime.now().strftime('%Y-%m-%d')}",
        f"paper_count: {len(papers)}",
        f"idea_count: {len(ideas)}",
        "---",
        "",
        f"# Weekly Digest — {week_label}",
        "",
        "## TL;DR",
        payload.get("tldr", "(none)"),
        "",
        "## Themes",
    ]
    for t in payload.get("themes", []):
        name = t.get("name", "Untitled")
        lines.append(f"### {name}")
        lines.append(f"- **Papers:** {link_ids(t.get('papers', []), pid_to_title)}")
        if t.get("what_unites"):
            lines.append(f"- **What unites them:** {t['what_unites']}")
        if t.get("open_question"):
            lines.append(f"- **Open question:** {t['open_question']}")
        lines.append("")

    cross = payload.get("idea_crossrefs", [])
    if cross:
        lines.append("## Idea Cross-References")
        for c in cross:
            iid = c.get("idea", "")
            ititle = iid_to_title.get(iid, iid)
            lines.append(f"### [[{ititle}]]" if ititle else f"### {iid}")
            sup = link_ids(c.get("supported_by", []), pid_to_title)
            chal = link_ids(c.get("challenged_by", []), pid_to_title)
            lines.append(f"- **Supported by:** {sup}")
            lines.append(f"- **Challenged by:** {chal}")
            if c.get("note"):
                lines.append(f"- **Note:** {c['note']}")
            lines.append("")

    qs = payload.get("open_questions", [])
    if qs:
        lines.append("## Open Questions")
        for q in qs:
            lines.append(f"- {q}")
        lines.append("")

    nr = payload.get("suggested_next_reads", [])
    if nr:
        lines.append("## Suggested Next Reads")
        for n in nr:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("## Index")
    lines.append("**Papers this week:**")
    for i, p in enumerate(papers, 1):
        lines.append(f"- P{i}: [[{p.title}]]")
    if ideas:
        lines.append("")
        lines.append("**Ideas referenced:**")
        for i, idea in enumerate(ideas, 1):
            lines.append(f"- I{i}: [[{idea.title}]]")

    return "\n".join(lines) + "\n"


def generate_digest(vault_path: Optional[str] = None, days: int = 7) -> Path:
    """Build the weekly digest. Returns path to the written note."""
    from nextbrain.config import get_obsidian_vault_path
    from nextbrain.tools.llm import call_llm

    vault = Path(vault_path or get_obsidian_vault_path()).expanduser()
    bundle = _gather_recent(vault, days)
    papers, ideas = bundle["papers"], bundle["ideas"]

    if not papers and not ideas:
        raise RuntimeError(
            f"No papers or ideas modified in the last {days} days — nothing to digest."
        )

    user_msg = _format_for_llm(papers, ideas)
    raw = call_llm(_SYSTEM_PROMPT, user_msg, json_mode=True)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Fall back to a minimal payload so the user still gets a note
        payload = {
            "themes": [],
            "idea_crossrefs": [],
            "open_questions": [],
            "suggested_next_reads": [],
            "tldr": f"(LLM JSON parse failed — see raw response)\n\n{raw[:1000]}",
        }

    iso_year, iso_week, _ = datetime.now().isocalendar()
    week_label = f"{iso_year}-W{iso_week:02d}"
    md = _render_markdown(week_label, payload, papers, ideas)

    out_dir = vault / "Syntheses"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{week_label}-weekly.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path
