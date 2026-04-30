"""Parse upstream AI Digest emails into structured DigestPaper records.

The upstream project sends HTML emails with stable CSS classes (see
memory/reference_email_schema.md). Each `.paper` block contains all the
information NextBrain needs — metadata, topic tags with scores, and the
seven content sections (问题/动机/挑战/方法/假设与局限/实验结果/要点总结).
No LLM is needed at this stage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple


# Section title → DigestPaper field. Both Chinese (current upstream) and
# English keys are accepted for resilience.
_SECTION_MAP: Dict[str, str] = {
    "问题": "problem", "Problem": "problem",
    "动机": "motivation", "Motivation": "motivation",
    "重要性": "importance", "Importance": "importance",
    "关键挑战": "challenge", "挑战": "challenge", "Challenge": "challenge", "Key Challenges": "challenge",
    "方法": "method", "Method": "method",
    "假设与局限": "limitations", "局限性": "limitations", "Limitations": "limitations",
    "实验结果": "results", "结果": "results", "Results": "results", "Key Results": "results",
    "要点总结": "summary", "总结": "summary", "Summary": "summary", "Takeaways": "summary",
}

_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})")
_LEADING_NUM_RE = re.compile(r"^\s*\d+\.\s*")


@dataclass
class DigestPaper:
    """One paper extracted from a digest email."""
    title: str = ""
    arxiv_id: str = ""
    semantic_scholar_id: str = ""
    source_url: str = ""              # Best link: arXiv abs URL or original
    pdf_url: str = ""
    published: str = ""               # ISO date (YYYY-MM-DD)
    categories: List[str] = field(default_factory=list)
    topic_tags: Dict[str, float] = field(default_factory=dict)  # {slug: score}

    # Content sections (already summarised by upstream LLM)
    problem: str = ""
    motivation: str = ""
    importance: str = ""
    challenge: str = ""              # bullet list (joined with \n- )
    method: str = ""
    limitations: str = ""
    results: str = ""
    summary: str = ""

    # Raw provenance
    digest_date: str = ""             # Date from email subject
    email_message_id: str = ""

    def canonical_id(self) -> str:
        """Stable identifier for dedup. Prefer arxiv_id."""
        return self.arxiv_id or self.semantic_scholar_id or self.source_url


@dataclass
class DigestEmail:
    """One parsed digest email."""
    digest_date: str = ""
    message_id: str = ""
    subject: str = ""
    papers: List[DigestPaper] = field(default_factory=list)
    stats_text: str = ""              # The .stats line, kept for logging


# ── HTML decoding ────────────────────────────────────────────────────────────

def _extract_html_from_eml(eml_bytes: bytes) -> Tuple[str, str, str]:
    """Return (html_body, subject, message_id) from a raw .eml file."""
    import email
    from email import policy
    msg = email.message_from_bytes(eml_bytes, policy=policy.default)
    subject = str(msg["Subject"] or "")
    msg_id = str(msg["Message-Id"] or msg["Message-ID"] or "")
    html = ""
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            html = part.get_content()
            break
    return html, subject, msg_id


def _digest_date_from_subject(subject: str) -> str:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", subject)
    return m.group(1) if m else date.today().isoformat()


# ── Element parsing ──────────────────────────────────────────────────────────

def _text(el) -> str:
    return el.get_text(separator=" ", strip=True) if el is not None else ""


def _parse_paper_meta(meta_el) -> Dict[str, str]:
    """Parse the .paper-meta block: ID, Published, Categories."""
    out: Dict[str, str] = {"arxiv_id": "", "ss_id": "", "url": "",
                            "pdf_url": "", "published": "", "categories": ""}
    if meta_el is None:
        return out

    # Find the link inside ID — that's the arxiv URL or "semantic_scholar:..." text
    link = meta_el.find("a")
    if link is not None:
        href = (link.get("href") or "").strip()
        text = link.get_text(strip=True)
        if "arxiv.org" in href:
            out["pdf_url"] = href
            out["url"] = href.replace("/pdf/", "/abs/")
            m = _ARXIV_ID_RE.search(text or href)
            if m:
                out["arxiv_id"] = m.group(1)
        elif text.startswith("semantic_scholar:"):
            out["ss_id"] = text.split(":", 1)[1].strip()
        else:
            out["url"] = href

    # Fallback: if no link found, try to scrape semantic_scholar:<hash> from text
    if not out["arxiv_id"] and not out["ss_id"]:
        full = _text(meta_el)
        m = re.search(r"semantic_scholar:([a-f0-9]+)", full)
        if m:
            out["ss_id"] = m.group(1)
        else:
            m = _ARXIV_ID_RE.search(full)
            if m:
                out["arxiv_id"] = m.group(1)

    # Published / Categories — they live as bold labels followed by text in the
    # same .paper-meta div. Walk the text and split on the labels.
    full = _text(meta_el)
    pub = re.search(r"Published:\s*([0-9T:\-+\s]+?)(?:\s*\||$)", full)
    if pub:
        # Take just the date portion if ISO datetime
        out["published"] = pub.group(1).strip().split("T")[0].strip()
    cats = re.search(r"Categories:\s*([^|]+?)$", full)
    if cats:
        out["categories"] = cats.group(1).strip()

    return out


def _parse_topic_tags(tags_el) -> Dict[str, float]:
    """Each .topic-tag has form: '<slug> <b>0.8</b>'."""
    out: Dict[str, float] = {}
    if tags_el is None:
        return out
    for tag in tags_el.find_all(class_="topic-tag"):
        score_el = tag.find("b")
        try:
            score = float(_text(score_el)) if score_el else 0.0
        except ValueError:
            score = 0.0
        name = _text(tag).rsplit(" ", 1)[0].strip() if score_el else _text(tag).strip()
        if name:
            out[name] = score
    return out


def _parse_paper(paper_el) -> Optional[DigestPaper]:
    """Parse a single .paper block."""
    title_el = paper_el.find("h2")
    if title_el is None:
        return None
    title = _LEADING_NUM_RE.sub("", _text(title_el))

    meta = _parse_paper_meta(paper_el.find(class_="paper-meta"))
    tags = _parse_topic_tags(paper_el.find(class_="topic-tags"))

    paper = DigestPaper(
        title=title,
        arxiv_id=meta["arxiv_id"],
        semantic_scholar_id=meta["ss_id"],
        source_url=meta["url"] or (
            f"https://arxiv.org/abs/{meta['arxiv_id']}" if meta["arxiv_id"] else ""
        ),
        pdf_url=meta["pdf_url"],
        published=meta["published"],
        categories=[c.strip() for c in meta["categories"].split(",") if c.strip()],
        topic_tags=tags,
    )

    # Walk siblings: each section is a .section-title followed by either a
    # .section-body paragraph or a <ul class="bullet">.
    current_section: Optional[str] = None
    for child in paper_el.find_all(["div", "p", "ul"], recursive=True):
        cls = child.get("class") or []
        if "section-title" in cls:
            label = _text(child)
            current_section = _SECTION_MAP.get(label)
            continue
        if current_section is None:
            continue
        if "section-body" in cls:
            setattr(paper, current_section, _text(child))
            current_section = None
        elif "bullet" in cls:
            items = [_text(li) for li in child.find_all("li")]
            setattr(paper, current_section, "\n".join(f"- {it}" for it in items))
            current_section = None

    return paper


# ── Public entry points ─────────────────────────────────────────────────────

def parse_digest_html(html: str, subject: str = "", message_id: str = "") -> DigestEmail:
    """Parse an HTML body into a DigestEmail."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "BeautifulSoup is required. Install with: pip install nextbrain[ingest]"
        ) from e

    soup = BeautifulSoup(html, "html.parser")
    digest_date = _digest_date_from_subject(subject)

    stats_el = soup.find(class_="stats")
    stats_text = _text(stats_el)

    papers: List[DigestPaper] = []
    for paper_el in soup.find_all(class_="paper"):
        p = _parse_paper(paper_el)
        if p is None or not p.title:
            continue
        p.digest_date = digest_date
        p.email_message_id = message_id
        papers.append(p)

    return DigestEmail(
        digest_date=digest_date,
        message_id=message_id,
        subject=subject,
        papers=papers,
        stats_text=stats_text,
    )


def parse_eml_file(path: str) -> DigestEmail:
    """Parse a .eml file from disk."""
    with open(path, "rb") as f:
        raw = f.read()
    html, subject, msg_id = _extract_html_from_eml(raw)
    return parse_digest_html(html, subject=subject, message_id=msg_id)
