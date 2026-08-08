from pathlib import Path

import pytest

from autoresearch.agent import AgentReply
from autoresearch.journal import UserMessageJournal
from autoresearch.orchestrator import AutoResearch, PathPolicyViolation
from autoresearch.workspace import ResearchWorkspace


class QueueAgent:
    def __init__(self, factories):
        self.factories = list(factories)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return self.factories.pop(0)(request)


def reply(request, *, decision="continue", **extra):
    data = {
        "content": extra.pop("content", "round report"),
        "decision": decision,
        "summary": "done",
        "alignment": {
            "requirements_digest": request.requirements_digest,
            "preserved_constraints": ["all"],
            "possible_drift": "none",
        },
        "files": extra.pop("files", {}),
        **extra,
    }
    return AgentReply(content=data["content"], data=data)


def prepared_workspace(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    UserMessageJournal(tmp_path).add("stay within systems research")


def test_idea_roles_alternate_and_stop_when_satisfied(tmp_path: Path) -> None:
    prepared_workspace(tmp_path)
    agent = QueueAgent(
        [
            lambda request: reply(
                request,
                candidates=[{"id": "I-1", "claim": "x"}],
                story="# Candidate story\n\nInitial proposal.",
            ),
            lambda request: reply(
                request,
                decision="satisfied",
                challenge="survives",
                surviving_candidates=["I-1"],
                story="# Accepted story\n\nThe candidate survives.",
            ),
        ]
    )
    outcomes = AutoResearch(tmp_path, agent).idea_loop("topic.md", max_rounds=4)

    assert [item.role for item in outcomes] == ["idea-scout", "idea-challenger"]
    assert outcomes[-1].decision == "satisfied"
    assert all("stay within systems research" in req.prompt for req in agent.requests)
    assert all("Topic document: topic.md" in req.prompt for req in agent.requests)
    assert all((tmp_path / item.alignment_path).exists() for item in outcomes)
    assert "The candidate survives" in (tmp_path / "story.md").read_text(encoding="utf-8")


def test_story_freeze_and_implementation_policy(tmp_path: Path) -> None:
    prepared_workspace(tmp_path)
    idea = tmp_path / "ideas" / "accepted.md"
    idea.write_text("accepted idea", encoding="utf-8")
    story_agent = QueueAgent(
        [lambda request: reply(
            request,
            decision="satisfied",
            files={"paper/STORY.md": "# Frozen story\n"},
        )]
    )
    research = AutoResearch(tmp_path, story_agent)
    research.freeze_story("ideas/accepted.md")
    research.freezes.verify("paper-story")

    bad_agent = QueueAgent(
        [lambda request: reply(request, files={"paper/STORY.md": "changed"})]
    )
    with pytest.raises(PathPolicyViolation):
        AutoResearch(tmp_path, bad_agent).implementation_loop(max_rounds=1)


def test_budget_exhaustion_produces_human_report(tmp_path: Path) -> None:
    prepared_workspace(tmp_path)
    agent = QueueAgent(
        [
            lambda request: reply(
                request, candidates=[{"id": "I-1"}], story="# Candidate\n"
            ),
            lambda request: reply(
                request, challenge="needs another round", story="# Still open\n"
            ),
        ]
    )
    outcomes = AutoResearch(tmp_path, agent).idea_loop("topic.md", max_rounds=1)

    assert outcomes[-1].role == "budget-reporter"
    assert outcomes[-1].decision == "report"


def test_failed_post_implementation_check_prevents_core_freeze(tmp_path: Path) -> None:
    prepared_workspace(tmp_path)
    story = tmp_path / "paper" / "STORY.md"
    story.write_text("# Fixed story\n", encoding="utf-8")
    research_agent = QueueAgent(
        [
            lambda request: reply(
                request,
                decision="satisfied",
                files={"code/core/model.py": "VALUE = 1\n"},
            )
        ]
    )
    research = AutoResearch(tmp_path, research_agent)
    research.freezes.create("paper-story", ("paper/STORY.md",))
    outcomes = research.implementation_loop(
        max_rounds=1,
        check_command="python -c 'import sys; sys.exit(7)'",
    )

    assert outcomes[-1].decision == "report"
    assert not (tmp_path / ".autoresearch" / "freezes" / "core-code.json").exists()
