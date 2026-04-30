"""Prune the vault: forget unread/unreferenced/off-topic papers.

Default is dry-run; pass apply=True to actually move files. Pruned notes go to
<vault>/<archive_dir>/<YYYY-MM-DD>/ rather than being deleted, and their RAG
index entries are removed.

Reference count includes wikilinks from ANY folder in the vault (Idea/,
Syntheses/, Daily/, Concepts/, etc.) — see memory/feedback_pruning.md and
project_design_decisions.md.
"""
from __future__ import annotations

import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from nextbrain import config


_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_LAST_OPENED_RE = re.compile(r"^last_opened:\s*\"?([^\"\n]*)\"?\s*$", re.MULTILINE)
_PAPER_TYPE_RE = re.compile(r"^paper_type:\s*(.+?)\s*$", re.MULTILINE)
_READ_STATUS_RE = re.compile(r"^read_status:\s*(.+?)\s*$", re.MULTILINE)
_TIMES_REF_RE = re.compile(r"^times_referenced:\s*(\d+)", re.MULTILINE)


@dataclass
class PruneCandidate:
    path: Path
    reason: str                      # "unread+unreferenced", "topic-prune", "inbox-stale"
    paper_type: str = ""
    last_opened: str = ""            # ISO date string
    age_days: int = 0
    times_referenced: int = 0
    read_status: str = ""


# ── Wikilink scanning ────────────────────────────────────────────────────────

def _vault_root(vault_path: Optional[str]) -> Path:
    from nextbrain.config import get_obsidian_vault_path
    return Path(vault_path or get_obsidian_vault_path()).expanduser()


def _scan_wikilink_counts(vault: Path, archive_dir: str) -> Counter:
    """Walk the entire vault (excluding Archive/) and count wikilink targets.

    Returns Counter keyed by note stem (without .md). Wikilinks like
    [[FooBar|alias]] or [[FooBar#section]] all count toward FooBar.
    """
    counts: Counter = Counter()
    for md in vault.rglob("*.md"):
        # Skip the archive
        if archive_dir in md.parts:
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _WIKILINK_RE.finditer(text):
            target = m.group(1).strip()
            if not target:
                continue
            # Strip path-prefix if user wrote [[Folder/Note]]
            target = target.rsplit("/", 1)[-1]
            counts[target] += 1
    return counts


# ── Lifecycle update ────────────────────────────────────────────────────────

def _read_head(path: Path, n: int = 4096) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(n)
    except OSError:
        return ""


def _parse_lifecycle(path: Path) -> Dict[str, str]:
    head = _read_head(path)
    fm_m = _FM_RE.match(head)
    fm = fm_m.group(1) if fm_m else ""
    out = {
        "paper_type": "",
        "last_opened": "",
        "read_status": "",
        "times_referenced": "0",
    }
    for key, regex in (
        ("paper_type", _PAPER_TYPE_RE),
        ("last_opened", _LAST_OPENED_RE),
        ("read_status", _READ_STATUS_RE),
        ("times_referenced", _TIMES_REF_RE),
    ):
        m = regex.search(fm)
        if m:
            out[key] = m.group(1).strip().strip('"\'')
    return out


def _update_frontmatter_field(path: Path, key: str, value: str) -> bool:
    """Set or replace a frontmatter field in-place. Returns True on change."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    fm_m = _FM_RE.match(text)
    if not fm_m:
        return False
    fm = fm_m.group(1)
    line_re = re.compile(rf"^{re.escape(key)}:\s*.*$", re.MULTILINE)
    new_line = f"{key}: {value}"
    if line_re.search(fm):
        new_fm = line_re.sub(new_line, fm)
    else:
        new_fm = fm + "\n" + new_line
    new_text = text.replace(fm_m.group(0), f"---\n{new_fm}\n---", 1)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def refresh_lifecycle(vault_path: Optional[str] = None) -> Dict[str, int]:
    """Recompute times_referenced and last_opened (from mtime if blank) for all
    paper notes. Returns counters: {paper_notes: N, updated_refs: M, updated_opened: K}."""
    vault = _vault_root(vault_path)
    archive_dir = config.get_archive_dir_name()
    wl_counts = _scan_wikilink_counts(vault, archive_dir)

    paper_iter = list(vault.glob("Papers-*/*.md")) + list(vault.glob("Inbox/*.md"))
    n_papers = 0
    n_refs = 0
    n_opened = 0
    for md in paper_iter:
        n_papers += 1
        stem = md.stem
        new_count = wl_counts.get(stem, 0)
        cur = _parse_lifecycle(md)
        if str(new_count) != cur["times_referenced"]:
            if _update_frontmatter_field(md, "times_referenced", str(new_count)):
                n_refs += 1
        if not cur["last_opened"]:
            mtime_iso = datetime.fromtimestamp(md.stat().st_mtime).strftime("%Y-%m-%d")
            if _update_frontmatter_field(md, "last_opened", f'"{mtime_iso}"'):
                n_opened += 1
    return {"paper_notes": n_papers, "updated_refs": n_refs,
            "updated_opened": n_opened}


# ── Selection ───────────────────────────────────────────────────────────────

def _age_days(date_str: str, fallback_path: Path) -> int:
    """Days since `date_str` (YYYY-MM-DD). Falls back to file mtime."""
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return max(0, (datetime.now() - dt).days)
        except ValueError:
            pass
    try:
        ts = fallback_path.stat().st_mtime
        return max(0, (datetime.now() - datetime.fromtimestamp(ts)).days)
    except OSError:
        return 0


def select_candidates(
    vault_path: Optional[str] = None,
    unread_since_days: Optional[int] = None,
    topic: Optional[str] = None,
    inbox_older_than_days: Optional[int] = None,
    unreferenced_only: bool = False,
) -> List[PruneCandidate]:
    """Find prune candidates by the given policy. Caller must call
    refresh_lifecycle() first to ensure times_referenced is current."""
    vault = _vault_root(vault_path)

    # Default thresholds from config when caller didn't pass overrides
    unread_thresh = unread_since_days if unread_since_days is not None \
        else config.get_prune_unread_threshold_days()
    inbox_thresh = inbox_older_than_days if inbox_older_than_days is not None \
        else config.get_prune_inbox_threshold_days()

    out: List[PruneCandidate] = []

    if topic:
        # Topic-based prune: every paper note in Papers-<topic>/
        for md in vault.glob(f"Papers-{topic}/*.md"):
            life = _parse_lifecycle(md)
            out.append(PruneCandidate(
                path=md, reason="topic-prune", paper_type=topic,
                last_opened=life["last_opened"],
                age_days=_age_days(life["last_opened"], md),
                times_referenced=int(life.get("times_referenced") or 0),
                read_status=life.get("read_status", ""),
            ))

    if inbox_older_than_days is not None or unread_since_days is None:
        # Inbox staleness — only when the caller explicitly asked OR no other
        # selector was given (run a default sweep).
        for md in vault.glob("Inbox/*.md"):
            life = _parse_lifecycle(md)
            age = _age_days(life["last_opened"], md)
            if age >= inbox_thresh:
                out.append(PruneCandidate(
                    path=md, reason="inbox-stale", paper_type=life.get("paper_type", ""),
                    last_opened=life["last_opened"], age_days=age,
                    times_referenced=int(life.get("times_referenced") or 0),
                    read_status=life.get("read_status", ""),
                ))

    if topic is None and inbox_older_than_days is None:
        # Unread + (optionally) unreferenced
        for md in vault.glob("Papers-*/*.md"):
            life = _parse_lifecycle(md)
            age = _age_days(life["last_opened"], md)
            refs = int(life.get("times_referenced") or 0)
            if age < unread_thresh:
                continue
            if life.get("read_status") in ("read", "deep"):
                continue
            if unreferenced_only and refs > 0:
                continue
            out.append(PruneCandidate(
                path=md, reason="unread+unreferenced" if unreferenced_only else "unread",
                paper_type=life.get("paper_type", ""),
                last_opened=life["last_opened"], age_days=age,
                times_referenced=refs, read_status=life.get("read_status", ""),
            ))

    return out


# ── Apply ───────────────────────────────────────────────────────────────────

def _drop_from_rag(path: Path) -> None:
    """Best-effort removal of a note's chunks from the RAG index."""
    try:
        from nextbrain.tools.rag import _ensure_collection, _get_rag_dir
    except ImportError:
        return
    try:
        coll = _ensure_collection(_get_rag_dir())
        coll.delete(where={"source": str(path)})
    except Exception:
        pass


def archive_paths(candidates: List[PruneCandidate],
                  vault_path: Optional[str] = None) -> List[Tuple[Path, Path]]:
    """Move each candidate to <vault>/<archive_dir>/<YYYY-MM-DD>/<orig-relpath>.

    Returns list of (src, dst) actually moved.
    """
    vault = _vault_root(vault_path)
    archive_root = vault / config.get_archive_dir_name() / datetime.now().strftime("%Y-%m-%d")
    archive_root.mkdir(parents=True, exist_ok=True)

    moved: List[Tuple[Path, Path]] = []
    for cand in candidates:
        if not cand.path.exists():
            continue
        rel = cand.path.relative_to(vault)
        dst = archive_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        # If something with that name already exists in archive, suffix it
        if dst.exists():
            stem, ext = dst.stem, dst.suffix
            i = 1
            while True:
                alt = dst.with_name(f"{stem}_{i}{ext}")
                if not alt.exists():
                    dst = alt
                    break
                i += 1
        shutil.move(str(cand.path), str(dst))
        _drop_from_rag(cand.path)
        moved.append((cand.path, dst))
    return moved
