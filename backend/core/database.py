"""SQLite persistence.

One connection per operation keeps the async collector and request handlers
safe without a global mutable connection. WAL mode allows concurrent readers
while the collector writes.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS services (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    port INTEGER NOT NULL,
    url TEXT NOT NULL,
    dependencies TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    ts REAL NOT NULL,
    latency_ms REAL NOT NULL,
    error_rate REAL NOT NULL,
    cpu_percent REAL NOT NULL,
    memory_mb REAL NOT NULL,
    request_rate REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_service_ts ON metrics(service_id, ts);

CREATE TABLE IF NOT EXISTS anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    score REAL NOT NULL,
    severity TEXT NOT NULL,
    detected_at REAL NOT NULL,
    details TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_anomalies_ts ON anomalies(detected_at);

CREATE TABLE IF NOT EXISTS faults (
    id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    fault_type TEXT NOT NULL,
    parameters TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    started_at REAL NOT NULL,
    ends_at REAL,
    recovered_at REAL
);
CREATE INDEX IF NOT EXISTS idx_faults_status ON faults(status);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    anomaly_id INTEGER,
    summary TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT '[]',
    recommendations TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.0,
    provider TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidents_ts ON incidents(created_at);
"""


class Database:
    """Small helper around sqlite3 with schema management."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self.connection() as connection:
            cursor = connection.execute(sql, params)
            return int(cursor.lastrowid or 0)

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(sql, params).fetchall()
            return [dict(row) for row in rows]


def get_database(path: str | Path) -> Database:
    database = Database(path)
    database.initialize()
    return database
