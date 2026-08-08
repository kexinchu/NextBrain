from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .io import atomic_copy
from .snapshot import full_snapshot


class TransactionError(RuntimeError):
    pass


IGNORED_RUNTIME_PARTS = {".pytest_cache", ".ruff_cache", "__pycache__", ".coverage"}


def _allowed(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


def _reject_symlinks(path: Path) -> None:
    if path.is_symlink():
        raise TransactionError(f"symlink is not allowed in a transaction: {path}")
    if path.is_dir():
        for candidate in path.rglob("*"):
            if candidate.is_symlink():
                raise TransactionError(f"symlink is not allowed in a transaction: {candidate}")


@dataclass
class RoundTransaction:
    root: Path
    round_id: str
    allowed_paths: tuple[str, ...]
    fresh_paths: tuple[str, ...] = ()

    @property
    def directory(self) -> Path:
        return self.root / ".autoresearch" / "transactions" / self.round_id

    @property
    def workspace(self) -> Path:
        return self.directory / "workspace"

    def create(self) -> dict[str, str]:
        if self.directory.exists():
            raise TransactionError(f"transaction already exists: {self.round_id}")
        self.workspace.mkdir(parents=True)
        for relative in self.allowed_paths:
            destination = self.workspace / relative
            if _allowed(relative, self.fresh_paths):
                destination.mkdir(parents=True, exist_ok=True)
                continue
            source = self.root / relative
            if not source.exists() and not source.is_symlink():
                destination.parent.mkdir(parents=True, exist_ok=True)
                continue
            _reject_symlinks(source)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        return full_snapshot(self.workspace)

    @property
    def backup(self) -> Path:
        return self.directory / "main-backup"

    @property
    def quarantine(self) -> Path:
        return self.directory / "quarantine"

    def backup_main(self, paths: Iterable[str], *, exclude: Iterable[str] = ()) -> None:
        excluded = tuple(exclude)
        for relative in paths:
            if _allowed(relative, excluded):
                continue
            source = self.root / relative
            destination = self.backup / relative
            if source.is_file() and not source.is_symlink():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            elif source.is_dir() and not source.is_symlink():
                for candidate in source.rglob("*"):
                    if not candidate.is_file() or candidate.is_symlink():
                        continue
                    child = candidate.relative_to(self.root).as_posix()
                    if _allowed(child, excluded):
                        continue
                    target = self.backup / child
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidate, target)

    def restore_direct_changes(self, changed: Iterable[str]) -> list[str]:
        restored = []
        for relative in changed:
            current = self.root / relative
            backup = self.backup / relative
            if current.is_file() and not current.is_symlink():
                quarantine = self.quarantine / relative
                quarantine.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(current, quarantine)
            if backup.is_file() and not backup.is_symlink():
                atomic_copy(backup, current)
            elif current.exists() or current.is_symlink():
                if current.is_dir() and not current.is_symlink():
                    raise TransactionError(f"refusing to remove a direct-created directory: {relative}")
                current.unlink()
            restored.append(relative)
        return restored

    def changes(self, before: dict[str, str]) -> tuple[list[str], list[str]]:
        before = {
            path: digest
            for path, digest in before.items()
            if not any(part in IGNORED_RUNTIME_PARTS for part in Path(path).parts)
        }
        current = {
            path: digest
            for path, digest in full_snapshot(self.workspace).items()
            if not any(part in IGNORED_RUNTIME_PARTS for part in Path(path).parts)
        }
        changed = sorted(
            path for path in set(before) | set(current) if before.get(path) != current.get(path)
        )
        violations = [path for path in changed if not _allowed(path, self.allowed_paths)]
        deleted = [path for path in changed if path in before and path not in current]
        if deleted:
            violations.extend(deleted)
        for relative in changed:
            candidate = self.workspace / relative
            if candidate.is_symlink():
                violations.append(relative)
        return changed, sorted(set(violations))

    def promote(self, changed: Iterable[str]) -> list[str]:
        candidates = list(changed)
        for relative in candidates:
            if not _allowed(relative, self.allowed_paths):
                raise TransactionError(f"transaction path is forbidden: {relative}")
            source = self.workspace / relative
            if not source.is_file() or source.is_symlink():
                raise TransactionError(f"transaction artifact is not a regular file: {relative}")

        promoted: list[str] = []
        try:
            for relative in candidates:
                atomic_copy(self.workspace / relative, self.root / relative)
                promoted.append(relative)
        except Exception as exc:
            try:
                self.restore_promoted(promoted)
            except Exception as rollback_exc:
                raise TransactionError(
                    f"promotion failed ({exc}); rollback also failed ({rollback_exc})"
                ) from exc
            raise TransactionError(f"promotion failed and was rolled back: {exc}") from exc
        return promoted

    def restore_promoted(self, promoted: Iterable[str]) -> None:
        for relative in promoted:
            current = self.root / relative
            backup = self.backup / relative
            if backup.is_file() and not backup.is_symlink():
                atomic_copy(backup, current)
            elif current.is_file() and not current.is_symlink():
                current.unlink()
            elif current.exists() or current.is_symlink():
                raise TransactionError(
                    f"refusing to remove non-file while rolling back promotion: {relative}"
                )
