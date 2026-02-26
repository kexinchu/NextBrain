# EfficientResearch (Multi-Agent Research + Workshop Writing) — Cursor Prompt

## 0) Mission
Build an end-to-end, **reproducible** multi-agent system that, given a research *topic*, automatically:
1) generates falsifiable hypotheses,
2) performs literature research with citations,
3) runs iterative critical review to select directions,
4) produces an experiment plan (and optionally runnable scripts),
5) writes a workshop-ready paper draft (LaTeX),
6) improves readability/style and formatting (human-like academic writing; no “evasion”).

The system must be **auditable**: every claim is backed by either a citation or an experiment artifact. Anything else is marked as speculation.

Target output: a working repo called `efficient_research/`.

---

## 1) Constraints & Non-negotiables
- Use **multiple agents** with **strict roles** and **structured IO** (JSON/YAML).
- Add **quality gates** after each phase (citation coverage, novelty risk, feasibility, checklist closure).
- Every stage logs artifacts to `artifacts/` and is versionable with git.
- Writing improvement = clarity, precision, coherence, format compliance. Do **not** implement “AI detector evasion”.

---

## 2) Tech Stack (choose one)
Pick **ONE** orchestrator approach and implement it cleanly:
- Preferred: **LangGraph** style workflow (state machine, deterministic stages).
- Acceptable: **AutoGen**-style multi-agent chat with explicit handoffs.

Also implement:
- Web search tool wrapper (pluggable)
- PDF/URL note capture (minimal; store citations as metadata)
- LaTeX builder (template folder + section stubs)
- Result table/plot pipeline (optional MVP)

---

## 3) Agent Roles (must implement)
Implement agents as modules under `agents/` with `run(input)->output`.

### A) Ideator (Hypotheses)
Input: topic, constraints (datasets/hardware/metrics/target venue)
Output: 3–10 `HypothesisCard` items:
- `id`, `claim`, `falsifiable_test`, `minimal_experiment`, `expected_gain`, `risks`

### B) Scout (Coarse literature + triage)
Input: HypothesisCards
Output:
- related-work map (papers + 1–2 lines each),
- novelty risk score per hypothesis,
- feasibility score per hypothesis,
- pick top 1–2 hypotheses with rationale.

### C) DeepResearcher (Evidence + bib)
Input: selected hypotheses
Output:
- annotated bibliography (per paper: contribution, settings, what to reproduce),
- baseline + metrics checklist,
- “what’s missing / gap” summary.

### D) Skeptic (Reviewer-style attack)
Input: proposed approach + evidence
Output:
- rejection-risk checklist (threats to validity, missing baselines, unfair comparisons),
- required experiments/ablations prioritized.

### E) Writer (Workshop LaTeX draft)
Input: final method outline + results plan + bib
Output:
- LaTeX paper skeleton with sections: Abstract, Intro, Background, Method, Experiments, Results, Related Work, Limitations, Conclusion
- Each claim must be tagged with `[CITE:...]` or `[EVID:...]` or `[SPEC]`.

### F) Editor (Style + format polish)
Input: LaTeX draft
Output:
- improved text for clarity and academic tone,
- terminology consistency,
- length control (avoid bloating),
- remove repetitive template phrases.

---

## 4) Quality Gates (must implement as `eval/gates.py`)
Implement gate functions that take stage outputs and return PASS/FAIL with reasons:
- `citation_coverage >= 0.8` for literature/related-work sections
- `speculation_ratio <= threshold` (e.g., <= 0.2 in intro/method)
- `baseline_checklist` coverage (at least X baselines / metrics if applicable)
- `skeptic_items_closed >= X%` before final draft export

If FAIL, route back to the responsible agent with an “actionable fix list”.

---

## 5) Repo Structure (must create)
Create exactly this structure (you may add small extras, not large redesign):

efficient_research/
  README.md
  pyproject.toml (or requirements.txt)
  orchestrator/
    pipeline.py
    state.py
  agents/
    ideator.py
    scout.py
    deep_researcher.py
    skeptic.py
    writer.py
    editor.py
  schemas/
    hypothesis.schema.json
    bib.schema.json
    review.schema.json
    paper_outline.schema.json
  tools/
    search.py
    citations.py
    latex_builder.py
    io.py
  eval/
    gates.py
  artifacts/
    library/        # bib + notes
    runs/           # logs/config snapshots
    paper/          # LaTeX project output
  prompts/
    ideator.md
    scout.md
    deep_researcher.md
    skeptic.md
    writer.md
    editor.md

---

## 6) MVP Behavior (must work locally)
Implement a CLI entry:
- `python -m orchestrator.pipeline --topic "<TOPIC>" --venue "<VENUE>"`

The pipeline should:
1) generate hypotheses
2) scout and select
3) deep research
4) skeptic review + fix loop (at least 1 iteration)
5) generate LaTeX draft into `artifacts/paper/`
6) run editor pass
7) print a final summary with paths to artifacts

Even if web/PDF tools are minimal, the system must still run end-to-end with placeholder citations.

---

## 7) Prompting Style Requirements (for prompts/*.md)
- Force structured outputs (JSON blocks) with explicit field names.
- Require evidence tagging for claims: `[CITE:key]`, `[EVID:run_id]`, `[SPEC]`.
- The Skeptic must be adversarial and list “reject reasons” first.
- The Writer must avoid bullet-only writing; use paragraphs suitable for double-column papers.

---

## 8) What to Implement First (Cursor execution plan)
1) Create repo skeleton + CLI
2) Implement schemas + IO validation
3) Implement agents with placeholder logic (deterministic prompts)
4) Implement gates + loop logic
5) Implement LaTeX builder output
6) Make one demo run with a sample topic

---

## 9) Deliverables (Cursor must output)
- All code files created under `efficient_research/`
- A short `README.md` with:
  - setup instructions
  - how to run a demo
  - where artifacts are saved
  - how quality gates work
- A successful demo run that produces `artifacts/paper/main.tex` and `references.bib` (can be minimal).

---

## 10) Demo Topic (use for quick test)
Topic: "OOD-aware graph-based ANNS for multimodal retrieval"
Venue: "Workshop, 4–6 pages, double-column"

Now implement the repository accordingly.