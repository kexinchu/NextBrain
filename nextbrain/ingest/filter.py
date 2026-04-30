"""Second-stage filter for digest papers.

Pipeline (cheap → expensive, short-circuit early):
  1. Dedup        — arXiv ID already in vault → skip
  2. Active topic — upstream tags don't overlap user's active topics → skip
  3. Topic score  — max upstream score < min_topic_score → Inbox/
  4. RAG novelty  — cosine ≥ rag_dup_threshold to existing note → Inbox/ (duplicate-of)
  5. Pass         — write to Papers-<paper_type>/

Decisions are returned as IngestDecision; the actual write to Obsidian is done
by the caller so this module stays testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from nextbrain import config
from nextbrain.ingest.digest_parser import DigestPaper
from nextbrain.models import PaperNote
from nextbrain.topics.active_topics import (
    ActiveTopics, get_active_topics, topic_overlap_score, _slug,
)


KEEP = "keep"
INBOX = "inbox"
SKIP = "skip"


@dataclass
class IngestDecision:
    paper: DigestPaper
    action: str                 # keep | inbox | skip
    reason: str                 # short tag like "duplicate", "off-topic", "low-score", "rag-dup"
    paper_type: str = "Other"   # mapped target type
    rag_duplicate_of: str = ""  # path of nearest neighbor (for INBOX/duplicate)
    rag_score: float = 0.0
    topic_match_score: float = 0.0


# ── Utilities ────────────────────────────────────────────────────────────────

_FM_SOURCE_RE = re.compile(r'source_url:\s*"?([^"\n]+)"?')
_ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})")


def _vault_arxiv_ids(vault_path: str) -> set:
    from pathlib import Path
    out = set()
    vault = Path(vault_path).expanduser()
    for md in vault.glob("Papers-*/*.md"):
        try:
            with open(md, "r", encoding="utf-8") as f:
                head = f.read(2048)
        except OSError:
            continue
        m = _FM_SOURCE_RE.search(head)
        if not m:
            continue
        url = m.group(1).strip()
        am = _ARXIV_RE.search(url)
        if am:
            out.add(am.group(1))
    # Also look in Inbox/
    for md in vault.glob("Inbox/*.md"):
        try:
            with open(md, "r", encoding="utf-8") as f:
                head = f.read(2048)
        except OSError:
            continue
        m = _FM_SOURCE_RE.search(head)
        if m:
            am = _ARXIV_RE.search(m.group(1))
            if am:
                out.add(am.group(1))
    return out


# Explicit mappings for upstream slugs that don't substring-match user paper_types.
# Key: slugified upstream tag. Value: user paper_type string (must be in config).
_SLUG_TO_PTYPE: Dict[str, str] = {
    # agent-systems / agentic → Agentic-OS
    "agentsystems":        "Agentic-OS",
    "agentruntime":        "Agentic-OS",
    "agentic":             "Agentic-OS",
    # systems-memory / gpu-memory → Memory
    "systemsmemory":       "Memory",
    "gpumemory":           "Memory",
    "kvmemory":            "Memory",
    # ann-retrieval-systems → ANNS
    "annretrievalsystems": "ANNS",
    "annretrieval":        "ANNS",
    "vectorsearch":        "ANNS",
    # llm-serving / llm-inference → LLM-Opt
    "llmserving":          "LLM-Opt",
    "llminference":        "LLM-Opt",
    "modelserving":        "LLM-Opt",
    # speculative-decoding → Speculative-LLM
    "speculativedecoding": "Speculative-LLM",
    "speculativellm":      "Speculative-LLM",
    # agent-security / llm-security → LLM-Security
    "agentsecurity":       "LLM-Security",
    "llmsecurity":         "LLM-Security",
    "aisecurity":          "LLM-Security",
    # kv-cache → KV-Cache
    "kvcache":             "KV-Cache",
    "kvcompression":       "KV-Cache",
    # deterministic-llm
    "deterministicllm":    "Deterministic-LLM",
}


def _map_paper_type(paper: DigestPaper) -> str:
    """Map upstream topic slugs to a user paper_type.

    Strategy:
      1. Try all tags in descending score order against explicit alias table.
      2. Then try substring matching against user taxonomy.
      3. Fall back to 'Other'.
    """
    user_types = config.get_paper_types()
    if not paper.topic_tags:
        return "Other"
    sorted_tags = sorted(paper.topic_tags.items(), key=lambda kv: kv[1], reverse=True)

    # Pass 1: explicit alias table
    for tag, _ in sorted_tags:
        mapped = _SLUG_TO_PTYPE.get(_slug(tag))
        if mapped and mapped in user_types:
            return mapped

    # Pass 2: substring match against user taxonomy
    for tag, _ in sorted_tags:
        bt = _slug(tag)
        for ptype in user_types:
            ps = _slug(ptype)
            if ps and (ps == bt or ps in bt or bt in ps):
                return ptype

    return "Other"


# ── RAG novelty (optional) ──────────────────────────────────────────────────

def _rag_nearest(query_text: str) -> Tuple[Optional[str], float]:
    """Return (nearest_doc_path, cosine_similarity) or (None, 0.0) if RAG unavailable.

    Chroma returns L2 / cosine *distance*; we approximate cosine similarity as
    `max(0, 1 - distance)` (works for both cosine-distance and small L2).
    """
    try:
        from nextbrain.tools.rag import query as rag_query
    except ImportError:
        return None, 0.0
    try:
        hits = rag_query(query_text, k=1)
    except Exception:
        return None, 0.0
    if not hits:
        return None, 0.0
    top = hits[0]
    distance = float(top.get("distance", 1.0))
    similarity = max(0.0, 1.0 - distance)
    return top.get("source", ""), similarity


# ── Conversion ──────────────────────────────────────────────────────────────

def digest_paper_to_note(paper: DigestPaper, paper_type: str) -> PaperNote:
    """Convert a parsed DigestPaper into a PaperNote ready to write.

    Reuses the upstream summary sections directly — no LLM call.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    year: Optional[int] = None
    if paper.published:
        try:
            year = int(paper.published[:4])
        except ValueError:
            year = None

    # Build the seven-section content directly from the email
    return PaperNote(
        title=paper.title,
        paper_type=paper_type,
        authors=[],   # not in digest; user can fill in or fetcher can backfill later
        year=year,
        venue=", ".join(paper.categories),
        source_url=paper.source_url or (
            f"https://arxiv.org/abs/{paper.arxiv_id}" if paper.arxiv_id else ""
        ),
        zotero_key="",
        tags=list(paper.topic_tags.keys()),
        created_at=today,
        updated_at=today,
        status="unread",
        last_opened="",
        times_referenced=0,
        read_status="skimmed",
        ingested_via="email",
        upstream_topic_scores=dict(paper.topic_tags),
        problem=paper.problem,
        importance=paper.motivation,   # upstream "动机" maps best to importance
        motivation=paper.motivation,
        challenge=paper.challenge,
        design=paper.method,
        related_work="",
        key_results=paper.results,
        summary=paper.summary,
        limitations=paper.limitations,
    )


# ── Main entry point ────────────────────────────────────────────────────────

def filter_papers(papers: List[DigestPaper],
                   vault_path: Optional[str] = None,
                   force_recompute_topics: bool = False) -> List[IngestDecision]:
    """Apply the second-stage filter to a batch of digest papers."""
    from nextbrain.config import get_obsidian_vault_path
    vault = vault_path or get_obsidian_vault_path()

    seen_ids = _vault_arxiv_ids(vault)
    active = get_active_topics(vault_path=vault, force_recompute=force_recompute_topics)
    min_score = config.get_filter_min_topic_score()
    rag_thresh = config.get_filter_rag_dup_threshold()

    decisions: List[IngestDecision] = []
    for p in papers:
        ptype = _map_paper_type(p)

        # 1. Dedup
        if p.arxiv_id and p.arxiv_id in seen_ids:
            decisions.append(IngestDecision(
                paper=p, action=SKIP, reason="duplicate", paper_type=ptype,
            ))
            continue

        # 2. Active-topic overlap (semantic match between upstream slugs and user labels)
        overlap = topic_overlap_score(active, p.topic_tags)

        # 3. Per-tag max score (raw signal from upstream)
        max_tag_score = max(p.topic_tags.values()) if p.topic_tags else 0.0

        # If we have active topics and zero overlap, this is off-topic — skip outright.
        if active.weights and overlap == 0.0:
            decisions.append(IngestDecision(
                paper=p, action=SKIP, reason="off-topic", paper_type=ptype,
                topic_match_score=overlap,
            ))
            continue

        # 4. Low upstream confidence → Inbox for review
        if max_tag_score < min_score:
            decisions.append(IngestDecision(
                paper=p, action=INBOX, reason="low-score", paper_type=ptype,
                topic_match_score=overlap,
            ))
            continue

        # 5. RAG novelty
        query = f"{p.title}\n\n{p.problem}\n\n{p.method}".strip()
        nearest_path, score = _rag_nearest(query)
        if nearest_path and score >= rag_thresh:
            decisions.append(IngestDecision(
                paper=p, action=INBOX, reason="rag-duplicate", paper_type=ptype,
                rag_duplicate_of=nearest_path, rag_score=score,
                topic_match_score=overlap,
            ))
            continue

        # 6. Pass
        decisions.append(IngestDecision(
            paper=p, action=KEEP, reason="pass", paper_type=ptype,
            rag_score=score, topic_match_score=overlap,
        ))

    return decisions
