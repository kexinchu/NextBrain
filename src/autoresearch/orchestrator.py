from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .agent import Agent
from .alignment import AlignmentGuard
from .freeze import FreezeGuard
from .io import atomic_write, utc_stamp, write_json
from .models import AgentRequest, RoundOutcome
from .sampling import risk_stratified_sample
from .skills import load_skill
from .topic import TopicDocument


class PathPolicyViolation(RuntimeError):
    pass


def _is_within(path: str, prefixes: Iterable[str]) -> bool:
    normalized = Path(path).as_posix().strip("/")
    return any(normalized == prefix.strip("/") or normalized.startswith(prefix.strip("/") + "/") for prefix in prefixes)


@dataclass
class AutoResearch:
    root: Path
    agent: Agent

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        self.alignment = AlignmentGuard(self.root)
        self.freezes = FreezeGuard(self.root)

    def _workspace_path(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise PathPolicyViolation(f"path escapes workspace: {relative}") from exc
        return candidate

    def _budget_report(self, skill_name: str, history: list[RoundOutcome]) -> RoundOutcome:
        snapshot = self.alignment.snapshot()
        round_id = f"{utc_stamp()}-{skill_name}-budget-report"
        run_dir = self.root / "runs" / round_id
        run_dir.mkdir(parents=True, exist_ok=False)
        previous = "\n".join(
            f"- `{item.round_id}`: {item.role} -> {item.decision}; {item.summary}"
            for item in history
        )
        output = run_dir / "output.md"
        atomic_write(
            output,
            "# Loop stopped: round budget exhausted\n\n"
            "No candidate or stage reached a terminal decision within the configured "
            "budget. Human direction is required before continuing.\n\n"
            f"## Prior rounds\n\n{previous}\n",
        )
        alignment = self.alignment.record(
            run_dir,
            "budget-reporter",
            snapshot,
            "report",
            possible_drift="none; stopped at configured round bound",
        )
        outcome = RoundOutcome(
            round_id=round_id,
            skill=skill_name,
            role="budget-reporter",
            decision="report",
            output_path=output.relative_to(self.root).as_posix(),
            alignment_path=alignment.relative_to(self.root).as_posix(),
            requirements_digest=snapshot.digest,
            summary="Round budget exhausted; human direction required.",
        )
        write_json(run_dir / "manifest.json", outcome.as_dict())
        return outcome

    def _update_idea_story(
        self,
        topic_path: str,
        outcome: RoundOutcome,
        data: dict[str, Any],
    ) -> Path:
        story = data.get("story") or data.get("content")
        if not story:
            story = (self.root / outcome.output_path).read_text(encoding="utf-8")
        content = (
            "# Research story (working document)\n\n"
            f"- Topic source: [`{topic_path}`]({topic_path})\n"
            f"- Latest role: `{outcome.role}`\n"
            f"- Loop decision: `{outcome.decision}`\n"
            f"- Requirements digest: `{outcome.requirements_digest}`\n"
            f"- Round: `{outcome.round_id}`\n\n"
            "This file is intentionally editable. The next idea-loop invocation reads the\n"
            "edited content before proposing or challenging anything.\n\n"
            "## Current story\n\n"
            f"{str(story).strip()}\n"
        )
        path = self.root / "story.md"
        atomic_write(path, content)
        return path

    def _apply_files(self, files: dict[str, Any], allowed: tuple[str, ...]) -> list[str]:
        written = []
        for relative, content in files.items():
            candidate = Path(relative)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise PathPolicyViolation(f"unsafe output path: {relative}")
            normalized = candidate.as_posix()
            if not _is_within(normalized, allowed):
                raise PathPolicyViolation(
                    f"skill attempted to write '{normalized}', allowed paths are {allowed}"
                )
            atomic_write(self.root / normalized, str(content))
            written.append(normalized)
        return written

    def _run_command(self, command: str | None) -> tuple[str, bool | None]:
        if not command:
            return "No deterministic command configured for this round.", None
        argv = shlex.split(command)
        result = subprocess.run(
            argv,
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=3600,
            check=False,
        )
        report = (
            f"command: {argv!r}\nexit_code: {result.returncode}\n"
            f"stdout:\n{result.stdout[-12000:]}\nstderr:\n{result.stderr[-12000:]}"
        )
        return report, result.returncode == 0

    def _round(
        self,
        *,
        skill_name: str,
        role: str,
        task: str,
        allowed_paths: tuple[str, ...] = (),
        forbidden_paths: tuple[str, ...] = (),
        verify_freezes: tuple[str, ...] = (),
        post_command: str | None = None,
    ) -> tuple[RoundOutcome, dict[str, Any]]:
        for freeze in verify_freezes:
            self.freezes.verify(freeze)
        before = self.alignment.snapshot()
        stamp = utc_stamp()
        round_id = f"{stamp}-{skill_name}-{role}"
        run_dir = self.root / "runs" / round_id
        run_dir.mkdir(parents=True, exist_ok=False)
        skill = load_skill(skill_name)
        output_contract = """
# Machine-readable response contract

Return exactly one JSON object. Required keys:
- `content`: Markdown report or artifact content.
- `decision`: one of `continue`, `satisfied`, `blocked`, `report`.
- `summary`: one short sentence.
- `alignment`: object with `requirements_digest`, `preserved_constraints`, and
  `possible_drift`. The digest must exactly match the supplied digest.
- `files`: mapping of workspace-relative paths to full UTF-8 contents. Use an empty
  object when this role should not create files. Never write outside allowed paths.
"""
        legacy_adapter_boundary = """
# Legacy standalone adapter boundary

This prompt is running through the explicitly selected `autoresearch run` adapter. The
skill text also documents conversation-host commands; do not execute those commands here.
Return only the JSON response contract below. Preserve all scientific, alignment, freeze,
and path-policy rules from the skill.
"""
        prompt = "\n\n".join(
            [
                skill.body,
                legacy_adapter_boundary,
                self.alignment.prompt_block(before),
                f"# Round role\n\n{role}",
                f"# Allowed paths\n\n{allowed_paths or '(no direct file writes)'}",
                f"# Forbidden paths\n\n{forbidden_paths or '(none beyond the allowed-path rule)'}",
                f"# Task\n\n{task}",
                output_contract,
            ]
        )
        atomic_write(run_dir / "prompt.md", prompt)
        reply = self.agent.complete(
            AgentRequest(
                role=role,
                skill=skill_name,
                round_id=round_id,
                prompt=prompt,
                requirements_digest=before.digest,
                allowed_paths=allowed_paths,
                forbidden_paths=forbidden_paths,
            )
        )
        data = reply.data
        decision = str(data.get("decision", "report"))
        if decision not in {"continue", "satisfied", "blocked", "report"}:
            decision = "report"
        alignment = data.get("alignment") if isinstance(data.get("alignment"), dict) else {}
        possible_drift = str(alignment.get("possible_drift", "agent omitted alignment result"))
        if alignment.get("requirements_digest") != before.digest:
            decision = "report"
            possible_drift = "requirements digest missing or mismatched"
        written = self._apply_files(data.get("files", {}), allowed_paths)
        for freeze in verify_freezes:
            self.freezes.verify(freeze)
        command_output, command_ok = self._run_command(post_command)
        if post_command:
            atomic_write(run_dir / "command.txt", command_output + "\n")
        if decision == "satisfied" and command_ok is False:
            decision = "report"
            possible_drift = "agent declared satisfaction but the deterministic command failed"
        data["_command_output"] = command_output
        after = self.alignment.snapshot()
        if after.digest != before.digest:
            decision = "report"
            possible_drift = "requirements changed during the round; rerun against the new digest"
        output_path = run_dir / "output.md"
        atomic_write(output_path, reply.content.rstrip() + "\n")
        alignment_path = self.alignment.record(
            run_dir, role, after, decision, possible_drift=possible_drift
        )
        outcome = RoundOutcome(
            round_id=round_id,
            skill=skill_name,
            role=role,
            decision=decision,  # type: ignore[arg-type]
            output_path=output_path.relative_to(self.root).as_posix(),
            alignment_path=alignment_path.relative_to(self.root).as_posix(),
            requirements_digest=after.digest,
            summary=str(data.get("summary", "")),
        )
        write_json(
            run_dir / "manifest.json",
            {**outcome.as_dict(), "written_files": written, "message_files": after.message_files},
        )
        return outcome, data

    def idea_loop(
        self, topic_file: str = "topic.md", max_rounds: int = 8, sample_size: int = 3
    ) -> list[RoundOutcome]:
        if max_rounds < 1 or sample_size < 1:
            raise ValueError("max_rounds and sample_size must be positive")
        topic_document = TopicDocument(self.root)
        topic_path = topic_document.set_active(topic_file).relative_to(self.root).as_posix()
        history: list[RoundOutcome] = []
        challenger_feedback = "No prior challenger feedback."
        current_candidates: Any = []
        for iteration in range(1, max_rounds + 1):
            topic_content = topic_document.active_path().read_text(encoding="utf-8")
            working_story_path = self.root / "story.md"
            working_story = (
                working_story_path.read_text(encoding="utf-8")
                if working_story_path.exists()
                else "No working story exists yet."
            )
            scout_task = f"""Iteration {iteration}/{max_rounds}. Topic document: {topic_path}

Read this topic document as the authoritative direction and session-requirement record:

{topic_content}

Read the human-editable working story from the previous state:

{working_story}

Find a small set of promising, falsifiable ideas. Search current primary literature and
name direct collisions. For each idea include problem potential, scope, novelty boundary,
fair baselines, whether the problem is already solved, why existing work is insufficient,
a minimum motivation test, predicted outcome, and kill criteria. Incorporate the previous
challenge below without merely paraphrasing an excluded idea.

Previous challenge:
{challenger_feedback}

Also return a `candidates` array and a complete human-readable Markdown `story` in the JSON.
The story must contain the current problem, motivation evidence, closest collisions, scope,
design sketch, baselines, motivation tests, predictions, kill criteria, and open issues.
Stop with decision=report on a material research blocker; use decision=satisfied only when
an idea already meets all gates.
"""
            scout, scout_data = self._round(
                skill_name="idea-loop", role="idea-scout", task=scout_task
            )
            history.append(scout)
            self._update_idea_story(topic_path, scout, scout_data)
            current_candidates = scout_data.get("candidates", [])
            if scout.decision in {"blocked", "report", "satisfied"}:
                break
            if isinstance(current_candidates, list) and all(
                isinstance(item, dict) for item in current_candidates
            ):
                sampled = risk_stratified_sample(current_candidates, sample_size)
            else:
                sampled = current_candidates
            current_story = (self.root / "story.md").read_text(encoding="utf-8")
            challenge_task = f"""Iteration {iteration}/{max_rounds}. Topic document: {topic_path}

Authoritative topic and session requirements:

{topic_content}

Current human-editable story:

{current_story}

Challenge only this bounded sample (sample size={sample_size}) for efficient review:

{json.dumps(sampled, ensure_ascii=False, indent=2)}

Check exact prior-art collision, scope coherence, claim-to-test traceability, baseline
fairness, confounders, compute feasibility, and kill criteria. Do not generate a broad new
idea list. Return `challenge`, `surviving_candidates`, and a complete revised Markdown
`story` in the JSON. Preserve valid human edits from the current story. Use
decision=satisfied only if at least one candidate survives all gates; use decision=report
when a discovered issue requires the human; otherwise continue.
"""
            challenger, challenger_data = self._round(
                skill_name="idea-loop", role="idea-challenger", task=challenge_task
            )
            history.append(challenger)
            self._update_idea_story(topic_path, challenger, challenger_data)
            challenger_feedback = str(
                challenger_data.get("challenge") or challenger_data.get("content") or ""
            )
            if challenger.decision in {"blocked", "report", "satisfied"}:
                break
        if history and history[-1].decision not in {"blocked", "report", "satisfied"}:
            history.append(self._budget_report("idea-loop", history))
        return history

    def freeze_story(self, idea_path: str = "story.md", human_context: str = "") -> RoundOutcome:
        idea = self._workspace_path(idea_path).read_text(encoding="utf-8")
        task = f"""Convert the accepted idea and human intervention into the canonical
research contract. Fix the paper thesis, scope, non-claims, design, assumptions, baselines,
metrics, experiment matrix, falsifiable predictions, and kill/report criteria. This is a
research contract, not polished prose.

Accepted idea:
{idea}

Human intervention:
{human_context or '(already captured in the requirement journal)'}

Write the complete contract to `paper/STORY.md` through the `files` map and set
decision=satisfied only when it is internally consistent.
"""
        outcome, _ = self._round(
            skill_name="story-freeze",
            role="story-architect",
            task=task,
            allowed_paths=("paper/STORY.md",),
        )
        if outcome.decision == "satisfied":
            self.freezes.create("paper-story", ("paper/STORY.md",))
        return outcome

    def implementation_loop(
        self, max_rounds: int = 8, check_command: str | None = None
    ) -> list[RoundOutcome]:
        feedback, _ = self._run_command(check_command)
        history = []
        for iteration in range(1, max_rounds + 1):
            self.freezes.verify("paper-story")
            story = (self.root / "paper" / "STORY.md").read_text(encoding="utf-8")
            task = f"""Iteration {iteration}/{max_rounds}. Read `paper/STORY.md` in full.
Implement the fixed design and small-scale tests without changing the story, claim scope,
or design. Supporting exploration is allowed only when it validates an implementation
choice and cannot redefine the idea. Put durable implementation in `code/core/`, tests in
`code/tests/`, and supporting probes in `experiments/scripts/support/`.

Deterministic check from the previous state:
{feedback}

Frozen paper story (authoritative):
{story}

Return complete file contents in `files`. Use decision=satisfied only when the core design
is implemented and small-scale checks pass; report contradictions to the human.
"""
            outcome, round_data = self._round(
                skill_name="implementation-loop",
                role="implementation-agent",
                task=task,
                allowed_paths=("code/core", "code/tests", "experiments/scripts/support"),
                forbidden_paths=("paper",),
                verify_freezes=("paper-story",),
                post_command=check_command,
            )
            history.append(outcome)
            feedback = str(round_data.get("_command_output", ""))
            if outcome.decision in {"satisfied", "blocked", "report"}:
                break
        if history and history[-1].decision == "satisfied":
            self.freezes.create("core-code", ("code/core",))
        elif history and history[-1].decision not in {"blocked", "report"}:
            history.append(self._budget_report("implementation-loop", history))
        return history

    def experiment_loop(
        self, max_rounds: int = 8, run_command: str | None = None
    ) -> list[RoundOutcome]:
        feedback, _ = self._run_command(run_command)
        history = []
        for iteration in range(1, max_rounds + 1):
            self.freezes.verify("paper-story")
            self.freezes.verify("core-code")
            story = (self.root / "paper" / "STORY.md").read_text(encoding="utf-8")
            task = f"""Iteration {iteration}/{max_rounds}. Read `paper/STORY.md` in full.
Do not modify the paper or `code/core/`. You may only create or revise batch experiment
scripts and record conclusions/results. Follow the frozen matrix, preserve failed runs, and
separate measured evidence from inference. If results disagree with any frozen prediction,
set decision=report and explain the mismatch instead of changing the paper or core code.

Latest user-authorized batch command result:
{feedback}

Frozen paper story (authoritative):
{story}

Write scripts under `experiments/scripts/` and reports/data summaries under
`experiments/results/` through `files`.
"""
            outcome, round_data = self._round(
                skill_name="experiment-loop",
                role="experiment-agent",
                task=task,
                allowed_paths=("experiments/scripts", "experiments/results"),
                forbidden_paths=("paper", "code/core"),
                verify_freezes=("paper-story", "core-code"),
                post_command=run_command,
            )
            history.append(outcome)
            feedback = str(round_data.get("_command_output", ""))
            if outcome.decision in {"satisfied", "blocked", "report"}:
                break
        if history and history[-1].decision not in {"blocked", "report", "satisfied"}:
            history.append(self._budget_report("experiment-loop", history))
        return history

    def write_section(
        self, venue: str, section: str, accepted_corpus: str | None = None
    ) -> RoundOutcome:
        corpus = "No local accepted-paper corpus supplied; use primary venue sources."
        if accepted_corpus:
            corpus_root = self._workspace_path(accepted_corpus)
            excerpts = []
            for path in sorted(corpus_root.rglob("*")):
                if path.is_file() and path.suffix.lower() in {".md", ".txt", ".tex"}:
                    excerpts.append(f"## {path.name}\n{path.read_text(encoding='utf-8')[:30000]}")
            corpus = "\n\n".join(excerpts)[:120000]
        story = (self.root / "paper" / "STORY.md").read_text(encoding="utf-8")
        support = []
        for directory in (self.root / "paper" / "manuscript", self.root / "experiments" / "results"):
            for path in sorted(directory.rglob("*")):
                if path.is_file() and path.name != ".gitkeep" and path.suffix.lower() in {".md", ".txt", ".tex", ".json", ".csv"}:
                    support.append(f"## {path.relative_to(self.root)}\n{path.read_text(encoding='utf-8')[:30000]}")
        support_context = "\n\n".join(support)[:120000]
        task = f"""Venue: {venue}. Optimize only manuscript section: {section}.
Read the frozen `paper/STORY.md`, current manuscript, and experiment results. Study the
style and structural conventions of relevant papers accepted by this venue in the previous
calendar year, but never copy phrasing. Improve organization, clarity, precision, and venue
fit without changing frozen claims, design, experiment plan, or result values. Report any
needed scientific change instead of making it.

Accepted-paper corpus/context:
{corpus}

Frozen paper story (authoritative):
{story}

Current manuscript and result context:
{support_context or '(none yet)'}

Write only `paper/manuscript/{section}.md` through `files`.
"""
        outcome, _ = self._round(
            skill_name="section-writing",
            role=f"section-writer-{section}",
            task=task,
            allowed_paths=(f"paper/manuscript/{section}.md",),
            forbidden_paths=("paper/STORY.md", "code"),
            verify_freezes=("paper-story",),
        )
        return outcome

    def review(self, venue: str, venue_guide: str | None = None) -> RoundOutcome:
        guide = "Use the venue's current public reviewer guidance."
        if venue_guide:
            guide = self._workspace_path(venue_guide).read_text(encoding="utf-8")
        manuscript = []
        for path in sorted((self.root / "paper" / "manuscript").glob("*")):
            if path.is_file() and path.name != ".gitkeep":
                manuscript.append(f"## {path.name}\n\n{path.read_text(encoding='utf-8')}")
        manuscript_text = "\n\n".join(manuscript)
        story = (self.root / "paper" / "STORY.md").read_text(encoding="utf-8")
        task = f"""Review this manuscript for {venue} using the venue requirements below.
Do not edit the paper. Evaluate novelty, scope, correctness, evidence, baseline fairness,
reproducibility, ethics, writing, and venue fit. Separate fatal flaws from required fixes
and optional improvements; identify claim/evidence mismatches with exact locations.

Venue guidance:
{guide}

Manuscript:
{manuscript_text}

Frozen story used for claim-alignment review:
{story}

Write the review to `reviews/{venue.lower().replace(' ', '-')}.md` through `files`.
"""
        outcome, _ = self._round(
            skill_name="venue-review",
            role="venue-reviewer",
            task=task,
            allowed_paths=("reviews",),
            forbidden_paths=("paper", "code", "experiments"),
            verify_freezes=("paper-story",),
        )
        return outcome
