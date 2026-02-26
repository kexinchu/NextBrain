"""Pipeline state (LangGraph-style): single dict passed between stages."""
from typing import Any, Dict, List, Optional

def create_initial_state(topic: str, venue: str, artifacts_root: str) -> Dict[str, Any]:
    return {
        "topic": topic,
        "venue": venue,
        "artifacts_root": artifacts_root,
        "hypotheses": [],           # List[HypothesisCard]
        "scout_output": None,      # related_work, novelty/feasibility, selected_ids
        "deep_research_output": None,  # annotated_bib, baseline_checklist, gap_summary
        "skeptic_output": None,    # rejection_risks, required_experiments
        "skeptic_iteration": 0,
        "writer_output": None,     # sections dict for LaTeX
        "editor_output": None,
        "gate_results": {},        # stage -> {pass: bool, reasons: []}
        "fix_list": [],            # actionable fix list when gate fails
    }

def get_selected_hypotheses(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return list of hypothesis dicts that were selected by Scout."""
    selected_ids = (state.get("scout_output") or {}).get("selected_ids") or []
    hypotheses = state.get("hypotheses") or []
    by_id = {h.get("id"): h for h in hypotheses if h.get("id")}
    return [by_id[sid] for sid in selected_ids if sid in by_id]
