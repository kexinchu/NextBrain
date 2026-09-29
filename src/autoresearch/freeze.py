from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .io import tree_hash, utc_stamp, write_json


class FreezeViolation(RuntimeError):
    pass


@dataclass
class FreezeGuard:
    root: Path

    @property
    def directory(self) -> Path:
        return self.root / ".autoresearch" / "freezes"

    def create(self, name: str, relative_paths: Iterable[str]) -> Path:
        relative_paths = list(relative_paths)
        if name == 'paper-story' or 'paper/STORY.md' in relative_paths:
            from researchos.controller import check_workspace_story_gate
            check_workspace_story_gate(self.root)
        resolved = [self.root / path for path in relative_paths]
        digest, files = tree_hash(resolved, self.root)
        if not files:
            raise FileNotFoundError("cannot freeze an empty or missing path set")
        lock = {
            "name": name,
            "created_at": utc_stamp(),
            "paths": list(relative_paths),
            "digest": digest,
            "files": files,
        }
        target = self.directory / f"{name}.json"
        write_json(target, lock)
        return target

    def load(self, name: str) -> dict:
        path = self.directory / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"freeze '{name}' does not exist; create it first")
        return json.loads(path.read_text(encoding="utf-8"))

    def verify(self, name: str) -> None:
        lock = self.load(name)
        digest, files = tree_hash([self.root / path for path in lock["paths"]], self.root)
        if digest != lock["digest"]:
            before = lock["files"]
            changed = sorted(
                path for path in set(before) | set(files) if before.get(path) != files.get(path)
            )
            raise FreezeViolation(f"freeze '{name}' violated by: {', '.join(changed)}")
