from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from autoresearch.alignment import AlignmentGuard
from autoresearch.freeze import FreezeGuard, FreezeViolation
from autoresearch.journal import JournalIntegrityError, UserMessageJournal
from autoresearch.requirements import RequirementSummary, RequirementSummaryError
from autoresearch.topic import TopicDocument
from autoresearch.workspace import ResearchWorkspace


def test_each_message_is_separate_and_changes_digest(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    journal = UserMessageJournal(tmp_path)
    first = journal.add("first constraint")
    _, digest_one = journal.context()
    second = journal.add("second constraint")
    context, digest_two = journal.context()

    assert first != second
    assert len(journal.files()) == 2
    assert "first constraint" in context and "second constraint" in context
    assert digest_one != digest_two


def test_freeze_detects_a_change(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    story = tmp_path / "paper" / "STORY.md"
    story.write_text("fixed", encoding="utf-8")
    guard = FreezeGuard(tmp_path)
    guard.create("paper-story", ("paper/STORY.md",))
    guard.verify("paper-story")

    story.write_text("drifted", encoding="utf-8")
    with pytest.raises(FreezeViolation, match="paper/STORY.md"):
        guard.verify("paper-story")


def test_topic_document_records_messages_and_is_part_of_digest(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    UserMessageJournal(tmp_path).add("fixed requirement")
    before = AlignmentGuard(tmp_path).snapshot()
    topic = tmp_path / "topic.md"
    assert "fixed requirement" in topic.read_text(encoding="utf-8")
    topic.write_text(topic.read_text(encoding="utf-8") + "\nNew direction\n", encoding="utf-8")
    after = AlignmentGuard(tmp_path).snapshot()

    assert "topic.md" in before.message_files
    assert before.digest != after.digest


def test_recorded_messages_are_append_only(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    journal = UserMessageJournal(tmp_path)
    message = journal.add("do not change this")
    message.write_text("silently changed", encoding="utf-8")

    with pytest.raises(JournalIntegrityError, match="modified"):
        journal.context()


def test_switching_topic_document_syncs_existing_session_requirements(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    UserMessageJournal(tmp_path).add("must survive a topic switch")
    alternate = tmp_path / "topics" / "storage.md"
    alternate.parent.mkdir()
    alternate.write_text("# Storage topic\n", encoding="utf-8")

    TopicDocument(tmp_path).set_active("topics/storage.md")

    assert "must survive a topic switch" in alternate.read_text(encoding="utf-8")
    assert TopicDocument(tmp_path).relative_path() == "topics/storage.md"


def test_compact_requirement_view_must_cover_every_message(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    journal = UserMessageJournal(tmp_path)
    journal.add("first requirement")
    journal.add("second requirement")
    summary = RequirementSummary(tmp_path)

    with pytest.raises(RequirementSummaryError, match="0002"):
        summary.update("- [0001] first requirement")

    summary.update("- [0001] first requirement\n- [0002] second requirement")
    assert summary.load_current() is not None
    assert "Current verified requirement summary" in AlignmentGuard(tmp_path).snapshot().context

    journal.add("third requirement")
    assert summary.load_current() is None


def test_concurrent_messages_keep_unique_records(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    journal = UserMessageJournal(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(journal.add, [f"requirement {index}" for index in range(8)]))

    journal.verify_integrity()
    assert len(journal.files()) == 8
    assert [path.name[:4] for path in journal.files()] == [f"{index:04d}" for index in range(1, 9)]
