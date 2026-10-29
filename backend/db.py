"""SQLite persistence for experiments and telemetry samples.

Two tables back the Phase 2 loop:

``experiments``
    One row per injected fault window (fault, target, start/end time and
    whether the run was supposed to show a fix).

``samples``
    One row per probe per second. ``label`` is ``1`` only for samples taken
    while an experiment is running, which is the supervised signal the Phase 3
    anomaly detector trains on.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "chaos.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    fault    TEXT    NOT NULL,
    target   TEXT    NOT NULL,
    started  REAL    NOT NULL,
    ended    REAL,
    fixes_on INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS samples (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER REFERENCES experiments(id) ON DELETE SET NULL,
    ts            REAL    NOT NULL,
    service       TEXT    NOT NULL,
    up            INTEGER NOT NULL,
    latency_ms    REAL,
    error         INTEGER NOT NULL,
    label         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
CREATE INDEX IF NOT EXISTS idx_samples_service_ts ON samples(service, ts);
CREATE INDEX IF NOT EXISTS idx_samples_experiment ON samples(experiment_id);

CREATE TABLE IF NOT EXISTS experiment_runs (
    experiment_id INTEGER PRIMARY KEY REFERENCES experiments(id) ON DELETE CASCADE,
    status        TEXT    NOT NULL DEFAULT 'running',
    resilient     INTEGER NOT NULL DEFAULT 0,
    baseline_end  REAL,
    fault_started REAL,
    fault_ended   REAL,
    recovery_end  REAL,
    score         REAL,
    postmortem    TEXT,
    error         TEXT
);
"""

RUN_FIELDS = frozenset(
    {
        "status",
        "resilient",
        "baseline_end",
        "fault_started",
        "fault_ended",
        "recovery_end",
        "score",
        "postmortem",
        "error",
    }
)


@dataclass(frozen=True)
class Sample:
    """A single collector observation."""

    ts: float
    service: str
    up: bool
    latency_ms: float | None
    error: bool
    label: int = 0
    experiment_id: int | None = None


class ChaosDatabase:
    """Thin SQLite wrapper; every call uses its own short-lived connection."""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_schema(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA)

    # ------------------------------------------------------------------
    # Experiments
    # ------------------------------------------------------------------
    def start_experiment(
        self,
        fault: str,
        target: str,
        *,
        fixes_on: bool = False,
        started: float | None = None,
    ) -> int:
        """Open an experiment window and return its id."""
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO experiments (fault, target, started, ended, fixes_on) "
                "VALUES (?, ?, ?, NULL, ?)",
                (fault, target, time.time() if started is None else started, int(fixes_on)),
            )
            experiment_id = int(cursor.lastrowid)
        return experiment_id

    def end_experiment(self, experiment_id: int, *, ended: float | None = None) -> bool:
        """Close an experiment window; returns False if it was already closed."""
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE experiments SET ended = ? WHERE id = ? AND ended IS NULL",
                (time.time() if ended is None else ended, experiment_id),
            )
            return cursor.rowcount > 0

    def active_experiment(self, *, at: float | None = None) -> dict[str, Any] | None:
        """Return the experiment covering ``at`` (default: now), if any."""
        moment = time.time() if at is None else at
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM experiments "
                "WHERE started <= ? AND (ended IS NULL OR ended > ?) "
                "ORDER BY started DESC LIMIT 1",
                (moment, moment),
            ).fetchone()
        return dict(row) if row else None

    def experiments(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM experiments ORDER BY started"
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Samples
    # ------------------------------------------------------------------
    def insert_sample(self, sample: Sample) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO samples "
                "(experiment_id, ts, service, up, latency_ms, error, label) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    sample.experiment_id,
                    sample.ts,
                    sample.service,
                    int(sample.up),
                    sample.latency_ms,
                    int(sample.error),
                    sample.label,
                ),
            )
            return int(cursor.lastrowid)

    def insert_samples(self, samples: Iterable[Sample]) -> int:
        rows = [
            (
                sample.experiment_id,
                sample.ts,
                sample.service,
                int(sample.up),
                sample.latency_ms,
                int(sample.error),
                sample.label,
            )
            for sample in samples
        ]
        if not rows:
            return 0
        with self.connect() as connection:
            connection.executemany(
                "INSERT INTO samples "
                "(experiment_id, ts, service, up, latency_ms, error, label) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def samples_between(
        self,
        start: float,
        end: float,
        *,
        service: str | None = None,
        label: int | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM samples WHERE ts >= ? AND ts < ?"
        params: list[Any] = [start, end]
        if service is not None:
            query += " AND service = ?"
            params.append(service)
        if label is not None:
            query += " AND label = ?"
            params.append(label)
        query += " ORDER BY ts"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def count_samples(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM samples").fetchone()
        return int(row["total"])

    # ------------------------------------------------------------------
    # Phase 3 run metadata (status, phases, score, postmortem)
    # ------------------------------------------------------------------
    def create_run(
        self,
        experiment_id: int,
        *,
        resilient: bool = False,
        status: str = "running",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO experiment_runs "
                "(experiment_id, status, resilient) VALUES (?, ?, ?)",
                (experiment_id, status, int(resilient)),
            )

    def update_run(self, experiment_id: int, **fields: Any) -> None:
        unknown = set(fields) - RUN_FIELDS
        if unknown:
            raise ValueError(f"unknown run fields: {', '.join(sorted(unknown))}")
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = list(fields.values())
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO experiment_runs (experiment_id) VALUES (?)",
                (experiment_id,),
            )
            connection.execute(
                f"UPDATE experiment_runs SET {assignments} WHERE experiment_id = ?",
                (*values, experiment_id),
            )

    def run_detail(self, experiment_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                f"{RUN_SELECT} WHERE e.id = ?",
                (experiment_id,),
            ).fetchone()
        return _normalize_run_row(row) if row else None

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                f"{RUN_SELECT} ORDER BY e.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_normalize_run_row(row) for row in rows]

    def samples_for_experiment(
        self, experiment_id: int, *, limit: int = 5_000
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, experiment_id, ts, service, up, latency_ms, error, label "
                "FROM samples WHERE experiment_id = ? ORDER BY ts LIMIT ?",
                (experiment_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]


RUN_SELECT = """
SELECT e.id, e.fault, e.target, e.started, e.ended, e.fixes_on,
       r.status, r.resilient, r.baseline_end, r.fault_started, r.fault_ended,
       r.recovery_end, r.score, r.postmortem, r.error,
       (SELECT COUNT(*) FROM samples s WHERE s.experiment_id = e.id) AS sample_count,
       (SELECT COUNT(*) FROM samples s WHERE s.experiment_id = e.id AND s.error = 1)
           AS error_count
FROM experiments e
LEFT JOIN experiment_runs r ON r.experiment_id = e.id
"""


def _normalize_run_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["fixes"] = bool(data.pop("fixes_on"))
    data["resilient"] = bool(data.get("resilient") or 0)
    if data.get("status") is None:
        data["status"] = "completed" if data.get("ended") is not None else "unknown"
    return data

