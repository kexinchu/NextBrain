"""Editor: style + format polish; preserve tags."""
import json
from pathlib import Path

def _load_prompt() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "editor.md"
    return p.read_text(encoding="utf-8")

def run(input_data: dict) -> dict:
    """
    Input: sections (from writer output)
    Output: { "sections": { ... } } improved
    """
    sections = input_data.get("sections") or {}
    system = _load_prompt()
    user = f"LaTeX sections (JSON):\n{json.dumps(sections, indent=2)}\n\nOutput valid JSON with key 'sections' only. Preserve [CITE:...], [EVID:...], [SPEC]."
    from tools.llm import call_llm
    raw = call_llm(system, user, json_mode=True)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {"sections": sections}
    out_sections = out.get("sections") or sections
    for key in ["abstract", "intro", "background", "method", "experiments", "results", "related_work", "limitations", "conclusion"]:
        if key not in out_sections:
            out_sections[key] = sections.get(key, "")
    return {"sections": out_sections}
