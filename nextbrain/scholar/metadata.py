"""Fetch paper metadata from various sources."""
import json
import re
import urllib.parse
import urllib.request
from typing import Optional

from nextbrain.models import PaperMetadata
from nextbrain.scholar.url_parser import parse_paper_url, arxiv_id_to_pdf_url, arxiv_id_to_abs_url


def fetch_metadata(url: str) -> PaperMetadata:
    """Fetch metadata for a paper URL. Tries arXiv API, Semantic Scholar, or falls back to generic."""
    source_type, identifier = parse_paper_url(url)

    if source_type == "arxiv" and identifier:
        meta = _fetch_arxiv(identifier)
        if meta:
            return meta

    if source_type == "semantic_scholar" and identifier:
        meta = _fetch_semantic_scholar_by_id(identifier)
        if meta:
            return meta

    if source_type == "doi" and identifier:
        meta = _fetch_semantic_scholar_by_doi(identifier)
        if meta:
            return meta

    # Fallback: try Semantic Scholar paper search by URL
    meta = _fetch_semantic_scholar_by_url(url)
    if meta:
        return meta

    # Minimal fallback
    return PaperMetadata(source_url=url)


def _fetch_arxiv(arxiv_id: str) -> Optional[PaperMetadata]:
    """Fetch metadata from arXiv API."""
    try:
        import arxiv as arxiv_lib
        client = arxiv_lib.Client(num_retries=2, delay_seconds=1.0)
        search = arxiv_lib.Search(id_list=[arxiv_id])
        for result in client.results(search):
            authors = [a.name for a in result.authors]
            year = result.published.year if result.published else None
            # Try to extract venue from comment
            venue = ""
            if result.comment:
                venue = result.comment
            return PaperMetadata(
                title=result.title.strip(),
                authors=authors,
                abstract=(result.summary or "").strip(),
                year=year,
                venue=venue,
                arxiv_id=arxiv_id,
                source_url=arxiv_id_to_abs_url(arxiv_id),
                pdf_url=arxiv_id_to_pdf_url(arxiv_id),
            )
    except Exception as e:
        print(f"[metadata] arXiv fetch failed for {arxiv_id}: {e}")
    return None


def _fetch_semantic_scholar_by_id(paper_id: str) -> Optional[PaperMetadata]:
    """Fetch from Semantic Scholar by paper ID."""
    return _fetch_s2(f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
                     "?fields=title,authors,abstract,year,venue,externalIds,openAccessPdf")


def _fetch_semantic_scholar_by_doi(doi: str) -> Optional[PaperMetadata]:
    """Fetch from Semantic Scholar by DOI."""
    return _fetch_s2(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
                     "?fields=title,authors,abstract,year,venue,externalIds,openAccessPdf")


def _fetch_semantic_scholar_by_url(url: str) -> Optional[PaperMetadata]:
    """Fetch from Semantic Scholar by URL."""
    return _fetch_s2(f"https://api.semanticscholar.org/graph/v1/paper/URL:{urllib.parse.quote(url, safe='')}"
                     "?fields=title,authors,abstract,year,venue,externalIds,openAccessPdf")


def _fetch_s2(api_url: str) -> Optional[PaperMetadata]:
    """Generic Semantic Scholar fetch."""
    import os
    headers = {"User-Agent": "ResearchNote/1.0"}
    ss_key = os.environ.get("SS_API_KEY") or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if ss_key:
        headers["x-api-key"] = ss_key
    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        ext = data.get("externalIds") or {}
        arxiv_id = ext.get("ArXiv") or ""
        doi = ext.get("DOI") or ""
        pdf_url = ""
        oa = data.get("openAccessPdf")
        if oa and isinstance(oa, dict):
            pdf_url = oa.get("url") or ""
        if not pdf_url and arxiv_id:
            pdf_url = arxiv_id_to_pdf_url(arxiv_id)
        source_url = ""
        if arxiv_id:
            source_url = arxiv_id_to_abs_url(arxiv_id)
        elif doi:
            source_url = f"https://doi.org/{doi}"
        authors = [a.get("name", "") for a in (data.get("authors") or [])]
        return PaperMetadata(
            title=(data.get("title") or "").strip(),
            authors=authors,
            abstract=(data.get("abstract") or "").strip(),
            year=data.get("year"),
            venue=(data.get("venue") or "").strip(),
            arxiv_id=arxiv_id,
            doi=doi,
            source_url=source_url,
            pdf_url=pdf_url,
        )
    except Exception as e:
        print(f"[metadata] Semantic Scholar fetch failed: {e}")
    return None
