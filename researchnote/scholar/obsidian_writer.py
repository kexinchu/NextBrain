"""Write structured notes to Obsidian vault as markdown with YAML frontmatter."""
import re
from pathlib import Path
from typing import Dict, List, Optional

from researchnote.config import get_obsidian_vault_path, get_output_language
from researchnote.models import PaperNote, IdeaNote
from researchnote.tools.io import write_markdown


# ── Duplicate detection ──────────────────────────────────────────────────────

_ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)")


def _normalize_url(url: str) -> str:
    """Extract a canonical arXiv ID or return the URL stripped of protocol/trailing slash."""
    m = _ARXIV_ID_RE.search(url)
    if m:
        return m.group(1)  # e.g. "2211.12850"
    return url.rstrip("/").removeprefix("https://").removeprefix("http://")


def find_existing_note(source_url: str, vault_path: Optional[str] = None) -> Optional[Path]:
    """Check if a paper with the given source_url already has a note in the vault.

    Scans YAML frontmatter of all .md files under Papers-*/ directories.
    Uses arXiv ID normalization so abs/pdf variants match.
    Returns the Path of the existing note, or None.
    """
    vault = Path(vault_path or get_obsidian_vault_path())
    target = _normalize_url(source_url)
    if not target:
        return None

    for md_file in vault.glob("Papers-*/*.md"):
        try:
            # Read only first 30 lines (frontmatter) for speed
            with open(md_file, "r", encoding="utf-8") as f:
                head = ""
                for i, line in enumerate(f):
                    if i >= 30:
                        break
                    head += line
        except Exception:
            continue

        # Look for source_url in frontmatter
        m = re.search(r'source_url:\s*"?([^"\n]+)"?', head)
        if m:
            existing_url = m.group(1).strip()
            if _normalize_url(existing_url) == target:
                return md_file

    return None


# ── Bilingual section headers ────────────────────────────────────────────────

_PAPER_HEADERS: Dict[str, Dict[str, str]] = {
    "en": {
        "problem": "Problem",
        "importance": "Importance",
        "method": "Method",
        "motivation": "Motivation",
        "challenge": "Challenge",
        "design": "Design",
        "related_work": "Related Work & Positioning",
        "key_results": "Key Results",
        "summary": "Summary",
        "limitations": "Limitations",
    },
    "zh": {
        "problem": "问题",
        "importance": "重要性",
        "method": "方法",
        "motivation": "动机",
        "challenge": "挑战",
        "design": "设计",
        "related_work": "相关工作与定位",
        "key_results": "关键结果",
        "summary": "总结",
        "limitations": "局限性",
    },
}

_IDEA_HEADERS: Dict[str, Dict[str, str]] = {
    "en": {
        "hypothesis": "Hypothesis",
        "motivation": "Motivation",
        "related_directions": "Related Directions",
        "open_questions": "Open Questions",
        "next_steps": "Next Steps",
    },
    "zh": {
        "hypothesis": "假设",
        "motivation": "动机",
        "related_directions": "相关方向",
        "open_questions": "开放问题",
        "next_steps": "后续步骤",
    },
}

# Map section keys used in figure_placement to the note field + header key
_SECTION_KEYS = [
    "problem", "importance", "motivation", "challenge", "design",
    "related_work", "key_results", "summary", "limitations",
]


def _get_headers(header_map: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    lang = get_output_language()
    return header_map.get(lang, header_map["en"])


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        name = name.replace(ch, "")
    name = " ".join(name.split())
    return name[:120].strip()


def _extract_short_name(title: str) -> str:
    """Extract a short system/method name from the paper title."""
    for sep in [":", "：", "—", "–", "|"]:
        if sep in title:
            candidate = title.split(sep)[0].strip()
            if 2 <= len(candidate) <= 60:
                return candidate
    words = title.split()[:4]
    return " ".join(words)


def _make_paper_filename(note) -> str:
    """Generate filename as SystemName_FirstAuthor_Year."""
    parts = []
    sys_name = (note.system_name or "").strip()
    if sys_name:
        parts.append(_sanitize_filename(sys_name))
    else:
        short = _extract_short_name(note.title)
        parts.append(_sanitize_filename(short))

    if note.authors:
        first_author = note.authors[0].strip().replace(" ", "-")
        parts.append(_sanitize_filename(first_author))

    if note.year:
        parts.append(str(note.year))

    return "_".join(parts) if parts else _sanitize_filename(note.title)


def _format_yaml_list(items: list) -> str:
    if not items:
        return "[]"
    lines = "\n".join(f"  - {item}" for item in items)
    return f"\n{lines}"


def _format_section(content) -> str:
    """Format a note section, handling both strings and lists."""
    if isinstance(content, list):
        return "\n".join(f"- {item}" for item in content)
    return str(content) if content else ""


def _build_figure_md(fig_ids: List[str], fig_paths: Dict[str, str],
                     fig_captions: Dict[str, str]) -> str:
    """Build markdown image embeds for a list of figure IDs."""
    lines = []
    for fid in fig_ids:
        path = fig_paths.get(fid)
        if not path:
            continue
        caption = fig_captions.get(fid, fid)
        lines.append(f"\n![{caption}]({path})")
    return "\n".join(lines)


def get_note_stem(note: PaperNote) -> str:
    """Return the filename stem (without .md) for a paper note."""
    return _make_paper_filename(note)


def write_paper_note(
    note: PaperNote,
    vault_path: Optional[str] = None,
    fig_paths: Optional[Dict[str, str]] = None,
    fig_captions: Optional[Dict[str, str]] = None,
) -> Path:
    """Write a paper note to Obsidian vault under Papers-<paper_type>/.

    Args:
        fig_paths: {fig_id: relative_path} mapping for saved images.
        fig_captions: {fig_id: caption_text} for alt text.

    Returns the path to the written file.
    """
    vault = Path(vault_path or get_obsidian_vault_path())
    paper_dir = vault / f"Papers-{note.paper_type}"
    paper_dir.mkdir(parents=True, exist_ok=True)
    filename = _make_paper_filename(note) + ".md"
    filepath = paper_dir / filename

    fig_paths = fig_paths or {}
    fig_captions = fig_captions or {}
    placement = note.figure_placement or {}

    authors_yaml = _format_yaml_list(note.authors)
    tags_yaml = _format_yaml_list(note.tags)
    h = _get_headers(_PAPER_HEADERS)

    def _section(key: str, content, heading_level: str = "##") -> str:
        """Render a section with optional inline figures."""
        text = f"{heading_level} {h[key]}\n{_format_section(content)}\n"
        figs = placement.get(key, [])
        if figs and fig_paths:
            text += _build_figure_md(figs, fig_paths, fig_captions) + "\n"
        return text

    md = f"""---
title: "{note.title}"
type: paper
paper_type: {note.paper_type}
authors: {authors_yaml}
year: {note.year or ""}
venue: "{note.venue}"
source_url: "{note.source_url}"
zotero_key: "{note.zotero_key}"
tags: {tags_yaml}
created_at: {note.created_at}
updated_at: {note.updated_at}
status: {note.status}
---

# {note.title}

{_section("problem", note.problem)}

{_section("importance", note.importance)}

## {h["method"]}

{_section("motivation", note.motivation, "###")}

{_section("challenge", note.challenge, "###")}

{_section("design", note.design, "###")}

{_section("related_work", note.related_work)}

{_section("key_results", note.key_results)}

{_section("summary", note.summary)}

{_section("limitations", note.limitations)}
"""

    write_markdown(filepath, md)
    return filepath


def write_idea_note(
    note: IdeaNote,
    vault_path: Optional[str] = None,
) -> Path:
    """Write an idea note to Obsidian vault under Idea/."""
    vault = Path(vault_path or get_obsidian_vault_path())
    idea_dir = vault / "Idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    filename = _sanitize_filename(note.title) + ".md"
    filepath = idea_dir / filename

    tags_yaml = _format_yaml_list(note.tags)
    h = _get_headers(_IDEA_HEADERS)

    md = f"""---
title: "{note.title}"
type: idea
tags: {tags_yaml}
created_at: {note.created_at}
updated_at: {note.updated_at}
status: {note.status}
---

# {note.title}

## {h["hypothesis"]}
{_format_section(note.hypothesis)}

## {h["motivation"]}
{_format_section(note.motivation)}

## {h["related_directions"]}
{_format_section(note.related_directions)}

## {h["open_questions"]}
{_format_section(note.open_questions)}

## {h["next_steps"]}
{_format_section(note.next_steps)}
"""

    write_markdown(filepath, md)
    return filepath
