from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ResearchConfig
from .io import sha256_file, utc_stamp, write_json
from .snapshot import full_snapshot


class EvidenceError(RuntimeError):
    pass


IGNORED_CHECK_PARTS = {".pytest_cache", ".ruff_cache", "__pycache__", ".coverage"}


def workspace_digest(workspace: Path) -> str:
    snapshot = {
        path: digest
        for path, digest in full_snapshot(workspace).items()
        if not any(part in IGNORED_CHECK_PARTS for part in Path(path).parts)
    }
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_evidence(path: Path, round_id: str, message_file: str) -> dict[str, Any]:
    if not path.exists():
        raise EvidenceError(f"evidence manifest is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1:
        raise EvidenceError("evidence schema_version must be 1")
    if value.get("round_id") != round_id:
        raise EvidenceError("evidence round_id mismatch")
    if value.get("message_file") != message_file:
        raise EvidenceError("evidence message_file mismatch")
    artifacts = value.get("artifacts", [])
    if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
        raise EvidenceError("evidence artifacts must be a string list")
    return value


@dataclass
class CheckRunner:
    root: Path

    def run(self, round_state: dict, command_name: str, workspace: Path) -> dict:
        command = ResearchConfig(self.root).command(command_name, round_state["skill"])
        result = subprocess.run(
            list(command.argv),
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=command.timeout,
            check=False,
        )
        check_dir = self.root / ".autoresearch" / "host-checks" / round_state["round_id"]
        check_dir.mkdir(parents=True, exist_ok=True)
        check_id = f"{utc_stamp()}-{command_name}"
        stdout_path = check_dir / f"{check_id}.stdout.txt"
        stderr_path = check_dir / f"{check_id}.stderr.txt"
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        record = {
            "schema_version": 1,
            "check_id": check_id,
            "round_id": round_state["round_id"],
            "skill": round_state["skill"],
            "command_name": command_name,
            "argv": list(command.argv),
            "exit_code": result.returncode,
            "workspace_digest": workspace_digest(workspace),
            "created_at": utc_stamp(),
            "stdout": stdout_path.relative_to(self.root).as_posix(),
            "stderr": stderr_path.relative_to(self.root).as_posix(),
        }
        record_path = check_dir / f"{check_id}.json"
        write_json(record_path, record)
        return record

    def successful(self, round_id: str, workspace: Path) -> list[dict]:
        directory = self.root / ".autoresearch" / "host-checks" / round_id
        records = []
        current_digest = workspace_digest(workspace)
        for path in sorted(directory.glob("*.json")) if directory.exists() else []:
            value = json.loads(path.read_text(encoding="utf-8"))
            if (
                value.get("round_id") == round_id
                and value.get("exit_code") == 0
                and value.get("workspace_digest") == current_digest
            ):
                records.append(value)
        return records


@dataclass
class ApprovalManager:
    root: Path

    @property
    def directory(self) -> Path:
        return self.root / ".autoresearch" / "approvals"

    def create(self, artifact: str, message_file: str) -> dict:
        path = (self.root / artifact).resolve()
        try:
            relative = path.relative_to(self.root.resolve()).as_posix()
        except ValueError as exc:
            raise EvidenceError("approval artifact must stay inside the workspace") from exc
        if not path.is_file():
            raise EvidenceError(f"approval artifact does not exist: {artifact}")
        receipt = {
            "schema_version": 1,
            "artifact": relative,
            "artifact_digest": sha256_file(path),
            "message_file": message_file,
            "approved_at": utc_stamp(),
        }
        target = self.directory / f"{receipt['artifact_digest']}.json"
        write_json(target, receipt)
        return receipt

    def verify(self, artifact: str, digest: str, *, draft_message: str, approval_message: str) -> None:
        path = self.directory / f"{digest}.json"
        if not path.exists():
            raise EvidenceError("matching human approval receipt is missing")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt.get("artifact") != artifact or receipt.get("artifact_digest") != digest:
            raise EvidenceError("approval receipt does not match the story draft")
        if receipt.get("message_file") != approval_message or approval_message == draft_message:
            raise EvidenceError("approval must be bound to a later user message")
