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
