"""
CLI: python -m orchestrator.pipeline --topic "<TOPIC>" --venue "<VENUE>"
Runs: ideator -> scout -> deep_research -> skeptic (1+ iteration) -> writer -> LaTeX -> editor -> summary.
"""
import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is on path so config, tools, agents are importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from orchestrator.state import create_initial_state, get_selected_hypotheses
from tools.io import ensure_artifacts_dirs, save_json
from tools.latex_builder import build_latex
from tools.citations import save_citations_to_bib

def run_pipeline(topic: str, venue: str, artifacts_root: str | None = None) -> dict:
    if artifacts_root is None:
        artifacts_root = str(_REPO_ROOT / "artifacts")
    dirs = ensure_artifacts_dirs(artifacts_root)
    state = create_initial_state(topic, venue, artifacts_root)

    # 1) Ideator
    from agents.ideator import run as ideator_run
    out = ideator_run({"topic": topic, "venue": venue, "constraints": venue})
    state["hypotheses"] = out.get("hypotheses") or []
    save_json(state, dirs["runs"] / "01_ideator.json")

    # 2) Scout
    from agents.scout import run as scout_run
    state["scout_output"] = scout_run({"topic": topic, "hypotheses": state["hypotheses"]})
    save_json(state, dirs["runs"] / "02_scout.json")

    # 3) DeepResearcher
    selected = get_selected_hypotheses(state)
    from agents.deep_researcher import run as deep_run
    state["deep_research_output"] = deep_run({
        "hypotheses": selected,
        "scout_output": state["scout_output"],
    })
    save_json(state, dirs["runs"] / "03_deep_research.json")

    # 4) Skeptic + at least 1 iteration
    from agents.skeptic import run as skeptic_run
    approach = "Selected hypotheses: " + json.dumps([h.get("claim") for h in selected], indent=2)
    state["skeptic_output"] = skeptic_run({
        "approach_summary": approach,
        "deep_research_output": state["deep_research_output"],
        "hypotheses": selected,
    })
    state["skeptic_iteration"] = 1
    save_json(state, dirs["runs"] / "04_skeptic.json")

    # 5) Writer -> LaTeX
    from agents.writer import run as writer_run
    method_outline = approach
    results_plan = "Experiments: " + json.dumps((state["deep_research_output"] or {}).get("baseline_checklist", []))
    state["writer_output"] = writer_run({
        "topic": topic,
        "venue": venue,
        "method_outline": method_outline,
        "results_plan": results_plan,
        "annotated_bib": (state["deep_research_output"] or {}).get("annotated_bib", []),
        "hypotheses": selected,
        "skeptic_output": state["skeptic_output"],
    })
    save_json(state, dirs["runs"] / "05_writer.json")

    # Gates (writer): if FAIL, we still proceed for MVP but log fix_list
    from eval.gates import run_gates
    gate_ok, gate_reasons = run_gates("writer", state)
    state["gate_results"] = state.get("gate_results") or {}
    state["gate_results"]["writer"] = {"pass": gate_ok, "reasons": gate_reasons}
    if not gate_ok:
        state["fix_list"] = gate_reasons

    # 6) Build LaTeX draft into artifacts/paper/
    sections = (state["writer_output"] or {}).get("sections") or {}
    bib_keys = [b.get("key") for b in (state["deep_research_output"] or {}).get("annotated_bib", []) if b.get("key")]
    build_latex(sections, dirs["paper"], main_name="main", bib_keys=bib_keys)
    # references.bib
    bib_entries = (state["deep_research_output"] or {}).get("annotated_bib") or []
    citations = [{"key": b.get("key", "ref" + str(i)), "title": b.get("title", ""), "bib_entry": ""} for i, b in enumerate(bib_entries)]
    for i, b in enumerate(bib_entries):
        key = b.get("key") or ("ref" + str(i))
        citations[i]["bib_entry"] = f'@article{{{key},\n  title = {{{b.get("title", "")}}},\n  author = {{Unknown}},\n  year = {{2024}}\n}}'
    save_citations_to_bib(citations, dirs["paper"] / "references.bib")

    # 7) Editor pass
    from agents.editor import run as editor_run
    state["editor_output"] = editor_run({"sections": sections})
    save_json(state, dirs["runs"] / "06_editor.json")

    # Gates (editor)
    gate_ok_ed, gate_reasons_ed = run_gates("editor", state)
    state["gate_results"]["editor"] = {"pass": gate_ok_ed, "reasons": gate_reasons_ed}

    # Rebuild final LaTeX from editor output
    final_sections = (state["editor_output"] or {}).get("sections") or sections
    build_latex(final_sections, dirs["paper"], main_name="main", bib_keys=bib_keys)

    return state

def main():
    parser = argparse.ArgumentParser(description="EfficientResearch pipeline")
    parser.add_argument("--topic", required=True, help="Research topic")
    parser.add_argument("--venue", default="Workshop, 4–6 pages, double-column", help="Target venue")
    parser.add_argument("--artifacts", default=None, help="Artifacts root (default: efficient_research/artifacts)")
    args = parser.parse_args()
    artifacts_root = args.artifacts or str(_REPO_ROOT / "artifacts")
    state = run_pipeline(args.topic, args.venue, artifacts_root)
    dirs = ensure_artifacts_dirs(artifacts_root)
    print("--- EfficientResearch pipeline done ---")
    print("Artifacts root:", artifacts_root)
    print("Paper (LaTeX):", dirs["paper"] / "main.tex")
    print("References:", dirs["paper"] / "references.bib")
    print("Run logs:     ", dirs["runs"])
    print("Gate results: ", state.get("gate_results", {}))

if __name__ == "__main__":
    main()
