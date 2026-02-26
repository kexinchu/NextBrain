"""Writer: workshop LaTeX draft with [CITE]/[EVID]/[SPEC] tags."""
import json
from pathlib import Path

def _load_prompt() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "writer.md"
    return p.read_text(encoding="utf-8")

def run(input_data: dict) -> dict:
    """
    Input: method outline, results plan, bib (annotated_bib), hypotheses, skeptic_output
    Output: { "sections": { abstract, intro, background, method, experiments, results, related_work, limitations, conclusion } }
    """
    method_outline = input_data.get("method_outline", "")
    results_plan = input_data.get("results_plan", "")
    bib = input_data.get("annotated_bib", [])
    hypotheses = input_data.get("hypotheses", [])
    skeptic = input_data.get("skeptic_output") or {}
    topic = input_data.get("topic", "")
    venue = input_data.get("venue", "")
    system = _load_prompt()
    user = (
        f"Topic: {topic}\nVenue: {venue}\n\n"
        f"Method outline:\n{method_outline}\n\nResults plan:\n{results_plan}\n\n"
        f"Annotated bib:\n{json.dumps(bib, indent=2)}\n\n"
        f"Hypotheses:\n{json.dumps(hypotheses, indent=2)}\n\n"
        f"Skeptic items to address:\n{json.dumps(skeptic, indent=2)}\n\n"
        "Output valid JSON with key 'sections' only."
    )
    from tools.llm import call_llm
    raw = call_llm(system, user, json_mode=True)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {}
    sections = out.get("sections") or {}
    for key in ["abstract", "intro", "background", "method", "experiments", "results", "related_work", "limitations", "conclusion"]:
        if key not in sections:
            sections[key] = ""
    return {"sections": sections}
