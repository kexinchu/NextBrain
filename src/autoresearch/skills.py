from __future__ import annotations

import importlib.resources
import re
from dataclasses import dataclass

import yaml


BUILTIN_SKILLS = (
    "idea-loop",
    "story-freeze",
    "implementation-loop",
    "experiment-loop",
    "section-writing",
    "venue-review",
)


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    body: str


def load_skill(name: str) -> SkillDefinition:
    if name not in BUILTIN_SKILLS:
        raise KeyError(f"unknown skill: {name}")
    resource = importlib.resources.files("autoresearch") / "builtin_skills" / name / "SKILL.md"
    text = resource.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"invalid SKILL.md for {name}")
    metadata = yaml.safe_load(match.group(1)) or {}
    return SkillDefinition(
        name=str(metadata.get("name", name)),
        description=str(metadata.get("description", "")),
        body=match.group(2).strip(),
    )


def list_skills() -> list[SkillDefinition]:
    return [load_skill(name) for name in BUILTIN_SKILLS]
