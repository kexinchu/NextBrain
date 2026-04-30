"""Vault health dashboard — what's worth pruning, what's stale, what's hot.

Pure local computation; no LLM, no network.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nextbrain import config
from nextbrain import prune as prune_mod


@dataclass
class VaultStats:
    total_papers: int = 0
    total_ideas: int = 0
    total_inbox: int = 0
    total_archived: int = 0
    by_paper_type: Dict[str, int] = field(default_factory=dict)
    by_read_status: Dict[str, int] = field(default_factory=dict)
    oldest_unread: List[Tuple[Path, int]] = field(default_factory=list)   # (path, age_days)
    top_unreferenced: List[Path] = field(default_factory=list)
    inbox_oldest: List[Tuple[Path, int]] = field(default_factory=list)
    syntheses_count: int = 0


def compute(vault_path: Optional[str] = None,
             refresh_lifecycle: bool = True,
             top_n: int = 5) -> VaultStats:
    from nextbrain.config import get_obsidian_vault_path
    vault = Path(vault_path or get_obsidian_vault_path()).expanduser()

    if refresh_lifecycle:
        prune_mod.refresh_lifecycle(vault_path=str(vault))

    stats = VaultStats()
    archive_dir = config.get_archive_dir_name()

    paper_paths = list(vault.glob("Papers-*/*.md"))
    inbox_paths = list(vault.glob("Inbox/*.md"))
    idea_paths = list(vault.glob("Idea/**/*.md"))
    archive_paths = [p for p in vault.rglob("*.md") if archive_dir in p.parts]
    synthesis_paths = list(vault.glob("Syntheses/**/*.md"))

    stats.total_papers = len(paper_paths)
    stats.total_ideas = len(idea_paths)
    stats.total_inbox = len(inbox_paths)
    stats.total_archived = len(archive_paths)
    stats.syntheses_count = len(synthesis_paths)

    # By paper_type
    type_counter: Counter = Counter()
    read_counter: Counter = Counter()
    unread_with_age: List[Tuple[Path, int]] = []
    unreferenced_unread: List[Tuple[Path, int]] = []

    for md in paper_paths:
        life = prune_mod._parse_lifecycle(md)
        ptype = life.get("paper_type") or "(none)"
        type_counter[ptype] += 1
        rs = life.get("read_status") or "skimmed"
        read_counter[rs] += 1

        age = prune_mod._age_days(life.get("last_opened", ""), md)
        refs = int(life.get("times_referenced") or 0)
        if rs in ("skimmed", "") and refs == 0:
            unreferenced_unread.append((md, age))
        if rs in ("skimmed", ""):
            unread_with_age.append((md, age))

    stats.by_paper_type = dict(type_counter.most_common())
    stats.by_read_status = dict(read_counter.most_common())

    unread_with_age.sort(key=lambda x: x[1], reverse=True)
    stats.oldest_unread = unread_with_age[:top_n]

    unreferenced_unread.sort(key=lambda x: x[1], reverse=True)
    stats.top_unreferenced = [p for p, _ in unreferenced_unread[:top_n]]

    inbox_aged: List[Tuple[Path, int]] = []
    for md in inbox_paths:
        life = prune_mod._parse_lifecycle(md)
        age = prune_mod._age_days(life.get("last_opened", ""), md)
        inbox_aged.append((md, age))
    inbox_aged.sort(key=lambda x: x[1], reverse=True)
    stats.inbox_oldest = inbox_aged[:top_n]

    return stats


def render(s: VaultStats, vault_path: Optional[str] = None) -> str:
    from nextbrain.config import get_obsidian_vault_path
    vault = Path(vault_path or get_obsidian_vault_path()).expanduser()

    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(vault))
        except ValueError:
            return str(p)

    lines = []
    lines.append("=" * 60)
    lines.append("  NextBrain — Vault Stats")
    lines.append("=" * 60)
    lines.append(f"Papers:     {s.total_papers}")
    lines.append(f"Ideas:      {s.total_ideas}")
    lines.append(f"Inbox:      {s.total_inbox}")
    lines.append(f"Syntheses:  {s.syntheses_count}")
    lines.append(f"Archived:   {s.total_archived}")
    lines.append("")

    if s.by_paper_type:
        lines.append("Papers by type:")
        for k, v in s.by_paper_type.items():
            lines.append(f"  {v:4d}  {k}")
        lines.append("")

    if s.by_read_status:
        lines.append("Papers by read status:")
        for k, v in s.by_read_status.items():
            lines.append(f"  {v:4d}  {k}")
        lines.append("")

    if s.oldest_unread:
        lines.append("Oldest unread papers (read_status=skimmed):")
        for p, age in s.oldest_unread:
            lines.append(f"  {age:4d}d  {rel(p)}")
        lines.append("")

    if s.top_unreferenced:
        lines.append("Top stale + unreferenced (zero incoming wikilinks, oldest first):")
        for p in s.top_unreferenced:
            lines.append(f"  - {rel(p)}")
        lines.append("")

    if s.inbox_oldest:
        lines.append("Oldest items in Inbox/ (review or prune):")
        for p, age in s.inbox_oldest:
            lines.append(f"  {age:4d}d  {rel(p)}")
        lines.append("")

    if s.total_papers > 0:
        unread_pct = 100.0 * s.by_read_status.get("skimmed", 0) / s.total_papers
        lines.append(f"Read-through rate: {100 - unread_pct:.1f}% have moved past 'skimmed'")

    return "\n".join(lines)
