"""Additive v2 migration. V0 research records and imported evidence remain readable."""
SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS envelopes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 digest TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_envelopes (
 project_id TEXT PRIMARY KEY REFERENCES projects(id), envelope_id TEXT NOT NULL REFERENCES envelopes(id)
);
CREATE TABLE IF NOT EXISTS object_approvals (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL,
 object_digest TEXT NOT NULL, message TEXT NOT NULL, message_digest TEXT NOT NULL,
 actor TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scope_requests (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), data TEXT NOT NULL,
 digest TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hypothesis_states (
 hypothesis_id TEXT PRIMARY KEY REFERENCES hypotheses(id), state TEXT NOT NULL,
 finding_id TEXT REFERENCES findings(id), updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiment_freezes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 experiment_id TEXT NOT NULL REFERENCES experiments(id), revision INTEGER NOT NULL,
 digest TEXT NOT NULL UNIQUE, data TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(experiment_id, revision)
);
CREATE TABLE IF NOT EXISTS executions (
 id TEXT PRIMARY KEY REFERENCES runs(id), project_id TEXT NOT NULL REFERENCES projects(id),
 experiment_id TEXT NOT NULL REFERENCES experiments(id), freeze_id TEXT NOT NULL REFERENCES experiment_freezes(id),
 experiment_digest TEXT NOT NULL, machine_alias TEXT NOT NULL, state TEXT NOT NULL,
 attempt INTEGER NOT NULL DEFAULT 0, max_retries INTEGER NOT NULL, reserved_gpu_hours REAL NOT NULL,
 reserved_cpu_hours REAL NOT NULL, receipt TEXT, failure TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_attempts (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES executions(id), attempt INTEGER NOT NULL,
 state TEXT NOT NULL, receipt TEXT, failure TEXT, completed_at TEXT, UNIQUE(run_id, attempt)
);
CREATE TABLE IF NOT EXISTS run_events (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES executions(id),
 state TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS policy_decisions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS findings_from_runs (
 run_id TEXT PRIMARY KEY REFERENCES executions(id), finding_id TEXT NOT NULL UNIQUE REFERENCES findings(id)
);
CREATE TABLE IF NOT EXISTS artifact_origins (
 run_id TEXT NOT NULL REFERENCES executions(id), attempt INTEGER NOT NULL, relative_path TEXT NOT NULL,
 artifact_id TEXT NOT NULL REFERENCES artifacts(id), PRIMARY KEY(run_id, attempt, relative_path)
);
CREATE TRIGGER IF NOT EXISTS immutable_execution_identity
BEFORE UPDATE OF project_id, experiment_id, freeze_id, experiment_digest, machine_alias ON executions
WHEN NEW.project_id != OLD.project_id OR NEW.experiment_id != OLD.experiment_id
 OR NEW.freeze_id != OLD.freeze_id OR NEW.experiment_digest != OLD.experiment_digest
 OR NEW.machine_alias != OLD.machine_alias
BEGIN SELECT RAISE(ABORT, 'run identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_experiment_freeze
BEFORE UPDATE ON experiment_freezes
BEGIN SELECT RAISE(ABORT, 'experiment snapshot is immutable'); END;
"""

SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS uncertainties (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 data TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS planner_proposals (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS planner_decisions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 state_digest TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_assessments (
 id TEXT PRIMARY KEY REFERENCES findings(id), project_id TEXT NOT NULL REFERENCES projects(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS controller_decisions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS maturity_gates (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 state_digest TEXT NOT NULL, digest TEXT NOT NULL, data TEXT NOT NULL,
 action TEXT, approval_id TEXT REFERENCES object_approvals(id), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advances (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 data TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advance_runs (
 advance_id TEXT NOT NULL REFERENCES advances(id), run_id TEXT NOT NULL UNIQUE REFERENCES executions(id),
 decision_id TEXT NOT NULL REFERENCES planner_decisions(id), PRIMARY KEY(advance_id,run_id)
);
CREATE TRIGGER IF NOT EXISTS immutable_planner_decision BEFORE UPDATE ON planner_decisions
BEGIN SELECT RAISE(ABORT, 'planner decision is immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_planner_proposal BEFORE UPDATE ON planner_proposals
BEGIN SELECT RAISE(ABORT, 'planner proposal is immutable'); END;
"""

SCHEMA_V4 = """
CREATE TABLE IF NOT EXISTS research_questions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL UNIQUE REFERENCES projects(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_edges (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_debt (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 data TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intelligence_notes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 finding_id TEXT REFERENCES findings(id), data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS immutable_research_question BEFORE UPDATE ON research_questions
BEGIN SELECT RAISE(ABORT, 'core question changes require scope review'); END;
CREATE TRIGGER IF NOT EXISTS immutable_intelligence_note BEFORE UPDATE ON intelligence_notes
BEGIN SELECT RAISE(ABORT, 'research journal evidence is append-only'); END;
"""
