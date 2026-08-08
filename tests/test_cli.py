import sys
from pathlib import Path

from autoresearch.cli import main
from autoresearch.journal import UserMessageJournal
from autoresearch.topic import TopicDocument
from autoresearch.workspace import ResearchWorkspace


def test_cli_idea_uses_topic_file_and_writes_story(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    custom_topic = tmp_path / "topics" / "storage.md"
    custom_topic.parent.mkdir()
    custom_topic.write_text("# Storage direction\n", encoding="utf-8")
    fake_agent = Path(__file__).with_name("fake_agent.py")

    result = main(
        [
            "--workspace",
            str(tmp_path),
            "run",
            "idea",
            "--topic",
            "topics/storage.md",
            "--max-rounds",
            "1",
            "--agent-command",
            f"{sys.executable} {fake_agent}",
        ]
    )

    assert result == 0
    assert TopicDocument(tmp_path).relative_path() == "topics/storage.md"
    assert "run directive" in custom_topic.read_text(encoding="utf-8")
    assert len(UserMessageJournal(tmp_path).files()) == 1
    assert "topic-file workflow" in (tmp_path / "story.md").read_text(encoding="utf-8")


def test_cli_shows_canonical_venue_profile(capsys) -> None:
    assert main(["venues", "show", "NIPS"]) == 0
    output = capsys.readouterr().out
    assert '"canonical": "NeurIPS"' in output
