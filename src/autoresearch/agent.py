from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Protocol

from .models import AgentReply, AgentRequest


class Agent(Protocol):
    """Small provider-neutral boundary used by every skill."""

    def complete(self, request: AgentRequest) -> AgentReply: ...


def _decode_reply(raw: str) -> AgentReply:
    text = raw.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return AgentReply(content=text)
    if isinstance(value, dict):
        content = value.get("content") or value.get("report") or text
        return AgentReply(content=str(content), data=value)
    return AgentReply(content=text)


@dataclass
class CommandAgent:
    """Run any local agent command; prompt goes to stdin and stdout is the reply."""

    command: str | list[str]
    timeout_seconds: int = 1800

    def complete(self, request: AgentRequest) -> AgentReply:
        argv = shlex.split(self.command) if isinstance(self.command, str) else self.command
        if not argv:
            raise ValueError("agent command cannot be empty")
        env = os.environ.copy()
        env.update(
            {
                "AUTORESEARCH_ROLE": request.role,
                "AUTORESEARCH_SKILL": request.skill,
                "AUTORESEARCH_ROUND": request.round_id,
                "AUTORESEARCH_REQUIREMENTS_DIGEST": request.requirements_digest,
            }
        )
        result = subprocess.run(
            argv,
            input=request.prompt,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
            env=env,
        )
        if result.returncode:
            raise RuntimeError(
                f"agent command failed with exit {result.returncode}: {result.stderr.strip()}"
            )
        return _decode_reply(result.stdout)


@dataclass
class OpenAIAgent:
    """Optional OpenAI Responses API adapter (install with ``.[openai]``)."""

    model: str
    reasoning_effort: str = "medium"

    def complete(self, request: AgentRequest) -> AgentReply:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("install the OpenAI adapter with: pip install '.[openai]'") from exc
        response = OpenAI().responses.create(
            model=self.model,
            reasoning={"effort": self.reasoning_effort},
            input=request.prompt,
        )
        return _decode_reply(response.output_text)
