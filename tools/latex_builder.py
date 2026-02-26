"""LaTeX builder: template folder + section stubs."""
from pathlib import Path
from typing import Dict, List

def build_latex(
    sections: Dict[str, str],
    output_dir: str | Path,
    main_name: str = "main",
    bib_keys: List[str] | None = None,
) -> Path:
    """
    Write main.tex and ensure references.bib path. Sections dict: abstract, intro, ...
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    bib_keys = bib_keys or []

    preamble = r"""
\documentclass[conference]{IEEEtran}
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{algorithmic}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{url}
\usepackage{hyperref}
\begin{document}
"""

    parts = [preamble]
    order = [
        "abstract", "intro", "background", "method",
        "experiments", "results", "related_work", "limitations", "conclusion"
    ]
    section_titles = {
        "abstract": "Abstract",
        "intro": "Introduction",
        "background": "Background",
        "method": "Method",
        "experiments": "Experiments",
        "results": "Results",
        "related_work": "Related Work",
        "limitations": "Limitations",
        "conclusion": "Conclusion",
    }
    for name in order:
        content = sections.get(name, "")
        if not content.strip():
            content = "% TODO: " + section_titles.get(name, name)
        if name == "abstract":
            parts.append("\\begin{abstract}\n" + content.strip() + "\n\\end{abstract}\n")
        else:
            title = section_titles.get(name, name.replace("_", " ").title())
            parts.append("\\section{" + title + "}\n\n" + content.strip() + "\n\n")
    parts.append("\n\n")
    if bib_keys:
        parts.append("\\bibliographystyle{IEEEtran}\n\\bibliography{references}\n")
    parts.append("\\end{document}\n")

    main_tex = output_dir / f"{main_name}.tex"
    main_tex.write_text("".join(parts), encoding="utf-8")
    return main_tex
