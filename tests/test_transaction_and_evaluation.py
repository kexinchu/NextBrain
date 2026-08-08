from pathlib import Path

import pytest

import autoresearch.transaction as transaction_module
from autoresearch.evaluation import CapabilityEvaluator
from autoresearch.installer import ConversationSkillInstaller
from autoresearch.journal import UserMessageJournal
from autoresearch.transaction import RoundTransaction, TransactionError
from autoresearch.workspace import ResearchWorkspace


def test_promotion_failure_rolls_back_previously_promoted_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ResearchWorkspace(tmp_path).init()
    first = tmp_path / "code" / "core" / "first.py"
    second = tmp_path / "code" / "core" / "second.py"
    first.write_text("before first\n", encoding="utf-8")
    second.write_text("before second\n", encoding="utf-8")

    transaction = RoundTransaction(tmp_path, "round-rollback", ("code/core",))
    transaction.create()
    transaction.backup_main(("code/core",))
    (transaction.workspace / "code/core/first.py").write_text("after first\n", encoding="utf-8")
    (transaction.workspace / "code/core/second.py").write_text("after second\n", encoding="utf-8")

    real_atomic_copy = transaction_module.atomic_copy
    calls = 0

    def fail_second_staged_copy(source: Path, destination: Path) -> None:
        nonlocal calls
        if source.is_relative_to(transaction.workspace):
            calls += 1
            if calls == 2:
                raise OSError("injected copy failure")
        real_atomic_copy(source, destination)

    monkeypatch.setattr(transaction_module, "atomic_copy", fail_second_staged_copy)
    with pytest.raises(TransactionError, match="rolled back"):
        transaction.promote(("code/core/first.py", "code/core/second.py"))

    assert first.read_text(encoding="utf-8") == "before first\n"
    assert second.read_text(encoding="utf-8") == "before second\n"


def test_eval_default_works_without_release_source_tree(tmp_path: Path) -> None:
    ResearchWorkspace(tmp_path).init()
    UserMessageJournal(tmp_path).add("evaluate installed workspace")
    ConversationSkillInstaller(tmp_path).install("all")

    result = CapabilityEvaluator(tmp_path).run()

    assert result["ok"]
    assert all(gate["name"] != "plugin-manifest" for gate in result["gates"])
