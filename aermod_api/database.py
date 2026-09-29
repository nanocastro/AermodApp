from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from .schemas import ProjectCreate, ScenarioCreate


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    responsible TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scenarios (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id),
                    name TEXT NOT NULL,
                    definition_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
                    status TEXT NOT NULL CHECK(status IN ('pending','running','completed','failed')),
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    result_json TEXT
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    UNIQUE(run_id, relative_path)
                );
                CREATE TABLE IF NOT EXISTS environment_jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL CHECK(kind IN ('surface','stations')),
                    latitude_deg REAL NOT NULL,
                    longitude_deg REAL NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','running','completed','failed')),
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    result_json TEXT,
                    progress_current INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER NOT NULL DEFAULT 0,
                    progress_label TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_scenarios_project ON scenarios(project_id);
                CREATE INDEX IF NOT EXISTS idx_runs_scenario ON runs(scenario_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);
                """
            )
            run_columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
            for name, declaration in (
                ("progress_current", "INTEGER NOT NULL DEFAULT 0"),
                ("progress_total", "INTEGER NOT NULL DEFAULT 0"),
                ("progress_label", "TEXT NOT NULL DEFAULT ''"),
            ):
                if name not in run_columns:
                    connection.execute(f"ALTER TABLE runs ADD COLUMN {name} {declaration}")

    def ping(self) -> None:
        with self.connect() as connection:
            connection.execute("SELECT 1").fetchone()

    def create_project(self, project: ProjectCreate) -> sqlite3.Row:
        identifier = str(uuid4())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
                (identifier, project.name, project.description, project.responsible, utc_now()),
            )
        return self.get_project(identifier)

    def get_project(self, identifier: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM projects WHERE id = ?", (identifier,)).fetchone()

    def list_projects(self) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()

    def create_scenario(self, project_id: str, scenario: ScenarioCreate) -> sqlite3.Row:
        identifier = str(uuid4())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO scenarios VALUES (?, ?, ?, ?, ?)",
                (
                    identifier,
                    project_id,
                    scenario.name,
                    scenario.definition.model_dump_json(),
                    utc_now(),
                ),
            )
        return self.get_scenario(identifier)

    def get_scenario(self, identifier: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM scenarios WHERE id = ?", (identifier,)).fetchone()

    def list_scenarios(self, project_id: str) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM scenarios WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()

    def create_run(self, scenario_id: str) -> sqlite3.Row:
        identifier = str(uuid4())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runs (id, scenario_id, status, created_at) VALUES (?, ?, 'pending', ?)",
                (identifier, scenario_id, utc_now()),
            )
        return self.get_run(identifier)

    def get_run(self, identifier: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM runs WHERE id = ?", (identifier,)).fetchone()

    def list_runs(self, scenario_id: str) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM runs WHERE scenario_id = ? ORDER BY created_at DESC",
                (scenario_id,),
            ).fetchall()

    def mark_run_running(self, identifier: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET status = 'running', started_at = ? WHERE id = ?",
                (utc_now(), identifier),
            )

    def update_run_progress(self, identifier: str, current: int, total: int, label: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET progress_current = ?, progress_total = ?, progress_label = ? WHERE id = ?",
                (current, total, label[:160], identifier),
            )

    def mark_run_completed(self, identifier: str, result: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET status = 'completed', finished_at = ?, result_json = ?, progress_current = progress_total, progress_label = 'Resultados listos' WHERE id = ?",
                (utc_now(), json.dumps(result), identifier),
            )

    def mark_run_failed(self, identifier: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET status = 'failed', finished_at = ?, error = ? WHERE id = ?",
                (utc_now(), error[:4000], identifier),
            )

    def add_artifact(
        self,
        run_id: str,
        *,
        name: str,
        kind: str,
        relative_path: str,
        size_bytes: int,
        sha256: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), run_id, name, kind, relative_path, size_bytes, sha256),
            )

    def create_environment_job(self, kind: str, latitude: float, longitude: float) -> sqlite3.Row:
        identifier = str(uuid4())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO environment_jobs (id, kind, latitude_deg, longitude_deg, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                (identifier, kind, latitude, longitude, utc_now()),
            )
        return self.get_environment_job(identifier)

    def get_environment_job(self, identifier: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM environment_jobs WHERE id = ?", (identifier,)).fetchone()

    def mark_environment_job_running(self, identifier: str, total: int, label: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE environment_jobs SET status = 'running', started_at = ?, progress_total = ?, progress_label = ? WHERE id = ?",
                (utc_now(), total, label[:160], identifier),
            )

    def update_environment_job_progress(self, identifier: str, current: int, total: int, label: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE environment_jobs SET progress_current = ?, progress_total = ?, progress_label = ? WHERE id = ?",
                (current, total, label[:160], identifier),
            )

    def mark_environment_job_completed(self, identifier: str, result: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE environment_jobs SET status = 'completed', finished_at = ?, result_json = ?, progress_current = progress_total, progress_label = 'Resultados listos' WHERE id = ?",
                (utc_now(), json.dumps(result), identifier),
            )

    def mark_environment_job_failed(self, identifier: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE environment_jobs SET status = 'failed', finished_at = ?, error = ? WHERE id = ?",
                (utc_now(), error[:4000], identifier),
            )

    def list_artifacts(self, run_id: str) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY name", (run_id,)
            ).fetchall()

    def get_artifact(self, identifier: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM artifacts WHERE id = ?", (identifier,)).fetchone()
