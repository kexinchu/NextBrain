from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .io import atomic_write
from .journal import UserMessageJournal


class RequirementSummaryError(RuntimeError):
    pass


@dataclass
class RequirementSummary:
    root: Path

    @property
    def path(self) -> Path:
        return self.root / "requirements" / "current.md"

    def update(self, text: str) -> Path:
        journal = UserMessageJournal(self.root)
        _, digest = journal.context()
        files = journal.files()
        missing = [path.name for path in files if path.name.split("-", 1)[0] not in text]
        if missing:
            raise RequirementSummaryError(
                "summary must cite every message id; missing: " + ", ".join(missing)
            )
        metadata = {
            "schema_version": 1,
            "source_digest": digest,
            "covered_messages": [path.name for path in files],
        }
        body = f"---\n{yaml.safe_dump(metadata, sort_keys=False)}---\n\n{text.strip()}\n"
        atomic_write(self.path, body)
        return self.path

    def load_current(self) -> str | None:
        if not self.path.exists():
            return None
        raw = self.path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
        if not match:
            return None
        metadata = yaml.safe_load(match.group(1)) or {}
        journal = UserMessageJournal(self.root)
        _, digest = journal.context()
        files = [path.name for path in journal.files()]
        if metadata.get("source_digest") != digest or metadata.get("covered_messages") != files:
            return None
        return match.group(2).strip()

    def status(self) -> dict:
        return {
            "path": self.path.as_posix(),
            "exists": self.path.exists(),
            "current": self.load_current() is not None,
        }
