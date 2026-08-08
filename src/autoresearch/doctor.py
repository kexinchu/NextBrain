from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .config import ConfigError, ResearchConfig
from .e2e import E2ERegistry
from .freeze import FreezeGuard, FreezeViolation
from .installer import ConversationSkillInstaller
from .journal import JournalIntegrityError, UserMessageJournal
from .topic import TopicDocument
from .workflow import WorkflowState
from .skills import BUILTIN_SKILLS


@dataclass
class Doctor:
    root: Path

    def run(self, *, require_e2e: bool = False, release: bool = False) -> dict:
        checks: list[dict] = []

        def add(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": ok, "detail": detail})

        try:
            ResearchConfig(self.root).load()
            add("config", True, "autoresearch.yaml is valid")
        except (ConfigError, OSError) as exc:
            add("config", False, str(exc))
        try:
            journal = UserMessageJournal(self.root)
            journal.verify_integrity()
            add("message-journal", bool(journal.files()), f"{len(journal.files())} messages")
        except JournalIntegrityError as exc:
            add("message-journal", False, str(exc))
        try:
            active = TopicDocument(self.root).relative_path()
            add("active-topic", True, active)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            add("active-topic", False, str(exc))

        installer = ConversationSkillInstaller(self.root)
        statuses = installer.status("all")
        add(
            "conversation-skills",
            all(item["current"] for item in statuses),
            f"{sum(item['current'] for item in statuses)}/{len(statuses)} current",
        )
        workflow = WorkflowState(self.root).load()
        add(
            "pending-round",
            workflow.get("pending_round") is None,
            str(workflow.get("pending_round") or "none"),
        )
        guard = FreezeGuard(self.root)
        for name in ("paper-story", "core-code"):
            try:
                guard.verify(name)
                add(f"freeze-{name}", True, "intact")
            except FileNotFoundError:
                add(f"freeze-{name}", True, "not created yet")
            except FreezeViolation as exc:
                add(f"freeze-{name}", False, str(exc))
        if release:
            plugin = self.root / ".codex-plugin" / "plugin.json"
            try:
                value = json.loads(plugin.read_text(encoding="utf-8"))
                add("plugin-manifest", bool(value.get("skills")), value.get("version", "unknown"))
                from . import __version__

                skill_versions = set()
                for name in BUILTIN_SKILLS:
                    skill_path = self.root / "src/autoresearch/builtin_skills" / name / "SKILL.md"
                    text = skill_path.read_text(encoding="utf-8")
                    match = re.search(r"^version:\s*(\S+)\s*$", text, re.M)
                    skill_versions.add(match.group(1) if match else "missing")
                add(
                    "version-consistency",
                    skill_versions == {__version__} and value.get("version") == __version__,
                    f"package={__version__}, plugin={value.get('version')}, "
                    f"skills={sorted(skill_versions)}",
                )
            except (OSError, json.JSONDecodeError) as exc:
                add("plugin-manifest", False, str(exc))
        if require_e2e:
            matrix = E2ERegistry(self.root).matrix()
            passed = [item for item in matrix if item["status"] == "pass" and item["evidence_ok"]]
            add("client-e2e", len(passed) == len(matrix), f"{len(passed)}/{len(matrix)} passed")
        return {"ok": all(item["ok"] for item in checks), "checks": checks}
