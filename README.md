# EfficientResearch

Multi-agent research + workshop writing.

## Setup

```bash
pip install -r requirements.txt
```

Set `OPENAI_API_KEY` (or `OPENAI_BASE_URL`). Model: `EFFICIENT_RESEARCH_MODEL` (default `gpt-4o-mini`).

## Run demo

From the repo root:

```bash
python -m orchestrator.pipeline --topic "OOD-aware graph-based ANNS for multimodal retrieval" --venue "Workshop, 4-6 pages, double-column"
```

## Artifacts

- `artifacts/paper/main.tex`, `references.bib`
- `artifacts/runs/` — 01_ideator.json … 06_editor.json
- `artifacts/library/` — for bib/notes

## Quality gates (`eval/gates.py`)

- citation_coverage >= 0.8 (intro/related_work)
- speculation_ratio <= 0.2 (intro/method)
- baseline_checklist (min 1 baseline)
- skeptic_items_closed >= 50%

Failures go to `state["fix_list"]` and `state["gate_results"]`.
