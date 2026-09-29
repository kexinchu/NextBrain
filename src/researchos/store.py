"""Versioned SQLite catalog, independent of any individual execution workspace."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .schema import SCHEMA_V2, SCHEMA_V3

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, current_revision TEXT NOT NULL,
 decision TEXT NOT NULL DEFAULT 'INBOX', updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
 id TEXT PRIMARY KEY, idea_id TEXT NOT NULL REFERENCES ideas(id),
 snapshot TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
 id TEXT PRIMARY KEY, idea_id TEXT NOT NULL REFERENCES ideas(id),
 revision_id TEXT NOT NULL REFERENCES revisions(id), value TEXT NOT NULL,
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, idea_id TEXT NOT NULL UNIQUE REFERENCES ideas(id),
 revision_id TEXT NOT NULL REFERENCES revisions(id), decision_id TEXT NOT NULL REFERENCES decisions(id),
 state TEXT NOT NULL, contract_digest TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 digest TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hypotheses (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
 data TEXT NOT NULL, digest TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dependencies (
 experiment_id TEXT NOT NULL REFERENCES experiments(id),
 dependency_id TEXT NOT NULL REFERENCES experiments(id), PRIMARY KEY(experiment_id, dependency_id),
 CHECK(experiment_id <> dependency_id)
);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 experiment_id TEXT NOT NULL REFERENCES experiments(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 path TEXT NOT NULL, digest TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS findings (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 experiment_id TEXT NOT NULL REFERENCES experiments(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS machines (
 id TEXT PRIMARY KEY, config_path TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS probes (
 id TEXT PRIMARY KEY, machine_id TEXT NOT NULL REFERENCES machines(id),
 data TEXT NOT NULL, created_at TEXT NOT NULL
);
"""
TABLES = frozenset(('ideas', 'revisions', 'decisions', 'projects', 'approvals', 'hypotheses',
                    'claims', 'experiments', 'runs', 'artifacts', 'findings', 'machines', 'probes',
                    'envelopes', 'object_approvals', 'scope_requests', 'experiment_freezes',
                    'executions', 'run_attempts', 'run_events', 'policy_decisions',
                    'uncertainties', 'planner_proposals', 'planner_decisions', 'research_assessments',
                    'controller_decisions', 'maturity_gates', 'advances'))


def encoded(data) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False)


class Store:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1, 2, 3):
                raise ValueError(f'unsupported ResearchOS schema version {version}')
            db.executescript(SCHEMA)
            db.executescript(SCHEMA_V2)
            db.executescript(SCHEMA_V3)
            db.execute("INSERT OR IGNORE INTO hypothesis_states SELECT id,'PROPOSED',NULL,created_at FROM hypotheses")
            db.execute('PRAGMA user_version=3')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / 'researchos.sqlite3', timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, table: str, record_id: str) -> dict:
        if table not in TABLES:
            raise ValueError('unknown record type')
        with self.connect() as db:
            row = db.execute(f'SELECT * FROM {table} WHERE id=?', (record_id,)).fetchone()
        if row is None:
            raise ValueError(f'{table}: unknown ID {record_id}')
        return dict(row)

    def list(self, table: str, project: str | None = None) -> list[dict]:
        if table not in TABLES:
            raise ValueError('unknown record type')
        with self.connect() as db:
            if project:
                if table not in {'hypotheses', 'claims', 'experiments', 'runs', 'findings', 'approvals', 'envelopes',
                                  'object_approvals', 'scope_requests', 'experiment_freezes',
                                  'executions', 'policy_decisions', 'uncertainties', 'planner_proposals',
                                  'planner_decisions', 'research_assessments', 'controller_decisions',
                                  'maturity_gates', 'advances'}:
                    raise ValueError('this record type has no project filter')
                rows = db.execute(f'SELECT * FROM {table} WHERE project_id=? ORDER BY rowid',
                                  (project,)).fetchall()
            else:
                rows = db.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
        return [dict(row) for row in rows]
