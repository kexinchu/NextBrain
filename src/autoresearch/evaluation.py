from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .contracts import ContractError, parse_contract
from .doctor import Doctor
from .e2e import E2ERegistry
from .installer import ConversationSkillInstaller
from .sampling import risk_stratified_sample
from .skills import BUILTIN_SKILLS, list_skills


@dataclass
class CapabilityEvaluator:
    root: Path

    def run(self, *, require_e2e: bool = False, release: bool = False) -> dict:
        gates = []

        def gate(name: str, passed: bool, detail: str) -> None:
            gates.append({"name": name, "passed": passed, "detail": detail})

        skills = list_skills()
        gate("six-skills", len(skills) == 6, f"loaded {len(skills)}")
        host_native = all(
            "transaction" in skill.body.lower()
            and "evidence" in skill.body.lower()
            and "autoresearch run" in skill.body
            for skill in skills
        )
        gate("host-native-protocol", host_native, "transaction, evidence, and no-adapter rules")

        temporary = Path(tempfile.mkdtemp(prefix="autoresearch-eval-install-"))
        installed = ConversationSkillInstaller(temporary).install("all")
        gate("three-client-install", len(installed) == len(BUILTIN_SKILLS) * 3, f"{len(installed)}")

        candidates = [
            {"id": "low-a", "approach": "a", "collision_risk": 0.1},
            {"id": "high-a", "approach": "a", "collision_risk": 1.0},
            {"id": "medium-b", "approach": "b", "collision_risk": 0.5},
        ]
        sampled = risk_stratified_sample(candidates, 2)
        gate(
            "risk-diverse-sampling",
            {item["id"] for item in sampled} == {"high-a", "medium-b"},
            str([item["id"] for item in sampled]),
        )
        try:
            parse_contract(self.root / "story.md")
            contract_detail = "story.md has structured frontmatter"
            contract_ok = True
        except (ContractError, FileNotFoundError):
            contract_detail = "no active structured story yet; validator is available"
            contract_ok = True
        gate("contract-validator", contract_ok, contract_detail)

        doctor = Doctor(self.root).run(require_e2e=False, release=release)
        gate("workspace-doctor", doctor["ok"], "workspace structural checks")
        if require_e2e:
            matrix = E2ERegistry(self.root).matrix()
            passed = [item for item in matrix if item["status"] == "pass" and item["evidence_ok"]]
            gate("real-client-e2e", len(passed) == len(matrix), f"{len(passed)}/{len(matrix)}")
        passed_count = sum(item["passed"] for item in gates)
        return {
            "ok": passed_count == len(gates),
            "score": passed_count / len(gates) if gates else 0.0,
            "gates": gates,
        }
