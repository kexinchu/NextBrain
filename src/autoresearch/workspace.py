from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG_TEMPLATE
from .io import atomic_write, write_json
from .topic import TopicDocument


@dataclass
class ResearchWorkspace:
    root: Path

    def init(self) -> list[Path]:
        directories = (
            "requirements/messages",
            "ideas",
            "paper/manuscript",
            "code/core",
            "code/tests",
            "experiments/scripts",
            "experiments/results",
            "reviews",
            "runs",
            ".autoresearch/freezes",
            ".autoresearch/approvals",
            ".autoresearch/transactions",
            ".autoresearch/host-checks",
        )
        for relative in directories:
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        manifest = self.root / "requirements" / "messages" / ".manifest.json"
        created: list[Path] = []
        if not manifest.exists():
            write_json(manifest, {"version": 1, "messages": {}})
            created.append(manifest)
        topic = TopicDocument(self.root)
        topic_path = self.root / "topic.md"
        topic_was_missing = not topic_path.exists()
        topic_state_was_missing = not topic.state_path.exists()
        topic.set_active("topic.md", create=True)
        if topic_was_missing:
            created.append(topic_path)
        if topic_state_was_missing:
            created.append(topic.state_path)
        files = {
            "autoresearch.yaml": CONFIG_TEMPLATE,
            "ideas/.gitkeep": "",
            "paper/manuscript/.gitkeep": "",
            "code/core/.gitkeep": "",
            "code/tests/.gitkeep": "",
            "experiments/scripts/.gitkeep": "",
            "experiments/results/.gitkeep": "",
            "reviews/.gitkeep": "",
        }
        for relative, content in files.items():
            path = self.root / relative
            if not path.exists():
                atomic_write(path, content)
                created.append(path)
        return created
