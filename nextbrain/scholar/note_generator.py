"""Generate structured reading notes from paper metadata using LLM + Scholar skill."""
import json
from typing import Dict, List, Optional

from nextbrain.models import PaperMetadata, PaperNote, IdeaNote

_LANG_INSTRUCTION = {
    "zh": "\n\nIMPORTANT: Write ALL field values in Chinese (中文). Keep JSON keys in English. "
          "Technical terms (e.g. system names, algorithm names, benchmark names) keep original English, "
          "but all descriptions, analysis, and bullet points must be in Chinese.",
    "en": "",
}


def _get_lang_suffix() -> str:
    from nextbrain.config import get_output_language
    lang = get_output_language()
    return _LANG_INSTRUCTION.get(lang, "")


def generate_paper_note(
    meta: PaperMetadata,
    figure_captions: Optional[List[Dict]] = None,
) -> PaperNote:
    """Generate a structured paper reading note from metadata + abstract.

    Args:
        meta: Paper metadata (title, abstract, authors, etc.)
        figure_captions: Optional list of {"id": "fig1", "page": 3, "caption": "Figure 1: ..."}
            If provided, the LLM will decide which figures to place in which sections.
    """
    from nextbrain.tools.llm import call_llm
    from nextbrain.tools.skills_loader import get_skill_prompt

    system = get_skill_prompt("scholar") + _get_lang_suffix()

    # Build user message
    user = f"Title: {meta.title}\n\nAbstract: {meta.abstract}"

    if figure_captions:
        user += "\n\nAvailable figures (from the PDF):"
        for fig in figure_captions:
            user += f"\n  - {fig['id']} (p{fig['page']}): \"{fig['caption']}\""
        user += "\n\nSelect at most 2 most valuable figures and place them in the appropriate sections via figure_placement."

    user += "\n\nOutput JSON only."

    raw = call_llm(system, user, json_mode=True, max_tokens=4000)
    try:
        data = json.loads(raw)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        if not isinstance(data, dict):
            print(f"[note_generator] WARNING: LLM returned non-dict type: {type(data).__name__}", flush=True)
            data = {}
    except json.JSONDecodeError:
        print(f"[note_generator] WARNING: Failed to parse LLM response as JSON.", flush=True)
        print(f"[note_generator] Raw response (first 500 chars): {raw[:500]}", flush=True)
        data = {}

    if not data or not any(data.get(k) for k in ("problem", "design", "summary")):
        print(f"[note_generator] WARNING: LLM returned empty or incomplete note data.", flush=True)
        if raw:
            print(f"[note_generator] Raw response (first 500 chars): {raw[:500]}", flush=True)

    # Parse figure_placement — validate it's a dict of {str: list}
    fig_placement = data.get("figure_placement", {})
    if not isinstance(fig_placement, dict):
        fig_placement = {}

    note = PaperNote(
        title=meta.title,
        system_name=data.get("system_name", ""),
        paper_type=meta.paper_type,
        authors=meta.authors,
        year=meta.year,
        venue=meta.venue,
        source_url=meta.source_url or meta.pdf_url,
        tags=data.get("tags", meta.tags),
        problem=data.get("problem", ""),
        importance=data.get("importance", ""),
        motivation=data.get("motivation", ""),
        challenge=data.get("challenge", ""),
        design=data.get("design", ""),
        related_work=data.get("related_work", ""),
        key_results=data.get("key_results", ""),
        summary=data.get("summary", ""),
        limitations=data.get("limitations", ""),
        figure_placement=fig_placement,
    )
    return note


def generate_idea_note(raw_text: str) -> IdeaNote:
    """Generate a structured idea note from free-form text."""
    from nextbrain.tools.llm import call_llm

    lang_suffix = _get_lang_suffix()
    system = f"""You are a senior systems/ML researcher. Given a raw research idea or thought, structure it into a clear research idea note.

Output JSON with these keys:
{{
  "title": "A concise title for this idea (< 80 chars)",
  "hypothesis": "The core hypothesis or claim",
  "motivation": "Why this matters, what gap it addresses",
  "related_directions": "Related work or research directions to explore",
  "open_questions": "Key open questions to resolve",
  "next_steps": "Concrete next steps to investigate",
  "tags": ["tag1", "tag2", ...]
}}{lang_suffix}"""

    user = f"Raw idea/thought:\n\n{raw_text}\n\nOutput JSON only."

    raw = call_llm(system, user, json_mode=True, max_tokens=1500)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}

    return IdeaNote(
        title=data.get("title", "Untitled Idea"),
        tags=data.get("tags", []),
        hypothesis=data.get("hypothesis", ""),
        motivation=data.get("motivation", ""),
        related_directions=data.get("related_directions", ""),
        open_questions=data.get("open_questions", ""),
        next_steps=data.get("next_steps", ""),
    )
