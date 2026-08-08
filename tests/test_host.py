import json
from pathlib import Path

import pytest
import yaml

from autoresearch.contracts import protocol_digest
from autoresearch.freeze import FreezeGuard
from autoresearch.host import HostRoundError, HostRoundManager
from autoresearch.journal import UserMessageJournal
from autoresearch.workflow import WorkflowError, WorkflowState
from autoresearch.workspace import ResearchWorkspace


HEADINGS = (
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


def contract(stage: str = "idea-story") -> str:
    experiment = {
        "id": "E-1",
        "kind": "motivation",
        "claim_ids": ["C-1"],
        "status": "planned",
    }
    if stage == "paper-story":
        experiment.update(
            prediction="system improves throughput",
            datasets=["tiny-fixture"],
            baselines=["baseline-a"],
            metrics=["throughput"],
            scales=["small"],
            seeds=[1],
            resource_budget="one CPU hour",
            success_criteria="throughput > baseline",
            kill_criteria="throughput <= baseline",
        )
    metadata = {
        "schema_version": 1,
        "stage": stage,
        "status": "accepted" if stage == "paper-story" else "exploring",
        "selected_candidate": "I-1" if stage == "paper-story" else None,
        "target_venues": ["OSDI"],
        "candidates": [
            {
                "id": "I-1",
                "approach": "systems",
                "collision_risk": 0.8,
                "novelty_uncertainty": 0.7,
                "scope_risk": 0.4,
                "motivation_cost": 0.2,
            }
        ],
        "sources": [
            {
                "id": "S-1",
                "title": "Primary source",
                "url": "https://example.com/paper",
                "kind": "primary-paper",
                "checked_at": "2026-08-08",
            }
        ],
        "claims": [
            {
                "id": "C-1",
                "statement": "A falsifiable claim.",
                "source_ids": ["S-1"],
                "experiment_ids": ["E-1"],
            }
        ],
        "experiments": [experiment],
    }
    headings = HEADINGS + (("Experiment matrix", "Human approval") if stage == "paper-story" else ())
    body = "\n\n".join(f"## {heading}\n\nEvidence." for heading in headings)
    return f"---\n{yaml.safe_dump(metadata, sort_keys=False)}---\n\n# Research story\n\n{body}\n"


def workspace(root: Path) -> tuple[HostRoundManager, UserMessageJournal, str]:
    ResearchWorkspace(root).init()
    journal = UserMessageJournal(root)
    message = journal.add("keep the requested scope fixed")
    return HostRoundManager(root), journal, message.name


def evidence(root: Path, started: dict, artifacts: list[str], **extra) -> None:
    value = {
        "schema_version": 1,
        "round_id": started["round_id"],
        "message_file": Path(extra.pop("message_file", "")).name
        or json.loads(
            (root / ".autoresearch/host-rounds" / f"{started['round_id']}.json").read_text()
        )["message_file"],
        "artifacts": artifacts,
        **extra,
    }
    path = root / started["evidence_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def accept_idea(root: Path, manager: HostRoundManager, message_file: str) -> None:
    scout = manager.begin("idea-loop", "idea-scout", message_file=message_file)
    (Path(scout["transaction_workspace"]) / "story.md").write_text(contract(), encoding="utf-8")
    evidence(
        root,
        scout,
        ["story.md"],
        subagents=[{"role": "idea-scout", "agent_id": "scout-1"}],
        sampled_candidate_ids=[],
    )
    manager.complete(scout["round_id"], "continue", output_file="story.md")

    challenger = manager.begin("idea-loop", "idea-challenger", message_file=message_file)
    (Path(challenger["transaction_workspace"]) / "story.md").write_text(
        contract() + "\nChallenger accepted the bounded sample.\n", encoding="utf-8"
    )
    evidence(
        root,
        challenger,
        ["story.md"],
        subagents=[{"role": "idea-challenger", "agent_id": "challenger-1"}],
        sampled_candidate_ids=["I-1"],
    )
    manager.complete(challenger["round_id"], "satisfied", output_file="story.md")


def freeze_story(
    root: Path,
    manager: HostRoundManager,
    journal: UserMessageJournal,
    message_file: str,
) -> str:
    draft = manager.begin("story-freeze", "story-editor", message_file=message_file)
    staged_story = Path(draft["transaction_workspace"]) / "paper/STORY.md"
    staged_story.parent.mkdir(parents=True, exist_ok=True)
    staged_story.write_text(contract("paper-story"), encoding="utf-8")
    evidence(root, draft, ["paper/STORY.md"])
    manager.complete(draft["round_id"], "continue")

    digest = WorkflowState(root).load()["story"]["draft_digest"]
    approval = journal.add(f"APPROVE paper/STORY.md {digest}")
    manager.approve_story(approval.name)
    final = manager.begin("story-freeze", "story-editor", message_file=approval.name)
    evidence(root, final, ["paper/STORY.md"])
    result = manager.complete(final["round_id"], "satisfied")
    assert result["decision"] == "satisfied"
    return approval.name


def test_host_uses_transaction_and_enforces_idea_alternation(tmp_path: Path) -> None:
    manager, _, message_file = workspace(tmp_path)
    scout = manager.begin("idea-loop", "idea-scout", message_file=message_file)
    staged = Path(scout["transaction_workspace"]) / "story.md"
    staged.write_text(contract(), encoding="utf-8")
    evidence(
        tmp_path,
        scout,
        ["story.md"],
        subagents=[{"role": "idea-scout", "agent_id": "scout-1"}],
        sampled_candidate_ids=[],
    )
    result = manager.complete(scout["round_id"], "continue", output_file="story.md")

    assert result["promoted_files"] == ["story.md"]
    assert "Research story" in (tmp_path / "story.md").read_text(encoding="utf-8")
    with pytest.raises(WorkflowError, match="requires role idea-challenger"):
        manager.begin("idea-loop", "idea-scout", message_file=message_file)


def test_direct_main_edit_is_quarantined_and_restored(tmp_path: Path) -> None:
    manager, _, message_file = workspace(tmp_path)
    started = manager.begin("idea-loop", "idea-scout", message_file=message_file)
    staged = Path(started["transaction_workspace"]) / "story.md"
    staged.write_text(contract(), encoding="utf-8")
    forbidden = tmp_path / "paper/manuscript/forbidden.md"
    forbidden.write_text("not allowed", encoding="utf-8")
    evidence(
        tmp_path,
        started,
        ["story.md"],
        subagents=[{"role": "idea-scout", "agent_id": "scout-1"}],
        sampled_candidate_ids=[],
    )

    with pytest.raises(HostRoundError, match="direct main-workspace edits"):
        manager.complete(started["round_id"], "continue")

    assert not forbidden.exists()
    quarantine = tmp_path / ".autoresearch/transactions" / started["round_id"] / "quarantine"
    assert (quarantine / "paper/manuscript/forbidden.md").exists()


def test_story_requires_later_exact_digest_approval(tmp_path: Path) -> None:
    manager, journal, message_file = workspace(tmp_path)
    accept_idea(tmp_path, manager, message_file)
    draft = manager.begin("story-freeze", "story-editor", message_file=message_file)
    staged_story = Path(draft["transaction_workspace"]) / "paper/STORY.md"
    staged_story.parent.mkdir(parents=True, exist_ok=True)
    staged_story.write_text(contract("paper-story"), encoding="utf-8")
    evidence(tmp_path, draft, ["paper/STORY.md"])
    manager.complete(draft["round_id"], "continue")

    vague = journal.add("looks good")
    with pytest.raises(HostRoundError, match="exact line"):
        manager.approve_story(vague.name)


def test_implementation_requires_successful_authorized_check(tmp_path: Path) -> None:
    manager, journal, message_file = workspace(tmp_path)
    accept_idea(tmp_path, manager, message_file)
    approval_message = freeze_story(tmp_path, manager, journal, message_file)
    config = yaml.safe_load((tmp_path / "autoresearch.yaml").read_text(encoding="utf-8"))
    config["commands"]["repository-tests"] = {
        "skill": "implementation-loop",
        "argv": ["python", "-m", "pytest", "code/tests"],
        "timeout": 3600,
    }
    (tmp_path / "autoresearch.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )

    started = manager.begin(
        "implementation-loop",
        "implementer",
        message_file=approval_message,
    )
    stage = Path(started["transaction_workspace"])
    (stage / "code/core/model.py").write_text("VALUE = 1\n", encoding="utf-8")
    (stage / "code/tests/test_model.py").write_text(
        "def test_value():\n    assert 1 == 1\n", encoding="utf-8"
    )
    evidence(
        tmp_path,
        started,
        ["code/core/model.py", "code/tests/test_model.py"],
    )
    with pytest.raises(HostRoundError, match="successful authorized check"):
        manager.complete(started["round_id"], "satisfied")
    assert not (tmp_path / ".autoresearch/freezes/core-code.json").exists()

    retry = manager.begin(
        "implementation-loop",
        "implementer",
        message_file=approval_message,
    )
    stage = Path(retry["transaction_workspace"])
    (stage / "code/core/model.py").write_text("VALUE = 1\n", encoding="utf-8")
    (stage / "code/tests/test_model.py").write_text(
        "def test_value():\n    assert 1 == 1\n", encoding="utf-8"
    )
    evidence(tmp_path, retry, ["code/core/model.py", "code/tests/test_model.py"])
    check = manager.check(retry["round_id"], "repository-tests")
    assert check["exit_code"] == 0
    result = manager.complete(retry["round_id"], "satisfied")
    assert result["decision"] == "satisfied"
    FreezeGuard(tmp_path).verify("core-code")


def test_implementation_check_is_bound_to_final_staged_contents(tmp_path: Path) -> None:
    manager, journal, message_file = workspace(tmp_path)
    accept_idea(tmp_path, manager, message_file)
    approval_message = freeze_story(tmp_path, manager, journal, message_file)
    config = yaml.safe_load((tmp_path / "autoresearch.yaml").read_text(encoding="utf-8"))
    config["commands"]["repository-tests"] = {
        "skill": "implementation-loop",
        "argv": ["python", "-m", "pytest", "code/tests"],
    }
    (tmp_path / "autoresearch.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    started = manager.begin(
        "implementation-loop", "implementer", message_file=approval_message
    )
    stage = Path(started["transaction_workspace"])
    core = stage / "code/core/model.py"
    core.write_text("VALUE = 1\n", encoding="utf-8")
    (stage / "code/tests/test_model.py").write_text(
        "def test_value():\n    assert 1 == 1\n", encoding="utf-8"
    )
    evidence(tmp_path, started, ["code/core/model.py", "code/tests/test_model.py"])
    assert manager.check(started["round_id"], "repository-tests")["exit_code"] == 0
    core.write_text("VALUE = 2\n", encoding="utf-8")

    with pytest.raises(HostRoundError, match="current staged contents"):
        manager.complete(started["round_id"], "satisfied")


def test_wrong_role_is_rejected_before_message_resolution(tmp_path: Path) -> None:
    manager, _, message_file = workspace(tmp_path)
    with pytest.raises(HostRoundError, match="invalid role"):
        manager.begin("idea-loop", "implementer", message_file=message_file)


def frozen_workspace(root: Path) -> tuple[HostRoundManager, str]:
    manager, _, message_file = workspace(root)
    story = root / "paper/STORY.md"
    story.write_text(contract("paper-story"), encoding="utf-8")
    (root / "code/core/model.py").write_text("VALUE = 1\n", encoding="utf-8")
    manager.freezes.create("paper-story", ("paper/STORY.md",))
    manager.freezes.create("core-code", ("code/core",))
    state = WorkflowState(root).load()
    state["idea"]["status"] = "satisfied"
    state["story"]["status"] = "frozen"
    state["implementation"]["status"] = "frozen"
    WorkflowState(root).save(state)
    return manager, message_file


def test_experiment_contradiction_is_promoted_but_forces_report(tmp_path: Path) -> None:
    manager, message_file = frozen_workspace(tmp_path)
    config = yaml.safe_load((tmp_path / "autoresearch.yaml").read_text(encoding="utf-8"))
    config["commands"]["batch"] = {
        "skill": "experiment-loop",
        "argv": [
            "python",
            "-c",
            "from pathlib import Path; p=Path('experiments/results/E-1.json'); "
            "p.parent.mkdir(parents=True, exist_ok=True); p.write_text('observed')",
        ],
    }
    (tmp_path / "autoresearch.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    started = manager.begin("experiment-loop", "experimenter", message_file=message_file)
    check = manager.check(started["round_id"], "batch")
    assert check["exit_code"] == 0
    evidence(
        tmp_path,
        started,
        ["experiments/results/E-1.json"],
        experiment_cells=[
            {
                "id": "E-1",
                "status": "contradiction",
                "result_paths": ["experiments/results/E-1.json"],
                "configuration_digest": "config-sha",
                "claim_ids": ["C-1"],
                "protocol_digest": protocol_digest(
                    yaml.safe_load(
                        (tmp_path / "paper/STORY.md").read_text(encoding="utf-8").split(
                            "---", 2
                        )[1]
                    )["experiments"][0]
                ),
            }
        ],
    )

    result = manager.complete(started["round_id"], "satisfied")
    assert result["decision"] == "report"
    assert (tmp_path / "experiments/results/E-1.json").is_file()
    FreezeGuard(tmp_path).verify("paper-story")
    FreezeGuard(tmp_path).verify("core-code")


def test_review_rejects_unrelated_output_and_requires_new_artifact(tmp_path: Path) -> None:
    manager, message_file = frozen_workspace(tmp_path)
    old = tmp_path / "reviews/old.md"
    old.write_text("old", encoding="utf-8")
    started = manager.begin(
        "venue-review", "venue-reviewer", message_file=message_file, venue="OSDI"
    )
    staged_review = Path(started["transaction_workspace"]) / "reviews/new.md"
    staged_review.parent.mkdir(parents=True, exist_ok=True)
    staged_review.write_text("# New review\n", encoding="utf-8")
    evidence(
        tmp_path,
        started,
        ["reviews/new.md"],
        venue="OSDI",
        venue_guidance_sources=[
            {
                "title": "OSDI call for papers",
                "url": "https://example.com/osdi",
                "accessed_at": "2026-08-08",
            }
        ],
        reviewer={"mode": "current-model"},
    )

    with pytest.raises(HostRoundError, match="outside the round allowlist"):
        manager.complete(started["round_id"], "satisfied", output_file="topic.md")
    assert old.read_text(encoding="utf-8") == "old"
    assert not (tmp_path / "reviews/new.md").exists()


def test_section_writing_binds_venue_and_style_sources(tmp_path: Path) -> None:
    manager, message_file = frozen_workspace(tmp_path)
    state = WorkflowState(tmp_path).load()
    state["experiment"]["status"] = "complete"
    WorkflowState(tmp_path).save(state)

    with pytest.raises(HostRoundError, match="requires --venue"):
        manager.begin(
            "section-writing",
            "section-writer",
            message_file=message_file,
            section="introduction",
        )

    started = manager.begin(
        "section-writing",
        "section-writer",
        message_file=message_file,
        section="introduction",
        venue="OSDI",
    )
    section = Path(started["transaction_workspace"]) / "paper/manuscript/introduction.md"
    section.parent.mkdir(parents=True, exist_ok=True)
    section.write_text("# Introduction\n\nC-1 remains bounded.\n", encoding="utf-8")
    evidence(
        tmp_path,
        started,
        ["paper/manuscript/introduction.md"],
        preserved_claim_ids=["C-1"],
        new_claims=[],
        venue="OSDI",
        style_sources=[
            {
                "title": "Accepted paper",
                "url": "https://example.com/paper",
                "venue": "OSDI",
                "year": 2025,
                "accessed_at": "2026-08-08",
            }
        ],
    )

    result = manager.complete(
        started["round_id"],
        "satisfied",
        output_file="paper/manuscript/introduction.md",
    )
    assert result["decision"] == "satisfied"


def test_venue_round_rejects_retired_or_unfrozen_targets(tmp_path: Path) -> None:
    manager, message_file = frozen_workspace(tmp_path)

    with pytest.raises(HostRoundError, match="ended after ATC '25"):
        manager.begin(
            "venue-review",
            "venue-reviewer",
            message_file=message_file,
            venue="ATC",
        )
    with pytest.raises(HostRoundError, match="not a frozen target venue"):
        manager.begin(
            "venue-review",
            "venue-reviewer",
            message_file=message_file,
            venue="NIPS",
        )
