from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .io import atomic_write, sha256_bytes, utc_stamp
from .journal import UserMessageJournal
from .requirements import RequirementSummary
from .topic import TopicDocument


@dataclass
class AlignmentSnapshot:
    context: str
    digest: str
    message_files: tuple[str, ...]


@dataclass
class AlignmentGuard:
    root: Path

    def snapshot(self) -> AlignmentSnapshot:
        journal = UserMessageJournal(self.root)
        message_context, message_digest = journal.context()
        topic = TopicDocument(self.root)
        topic_path = topic.active_path()
        topic_content = topic_path.read_text(encoding="utf-8")
        if not message_context:
            raise RuntimeError("no user messages recorded; run 'autoresearch message add' first")
        audited = "\n".join(f"- `{path.name}`" for path in journal.files())
        summary = RequirementSummary(self.root).load_current()
        if summary:
            topic_direction = topic_content.split("## Session requirements", 1)[0].rstrip()
            latest = journal.latest()
            requirement_view = (
                f"{topic_direction}\n\n# Current verified requirement summary\n\n{summary}\n\n"
                f"# Latest exact user message\n\n{journal.body(latest)}"
            )
        else:
            requirement_view = topic_content.strip()
        context = (
            f"# Active topic: {topic.relative_path()}\n\n{requirement_view}\n\n"
            "# Verified immutable session records\n\n"
            f"The following source records were hash-verified before this round:\n{audited}"
        )
        digest_input = f"{topic.relative_path()}\n{topic_content}\n{message_digest}"
        digest = sha256_bytes(digest_input.encode("utf-8"))
        files = (topic.relative_path(), *(p.name for p in journal.files()))
        return AlignmentSnapshot(context, digest, files)

    def prompt_block(self, snapshot: AlignmentSnapshot) -> str:
        return (
            "# Non-negotiable user requirements\n\n"
            f"Requirements digest: `{snapshot.digest}`\n\n"
            f"{snapshot.context}\n\n"
            "Before doing work, restate the constraints that govern this round. "
            "After doing work, report any possible drift or conflict. If a conflict exists, "
            "stop and choose decision=report. Never silently reinterpret a frozen decision.\n"
        )

    def record(
        self,
        run_dir: Path,
        role: str,
        snapshot: AlignmentSnapshot,
        decision: str,
        possible_drift: str = "none reported",
    ) -> Path:
        path = run_dir / "alignment.md"
        files = "\n".join(f"- `{name}`" for name in snapshot.message_files)
        content = (
            "# Alignment report\n\n"
            f"- Checked at: `{utc_stamp()}`\n"
            f"- Role: `{role}`\n"
            f"- Requirements digest: `{snapshot.digest}`\n"
            f"- Decision: `{decision}`\n"
            f"- Possible drift: {possible_drift}\n\n"
            "## Requirement files read\n\n"
            f"{files}\n"
        )
        atomic_write(path, content)
        return path
