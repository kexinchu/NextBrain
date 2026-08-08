from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .venues import VenueError, resolve_venue


class ContractError(ValueError):
    pass


IDEA_HEADINGS = (
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

PAPER_HEADINGS = IDEA_HEADINGS + (
    "Experiment matrix",
    "Human approval",
)


@dataclass(frozen=True)
class MarkdownContract:
    metadata: dict[str, Any]
    body: str


def protocol_digest(experiment: dict[str, Any]) -> str:
    encoded = json.dumps(experiment, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def parse_contract(path: Path) -> MarkdownContract:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ContractError(f"{path.name} requires YAML frontmatter")
    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ContractError(f"{path.name} frontmatter must be a mapping")
    return MarkdownContract(metadata, match.group(2).strip())


def _records(metadata: dict[str, Any], name: str) -> list[dict[str, Any]]:
    value = metadata.get(name, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ContractError(f"{name} must be a list of mappings")
    return value


def _unique_ids(records: list[dict[str, Any]], name: str) -> set[str]:
    ids = [item.get("id") for item in records]
    if any(not isinstance(item, str) or not item.strip() for item in ids):
        raise ContractError(f"every {name} entry requires a non-empty id")
    if len(ids) != len(set(ids)):
        raise ContractError(f"duplicate {name} ids")
    return set(ids)


def _references(record: dict[str, Any], field: str) -> set[str]:
    value = record.get(field, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ContractError(f"{field} must be a list of non-empty ids")
    return set(value)


def _require_headings(body: str, headings: tuple[str, ...]) -> None:
    present = {match.group(1).strip() for match in re.finditer(r"^##\s+(.+?)\s*$", body, re.M)}
    missing = [heading for heading in headings if heading not in present]
    if missing:
        raise ContractError(f"missing required headings: {', '.join(missing)}")


def validate_contract(path: Path, *, stage: str) -> MarkdownContract:
    contract = parse_contract(path)
    metadata = contract.metadata
    if metadata.get("schema_version") != 1:
        raise ContractError("schema_version must be 1")
    if metadata.get("stage") != stage:
        raise ContractError(f"stage must be '{stage}'")

    candidates = _records(metadata, "candidates")
    claims = _records(metadata, "claims")
    sources = _records(metadata, "sources")
    experiments = _records(metadata, "experiments")
    candidate_ids = _unique_ids(candidates, "candidate")
    claim_ids = _unique_ids(claims, "claim")
    source_ids = _unique_ids(sources, "source")
    experiment_ids = _unique_ids(experiments, "experiment")
    target_venues = metadata.get("target_venues", [])
    if not isinstance(target_venues, list) or not target_venues or not all(
        isinstance(item, str) and item.strip() for item in target_venues
    ):
        raise ContractError("target_venues must be a non-empty venue-name list")
    try:
        for venue in target_venues:
            resolve_venue(venue)
    except VenueError as exc:
        raise ContractError(f"invalid active target venue: {exc}") from exc

    for candidate in candidates:
        if not candidate.get("approach"):
            raise ContractError("every candidate requires an approach")
        for key in ("collision_risk", "novelty_uncertainty", "scope_risk", "motivation_cost"):
            value = candidate.get(key)
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                raise ContractError(f"candidate {key} must be numeric in [0, 1]")
    for source in sources:
        if (
            not source.get("title")
            or not source.get("url")
            or not source.get("kind")
            or not source.get("checked_at")
        ):
            raise ContractError("every source requires title, url, kind, and checked_at")
    for claim in claims:
        if not claim.get("statement"):
            raise ContractError("every claim requires a statement")
        unknown_sources = _references(claim, "source_ids") - source_ids
        unknown_experiments = _references(claim, "experiment_ids") - experiment_ids
        if unknown_sources or unknown_experiments:
            raise ContractError("claim references unknown sources or experiments")
    for experiment in experiments:
        if not experiment.get("kind") or not experiment.get("status"):
            raise ContractError("every experiment requires kind and status")
        unknown_claims = _references(experiment, "claim_ids") - claim_ids
        if unknown_claims:
            raise ContractError("experiment references unknown claims")

    selected = metadata.get("selected_candidate")
    if selected is not None and not isinstance(selected, str):
        raise ContractError("selected_candidate must be a candidate id")
    if selected is not None and selected not in candidate_ids:
        raise ContractError("selected_candidate must reference a candidate id")
    if stage == "paper-story":
        if not selected:
            raise ContractError("paper-story requires selected_candidate")
        if not claims or not experiments:
            raise ContractError("paper-story requires claims and experiments")
        required_protocol = (
            "prediction",
            "datasets",
            "baselines",
            "metrics",
            "scales",
            "seeds",
            "resource_budget",
            "success_criteria",
            "kill_criteria",
        )
        for experiment in experiments:
            missing = [field for field in required_protocol if not experiment.get(field)]
            if missing:
                raise ContractError(
                    f"paper experiment {experiment['id']} lacks frozen protocol fields: "
                    f"{', '.join(missing)}"
                )
            for field in ("datasets", "baselines", "metrics", "scales", "seeds"):
                value = experiment[field]
                if not isinstance(value, list) or not value:
                    raise ContractError(f"paper experiment {field} must be a non-empty list")
        _require_headings(contract.body, PAPER_HEADINGS)
    else:
        if not candidates:
            raise ContractError("idea-story requires at least one candidate")
        _require_headings(contract.body, IDEA_HEADINGS)
    return contract


def contract_ids(path: Path) -> dict[str, set[str]]:
    contract = parse_contract(path)
    return {
        name: _unique_ids(_records(contract.metadata, name), name.rstrip("s"))
        for name in ("candidates", "claims", "sources", "experiments")
    }
