from __future__ import annotations

from typing import Any


def _risk(candidate: dict[str, Any]) -> float:
    keys = ("collision_risk", "novelty_uncertainty", "scope_risk", "motivation_cost")
    total = 0.0
    for key in keys:
        value = candidate.get(key, 0)
        if isinstance(value, (int, float)):
            total += min(max(float(value), 0.0), 1.0)
    return total


def risk_stratified_sample(candidates: list[dict[str, Any]], sample_size: int) -> list[dict[str, Any]]:
    """Choose high-risk candidates while preserving approach diversity."""

    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    ranked = sorted(candidates, key=lambda item: (-_risk(item), str(item.get("id", ""))))
    selected: list[dict[str, Any]] = []
    approaches: set[str] = set()
    for candidate in ranked:
        approach = str(candidate.get("approach", "unspecified"))
        if approach not in approaches:
            selected.append(candidate)
            approaches.add(approach)
        if len(selected) == sample_size:
            return selected
    for candidate in ranked:
        if candidate not in selected:
            selected.append(candidate)
        if len(selected) == sample_size:
            break
    return selected
