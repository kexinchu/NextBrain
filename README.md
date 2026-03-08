# ResearchBot

Multi-agent research automation with human-in-the-loop. Given a research topic, ResearchBot runs a full pipeline — **ideation, literature review, critique, experiment design, writing, editing, and peer review** — and outputs a workshop-ready LaTeX paper.

Every major stage writes its results to an editable Markdown file. You review and edit the Markdown, confirm, and the pipeline continues with your changes.

---

## Installation

```bash
# Basic install (API mode)
pip install -e .

# With browser mode (use ChatGPT web UI, no API key needed)
pip install -e ".[browser]"
playwright install chromium

# With local RAG (long-term memory across runs)
pip install -e ".[rag]"

# Everything
pip install -e ".[all]"
```

Requires **Python 3.10+**.

---

## Quick Start

```bash
# 1. Create input.md template in current directory
researchbot init

# 2. Edit input.md with your research topic
#    (see "Input File Format" below)

# 3. Run the pipeline
researchbot run
```

All output files (Markdown reviews, JSON run logs, LaTeX paper) are written to the **current working directory**.

---

## Input File Format

`researchbot init` creates an `input.md` template:

```markdown
Topic: <your research topic here>
Venue: Workshop, 4-6 pages, double-column

# Optional fields:
# Constraints: <problem constraints>
# Sections: experiments,results,conclusion   (only regenerate these sections)
# Focus: system                              (system | theory | empirical | analysis)
```

You can also skip `input.md` and pass everything via CLI flags:

```bash
researchbot run --topic "Your topic" --venue "NeurIPS Workshop, 4 pages"
```

---

## CLI Reference

### `researchbot init`

Creates `input.md` in the current directory.

| Flag | Description |
|---|---|
| `--force` | Overwrite existing `input.md` |

### `researchbot run`

Runs the research pipeline.

| Flag | Description |
|---|---|
| `--topic TEXT` | Research topic (overrides `input.md`) |
| `--venue TEXT` | Target venue (default: `Workshop, 4-6 pages, double-column`) |
| `--constraints TEXT` | Problem constraints |
| `--browser` | Use ChatGPT via browser automation (no API key needed) |
| `--sections LIST` | Comma-separated sections to regenerate (e.g. `experiments,results`) |
| `--focus TYPE` | Research focus: `system`, `theory`, `empirical`, or `analysis` |
| `--resume` | Resume from last completed stage |

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key (required for API mode) | — |
| `OPENAI_BASE_URL` | Custom API endpoint (for compatible providers) | OpenAI default |
| `EFFICIENT_RESEARCH_MODEL` | Model name | `gpt-4o-mini` |
| `RESEARCHBOT_MAX_REVIEW_ITER` | Max Skeptic/DeepResearch review loops | `2` |
| `RESEARCHBOT_MAX_WRITE_ITER` | Max Writer rewrite loops | `3` |
| `EFFICIENT_RESEARCH_RAG_DIR` | RAG storage directory | `<cwd>/rag/` |
| `EFFICIENT_RESEARCH_COOKIE_FILE` | ChatGPT cookie file for browser mode | — |
| `EFFICIENT_RESEARCH_BROWSER_MIN_INTERVAL` | Seconds between browser LLM calls | `5` |

### Browser Mode

Browser mode uses Playwright to automate ChatGPT — no API key required.

```bash
researchbot run --browser --topic "Your topic"
```

First run: a Chrome window opens — log in to ChatGPT manually. Subsequent runs reuse the session.

To auto-login, export cookies from a logged-in browser (e.g. via Cookie-Editor extension on chatgpt.com) and set:
```bash
export EFFICIENT_RESEARCH_COOKIE_FILE="$HOME/cookies_chatgpt.json"
```

---

## Pipeline Architecture

```
Phase 1 · Explore    Ideator → Scout → DeepResearcher
Phase 2 · Review     Skeptic ⟲ DeepResearcher        (loop: up to 2x)
Phase 3 · Experiment Experimenter
Phase 4 · Write      Writer ⟲ [DeepResearcher | Experimenter | self]  (loop: up to 3x)
Phase 5 · Edit       Editor → LaTeX
Phase 6 · PeerReview Reviewer
```

| Agent | Role | Output |
|---|---|---|
| **Ideator** | Generate 3-10 falsifiable hypotheses | `HypothesisCard[]` |
| **Scout** | ArXiv literature search, select best 1-2 hypotheses | `related_work`, `selected_ids` |
| **DeepResearcher** | Deep literature search, build annotated bibliography | `annotated_bib`, `baseline_checklist`, `gap_summary` |
| **Skeptic** | Adversarial reviewer — rejection risks and required experiments | `rejection_risks`, `required_experiments` |
| **Experimenter** | Design experiments and theoretical validation | `experiment_plan`, `theoretical_validation` |
| **Writer** | Write full LaTeX paper (9 sections) | `sections` dict |
| **Editor** | Polish academic tone, preserve citation tags | Improved `sections` |
| **Reviewer** | Simulated peer review with scores | `overall`, `recommendation` |

### Iteration Loops

- Skeptic finds evidence gaps → DeepResearcher re-searches using rejection risks as queries
- Writer quality gates fail (citation/baseline) → loop back to DeepResearcher + Skeptic
- Writer quality gates fail (experiment coverage) → loop back to Experimenter
- Writer quality gates fail (speculation) → Writer self-corrects with `fix_list`

---

## Human-in-the-Loop

Human review is the default at every major stage:

1. **After Ideator**: Review `review/01_ideator_report.md`. Select which hypotheses to pursue (enter numbers like `1` or `1,3`).
2. **After DeepResearch**: Review `review/03_deep_research_round_N.md`. Edit the Markdown (add/remove bibliography entries, adjust baselines), then confirm to continue or loop.
3. **After Experimenter**: Review `review/05_experimenter_report.md`. Edit experiment design, then confirm.
4. **After Writer**: Review `review/06_writer_report.md`. Edit sections if needed, then confirm.

Edits you make to the Markdown files are read back into the pipeline as the stage output.

---

## Output Structure

After a complete run, your working directory contains:

```
./
├── review/                     # Editable Markdown reports (one per stage)
│   ├── 01_ideator_report.md
│   ├── 03_deep_research_round_1.md
│   ├── 05_experimenter_report.md
│   └── 06_writer_report.md
├── runs/                       # JSON state snapshots
│   ├── 01_ideator.json
│   ├── 02_scout.json
│   ├── 03_deep_research.json   # _iter2, _iter3 etc. for loops
│   ├── 04_skeptic.json
│   ├── 05_experimenter.json
│   ├── 06_writer.json
│   └── 07_editor.json
├── paper/
│   ├── main.tex                # LaTeX paper (IEEEtran double-column)
│   ├── references.bib          # BibTeX references
│   └── main.pdf                # Compiled PDF (if LaTeX is installed)
└── input.md                    # Your research input
```

---

## Quality Gates

The pipeline runs 8 quality checks after Writer and Editor stages. Failed gates trigger automatic correction loops.

| Gate | What it checks | Threshold |
|---|---|---|
| `citation_coverage` | `[CITE:]`/`[EVID:]` tag density in intro/related_work | >= 80% |
| `speculation_ratio` | `[SPEC]` tag ratio in intro/method | <= 20% |
| `baseline_checklist` | Number of baselines from DeepResearcher | >= 1 |
| `skeptic_items_closed` | Skeptic concerns addressed in paper | >= 50% |
| `experiment_evidence_coverage` | `[EVID:]` tags in results/experiments | >= 50% of experiments |
| `abstract_completeness` | Abstract has evidence tags | Required |
| `cite_key_validity` | All `[CITE:key]` match annotated_bib | 100% |
| `section_minimum_length` | Critical sections have sufficient content | >= 30 words each |

---

## Debugging

### Check if the pipeline is working

1. **Review Markdown files** in `review/` — they show what each agent produced.
2. **Inspect JSON logs** in `runs/` — each file contains the raw agent output for that stage.
3. **Quality gate results** are printed to the terminal after Writer/Editor stages, showing which gates passed/failed and why.

### Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `OPENAI_API_KEY not set` | No API key configured | Set `export OPENAI_API_KEY="sk-..."` or use `--browser` |
| Pipeline hangs at "waiting for confirmation" | Normal — it's waiting for you to review the Markdown | Edit the file in `review/`, then type `y` in the terminal |
| Empty annotated bibliography | Search returned no results | Check your internet connection; try a broader topic |
| Quality gates keep failing | Writer output doesn't meet thresholds | Check the gate failure reasons in terminal output; the pipeline auto-retries up to `MAX_WRITE_ITER` times |
| Browser mode: "verify you're human" | ChatGPT bot detection | Delete `~/.chatgpt-bot-profile` and re-run; complete the CAPTCHA manually in the browser window |
| `ModuleNotFoundError` | Package not installed | Run `pip install -e .` from the repo root |

### Resume after failure

If the pipeline crashes mid-run, use `--resume` to pick up where it left off:

```bash
researchbot run --resume
```

This loads the last saved state from `runs/` and continues from the next stage.

### Verbose debugging

Inspect individual stage outputs:

```bash
python -c "import json; print(json.dumps(json.load(open('runs/01_ideator.json')), indent=2))"
```

---

## Local RAG (Long-Term Memory)

Each completed run is indexed into a local vector store (`rag/`). On subsequent runs, the pipeline retrieves relevant context from past research to inform the Ideator.

Requires: `pip install -e ".[rag]"`

| Variable | Description | Default |
|---|---|---|
| `EFFICIENT_RESEARCH_RAG_DIR` | RAG storage path | `<cwd>/rag/` |

Manual indexing of a previous run:
```python
from researchbot.tools.rag import index_run_artifacts
index_run_artifacts("runs")
```

---

## Customizing Agent Behavior

Each agent's system prompt lives in `researchbot/skills/<name>/SKILL.md`. Edit these files to adjust agent behavior (e.g. change hypothesis count, citation style, section lengths).

---

## Project Structure

```
researchbot/
├── cli.py              # CLI entry point (init, run)
├── config.py           # LLM configuration
├── agents/             # 8 agents (ideator, scout, deep_researcher, skeptic,
│                       #           experimenter, writer, editor, reviewer)
├── orchestrator/
│   ├── pipeline.py     # Main pipeline with iteration loops
│   ├── state.py        # Shared state management
│   └── human_review.py # Markdown report generation and read-back
├── tools/
│   ├── llm.py          # LLM calls (API + browser)
│   ├── search.py       # ArXiv, Semantic Scholar, DuckDuckGo
│   ├── browser_llm.py  # Playwright-based ChatGPT automation
│   ├── citations.py    # BibTeX generation
│   ├── latex_builder.py# LaTeX document assembly
│   ├── io.py           # File I/O utilities
│   ├── rag.py          # Local RAG indexing/retrieval
│   └── skills_loader.py# SKILL.md prompt loader
├── eval/
│   └── gates.py        # Quality gate checks
└── skills/             # Agent system prompts (SKILL.md files)
```

---

## Citation Tags

Every claim in the generated paper carries one of these tags:

| Tag | Meaning |
|---|---|
| `[CITE:key]` | References a paper in `annotated_bib` |
| `[EVID:exp_N]` | References an experiment result |
| `[EVID:ablation_N]` | References an ablation study result |
| `[SPEC]` | Speculative claim (no supporting evidence) |

These are converted to proper `\cite{}` commands when building the final LaTeX.
