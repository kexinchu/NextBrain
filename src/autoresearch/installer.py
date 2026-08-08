from __future__ import annotations

import importlib.resources
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .skills import BUILTIN_SKILLS
from .io import sha256_bytes
from .snapshot import full_snapshot


def _directory_digest(path: Path) -> str | None:
    if not path.is_dir():
        return None
    files = full_snapshot(path)
    joined = "\n".join(f"{name}\0{digest}" for name, digest in sorted(files.items()))
    return sha256_bytes(joined.encode("utf-8"))


TARGET_DIRS = {
    "gpt": Path(".agents/skills"),
    "codex": Path(".agents/skills"),
    "claude": Path(".claude/skills"),
    "cursor": Path(".cursor/skills"),
}


@dataclass
class ConversationSkillInstaller:
    project_root: Path

    def _base(self, target: str, scope: str) -> Path:
        if target not in TARGET_DIRS:
            raise ValueError(f"unknown target: {target}")
        relative = TARGET_DIRS[target]
        if scope == "project":
            return self.project_root.resolve() / relative
        if scope == "user":
            return Path.home() / relative
        raise ValueError("scope must be 'project' or 'user'")

    def install(
        self,
        target: str,
        *,
        scope: str = "project",
        force: bool = False,
    ) -> list[Path]:
        targets = ("gpt", "claude", "cursor") if target == "all" else (target,)
        installed = []
        source_root = importlib.resources.files("autoresearch") / "builtin_skills"
        for client in targets:
            base = self._base(client, scope)
            base.mkdir(parents=True, exist_ok=True)
            for skill_name in BUILTIN_SKILLS:
                destination = base / skill_name
                if destination.exists():
                    if not force:
                        raise FileExistsError(
                            f"skill already exists: {destination}; pass --force to replace it"
                        )
                    shutil.rmtree(destination)
                source = source_root / skill_name
                with importlib.resources.as_file(source) as source_path:
                    shutil.copytree(source_path, destination)
                installed.append(destination)
        return installed

    def status(self, target: str, *, scope: str = "project") -> list[dict]:
        targets = ("gpt", "claude", "cursor") if target == "all" else (target,)
        source_root = importlib.resources.files("autoresearch") / "builtin_skills"
        results = []
        for client in targets:
            base = self._base(client, scope)
            for skill_name in BUILTIN_SKILLS:
                destination = base / skill_name
                source = source_root / skill_name
                with importlib.resources.as_file(source) as source_path:
                    expected = _directory_digest(source_path)
                installed = _directory_digest(destination)
                results.append(
                    {
                        "client": client,
                        "skill": skill_name,
                        "path": destination.as_posix(),
                        "installed": installed is not None,
                        "current": installed == expected,
                    }
                )
        return results

    def uninstall(
        self,
        target: str,
        *,
        scope: str = "project",
        force: bool = False,
    ) -> list[Path]:
        targets = ("gpt", "claude", "cursor") if target == "all" else (target,)
        removed = []
        for client in targets:
            base = self._base(client, scope)
            for skill_name in BUILTIN_SKILLS:
                destination = base / skill_name
                skill_file = destination / "SKILL.md"
                if not destination.exists():
                    continue
                content = skill_file.read_text(encoding="utf-8") if skill_file.is_file() else ""
                declared = re.search(r"^name:\s*([^\s]+)\s*$", content, re.M)
                if not force and (not declared or declared.group(1) != skill_name):
                    raise ValueError(f"refusing to remove an unrecognized skill directory: {destination}")
                shutil.rmtree(destination)
                removed.append(destination)
        return removed
