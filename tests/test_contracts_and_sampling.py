from pathlib import Path

import pytest
import yaml

from autoresearch.contracts import ContractError, validate_contract
from autoresearch.sampling import risk_stratified_sample


def _contract() -> dict:
    return {
        "schema_version": 1,
        "stage": "idea-story",
        "selected_candidate": None,
        "target_venues": ["OSDI"],
        "candidates": [
            {
                "id": "I-1",
                "approach": "a",
                "collision_risk": 0.9,
                "novelty_uncertainty": 0.5,
                "scope_risk": 0.4,
                "motivation_cost": 0.1,
            }
        ],
        "sources": [
            {
                "id": "S-1",
                "title": "Paper",
                "url": "https://example.com",
                "kind": "primary-paper",
                "checked_at": "2026-08-08",
            }
        ],
        "claims": [
            {
                "id": "C-1",
                "statement": "claim",
                "source_ids": ["S-1"],
                "experiment_ids": ["E-1"],
            }
        ],
        "experiments": [
            {"id": "E-1", "kind": "motivation", "status": "planned", "claim_ids": ["C-1"]}
        ],
    }


def _write(path: Path, metadata: dict) -> None:
    headings = (
        "Thesis",
        "Target venue and contribution type",
        "Problem and motivation",
        "Scope and non-goals",
        "Novelty and closest work",
        "Design",
        "Baselines",
        "Motivation tests",
        "Predictions and kill criteria",
        "Claims and evidence",
        "Open issues",
    )
    body = "\n\n".join(f"## {heading}\ntext" for heading in headings)
    path.write_text(f"---\n{yaml.safe_dump(metadata)}---\n{body}\n", encoding="utf-8")


def test_contract_validates_claim_source_and_experiment_links(tmp_path: Path) -> None:
    path = tmp_path / "story.md"
    _write(path, _contract())
    assert validate_contract(path, stage="idea-story").metadata["claims"][0]["id"] == "C-1"

    broken = _contract()
    broken["claims"][0]["source_ids"] = ["missing"]
    _write(path, broken)
    with pytest.raises(ContractError, match="unknown sources"):
        validate_contract(path, stage="idea-story")


def test_risk_sampling_preserves_diversity_before_filling() -> None:
    candidates = [
        {"id": "high-a", "approach": "a", "collision_risk": 1.0},
        {"id": "next-a", "approach": "a", "collision_risk": 0.9},
        {"id": "medium-b", "approach": "b", "collision_risk": 0.5},
    ]
    sampled = risk_stratified_sample(candidates, 2)
    assert [item["id"] for item in sampled] == ["high-a", "medium-b"]


def test_paper_contract_requires_an_executable_frozen_protocol(tmp_path: Path) -> None:
    path = tmp_path / "STORY.md"
    metadata = _contract()
    metadata["stage"] = "paper-story"
    metadata["selected_candidate"] = "I-1"
    _write(path, metadata)

    with pytest.raises(ContractError, match="lacks frozen protocol fields"):
        validate_contract(path, stage="paper-story")
