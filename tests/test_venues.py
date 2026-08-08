from pathlib import Path

import pytest

from autoresearch.config import ResearchConfig
from autoresearch.venues import VenueError, resolve_venue
from autoresearch.workspace import ResearchWorkspace


def test_nips_alias_normalizes_to_neurips() -> None:
    profile = resolve_venue("NIPS")
    assert profile.canonical == "NeurIPS"
    assert profile.family == "machine-learning"


def test_atc_is_historical_not_an_active_submission_target() -> None:
    with pytest.raises(VenueError, match="ended after ATC '25"):
        resolve_venue("ATC")
    assert resolve_venue("ATC", allow_inactive=True).status == "retired"


def test_default_workspace_carries_research_venue_priorities(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    context = ResearchConfig(tmp_path).venue_context()
    assert "systems-and-ai-infrastructure" in context
    assert "SOSP" in context and "MLSys" in context and "NeurIPS" in context
    assert "USENIX ATC (historical-general-systems, retired)" in context
