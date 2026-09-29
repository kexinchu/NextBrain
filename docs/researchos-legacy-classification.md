# Legacy component classification for V0.2

The cleanup criterion is active dependency and scientific responsibility, not file age.
No complete module can safely be deleted in this iteration. Reusable infrastructure stays.

| Classification | Component | Reason |
|---|---|---|
| REUSE | `researchos/execution.py`, `transport.py`, `worker.py`, `freeze.py` | V0.1 remains the execution primitive. Only evidence labeling, bounded transport deadlines, resource checks and a completion-inspection race fix were added. |
| REUSE | `researchos/store.py`, `schema.py`, `policy.py`, `ssh.py` | Additive schema v3, approvals, budgets and resource inventory support the coordinator. |
| REUSE | AutoResearch journal, evidence, transaction, alignment, snapshot and hash primitives | Active dependencies preserve provenance, rollback and integrity. |
| KEEP | AutoResearch paper workflow, admission, freeze guard, writing and venue-review skills | Downstream of Human Gate #2 for enabled ResearchOS projects; standalone workspaces remain supported. |
| KEEP | Provider adapters and client installers | Optional vendor-neutral interfaces remain independently useful. |
| DEPRECATE | `next_experiment.legacy_next` | Compatibility for projects without uncertainties. New projects should add uncertainties and use the durable planner. Existing users and regression tests still depend on its output. |
| DEPRECATE | V0 contract-first execution guidance | Superseded for exploration by Project Envelope plus per-experiment freeze. Old contract/handoff commands remain available for old data and downstream paper admission. |
| KEEP | Manual run/Finding imports | Useful historical records, explicitly UNVERIFIED; never used as executor-certified scientific support. |
| DELETE | No additional complete component | The generic contradiction-to-human-escalation path was already removed in V0.1. No remaining module was proven unused and superseded. |

The new planner does not duplicate subprocess management, SSH execution, artifact collection,
run retry logic or numeric scientific interpretation. It delegates these to V0.1. There is no
new multi-agent system, provider SDK dependency, literature crawler or paper-writing engine.
