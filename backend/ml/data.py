"""Read samples and run metadata from the SQLite dataset."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from db import ChaosDatabase


@dataclass(frozen=True)
class Dataset:
    """Everything the feature builder needs from one dataset database."""

    path: Path
    samples: list[dict[str, Any]]
    runs: dict[int, dict[str, Any]]
    stats: dict[str, Any]


def load_dataset(path: str | Path) -> Dataset:
    """Load all telemetry and experiment phase timings from ``path``."""
    database = ChaosDatabase(path)
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS ml_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        sample_rows = connection.execute(
            "SELECT id, experiment_id, ts, service, up, latency_ms, error, label "
            "FROM samples ORDER BY ts, service"
        ).fetchall()
        run_rows = connection.execute(
            "SELECT e.id, e.fault, e.target, e.started, e.ended, "
            "r.status, r.baseline_end, r.fault_started, r.fault_ended, r.recovery_end "
            "FROM experiments e "
            "LEFT JOIN experiment_runs r ON r.experiment_id = e.id "
            "ORDER BY e.id"
        ).fetchall()
        meta_rows = connection.execute("SELECT key, value FROM ml_meta").fetchall()

    samples = [dict(row) for row in sample_rows]
    runs = {
        int(row["id"]): {
            **dict(row),
            "started": float(row["started"]),
        }
        for row in run_rows
    }
    metadata = {str(row["key"]): str(row["value"]) for row in meta_rows}

    fault_samples = sum(1 for row in samples if row.get("label") == 1)
    healthy_samples = sum(1 for row in samples if row.get("experiment_id") is None)
    services = sorted({str(row["service"]) for row in samples})
    timestamps = [float(row["ts"]) for row in samples]
    stats = {
        "samples": len(samples),
        "services": len(services),
        "service_names": services,
        "experiments": len(runs),
        "fault_samples": fault_samples,
        "healthy_only_samples": healthy_samples,
        "first_sample": min(timestamps) if timestamps else None,
        "last_sample": max(timestamps) if timestamps else None,
        "metadata": metadata,
    }
    return Dataset(path=Path(path), samples=samples, runs=runs, stats=stats)


def write_metadata(database: ChaosDatabase, values: Mapping[str, Any]) -> None:
    """Persist generator provenance with the dataset."""
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS ml_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.executemany(
            "INSERT OR REPLACE INTO ml_meta (key, value) VALUES (?, ?)",
            [(str(key), str(value)) for key, value in values.items()],
        )


def experiment_table(runs: Mapping[int, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Compact experiment rows for reports and split summaries."""
    return [
        {
            "id": int(run["id"]),
            "fault": run.get("fault"),
            "target": run.get("target"),
            "status": run.get("status"),
            "started": run.get("started"),
            "baseline_end": run.get("baseline_end"),
            "fault_started": run.get("fault_started"),
            "fault_ended": run.get("fault_ended"),
            "recovery_end": run.get("recovery_end"),
        }
        for run in runs.values()
    ]
