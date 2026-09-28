# ResearchOS V0 validation — 2026-09-28

## Delivered

The V0 catalog and CLI are implemented on the latest `origin/master` baseline (`fac564a`).
No supplied `NextBrain-ResearchOS-V0` archive was found in the inspected attachment,
Downloads, Desktop, Documents, or Github locations, so this implementation follows the
provided specification and reuses the existing engine components directly.

Changes are in `src/researchos/`, `src/autoresearch/admission.py`, the ResearchOS tests and
documentation, package entry points/version, runtime ignore rules, and a Python 3.11/3.13 CI
workflow. The original user requirements and implementation request are journaled and mirrored
in `topic.md`. Existing uncommitted engine/skill changes in the user's original checkout are
preserved and are not included in this branch.

## Verification

- Main-branch baseline plus ResearchOS: **56 tests passed**.
- Compatibility against the original checkout's uncommitted engine changes: **61 tests passed**.
- `ruff check .`: passed.
- Source distribution and wheel build: passed.
- Installed 0.4.0 wheel: **15 CLI calls** completed the local functional flow in a temporary
  catalog, including prediction, manual run report, artifact copy, finding and contradiction stop.
- SQLite `integrity_check`: `ok`; `foreign_key_check`: no violations.
- `autoresearch skills list`: all six existing skills available.
- Actual upstream decision packet: five candidates detected, each with its linked full plan;
  zero unresolved links. All remain INBOX; no real research idea was approved during development.
- No remote experiment was executed. Synthetic tests are not scientific results.

The CLI exposes scan/inbox/decide, contract check/approve, hypothesis/claim/experiment/run/finding
add/list, experiment readiness, artifact ingestion, context, handoff, SSH import/probe/list and
status. SQLite schema version 1 contains the research objects, source revisions, human approval
history, experiment edges, artifacts and probe history. Hand-entered results stay UNVERIFIED.

## Live machine inventory

| SSH alias | Observed hardware / outcome | Environment |
|---|---|---|
| cloudsys01.engr.uconn.edu | 2 × NVIDIA RTX A6000, 49,140 MiB each | Python 3.10.12; driver 610.57.04; CUDA toolkit 11.5 reported by nvcc; Git 2.34.1; Docker CLI 29.7.2 |
| cloudsys02.engr.uconn.edu | 2 × NVIDIA RTX A6000, 49,140 MiB each | Python 3.10.12; driver 610.57.04; nvcc not reported on default PATH; Git 2.34.1; Docker CLI 29.6.0 |
| kexin-server | No route to host | GPU and environment unknown |
| 6787p | Strict SSH host-key verification failed because the recorded key differs | GPU and environment unknown |

Both A6000 hosts report a driver CUDA UMD version of 13.3, which is distinct from an installed
CUDA toolkit version. `df` reports root usage of 87% on cloudsys01 and 100% on cloudsys02
(with about 20.8 GiB available on the latter). No disk cleanup or environment changes were made.
Docker CLI availability does not prove daemon access. Default Python 3.10 is below NextBrain's
3.11 minimum; suitable project/container interpreters have not yet been selected.

Inventory is stored locally, outside Git. Host-key files, credentials and existing server
experiments were not changed. The RTX 4060 mapping remains unverified.

## Existing engine components reused

- `ResearchWorkspace` for normal project layout and configuration.
- `UserMessageJournal` for immutable admission records and topic mirroring.
- `validate_contract` and `protocol_digest` for story and protocol identities.
- `RoundTransaction` for explicit external-idea staging and allowlisted promotion.
- `WorkflowState` for admission into the normal story-freeze sequence.
- `ResearchConfig` for human-authorized command names.
- `FreezeGuard` for reporting actual execution freezes.

External admission is separate from story approval. The existing draft/review/hash approval,
implementation freeze, check receipts and experiment evidence requirements remain in place.

## Remaining operational blockers and V0.1

V0 local catalog acceptance passes. Full three-machine environment acceptance is incomplete:
the 4060 host is not yet identified, and the reachable servers need an appropriate Python
runtime and a verified experiment storage location. Changed SSH host keys require independent
human verification before updating trust records.

V0.1 should start with a single isolated 4060 execution: record prediction before dispatch,
reserve bounded resources, capture an executor receipt, recover interrupted runs, and verify
artifacts. Then add A6000 promotion and replication. Catalog approval must never bypass a
frozen story/core boundary. Source revisions, contract revisions after handoff, verified run
imports and automated budget accounting are deliberately not automated in V0.
