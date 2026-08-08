from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .io import write_json


class WorkflowError(RuntimeError):
    pass


def default_workflow() -> dict:
    return {
        "version": 1,
        "pending_round": None,
        "idea": {
            "status": "idle",
            "next_role": "idea-scout",
            "iteration": 1,
            "max_rounds": 8,
            "sample_size": 3,
            "last_scout_agent": None,
        },
        "story": {"status": "idle", "draft_digest": None, "draft_message": None},
        "implementation": {"status": "idle"},
        "experiment": {"status": "idle"},
    }


@dataclass
class WorkflowState:
    root: Path

    @property
    def path(self) -> Path:
        return self.root / ".autoresearch" / "workflow.json"

    def load(self) -> dict:
        if not self.path.exists():
            return default_workflow()
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("version") != 1:
            raise WorkflowError("unsupported workflow state version")
        return value

    def save(self, state: dict) -> None:
        write_json(self.path, state)

    def begin(
        self,
        round_id: str,
        skill: str,
        role: str,
        message_file: str,
        *,
        max_rounds: int = 8,
        sample_size: int = 3,
    ) -> dict:
        state = self.load()
        if state["pending_round"]:
            raise WorkflowError(f"round already pending: {state['pending_round']}")
        if skill == "idea-loop":
            idea = state["idea"]
            if idea["status"] == "idle":
                if max_rounds < 1 or sample_size < 1:
                    raise WorkflowError("max_rounds and sample_size must be positive")
                idea.update(
                    status="running",
                    max_rounds=max_rounds,
                    sample_size=sample_size,
                    iteration=1,
                    next_role="idea-scout",
                )
            if idea["status"] != "running":
                raise WorkflowError("idea loop is terminal; record a human decision before restarting")
            if role != idea["next_role"]:
                raise WorkflowError(f"idea loop requires role {idea['next_role']}, not {role}")
        elif skill == "story-freeze" and state["idea"]["status"] != "satisfied":
            raise WorkflowError("story-freeze requires a challenger-accepted idea")
        elif skill == "implementation-loop" and state["story"]["status"] != "frozen":
            raise WorkflowError("implementation-loop requires a frozen story")
        elif skill == "experiment-loop" and state["implementation"]["status"] != "frozen":
            raise WorkflowError("experiment-loop requires frozen core implementation")
        elif skill == "section-writing" and state["experiment"]["status"] != "complete":
            raise WorkflowError("section-writing requires a completed experiment loop")
        elif skill == "venue-review" and state["story"]["status"] != "frozen":
            raise WorkflowError("venue-review requires a frozen story")
        state["pending_round"] = {
            "round_id": round_id,
            "skill": skill,
            "role": role,
            "message_file": message_file,
        }
        self.save(state)
        return state

    def complete(
        self,
        round_id: str,
        decision: str,
        *,
        agent_id: str | None = None,
        draft_digest: str | None = None,
    ) -> tuple[dict, str]:
        state = self.load()
        pending = state.get("pending_round")
        if not pending or pending.get("round_id") != round_id:
            raise WorkflowError("round is not the active pending round")
        skill = pending["skill"]
        role = pending["role"]
        final_decision = decision
        if skill == "idea-loop":
            idea = state["idea"]
            if decision == "satisfied" and role != "idea-challenger":
                final_decision = "report"
            if final_decision == "continue" and role == "idea-scout":
                idea["next_role"] = "idea-challenger"
                idea["last_scout_agent"] = agent_id
            elif final_decision == "continue" and role == "idea-challenger":
                if idea["iteration"] >= idea["max_rounds"]:
                    final_decision = "report"
                    idea["status"] = "report"
                else:
                    idea["iteration"] += 1
                    idea["next_role"] = "idea-scout"
            elif final_decision in {"satisfied", "blocked", "report"}:
                idea["status"] = final_decision
        elif skill == "story-freeze":
            if final_decision == "continue":
                state["story"].update(
                    status="draft",
                    draft_digest=draft_digest,
                    draft_message=pending["message_file"],
                )
            elif final_decision == "satisfied":
                state["story"]["status"] = "frozen"
        elif skill == "implementation-loop" and final_decision == "satisfied":
            state["implementation"]["status"] = "frozen"
        elif skill == "experiment-loop" and final_decision == "satisfied":
            state["experiment"]["status"] = "complete"
        state["pending_round"] = None
        self.save(state)
        return state, final_decision

    def abort(self, round_id: str) -> None:
        state = self.load()
        pending = state.get("pending_round")
        if pending and pending.get("round_id") == round_id:
            state["pending_round"] = None
            self.save(state)

    def reset(self, skill: str) -> dict:
        state = self.load()
        if state.get("pending_round"):
            raise WorkflowError("cannot reset while a round is pending")
        defaults = default_workflow()
        if skill == "idea-loop":
            state = defaults
        elif skill == "story-freeze":
            state["story"] = defaults["story"]
            state["implementation"] = defaults["implementation"]
            state["experiment"] = defaults["experiment"]
        elif skill == "implementation-loop":
            state["implementation"] = defaults["implementation"]
            state["experiment"] = defaults["experiment"]
        elif skill == "experiment-loop":
            state["experiment"] = defaults["experiment"]
        elif skill not in {"section-writing", "venue-review"}:
            raise WorkflowError(f"unknown skill: {skill}")
        self.save(state)
        return state
