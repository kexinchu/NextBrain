"""Parse paper URLs to extract source type and identifiers."""
import re
from typing import Optional, Tuple


def parse_paper_url(url: str) -> Tuple[str, Optional[str]]:
    """Parse a paper URL and return (source_type, identifier).

    source_type: "arxiv" | "semantic_scholar" | "doi" | "generic"
    identifier: arXiv ID, S2 paper ID, DOI, or None
    """
    url = url.strip()

    # arXiv: abs or pdf
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", url)
    if m:
        return "arxiv", m.group(1)

    # arXiv old format
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([a-z\-]+/\d{7})", url)
    if m:
        return "arxiv", m.group(1)

    # Semantic Scholar
    m = re.search(r"semanticscholar\.org/paper/[^/]*/([a-f0-9]{40})", url)
    if m:
        return "semantic_scholar", m.group(1)
    m = re.search(r"semanticscholar\.org/paper/([a-f0-9]{40})", url)
    if m:
        return "semantic_scholar", m.group(1)

    # DOI
    m = re.search(r"doi\.org/(10\.\d{4,}/\S+)", url)
    if m:
        return "doi", m.group(1)

    return "generic", None


def arxiv_id_to_pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}"


def arxiv_id_to_abs_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{arxiv_id}"
