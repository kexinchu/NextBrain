from pathlib import Path

from autoresearch.doctor import Doctor
from autoresearch.e2e import E2ERegistry
from autoresearch.installer import ConversationSkillInstaller
from autoresearch.journal import UserMessageJournal
from autoresearch.workspace import ResearchWorkspace


def test_doctor_distinguishes_local_readiness_from_real_client_e2e(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    UserMessageJournal(tmp_path).add("audit this workspace")
    ConversationSkillInstaller(tmp_path).install("all")

    assert Doctor(tmp_path).run()["ok"]
    assert not Doctor(tmp_path).run(require_e2e=True)["ok"]


def test_e2e_receipt_is_bound_to_evidence_digest(tmp_path: Path) -> None:
    evidence = tmp_path / "codex-evidence.md"
    evidence.write_text("passed in Codex", encoding="utf-8")
    registry = E2ERegistry(tmp_path)
    registry.record("gpt", "idea-loop", "gpt-test", "pass", evidence)

    row = next(
        item
        for item in registry.matrix()
        if item["client"] == "gpt" and item["skill"] == "idea-loop"
    )
    assert row["status"] == "pass" and row["evidence_ok"]

    evidence.write_text("changed", encoding="utf-8")
    row = next(
        item
        for item in registry.matrix()
        if item["client"] == "gpt" and item["skill"] == "idea-loop"
    )
    assert not row["evidence_ok"]
