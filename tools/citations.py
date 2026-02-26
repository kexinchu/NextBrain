"""PDF/URL note capture — minimal; store citations as metadata."""
from typing import List, Dict, Any
from pathlib import Path

def capture_citation(
    key: str,
    title: str,
    url: str = "",
    notes: str = "",
    bib_entry: str = "",
) -> Dict[str, Any]:
    """Store one citation as metadata (MVP: in-memory / later persist to artifacts/library)."""
    return {
        "key": key,
        "title": title,
        "url": url,
        "notes": notes,
        "bib_entry": bib_entry or f"@misc{{{key},\n  title = {{{title}}},\n  url = {{{url}}}\n}}",
    }

def save_citations_to_bib(citations: List[Dict[str, Any]], path: str | Path) -> None:
    """Write references.bib from list of citation dicts (use bib_entry when present)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for c in citations:
        lines.append(c.get("bib_entry", f"@misc{{{c['key']},\n  title = {{{c.get('title', '')}}},\n  url = {{{c.get('url', '')}}}\n}}"))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
