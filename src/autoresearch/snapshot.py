from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .io import sha256_file, write_json


DEFAULT_GOVERNED_PATHS = (
    "topic.md",
    "requirements",
    "story.md",
    "paper",
    "code",
    "experiments/scripts",
    "reviews",
    "autoresearch.yaml",
    ".agents/skills",
    ".claude/skills",
    ".cursor/skills",
)


def _within(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


@dataclass
class IncrementalSnapshotter:
    root: Path

    @property
    def cache_path(self) -> Path:
        return self.root / ".autoresearch" / "snapshot-cache.json"

    def _cache(self) -> dict:
        if not self.cache_path.exists():
            return {"version": 1, "files": {}}
        try:
            value = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "files": {}}
        return value if value.get("version") == 1 else {"version": 1, "files": {}}

    def snapshot(
        self,
        paths: Iterable[str] = DEFAULT_GOVERNED_PATHS,
        *,
        exclude: Iterable[str] = (),
        force_hash: Iterable[str] = ("requirements", "paper/STORY.md", "code/core"),
        verify_content: bool = False,
    ) -> dict[str, str]:
        selected: list[Path] = []
        excluded = tuple(exclude)
        for relative in paths:
            candidate = self.root / relative
            if candidate.is_dir():
                for directory, directory_names, file_names in os.walk(candidate, followlinks=False):
                    current = Path(directory)
                    kept_directories = []
                    for name in directory_names:
                        child = current / name
                        child_relative = child.relative_to(self.root).as_posix()
                        if _within(child_relative, excluded):
                            continue
                        if child.is_symlink():
                            selected.append(child)
                        else:
                            kept_directories.append(name)
                    directory_names[:] = kept_directories
                    selected.extend(current / name for name in file_names)
            elif candidate.is_file() or candidate.is_symlink():
                selected.append(candidate)
        forced = tuple(force_hash)
        cache = self._cache()
        prior = cache.get("files", {})
        updated: dict[str, dict] = {}
        result: dict[str, str] = {}
        for path in sorted(set(selected)):
            relative = path.relative_to(self.root).as_posix()
            if excluded and _within(relative, excluded):
                continue
            stat = path.lstat()
            if path.is_symlink():
                digest = f"symlink:{os.readlink(path)}"
            else:
                cached = prior.get(relative, {})
                stable = cached.get("size") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns
                may_reuse = stable and not verify_content and not _within(relative, forced)
                digest = cached.get("digest") if may_reuse else None
                if not digest:
                    digest = sha256_file(path)
            result[relative] = digest
            updated[relative] = {
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "digest": digest,
            }
        write_json(self.cache_path, {"version": 1, "files": updated})
        return result


def full_snapshot(root: Path) -> dict[str, str]:
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        if not path.is_file() and not path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = f"symlink:{os.readlink(path)}"
        else:
            result[relative] = sha256_file(path)
    return result
