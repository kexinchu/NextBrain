"""Extract figures and their captions from paper PDFs."""
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request


def download_pdf(url: str) -> Optional[bytes]:
    """Download PDF from URL (arXiv, direct link, etc.). Returns PDF bytes or None."""
    arxiv_match = re.match(r"https?://arxiv\.org/abs/(\d+\.\d+)", url)
    if arxiv_match:
        url = f"https://arxiv.org/pdf/{arxiv_match.group(1)}.pdf"

    try:
        req = Request(url, headers={"User-Agent": "ResearchNote/1.0"})
        resp = urlopen(req, timeout=60)
        data = resp.read()
        if data[:5] == b"%PDF-":
            return data
    except Exception as e:
        print(f"[figures] Failed to download PDF: {e}", flush=True)
    return None


# ── Caption extraction ────────────────────────────────────────────────────────

_CAPTION_RE = re.compile(
    r"(?:Figure|Fig\.?)\s*(\d+)[.:]\s*(.+)",
    re.IGNORECASE,
)


def _extract_page_captions(page) -> Dict[int, str]:
    """Extract figure captions from a PDF page.

    Returns {figure_number: caption_text} for all captions found on the page.
    """
    text = page.get_text("text")
    captions = {}
    for m in _CAPTION_RE.finditer(text):
        fig_num = int(m.group(1))
        caption_text = m.group(2).strip()
        # Take first sentence or first 200 chars
        end = caption_text.find(". ", 80)
        if end > 0:
            caption_text = caption_text[:end + 1]
        elif len(caption_text) > 200:
            caption_text = caption_text[:200] + "..."
        captions[fig_num] = f"Figure {fig_num}: {caption_text}"
    return captions


# ── Figure extraction ─────────────────────────────────────────────────────────

def extract_figures_with_captions(
    pdf_bytes: bytes,
    max_figures: int = 10,
    min_size: int = 15000,
) -> List[Dict]:
    """Extract figure images and captions from PDF bytes.

    Returns list of dicts:
        {"id": "fig1", "page": 3, "caption": "Figure 1: ...", "image_bytes": bytes, "ext": "png"}
    Only keeps images above min_size bytes (skips icons/logos).
    """
    try:
        import fitz
    except ImportError:
        print("[figures] PyMuPDF not installed. Run: pip install pymupdf", flush=True)
        return []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # First pass: collect all captions across all pages
    all_captions: Dict[int, str] = {}
    for page_num in range(len(doc)):
        page = doc[page_num]
        all_captions.update(_extract_page_captions(page))

    # Second pass: extract images
    figures = []
    fig_counter = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            img_bytes = base_image["image"]
            ext = base_image["ext"]
            w = base_image.get("width", 0)
            h = base_image.get("height", 0)

            # Skip small/narrow images
            if len(img_bytes) < min_size or w < 100 or h < 100:
                continue

            fig_counter += 1
            fig_id = f"fig{fig_counter}"

            # Try to match with a caption on this page
            page_captions = _extract_page_captions(page)
            caption = ""
            if page_captions:
                # Use the first unmatched caption on this page
                for fnum, cap in sorted(page_captions.items()):
                    caption = cap
                    break
            if not caption:
                caption = f"Figure (page {page_num + 1})"

            figures.append({
                "id": fig_id,
                "page": page_num + 1,
                "caption": caption,
                "image_bytes": img_bytes,
                "ext": ext,
            })

            if len(figures) >= max_figures:
                break
        if len(figures) >= max_figures:
            break

    doc.close()
    return figures


# ── Save to vault ─────────────────────────────────────────────────────────────

def save_figures_to_vault(
    figures: List[Dict],
    note_stem: str,
    vault_path: str,
    paper_type: str,
) -> Dict[str, str]:
    """Save extracted figures to Obsidian vault.

    Saves to: <vault>/Papers-<type>/assets/<note_stem>/fig_<N>.<ext>
    Returns {fig_id: relative_path} mapping.
    """
    if not figures:
        return {}

    assets_dir = Path(vault_path) / f"Papers-{paper_type}" / "assets" / note_stem
    assets_dir.mkdir(parents=True, exist_ok=True)

    paths = {}
    for fig in figures:
        filename = f"{fig['id']}_p{fig['page']}.{fig['ext']}"
        filepath = assets_dir / filename
        filepath.write_bytes(fig["image_bytes"])
        paths[fig["id"]] = f"assets/{note_stem}/{filename}"

    return paths


# ── Public API ────────────────────────────────────────────────────────────────

def extract_and_save(
    source_url: str,
    note_stem: str,
    vault_path: str,
    paper_type: str,
    max_figures: int = 10,
) -> Tuple[List[Dict], Dict[str, str]]:
    """Full pipeline: download PDF → extract figures with captions → save to vault.

    Returns:
        (figure_info_list, fig_id_to_path_map)
        figure_info_list: [{"id": "fig1", "page": 3, "caption": "Figure 1: ..."}, ...]
        fig_id_to_path_map: {"fig1": "assets/xxx/fig1_p3.png", ...}
    """
    pdf_bytes = download_pdf(source_url)
    if not pdf_bytes:
        return [], {}

    figures = extract_figures_with_captions(pdf_bytes, max_figures=max_figures)
    if not figures:
        print("[figures] No figures extracted from PDF.", flush=True)
        return [], {}

    paths = save_figures_to_vault(figures, note_stem, vault_path, paper_type)

    # Return info without image_bytes (not needed downstream)
    info = [{"id": f["id"], "page": f["page"], "caption": f["caption"]} for f in figures]
    print(f"[figures] Extracted {len(info)} figures with captions.", flush=True)
    return info, paths
