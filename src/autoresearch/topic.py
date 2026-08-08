from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .io import atomic_write, write_json


TOPIC_TEMPLATE = """# Research topic

## Direction

Describe the research direction and target problem.

## Scope and hard exclusions

- Add ideas that must not be rediscovered or rephrased.

## Resources and limits

- Compute budget:
- Time budget:
- Allowed data:

## Success and kill criteria

- Success:
- Kill:

## Session requirements

Requirements recorded through `autoresearch message` and `autoresearch run` are mirrored
below. The immutable source records remain under `requirements/messages/`.
"""


class TopicPathError(ValueError):
    pass


@dataclass
class TopicDocument:
    root: Path

    @property
    def state_path(self) -> Path:
        return self.root / ".autoresearch" / "active-topic.json"

    def _resolve(self, value: str | Path) -> tuple[Path, str]:
        supplied = Path(value)
        if supplied.suffix.lower() != ".md":
            raise TopicPathError("topic must point to a Markdown (.md) document")
        candidate = (self.root / supplied).resolve()
        try:
            relative = candidate.relative_to(self.root.resolve()).as_posix()
        except ValueError as exc:
            raise TopicPathError("topic document must stay inside the research workspace") from exc
        return candidate, relative

    def set_active(self, value: str | Path, *, create: bool = False) -> Path:
        path, relative = self._resolve(value)
        if not path.exists():
            if not create:
                raise FileNotFoundError(f"topic document does not exist: {relative}")
            atomic_write(path, TOPIC_TEMPLATE)
        current = path.read_text(encoding="utf-8")
        if "## Session requirements" not in current:
            atomic_write(
                path,
                current.rstrip()
                + "\n\n## Session requirements\n\n"
                + "Session requirements recorded by AutoResearch appear below.\n",
            )
        write_json(self.state_path, {"path": relative})
        self.sync_requirements()
        return path

    def active_path(self) -> Path:
        if self.state_path.exists():
            import json

            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            path, _ = self._resolve(state["path"])
            if not path.exists():
                raise FileNotFoundError(f"active topic document does not exist: {path}")
            return path
        return self.set_active("topic.md", create=True)

    def relative_path(self) -> str:
        return self.active_path().relative_to(self.root.resolve()).as_posix()

    def append_requirement(
        self,
        message_path: Path,
        text: str,
        *,
        source: str,
        recorded_at: str,
    ) -> None:
        topic_path = self.active_path()
        marker = f"<!-- autoresearch-message:{message_path.name} -->"
        current = topic_path.read_text(encoding="utf-8")
        if marker in current:
            return
        link = os.path.relpath(message_path, topic_path.parent)
        entry = (
            f"\n\n### Session requirement {message_path.name.split('-', 1)[0]}\n\n"
            f"{marker}\n"
            f"- Recorded at: `{recorded_at}`\n"
            f"- Source: `{source}`\n"
            f"- Immutable record: [`{message_path.name}`]({Path(link).as_posix()})\n\n"
            f"{text.rstrip()}\n"
        )
        atomic_write(topic_path, current.rstrip() + entry)

    def sync_requirements(self) -> None:
        from .journal import UserMessageJournal

        journal = UserMessageJournal(self.root)
        journal.verify_integrity()
        for message_path in journal.files():
            raw = message_path.read_text(encoding="utf-8")
            parts = raw.split("---\n", 2)
            metadata: dict[str, str] = {}
            body = raw
            if len(parts) == 3:
                for line in parts[1].splitlines():
                    key, separator, value = line.partition(":")
                    if separator:
                        metadata[key.strip()] = value.strip()
                body = parts[2].lstrip()
            self.append_requirement(
                message_path,
                body,
                source=metadata.get("source", "user"),
                recorded_at=metadata.get("recorded_at", "unknown"),
            )
