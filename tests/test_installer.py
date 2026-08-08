from pathlib import Path

from autoresearch.installer import ConversationSkillInstaller
from autoresearch.skills import BUILTIN_SKILLS


def test_installs_portable_skills_for_all_conversation_hosts(tmp_path: Path) -> None:
    installed = ConversationSkillInstaller(tmp_path).install("all")

    assert len(installed) == len(BUILTIN_SKILLS) * 3
    for relative in (".agents/skills", ".claude/skills", ".cursor/skills"):
        for skill in BUILTIN_SKILLS:
            content = (tmp_path / relative / skill / "SKILL.md").read_text(encoding="utf-8")
            assert "model: inherit" in content
            assert "current" in content
            assert "autoresearch run" in content
            assert (tmp_path / relative / skill / "agents/openai.yaml").is_file()


def test_force_replaces_only_the_named_skill_destinations(tmp_path: Path) -> None:
    installer = ConversationSkillInstaller(tmp_path)
    installer.install("claude")
    skill_file = tmp_path / ".claude" / "skills" / "idea-loop" / "SKILL.md"
    skill_file.write_text("changed", encoding="utf-8")

    installer.install("claude", force=True)

    assert skill_file.read_text(encoding="utf-8").startswith("---\nname: idea-loop")


def test_status_update_and_safe_uninstall(tmp_path: Path) -> None:
    installer = ConversationSkillInstaller(tmp_path)
    installer.install("cursor")
    assert all(item["current"] for item in installer.status("cursor"))

    skill_file = tmp_path / ".cursor/skills/idea-loop/SKILL.md"
    skill_file.write_text("changed", encoding="utf-8")
    assert not all(item["current"] for item in installer.status("cursor"))
    installer.install("cursor", force=True)
    removed = installer.uninstall("cursor")
    assert len(removed) == 6
    assert not (tmp_path / ".cursor/skills/idea-loop").exists()
