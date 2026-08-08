from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Decision = Literal["continue", "satisfied", "blocked", "report"]


@dataclass(frozen=True)
class AgentRequest:
    role: str
    skill: str
    round_id: str
    prompt: str
    requirements_digest: str
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()


@dataclass
class AgentReply:
    content: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoundOutcome:
    round_id: str
    skill: str
    role: str
    decision: Decision
    output_path: str
    alignment_path: str
    requirements_digest: str
    summary: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
