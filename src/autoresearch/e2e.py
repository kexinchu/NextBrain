from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .io import sha256_file, utc_stamp, write_json
from .skills import BUILTIN_SKILLS


CLIENTS = ("gpt", "claude", "cursor")


@dataclass
class E2ERegistry:
    root: Path

    @property
    def directory(self) -> Path:
        return self.root / ".autoresearch" / "e2e"

    def record(
        self,
        client: str,
        skill: str,
        model: str,
        status: str,
        evidence: Path,
    ) -> Path:
        if client not in CLIENTS:
            raise ValueError(f"unknown client: {client}")
        if skill not in BUILTIN_SKILLS:
            raise ValueError(f"unknown skill: {skill}")
        if status not in {"pass", "fail"}:
            raise ValueError("status must be pass or fail")
        if not evidence.is_file():
            raise FileNotFoundError(evidence)
        value = {
            "schema_version": 1,
            "client": client,
            "skill": skill,
            "model": model,
            "status": status,
            "evidence_path": evidence.resolve().as_posix(),
            "evidence_digest": sha256_file(evidence),
            "recorded_at": utc_stamp(),
        }
        target = self.directory / client / f"{skill}.json"
        write_json(target, value)
        return target

    def matrix(self) -> list[dict]:
        results = []
        for client in CLIENTS:
            for skill in BUILTIN_SKILLS:
                path = self.directory / client / f"{skill}.json"
                value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                evidence = Path(value.get("evidence_path", ""))
                evidence_ok = (
                    evidence.is_file()
                    and value.get("evidence_digest") == sha256_file(evidence)
                )
                results.append(
                    {
                        "client": client,
                        "skill": skill,
                        "status": value.get("status", "missing"),
                        "model": value.get("model"),
                        "evidence_ok": evidence_ok,
                    }
                )
        return results
