from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .io import atomic_write, exclusive_lock, sha256_bytes, sha256_file, utc_stamp, write_json


class JournalIntegrityError(RuntimeError):
    pass


@dataclass
class UserMessageJournal:
    root: Path

    @property
    def directory(self) -> Path:
        return self.root / "requirements" / "messages"

    @property
    def manifest_path(self) -> Path:
        return self.directory / ".manifest.json"

    def _manifest(self) -> dict:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if self.files():
            raise JournalIntegrityError("message manifest missing for a non-empty journal")
        return {"version": 1, "messages": {}}

    def verify_integrity(self) -> None:
        manifest = self._manifest()
        expected = manifest.get("messages", {})
        actual_names = {path.name for path in self.files()}
        if actual_names != set(expected):
            raise JournalIntegrityError("message set differs from the append-only manifest")
        changed = [
            name
            for name, digest in expected.items()
            if sha256_file(self.directory / name) != digest
        ]
        if changed:
            raise JournalIntegrityError(f"recorded user messages were modified: {', '.join(changed)}")

    def add(self, text: str, source: str = "user") -> Path:
        if not text.strip():
            raise ValueError("user message cannot be empty")
        with exclusive_lock(self.root / ".autoresearch" / "journal.lock"):
            self.verify_integrity()
            manifest = self._manifest()
            stamp = utc_stamp()
            existing = len(manifest["messages"])
            path = self.directory / f"{existing + 1:04d}-{stamp}.md"
            body = (
                "---\n"
                f"message_id: {existing + 1:04d}\n"
                f"recorded_at: {stamp}\n"
                f"source: {source}\n"
                "---\n\n"
                f"{text.rstrip()}\n"
            )
            atomic_write(path, body)
            manifest["messages"][path.name] = sha256_file(path)
            write_json(self.manifest_path, manifest)
            from .topic import TopicDocument

            TopicDocument(self.root).append_requirement(
                path,
                text,
                source=source,
                recorded_at=stamp,
            )
        return path

    def files(self) -> list[Path]:
        return sorted(self.directory.glob("*.md")) if self.directory.exists() else []

    def latest(self) -> Path:
        self.verify_integrity()
        files = self.files()
        if not files:
            raise JournalIntegrityError("no user messages have been recorded")
        return files[-1]

    def resolve(self, value: str) -> Path:
        self.verify_integrity()
        matches = [path for path in self.files() if path.name == value or path.name.startswith(value)]
        if len(matches) != 1:
            raise JournalIntegrityError(f"message reference must resolve exactly once: {value}")
        return matches[0]

    def body(self, path: Path) -> str:
        raw = path.read_text(encoding="utf-8")
        parts = raw.split("---\n", 2)
        return parts[2].strip() if len(parts) == 3 else raw.strip()

    def context(self) -> tuple[str, str]:
        self.verify_integrity()
        messages = []
        for path in self.files():
            messages.append(f"## {path.name}\n\n{path.read_text(encoding='utf-8').strip()}")
        content = "\n\n".join(messages)
        return content, sha256_bytes(content.encode("utf-8"))
