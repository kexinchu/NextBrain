"""Auto-infer the user's currently active research topics from vault activity.

Signal sources, all weighted by recency (exponential decay, half-life configurable):
  - `paper_type` frontmatter on Papers-* notes
  - `tags` frontmatter (any note)
  - YAML `topic` field if present (e.g. on Idea/ notes)

Output is a normalized {label: weight} dict, top-K. Cached on disk and refreshed
when stale or on `--force`.
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nextbrain import config


@dataclass
class ActiveTopics:
    computed_at: float                # epoch seconds
    weights: Dict[str, float]         # label → weight (sum-to-1)
    raw_counts: Dict[str, float]      # label → unnormalized weight (for debugging)

    def labels(self) -> List[str]:
        return list(self.weights.keys())

    def weight(self, label: str) -> float:
        return self.weights.get(label, 0.0)

    def to_dict(self) -> dict:
        return {
            "computed_at": self.computed_at,
            "weights": self.weights,
            "raw_counts": self.raw_counts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ActiveTopics":
        return cls(
            computed_at=float(d.get("computed_at", 0)),
            weights=dict(d.get("weights", {})),
            raw_counts=dict(d.get("raw_counts", {})),
        )


# ── Frontmatter scraping (cheap; avoids YAML lib for performance) ───────────

_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_PAPER_TYPE_RE = re.compile(r"^paper_type:\s*(.+?)\s*$", re.MULTILINE)
_TOPIC_RE = re.compile(r"^topic:\s*(.+?)\s*$", re.MULTILINE)
_TYPE_RE = re.compile(r"^type:\s*(.+?)\s*$", re.MULTILINE)
_DATE_RE = re.compile(r"^updated_at:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)

# Tags can be inline ("tags: [a, b]") or YAML list under tags:
_TAGS_INLINE_RE = re.compile(r"^tags:\s*\[(.*?)\]\s*$", re.MULTILINE)
_TAGS_BLOCK_RE = re.compile(r"^tags:\s*\n((?:\s*-\s*.+\n?)+)", re.MULTILINE)

# upstream_topic_scores block: "upstream_topic_scores:\n  rag-systems: 0.8\n  ..."
_UPSTREAM_BLOCK_RE = re.compile(
    r"^upstream_topic_scores:\s*\n((?:\s+\S+:\s*[\d.]+\n?)+)", re.MULTILINE
)
_UPSTREAM_LINE_RE = re.compile(r"^\s+(\S+):\s*([\d.]+)\s*$", re.MULTILINE)


def _read_frontmatter(path: Path) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
    except OSError:
        return None
    m = _FM_RE.match(head)
    return m.group(1) if m else None


def _parse_tags(fm: str) -> List[str]:
    out: List[str] = []
    m = _TAGS_INLINE_RE.search(fm)
    if m:
        out.extend(t.strip().strip('"\'') for t in m.group(1).split(","))
    m = _TAGS_BLOCK_RE.search(fm)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip()
            if line.startswith("-"):
                out.append(line[1:].strip().strip('"\''))
    return [t for t in out if t]


def _parse_upstream_scores(fm: str) -> Dict[str, float]:
    """Parse upstream_topic_scores YAML block from frontmatter."""
    block = _UPSTREAM_BLOCK_RE.search(fm)
    if not block:
        return {}
    out: Dict[str, float] = {}
    for m in _UPSTREAM_LINE_RE.finditer(block.group(1)):
        try:
            out[m.group(1).strip()] = float(m.group(2))
        except ValueError:
            continue
    return out


def _signals_from_note(path: Path) -> Tuple[List[Tuple[str, float]], Optional[float]]:
    """Return (weighted_labels, recency_timestamp).

    weighted_labels is a list of (label, intra-note weight) pairs. Strong
    signals (paper_type, high upstream scores) get higher weight; tags get 1.0.
    Recency falls back to file mtime.
    """
    fm = _read_frontmatter(path)
    labels: List[Tuple[str, float]] = []
    if fm:
        # paper_type: strong signal (weight 2.0)
        m = _PAPER_TYPE_RE.search(fm)
        if m:
            v = m.group(1).strip().strip('"\'')
            if v and v.lower() != "other":
                labels.append((v, 2.0))
        m = _TOPIC_RE.search(fm)
        if m:
            v = m.group(1).strip().strip('"\'')
            if v:
                labels.append((v, 1.0))
        for tag in _parse_tags(fm):
            labels.append((tag, 1.0))
        # upstream_topic_scores — weight by the upstream score itself
        for slug, score in _parse_upstream_scores(fm).items():
            labels.append((slug, max(0.0, score)))

        # Recency — prefer updated_at, fall back to mtime
        m = _DATE_RE.search(fm)
        if m:
            try:
                dt = datetime.strptime(m.group(1), "%Y-%m-%d")
                return labels, dt.timestamp()
            except ValueError:
                pass

    try:
        return labels, path.stat().st_mtime
    except OSError:
        return labels, None


# ── Computation ─────────────────────────────────────────────────────────────

def _decay(age_days: float, half_life: float) -> float:
    if half_life <= 0:
        return 1.0
    return math.pow(0.5, age_days / half_life)


def _scan_vault(vault: Path) -> Dict[str, float]:
    """Return label → weighted count across the vault."""
    half_life = config.get_topics_half_life_days()
    now = time.time()

    # Scan active folders. Ignore Archive/ and assets.
    targets = [
        vault.glob("Papers-*/*.md"),
        vault.glob("Idea/**/*.md"),
        vault.glob("Daily/**/*.md"),
        vault.glob("Concepts/**/*.md"),
        vault.glob("Projects/**/*.md"),
        vault.glob("Syntheses/**/*.md"),
    ]

    counts: Dict[str, float] = defaultdict(float)
    for it in targets:
        for path in it:
            # Skip Archive
            if "Archive" in path.parts:
                continue
            weighted_labels, ts = _signals_from_note(path)
            if not weighted_labels or ts is None:
                continue
            age_days = max(0.0, (now - ts) / 86400.0)
            recency = _decay(age_days, half_life)
            for label, intra_w in weighted_labels:
                counts[label] += recency * intra_w
    return dict(counts)


def _normalize_top_k(counts: Dict[str, float], k: int) -> Dict[str, float]:
    if not counts:
        return {}
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:k]
    total = sum(w for _, w in items) or 1.0
    return {label: w / total for label, w in items}


def compute_active_topics(vault_path: Optional[str] = None,
                           top_k: Optional[int] = None) -> ActiveTopics:
    from nextbrain.config import get_obsidian_vault_path
    vault = Path(vault_path or get_obsidian_vault_path()).expanduser()
    k = top_k if top_k is not None else config.get_topics_top_k()
    raw = _scan_vault(vault)
    weights = _normalize_top_k(raw, k)
    return ActiveTopics(
        computed_at=time.time(),
        weights=weights,
        raw_counts={lab: raw[lab] for lab in weights} if weights else {},
    )


# ── Cache ───────────────────────────────────────────────────────────────────

def _cache_path() -> Path:
    return Path(config.get_topics_cache_path()).expanduser()


def load_cached() -> Optional[ActiveTopics]:
    p = _cache_path()
    if not p.exists():
        return None
    try:
        return ActiveTopics.from_dict(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return None


def save_cached(at: ActiveTopics) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(at.to_dict(), indent=2, ensure_ascii=False),
                 encoding="utf-8")


def get_active_topics(vault_path: Optional[str] = None,
                       force_recompute: bool = False) -> ActiveTopics:
    """Return active topics, using cache if fresh."""
    if not force_recompute:
        cached = load_cached()
        if cached is not None:
            ttl_seconds = config.get_topics_recompute_hours() * 3600
            if (time.time() - cached.computed_at) < ttl_seconds:
                return cached
    at = compute_active_topics(vault_path=vault_path)
    save_cached(at)
    return at


# ── Matching helpers (used by ingest filter) ────────────────────────────────

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def topic_overlap_score(active: ActiveTopics, upstream_tags: Dict[str, float]) -> float:
    """Score how strongly an upstream paper matches the user's active topics.

    Active labels come from the user's vocabulary (paper_type / tags). Upstream
    tags use the digest's own slugs (rag-systems, agent-systems, …). We match
    by normalized substring of slugs in either direction.
    """
    if not active.weights or not upstream_tags:
        return 0.0
    score = 0.0
    for active_label, active_w in active.weights.items():
        a = _slug(active_label)
        if not a:
            continue
        for tag, tag_score in upstream_tags.items():
            t = _slug(tag)
            if not t:
                continue
            if a == t or a in t or t in a:
                score += active_w * tag_score
    return score
