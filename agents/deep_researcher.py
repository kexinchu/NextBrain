"""DeepResearcher: evidence + annotated bibliography."""
import json
from pathlib import Path

def _load_prompt() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "deep_researcher.md"
    return p.read_text(encoding="utf-8")

def run(input_data: dict) -> dict:
    """
    Input: selected hypotheses, scout_output (related_work)
    Output: annotated_bib, baseline_checklist, metrics_checklist, gap_summary
    """
    hypotheses = input_data.get("hypotheses", [])
    scout = input_data.get("scout_output") or {}
    related_work = scout.get("related_work", [])
    system = _load_prompt()
    user = f"Selected hypotheses:\n{json.dumps(hypotheses, indent=2)}\n\nRelated work (coarse):\n{json.dumps(related_work, indent=2)}\n\nOutput valid JSON only."
    from tools.llm import call_llm
    raw = call_llm(system, user, json_mode=True)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {}
    return {
        "annotated_bib": out.get("annotated_bib") or [],
        "baseline_checklist": out.get("baseline_checklist") or [],
        "metrics_checklist": out.get("metrics_checklist") or [],
        "gap_summary": out.get("gap_summary", ""),
    }
