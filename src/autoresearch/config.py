from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .venues import VenueError, resolve_venue


CONFIG_TEMPLATE = """# Human-authorized deterministic commands used by conversation skills.
version: 1
commands: {}
research:
  domain: systems-and-ai-infrastructure
  primary_venues: [SOSP, FAST, OSDI, EuroSys, MLSys]
  secondary_venues: [ICLR, NeurIPS, AAAI, DAC]
  historical_venues: [USENIX ATC]
snapshot:
  # Large datasets are inputs, not governed research artifacts. Add project-local paths here.
  exclude:
    - datasets
    - venue-corpus
"""


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AuthorizedCommand:
    name: str
    skill: str
    argv: tuple[str, ...]
    timeout: int = 3600


@dataclass
class ResearchConfig:
    root: Path

    @property
    def path(self) -> Path:
        return self.root / "autoresearch.yaml"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            raise ConfigError("autoresearch.yaml is missing; run 'autoresearch init'")
        value = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        if value.get("version") != 1:
            raise ConfigError("autoresearch.yaml must use version: 1")
        commands = value.get("commands", {})
        if not isinstance(commands, dict):
            raise ConfigError("commands must be a mapping")
        research = value.get("research", {})
        if not isinstance(research, dict) or not isinstance(research.get("domain", ""), str):
            raise ConfigError("research must be a mapping with a string domain")
        for field in ("primary_venues", "secondary_venues", "historical_venues"):
            venues = research.get(field, [])
            if not isinstance(venues, list) or not all(isinstance(item, str) for item in venues):
                raise ConfigError(f"research.{field} must be a list of venue names")
            try:
                for venue in venues:
                    resolve_venue(venue, allow_inactive=field == "historical_venues")
            except VenueError as exc:
                raise ConfigError(f"invalid research.{field}: {exc}") from exc
        return value

    def command(self, name: str, skill: str) -> AuthorizedCommand:
        value = self.load().get("commands", {}).get(name)
        if not isinstance(value, dict):
            raise ConfigError(f"authorized command does not exist: {name}")
        if value.get("skill") != skill:
            raise ConfigError(f"command '{name}' is not authorized for {skill}")
        argv = value.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
            raise ConfigError(f"command '{name}' requires a non-empty argv string list")
        timeout = int(value.get("timeout", 3600))
        if timeout < 1 or timeout > 86400:
            raise ConfigError("command timeout must be between 1 and 86400 seconds")
        return AuthorizedCommand(name, skill, tuple(argv), timeout)

    def excluded_snapshot_paths(self) -> tuple[str, ...]:
        values = self.load().get("snapshot", {}).get("exclude", [])
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ConfigError("snapshot.exclude must be a list of paths")
        cleaned = []
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise ConfigError(f"unsafe snapshot exclusion: {value}")
            cleaned.append(path.as_posix().strip("/"))
        return tuple(item for item in cleaned if item)

    def venue_context(self) -> str:
        research = self.load().get("research", {})
        lines = [f"- Research domain: `{research.get('domain', 'unspecified')}`"]
        for field, label in (
            ("primary_venues", "Primary active venues"),
            ("secondary_venues", "Secondary active venues"),
            ("historical_venues", "Historical-only venues"),
        ):
            profiles = [
                resolve_venue(name, allow_inactive=field == "historical_venues")
                for name in research.get(field, [])
            ]
            values = ", ".join(
                f"{profile.canonical} ({profile.family}, {profile.status})"
                for profile in profiles
            )
            lines.append(f"- {label}: {values or 'none'}")
        lines.append(
            "- Venue rules are temporal: load the current official CFP, author guide, and "
            "reviewer guidance during each venue-dependent round."
        )
        return "\n".join(lines)
