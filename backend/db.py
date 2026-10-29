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
"""


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
