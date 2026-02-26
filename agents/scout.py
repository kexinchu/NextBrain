"""Scout: coarse literature + triage, select top 1–2 hypotheses."""
import json
from pathlib import Path

def _load_prompt() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "scout.md"
    return p.read_text(encoding="utf-8")

def run(input_data: dict) -> dict:
    """
    Input: hypotheses (list of HypothesisCards), optional topic
    Output: related_work map, novelty/feasibility scores, selected_ids, rationale
    """
    hypotheses = input_data.get("hypotheses", [])
    topic = input_data.get("topic", "")
    system = _load_prompt()
    user = f"Topic: {topic}\n\nHypotheses (JSON):\n{json.dumps(hypotheses, indent=2)}\n\nOutput valid JSON only."
    from tools.llm import call_llm
    raw = call_llm(system, user, json_mode=True)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {}
    related_work = out.get("related_work") or []
    hypothesis_scores = out.get("hypothesis_scores") or []
    selected_ids = out.get("selected_ids") or []
    if not selected_ids and hypotheses:
        selected_ids = [hypotheses[0].get("id")] if hypotheses else []
    return {
        "related_work": related_work,
        "hypothesis_scores": hypothesis_scores,
        "selected_ids": [str(s) for s in selected_ids],
        "selection_rationale": out.get("selection_rationale", ""),
    }
