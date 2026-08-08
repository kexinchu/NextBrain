from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .alignment import AlignmentGuard
from .config import ResearchConfig
from .contracts import ContractError, parse_contract, protocol_digest, validate_contract
from .evidence import ApprovalManager, CheckRunner, EvidenceError, load_evidence
from .freeze import FreezeGuard, FreezeViolation
from .io import atomic_write, sha256_file, utc_stamp, write_json
from .journal import UserMessageJournal
from .sampling import risk_stratified_sample
from .skills import BUILTIN_SKILLS, load_skill
from .snapshot import DEFAULT_GOVERNED_PATHS, IncrementalSnapshotter
from .transaction import RoundTransaction, TransactionError
from .venues import VenueError, resolve_venue
from .workflow import WorkflowError, WorkflowState


class HostRoundError(RuntimeError):
    pass


POLICIES = {
    "idea-loop": {
        "allowed": ("story.md",),
        "fresh": (),
        "freezes": (),
        "roles": ("idea-scout", "idea-challenger"),
    },
    "story-freeze": {
        "allowed": ("paper/STORY.md",),
        "fresh": (),
        "freezes": (),
        "roles": ("story-editor",),
    },
    "implementation-loop": {
        "allowed": ("code/core", "code/tests", "experiments/scripts/support"),
        "fresh": (),
        "freezes": ("paper-story",),
        "roles": ("implementer",),
    },
    "experiment-loop": {
        "allowed": ("experiments/scripts", "experiments/results"),
        "fresh": ("experiments/results",),
        "freezes": ("paper-story", "core-code"),
        "roles": ("experimenter",),
    },
    "section-writing": {
        "allowed": (),
        "fresh": (),
        "freezes": ("paper-story", "core-code"),
        "roles": ("section-writer",),
    },
    "venue-review": {
        "allowed": ("reviews",),
        "fresh": ("reviews",),
        "freezes": ("paper-story",),
        "roles": ("venue-reviewer",),
    },
}


def _allowed(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


def _changed(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _has_substantive_file(root: Path, relative: str) -> bool:
    path = root / relative
    if path.is_file() and not path.is_symlink():
        return path.stat().st_size > 0
    if not path.is_dir():
        return False
    return any(
        candidate.is_file()
        and not candidate.is_symlink()
        and candidate.name != ".gitkeep"
        and candidate.stat().st_size > 0
        for candidate in path.rglob("*")
    )


@dataclass
class HostRoundManager:
    """Evidence-gated transaction boundary for the current conversation model."""

    root: Path

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        self.alignment = AlignmentGuard(self.root)
        self.freezes = FreezeGuard(self.root)
        self.workflow = WorkflowState(self.root)
        self.snapshots = IncrementalSnapshotter(self.root)
        self.state_dir = self.root / ".autoresearch" / "host-rounds"

    def _state(self, round_id: str) -> tuple[Path, dict]:
        path = self.state_dir / f"{round_id}.json"
        if not path.exists():
            raise HostRoundError(f"unknown host round: {round_id}")
        state = json.loads(path.read_text(encoding="utf-8"))
        return path, state

    def _control_files(self, freezes: Iterable[str]) -> dict[str, str]:
        paths = [
            self.root / "autoresearch.yaml",
            self.root / ".autoresearch" / "active-topic.json",
            self.root / ".autoresearch" / "workflow.json",
        ]
        paths.extend(self.root / ".autoresearch" / "freezes" / f"{name}.json" for name in freezes)
        return {
            path.relative_to(self.root).as_posix(): sha256_file(path)
            for path in paths
            if path.is_file()
        }

    def begin(
        self,
        skill_name: str,
        role: str,
        *,
        message_file: str,
        section: str | None = None,
        venue: str | None = None,
        max_rounds: int = 8,
        sample_size: int = 3,
    ) -> dict:
        if skill_name not in BUILTIN_SKILLS:
            raise HostRoundError(f"unknown skill: {skill_name}")
        policy = POLICIES[skill_name]
        if role not in policy["roles"]:
            expected = ", ".join(policy["roles"])
            raise HostRoundError(f"invalid role for {skill_name}: {role}; expected {expected}")

        journal = UserMessageJournal(self.root)
        bound_message = journal.resolve(message_file)
        if bound_message != journal.latest():
            raise HostRoundError("host begin must bind the latest recorded user message")

        allowed_paths = tuple(policy["allowed"])
        fresh_paths = tuple(policy["fresh"])
        if skill_name == "section-writing":
            if not section or Path(section).name != section:
                raise HostRoundError("section-writing requires a simple --section name")
            allowed_paths = (f"paper/manuscript/{section}.md",)
        if skill_name in {"section-writing", "venue-review"} and not venue:
            raise HostRoundError(f"{skill_name} requires --venue")
        venue_profile = None
        if venue:
            try:
                venue_profile = resolve_venue(venue)
            except VenueError as exc:
                raise HostRoundError(str(exc)) from exc
            venue = venue_profile.canonical
        for freeze in policy["freezes"]:
            self.freezes.verify(freeze)
        if venue_profile and skill_name in {"section-writing", "venue-review"}:
            frozen_targets = {
                resolve_venue(name).canonical
                for name in parse_contract(self.root / "paper" / "STORY.md").metadata.get(
                    "target_venues", []
                )
            }
            if venue_profile.canonical not in frozen_targets:
                raise HostRoundError(
                    f"{venue_profile.canonical} is not a frozen target venue: "
                    f"{sorted(frozen_targets)}"
                )

        snapshot = self.alignment.snapshot()
        round_id = f"{utc_stamp()}-{skill_name}-{role}-host"
        run_dir = self.root / "runs" / round_id
        run_dir.mkdir(parents=True, exist_ok=False)
        try:
            workflow = self.workflow.begin(
                round_id,
                skill_name,
                role,
                bound_message.name,
                max_rounds=max_rounds,
                sample_size=sample_size,
            )
            transaction = RoundTransaction(
                self.root,
                round_id,
                allowed_paths,
                fresh_paths=fresh_paths,
            )
            staged_before = transaction.create()
        except Exception:
            self.workflow.abort(round_id)
            raise

        sample_plan = None
        if skill_name == "idea-loop" and role == "idea-challenger":
            try:
                contract = validate_contract(self.root / "story.md", stage="idea-story")
                candidates = contract.metadata["candidates"]
                sampled = risk_stratified_sample(candidates, workflow["idea"]["sample_size"])
            except (ContractError, FileNotFoundError) as exc:
                self.workflow.abort(round_id)
                raise HostRoundError(f"challenger requires a valid story contract: {exc}") from exc
            sample_plan = {
                "strategy": "risk-stratified-diverse",
                "sample_size": workflow["idea"]["sample_size"],
                "candidate_ids": [item["id"] for item in sampled],
                "candidates": sampled,
            }
            write_json(run_dir / "sample-plan.json", sample_plan)

        config = ResearchConfig(self.root)
        before_main = self.snapshots.snapshot(exclude=config.excluded_snapshot_paths())
        transaction.backup_main(
            DEFAULT_GOVERNED_PATHS,
            exclude=config.excluded_snapshot_paths(),
        )
        transaction.backup_main(self._control_files(policy["freezes"]).keys())
        evidence_path = transaction.directory / "evidence.json"
        skill = load_skill(skill_name)
        prompt = (
            f"{skill.body}\n\n"
            f"{self.alignment.prompt_block(snapshot)}\n\n"
            "# Configured research and venue scope\n\n"
            f"{config.venue_context()}\n\n"
            "# Evidence-gated host transaction\n\n"
            "Use the model selected in this conversation. Never call another model API. "
            "Read source artifacts from the main workspace, but write every proposed artifact "
            "under the transaction workspace below. Direct main-workspace edits invalidate "
            "the round. Only validated staged files are promoted.\n\n"
            f"- Round ID: `{round_id}`\n"
            f"- Role: `{role}`\n"
            f"- Target venue: `{venue or 'not applicable'}`\n"
            f"- Bound user message: `{bound_message.name}`\n"
            f"- Transaction workspace: `{transaction.workspace}`\n"
            f"- Logical allowed paths: `{allowed_paths}`\n"
            f"- Evidence manifest: `{evidence_path}`\n"
            f"- Requirements digest: `{snapshot.digest}`\n"
        )
        if venue_profile:
            prompt += (
                f"- Selected venue family: `{venue_profile.family}`\n"
                f"- Selected venue contribution focus: "
                f"`{'; '.join(venue_profile.contribution_focus)}`\n"
                f"- Seed official sources (refresh current guidance): "
                f"`{venue_profile.official_sources}`\n"
            )
        if sample_plan:
            prompt += f"- Challenger sample plan: `{run_dir / 'sample-plan.json'}`\n"
        prompt += (
            "\nWrite a schema_version=1 JSON evidence manifest with round_id, message_file, "
            "artifacts, and the skill-specific evidence requested by the skill. Run only "
            "human-authorized checks through `autoresearch host check`. Then complete the round.\n"
        )
        prompt_path = run_dir / "prompt.md"
        atomic_write(prompt_path, prompt)
        state = {
            "round_id": round_id,
            "skill": skill_name,
            "role": role,
            "section": section,
            "venue": venue,
            "venue_profile": venue_profile.as_dict() if venue_profile else None,
            "status": "pending",
            "created_at": utc_stamp(),
            "message_file": bound_message.name,
            "requirements_digest": snapshot.digest,
            "allowed_paths": allowed_paths,
            "fresh_paths": fresh_paths,
            "required_freezes": policy["freezes"],
            "before_main": before_main,
            "before_control": self._control_files(policy["freezes"]),
            "staged_before": staged_before,
            "prompt_path": prompt_path.relative_to(self.root).as_posix(),
            "transaction_workspace": transaction.workspace.as_posix(),
            "evidence_path": evidence_path.relative_to(self.root).as_posix(),
            "sample_plan": sample_plan,
        }
        write_json(self.state_dir / f"{round_id}.json", state)
        write_json(run_dir / "host-state.json", state)
        return {
            "round_id": round_id,
            "prompt_path": state["prompt_path"],
            "transaction_workspace": state["transaction_workspace"],
            "evidence_path": state["evidence_path"],
            "requirements_digest": snapshot.digest,
            "allowed_paths": allowed_paths,
        }

    def check(self, round_id: str, command_name: str) -> dict:
        _, state = self._state(round_id)
        if state["status"] != "pending":
            raise HostRoundError(f"host round is already {state['status']}")
        transaction = RoundTransaction(
            self.root,
            round_id,
            tuple(state["allowed_paths"]),
            tuple(state["fresh_paths"]),
        )
        return CheckRunner(self.root).run(state, command_name, transaction.workspace)

    def approve_story(self, message_file: str) -> dict:
        journal = UserMessageJournal(self.root)
        message = journal.resolve(message_file)
        if message != journal.latest():
            raise HostRoundError("approval must bind the latest recorded user message")
        workflow = self.workflow.load()
        story = workflow["story"]
        if story["status"] != "draft" or not story["draft_digest"]:
            raise HostRoundError("no story draft is waiting for approval")
        path = self.root / "paper" / "STORY.md"
        if sha256_file(path) != story["draft_digest"]:
            raise HostRoundError("paper/STORY.md changed after the draft round")
        if message.name == story["draft_message"]:
            raise HostRoundError("approval requires a later user message")
        expected = f"APPROVE paper/STORY.md {story['draft_digest']}"
        if expected not in journal.body(message).splitlines():
            raise HostRoundError(f"approval message must contain the exact line: {expected}")
        return ApprovalManager(self.root).create("paper/STORY.md", message.name)

    def reset(self, skill: str, message_file: str) -> dict:
        journal = UserMessageJournal(self.root)
        message = journal.resolve(message_file)
        if message != journal.latest():
            raise HostRoundError("workflow reset must bind the latest user message")
        return self.workflow.reset(skill)

    def _evidence(self, state: dict) -> tuple[dict, list[str]]:
        errors = []
        try:
            value = load_evidence(
                self.root / state["evidence_path"],
                state["round_id"],
                state["message_file"],
            )
        except (EvidenceError, OSError, json.JSONDecodeError) as exc:
            return {}, [str(exc)]
        return value, errors

    def complete(
        self,
        round_id: str,
        decision: str,
        *,
        summary: str = "",
        output_file: str | None = None,
    ) -> dict:
        if decision not in {"continue", "satisfied", "blocked", "report"}:
            raise HostRoundError("invalid decision")
        state_path, state = self._state(round_id)
        if state["status"] != "pending":
            raise HostRoundError(f"host round is already {state['status']}")

        run_dir = self.root / "runs" / round_id
        transaction = RoundTransaction(
            self.root,
            round_id,
            tuple(state["allowed_paths"]),
            tuple(state["fresh_paths"]),
        )
        hard_errors: list[str] = []
        staged_changed, staged_violations = transaction.changes(state["staged_before"])
        if staged_violations:
            hard_errors.append(f"invalid staged paths: {', '.join(staged_violations)}")

        config = ResearchConfig(self.root)
        current_main = self.snapshots.snapshot(
            exclude=config.excluded_snapshot_paths(), verify_content=True
        )
        direct_changes = _changed(state["before_main"], current_main)
        if direct_changes:
            hard_errors.append(f"direct main-workspace edits: {', '.join(direct_changes)}")
        control_changes = _changed(
            state["before_control"], self._control_files(state["required_freezes"])
        )
        if control_changes:
            hard_errors.append(f"control-plane drift: {', '.join(control_changes)}")
        restored_direct = []
        if direct_changes or control_changes:
            try:
                restored_direct = transaction.restore_direct_changes(
                    sorted(set(direct_changes) | set(control_changes))
                )
            except TransactionError as exc:
                hard_errors.append(str(exc))
        for freeze in state["required_freezes"]:
            try:
                self.freezes.verify(freeze)
            except (FreezeViolation, FileNotFoundError) as exc:
                hard_errors.append(str(exc))

        alignment = self.alignment.snapshot()
        if alignment.digest != state["requirements_digest"]:
            hard_errors.append("requirements changed during the host-model round")

        evidence, evidence_errors = self._evidence(state)
        if decision in {"continue", "satisfied", "report"}:
            hard_errors.extend(evidence_errors)
        artifacts = evidence.get("artifacts", []) if evidence else []
        invalid_artifacts = [
            item for item in artifacts if not _allowed(item, state["allowed_paths"])
        ]
        if invalid_artifacts:
            hard_errors.append(f"evidence names forbidden artifacts: {', '.join(invalid_artifacts)}")
        missing_changed = [
            item
            for item in artifacts
            if item not in staged_changed
            and not (state["skill"] == "story-freeze" and decision == "satisfied")
        ]
        if missing_changed:
            hard_errors.append(f"evidence artifacts were not changed this round: {', '.join(missing_changed)}")

        staged_root = transaction.workspace
        agent_id = None
        draft_digest = None
        semantic_report = None
        try:
            if state["skill"] == "idea-loop" and decision != "blocked":
                if "story.md" not in artifacts:
                    raise EvidenceError("idea evidence must name story.md")
                validate_contract(staged_root / "story.md", stage="idea-story")
                subagents = evidence.get("subagents", [])
                matching = [item for item in subagents if item.get("role") == state["role"]]
                if len(matching) != 1 or not matching[0].get("agent_id"):
                    raise EvidenceError("idea round requires exactly one identified role subagent")
                agent_id = str(matching[0]["agent_id"])
                workflow = self.workflow.load()
                if (
                    state["role"] == "idea-challenger"
                    and agent_id == workflow["idea"].get("last_scout_agent")
                ):
                    raise EvidenceError("challenger must be independent from the scout")
                if state["role"] == "idea-challenger":
                    expected = state["sample_plan"]["candidate_ids"]
                    if evidence.get("sampled_candidate_ids") != expected:
                        raise EvidenceError("challenger evidence does not match the sample plan")
            elif state["skill"] == "story-freeze" and decision != "blocked":
                contract_path = staged_root / "paper" / "STORY.md"
                validate_contract(contract_path, stage="paper-story")
                draft_digest = sha256_file(contract_path)
                if decision == "satisfied":
                    story_state = self.workflow.load()["story"]
                    if story_state["status"] != "draft" or story_state["draft_digest"] != draft_digest:
                        raise EvidenceError("satisfied story must exactly match the prior draft")
                    ApprovalManager(self.root).verify(
                        "paper/STORY.md",
                        draft_digest,
                        draft_message=story_state["draft_message"],
                        approval_message=state["message_file"],
                    )
                elif "paper/STORY.md" not in artifacts:
                    raise EvidenceError("story draft evidence must name paper/STORY.md")
            elif state["skill"] == "implementation-loop" and decision == "satisfied":
                for relative in ("code/core", "code/tests"):
                    if not _has_substantive_file(staged_root, relative):
                        raise EvidenceError(f"substantive staged artifact is missing: {relative}")
                if not CheckRunner(self.root).successful(round_id, staged_root):
                    raise EvidenceError(
                        "implementation satisfaction requires a successful authorized check "
                        "bound to the current staged contents"
                    )
            elif state["skill"] == "experiment-loop" and decision != "blocked":
                story_contract = parse_contract(self.root / "paper" / "STORY.md")
                experiment_map = {
                    item["id"]: {
                        "claim_ids": set(item.get("claim_ids", [])),
                        "protocol_digest": protocol_digest(item),
                    }
                    for item in story_contract.metadata.get("experiments", [])
                }
                expected = set(experiment_map)
                cells = evidence.get("experiment_cells", [])
                if not isinstance(cells, list) or not all(
                    isinstance(item, dict) for item in cells
                ):
                    raise EvidenceError("experiment_cells must be a list of mappings")
                observed = {item.get("id") for item in cells}
                for cell in cells:
                    if cell.get("status") not in {
                        "completed",
                        "failed",
                        "skipped",
                        "contradiction",
                    }:
                        raise EvidenceError("experiment cell has an invalid status")
                    result_paths = cell.get("result_paths", [])
                    if not result_paths or any(
                        path not in artifacts or path not in staged_changed for path in result_paths
                    ):
                        raise EvidenceError("experiment cell results must be new evidence artifacts")
                    frozen = experiment_map.get(cell.get("id"))
                    if frozen is None:
                        raise EvidenceError("experiment cell is absent from the frozen matrix")
                    if set(cell.get("claim_ids", [])) != frozen["claim_ids"]:
                        raise EvidenceError("experiment cell claim IDs differ from the frozen matrix")
                    if cell.get("protocol_digest") != frozen["protocol_digest"]:
                        raise EvidenceError("experiment cell protocol digest differs from frozen plan")
                    if not cell.get("configuration_digest"):
                        raise EvidenceError("experiment cell requires a configuration digest")
                contradictions = [item for item in cells if item.get("status") == "contradiction"]
                if contradictions:
                    semantic_report = "experiment evidence contradicts the frozen story"
                if decision == "satisfied":
                    if observed != expected:
                        raise EvidenceError("experiment evidence does not cover the frozen matrix")
                    if not CheckRunner(self.root).successful(round_id, staged_root):
                        raise EvidenceError(
                            "experiment satisfaction requires a successful authorized check "
                            "bound to the current staged contents"
                        )
            elif state["skill"] == "section-writing" and decision != "blocked":
                expected = {item["id"] for item in parse_contract(
                    self.root / "paper" / "STORY.md"
                ).metadata.get("claims", [])}
                if set(evidence.get("preserved_claim_ids", [])) != expected:
                    raise EvidenceError("writing evidence must preserve every frozen claim id")
                if evidence.get("new_claims"):
                    raise EvidenceError("section writing cannot introduce new claims")
                if evidence.get("venue") != state["venue"]:
                    raise EvidenceError("writing evidence venue differs from the bound venue")
                sources = evidence.get("style_sources", [])
                if not isinstance(sources, list) or not sources or not all(
                    isinstance(item, dict)
                    and item.get("title")
                    and item.get("url")
                    and item.get("venue") == state["venue"]
                    and item.get("year")
                    and item.get("accessed_at")
                    for item in sources
                ):
                    raise EvidenceError("writing requires complete bound-venue style sources")
            elif state["skill"] == "venue-review" and decision == "satisfied":
                if not artifacts or not all(item in staged_changed for item in artifacts):
                    raise EvidenceError("review satisfaction requires a new review artifact")
                if evidence.get("venue") != state["venue"]:
                    raise EvidenceError("review evidence venue differs from the bound venue")
                guidance = evidence.get("venue_guidance_sources", [])
                if not isinstance(guidance, list) or not guidance or not all(
                    isinstance(item, dict)
                    and item.get("title")
                    and item.get("url")
                    and item.get("accessed_at")
                    for item in guidance
                ):
                    raise EvidenceError("review requires current venue-guidance sources")
                reviewer = evidence.get("reviewer")
                if not isinstance(reviewer, dict) or reviewer.get("mode") not in {
                    "independent-subagent",
                    "current-model",
                }:
                    raise EvidenceError("review evidence must disclose reviewer independence")
                if reviewer["mode"] == "independent-subagent" and not reviewer.get("agent_id"):
                    raise EvidenceError("independent reviewer requires a host agent id")
        except (
            AttributeError,
            ContractError,
            EvidenceError,
            FileNotFoundError,
            KeyError,
            TypeError,
        ) as exc:
            hard_errors.append(str(exc))

        if output_file:
            if not _allowed(output_file, state["allowed_paths"]):
                hard_errors.append("output file is outside the round allowlist")
            elif output_file not in artifacts:
                hard_errors.append("output file is not declared in the evidence manifest")

        if semantic_report:
            decision = "report"
        if hard_errors:
            decision = "report"

        promoted: list[str] = []
        if not hard_errors and decision in {"continue", "satisfied", "report"}:
            try:
                promoted = transaction.promote(staged_changed)
            except TransactionError as exc:
                hard_errors.append(str(exc))
                decision = "report"

        try:
            _, decision = self.workflow.complete(
                round_id,
                decision,
                agent_id=agent_id,
                draft_digest=draft_digest,
            )
        except WorkflowError as exc:
            hard_errors.append(str(exc))
            decision = "report"
            if promoted:
                transaction.restore_direct_changes(promoted)
                promoted = []
            self.workflow.abort(round_id)

        if not hard_errors and decision == "satisfied" and state["skill"] == "story-freeze":
            self.freezes.create("paper-story", ("paper/STORY.md",))
        if not hard_errors and decision == "satisfied" and state["skill"] == "implementation-loop":
            self.freezes.create("core-code", ("code/core",))

        if output_file and (staged_root / output_file).is_file():
            try:
                output = (staged_root / output_file).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                output = summary or f"Binary artifact: {output_file}"
        else:
            output = summary or f"Host-model round completed with decision `{decision}`."
        atomic_write(run_dir / "output.md", output.rstrip() + "\n")
        possible_drift = "; ".join(hard_errors) if hard_errors else semantic_report or "none"
        alignment_path = self.alignment.record(
            run_dir,
            state["role"],
            alignment,
            decision,
            possible_drift=possible_drift,
        )
        state.update(
            status="complete",
            completed_at=utc_stamp(),
            decision=decision,
            summary=summary,
            staged_changed=staged_changed,
            direct_changes=direct_changes,
            restored_direct_changes=restored_direct,
            hard_errors=hard_errors,
            promoted_files=promoted,
            alignment_path=alignment_path.relative_to(self.root).as_posix(),
        )
        write_json(state_path, state)
        write_json(run_dir / "host-state.json", state)
        result = {
            "round_id": round_id,
            "decision": decision,
            "promoted_files": promoted,
            "hard_errors": hard_errors,
            "alignment_path": state["alignment_path"],
        }
        if hard_errors:
            raise HostRoundError(json.dumps(result, ensure_ascii=False))
        return result
