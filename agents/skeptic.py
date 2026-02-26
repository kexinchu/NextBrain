"""Skeptic: reviewer-style attack — rejection risks and required experiments."""
import json
from pathlib import Path

def _load_prompt() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "skeptic.md"
    return p.read_text(encoding="utf-8")

def run(input_data: dict) -> dict:
    """
    Input: method/approach summary, evidence (deep_research_output), hypotheses
    Output: rejection_risks, required_experiments, threats_to_validity
    """
    approach = input_data.get("approach_summary", "")
    evidence = input_data.get("deep_research_output") or {}
    hypotheses = input_data.get("hypotheses", [])
    system = _load_prompt()
    user = f"Approach summary:\n{approach}\n\nEvidence (deep research):\n{json.dumps(evidence, indent=2)}\n\nHypotheses:\n{json.dumps(hypotheses, indent=2)}\n\nOutput valid JSON only."
    from tools.llm import call_llm
    raw = call_llm(system, user, json_mode=True)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {}
    return {
        "rejection_risks": out.get("rejection_risks") or [],
        "required_experiments": out.get("required_experiments") or [],
        "threats_to_validity": out.get("threats_to_validity") or [],
    }
