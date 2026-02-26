"""Ideator: generates falsifiable hypotheses."""
import json
from pathlib import Path

def _load_prompt() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "ideator.md"
    return p.read_text(encoding="utf-8")

def run(input_data: dict) -> dict:
    """
    Input: topic, constraints (datasets/hardware/metrics/target venue)
    Output: { "hypotheses": [ HypothesisCard, ... ] }
    """
    topic = input_data.get("topic", "")
    venue = input_data.get("venue", "")
    constraints = input_data.get("constraints", "")
    system = _load_prompt()
    user = f"Topic: {topic}\nVenue: {venue}\nConstraints: {constraints}\n\nOutput valid JSON only."
    from tools.llm import call_llm
    raw = call_llm(system, user, json_mode=True)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {"hypotheses": []}
    hypotheses = out.get("hypotheses") or []
    # Normalize to HypothesisCard shape
    cards = []
    for i, h in enumerate(hypotheses):
        if isinstance(h, dict):
            cards.append({
                "id": h.get("id") or f"H{i+1}",
                "claim": h.get("claim", ""),
                "falsifiable_test": h.get("falsifiable_test", ""),
                "minimal_experiment": h.get("minimal_experiment", ""),
                "expected_gain": h.get("expected_gain", ""),
                "risks": h.get("risks", ""),
            })
    return {"hypotheses": cards}
