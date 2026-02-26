"""Quality gates: PASS/FAIL with reasons."""
import re
from typing import Any, Dict, List

def _count_tag(text: str, tag: str) -> int:
    return len(re.findall(re.escape(tag), text))

def citation_coverage(sections: Dict[str, str], threshold: float = 0.8):
    lit_text = (sections.get("related_work") or "") + (sections.get("intro") or "")
    if not lit_text.strip():
        return True, []
    cite = _count_tag(lit_text, "[CITE:")
    evid = _count_tag(lit_text, "[EVID:")
    spec = _count_tag(lit_text, "[SPEC]")
    total = cite + evid + spec
    if total == 0:
        return False, ["No [CITE:...] or [EVID:...] or [SPEC] tags in intro/related_work."]
    coverage = (cite + evid) / total
    reasons = [] if coverage >= threshold else ["citation_coverage < {} in intro/related_work".format(threshold)]
    return coverage >= threshold, reasons

def speculation_ratio(sections: Dict[str, str], threshold: float = 0.2):
    text = (sections.get("intro") or "") + (sections.get("method") or "")
    if not text.strip():
        return True, []
    cite = _count_tag(text, "[CITE:")
    evid = _count_tag(text, "[EVID:")
    spec = _count_tag(text, "[SPEC]")
    total = cite + evid + spec
    if total == 0:
        return True, []
    ratio = spec / total
    reasons = [] if ratio <= threshold else ["speculation_ratio > {} in intro/method".format(threshold)]
    return ratio <= threshold, reasons

def baseline_checklist(baseline_checklist: List[str], min_baselines: int = 1):
    n = len(baseline_checklist) if baseline_checklist else 0
    reasons = [] if n >= min_baselines else ["baseline_checklist has < {} items".format(min_baselines)]
    return n >= min_baselines, reasons

def skeptic_items_closed(skeptic_output: Dict[str, Any], writer_sections: Dict[str, str], close_ratio: float = 0.5):
    req_exp = skeptic_output.get("required_experiments") or []
    rej = skeptic_output.get("rejection_risks") or []
    items = req_exp + rej
    if not items:
        return True, []
    text = (writer_sections.get("method") or "") + (writer_sections.get("experiments") or "") + (writer_sections.get("limitations") or "")
    mentioned = sum(1 for item in items if item and item[:20] in text)
    ratio = mentioned / len(items)
    reasons = [] if ratio >= close_ratio else ["skeptic_items_closed < {}".format(close_ratio)]
    return ratio >= close_ratio, reasons

def run_gates(stage: str, state: Dict[str, Any], citation_threshold=0.8, speculation_threshold=0.2, min_baselines=1, skeptic_close_ratio=0.5):
    all_passed = True
    reasons = []
    if stage in ("writer", "editor"):
        sections = (state.get("editor_output") or state.get("writer_output") or {}).get("sections") or {}
        deep = state.get("deep_research_output") or {}
        skeptic = state.get("skeptic_output") or {}
        ok, r1 = citation_coverage(sections, citation_threshold)
        if not ok:
            all_passed = False
            reasons.extend(r1)
        ok, r2 = speculation_ratio(sections, speculation_threshold)
        if not ok:
            all_passed = False
            reasons.extend(r2)
        ok, r3 = baseline_checklist(deep.get("baseline_checklist", []), min_baselines)
        if not ok:
            all_passed = False
            reasons.extend(r3)
        ok, r4 = skeptic_items_closed(skeptic, sections, skeptic_close_ratio)
        if not ok:
            all_passed = False
            reasons.extend(r4)
    return all_passed, reasons
