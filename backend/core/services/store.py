"""Read/write helpers for every table.

Routes and subsystems use these functions instead of writing SQL inline.
Rows are returned as plain dictionaries with JSON columns decoded.
"""

from __future__ import annotations

import json
import time
from typing import Any

from core.database import Database

JsonDict = dict[str, Any]

METRIC_FIELDS = (
    "latency_ms",
    "error_rate",
    "cpu_percent",
    "memory_mb",
    "request_rate",
)


def _decode(row: JsonDict, *columns: str) -> JsonDict:
    for column in columns:
        raw = row.get(column)
        if isinstance(raw, str):
            try:
                row[column] = json.loads(raw)
            except json.JSONDecodeError:
                row[column] = [] if column != "parameters" else {}
    return row


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def list_services(database: Database) -> list[JsonDict]:
    return database.fetch_all("SELECT * FROM services ORDER BY name")


def get_service(database: Database, service_id: str) -> JsonDict | None:
    return database.fetch_one("SELECT * FROM services WHERE id = ?", (service_id,))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def record_metric(database: Database, service_id: str, sample: JsonDict) -> int:
    return database.execute(
        """
        INSERT INTO metrics
            (service_id, ts, latency_ms, error_rate, cpu_percent, memory_mb, request_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            service_id,
            float(sample.get("timestamp", time.time())),
            float(sample.get("latency_ms", 0.0)),
            float(sample.get("error_rate", 0.0)),
            float(sample.get("cpu_percent", 0.0)),
            float(sample.get("memory_mb", 0.0)),
            float(sample.get("request_rate", 0.0)),
        ),
    )


def metrics_since(database: Database, service_id: str, since: float) -> list[JsonDict]:
    return database.fetch_all(
        "SELECT * FROM metrics WHERE service_id = ? AND ts >= ? ORDER BY ts ASC",
        (service_id, since),
    )


def recent_metrics(database: Database, service_id: str, limit: int = 60) -> list[JsonDict]:
    rows = database.fetch_all(
        "SELECT * FROM metrics WHERE service_id = ? ORDER BY ts DESC LIMIT ?",
        (service_id, limit),
    )
    return list(reversed(rows))


def latest_metrics(database: Database) -> list[JsonDict]:
    return database.fetch_all(
        """
        SELECT m.* FROM metrics m
        JOIN (
            SELECT service_id, MAX(id) AS max_id FROM metrics GROUP BY service_id
        ) newest ON newest.max_id = m.id
        """
    )


def latest_metric(database: Database, service_id: str) -> JsonDict | None:
    return database.fetch_one(
        "SELECT * FROM metrics WHERE service_id = ? ORDER BY ts DESC LIMIT 1",
        (service_id,),
    )


def metric_count(database: Database, service_id: str | None = None) -> int:
    if service_id:
        row = database.fetch_one(
            "SELECT COUNT(*) AS total FROM metrics WHERE service_id = ?", (service_id,)
        )
    else:
        row = database.fetch_one("SELECT COUNT(*) AS total FROM metrics")
    return int(row["total"]) if row else 0


def prune_metrics(database: Database, older_than: float) -> int:
    with database.connection() as connection:
        cursor = connection.execute("DELETE FROM metrics WHERE ts < ?", (older_than,))
        return int(cursor.rowcount or 0)


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------


def record_anomaly(
    database: Database,
    *,
    service_id: str,
    metric: str,
    value: float,
    score: float,
    severity: str,
    detected_at: float,
    details: JsonDict | None = None,
) -> int:
    return database.execute(
        """
        INSERT INTO anomalies
            (service_id, metric, value, score, severity, detected_at, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            service_id,
            metric,
            value,
            score,
            severity,
            detected_at,
            json.dumps(details or {}),
        ),
    )


def list_anomalies(
    database: Database, limit: int = 50, service_id: str | None = None
) -> list[JsonDict]:
    if service_id:
        rows = database.fetch_all(
            "SELECT * FROM anomalies WHERE service_id = ? ORDER BY detected_at DESC LIMIT ?",
            (service_id, limit),
        )
    else:
        rows = database.fetch_all(
            "SELECT * FROM anomalies ORDER BY detected_at DESC LIMIT ?", (limit,)
        )
    return [_decode(row, "details") for row in rows]


def get_anomaly(database: Database, anomaly_id: int) -> JsonDict | None:
    row = database.fetch_one("SELECT * FROM anomalies WHERE id = ?", (anomaly_id,))
    return _decode(row, "details") if row else None


def last_anomaly_at(database: Database, service_id: str) -> float:
    row = database.fetch_one(
        "SELECT MAX(detected_at) AS last FROM anomalies WHERE service_id = ?",
        (service_id,),
    )
    return float(row["last"]) if row and row["last"] is not None else 0.0


# ---------------------------------------------------------------------------
# Faults
# ---------------------------------------------------------------------------


def create_fault(
    database: Database,
    *,
    fault_id: str,
    service_id: str,
    fault_type: str,
    parameters: JsonDict,
    started_at: float,
    ends_at: float | None,
) -> None:
    database.execute(
        """
        INSERT INTO faults
            (id, service_id, fault_type, parameters, status, started_at, ends_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?)
        """,
        (
            fault_id,
            service_id,
            fault_type,
            json.dumps(parameters),
            started_at,
            ends_at,
        ),
    )


def get_fault(database: Database, fault_id: str) -> JsonDict | None:
    row = database.fetch_one("SELECT * FROM faults WHERE id = ?", (fault_id,))
    return _decode(row, "parameters") if row else None


def list_faults(database: Database, status: str | None = None, limit: int = 50) -> list[JsonDict]:
    if status:
        rows = database.fetch_all(
            "SELECT * FROM faults WHERE status = ? ORDER BY started_at DESC LIMIT ?",
            (status, limit),
        )
    else:
        rows = database.fetch_all(
            "SELECT * FROM faults ORDER BY started_at DESC LIMIT ?", (limit,)
        )
    return [_decode(row, "parameters") for row in rows]


def active_faults(database: Database) -> list[JsonDict]:
    rows = database.fetch_all(
        "SELECT * FROM faults WHERE status = 'active' ORDER BY started_at DESC"
    )
    return [_decode(row, "parameters") for row in rows]


def recently_recovered_faults(
    database: Database, service_id: str, since: float
) -> list[JsonDict]:
    rows = database.fetch_all(
        """
        SELECT * FROM faults
        WHERE service_id = ? AND status != 'active' AND started_at >= ?
        ORDER BY started_at DESC
        """,
        (service_id, since),
    )
    return [_decode(row, "parameters") for row in rows]


def set_fault_status(
    database: Database, fault_id: str, status: str, recovered_at: float | None = None
) -> None:
    database.execute(
        "UPDATE faults SET status = ?, recovered_at = COALESCE(?, recovered_at) WHERE id = ?",
        (status, recovered_at, fault_id),
    )


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


def create_incident(
    database: Database,
    *,
    incident_id: str,
    service_id: str,
    anomaly_id: int | None,
    summary: str,
    root_cause: str,
    evidence: list[str],
    recommendations: list[str],
    confidence: float,
    provider: str,
    created_at: float,
) -> None:
    database.execute(
        """
        INSERT INTO incidents
            (id, service_id, anomaly_id, summary, root_cause, evidence,
             recommendations, confidence, provider, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            service_id,
            anomaly_id,
            summary,
            root_cause,
            json.dumps(evidence),
            json.dumps(recommendations),
            confidence,
            provider,
            created_at,
        ),
    )


def list_incidents(database: Database, limit: int = 20) -> list[JsonDict]:
    rows = database.fetch_all(
        "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    return [_decode(row, "evidence", "recommendations") for row in rows]


def get_incident(database: Database, incident_id: str) -> JsonDict | None:
    row = database.fetch_one("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    return _decode(row, "evidence", "recommendations") if row else None
