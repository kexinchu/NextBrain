from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    shutil.copy2(source, temporary)
    temporary.replace(destination)


@contextmanager
def exclusive_lock(path: Path, timeout: float = 10.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    descriptor = None
    while descriptor is None:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > max(timeout * 3, 30):
                    path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for lock: {path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(descriptor)
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def tree_hash(paths: Iterable[Path], root: Path) -> tuple[str, dict[str, str]]:
    files: dict[str, str] = {}
    for candidate in paths:
        if candidate.is_dir():
            selected = sorted(p for p in candidate.rglob("*") if p.is_file())
        elif candidate.is_file():
            selected = [candidate]
        else:
            selected = []
        for path in selected:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
            files[relative] = sha256_file(path)
    joined = "\n".join(f"{name}\0{digest}" for name, digest in sorted(files.items()))
    return sha256_bytes(joined.encode()), files
