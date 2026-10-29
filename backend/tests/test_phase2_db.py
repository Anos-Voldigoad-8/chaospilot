"""Phase 2 SQLite schema and experiment labelling."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from db import ChaosDatabase, Sample

EXPECTED_COLUMNS = {
    "experiments": ["id", "fault", "target", "started", "ended", "fixes_on"],
    "samples": [
        "id",
        "experiment_id",
        "ts",
        "service",
        "up",
        "latency_ms",
        "error",
        "label",
    ],
}


def table_columns(path: Path, table: str) -> list[str]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def test_schema_matches_phase2_contract(tmp_path: Path) -> None:
    database = ChaosDatabase(tmp_path / "chaos.db")

    for table, expected in EXPECTED_COLUMNS.items():
        assert table_columns(database.path, table) == expected


def test_experiment_lifecycle(tmp_path: Path) -> None:
    database = ChaosDatabase(tmp_path / "chaos.db")
    assert database.active_experiment() is None

    experiment_id = database.start_experiment(
        "latency", "payments", fixes_on=True, started=1_000.0
    )
    assert database.active_experiment(at=1_001.0)["id"] == experiment_id
    assert database.active_experiment(at=999.0) is None

    assert database.end_experiment(experiment_id, ended=1_010.0) is True
    # A closed window is still discoverable for historical samples.
    assert database.active_experiment(at=1_005.0)["id"] == experiment_id
    assert database.active_experiment(at=1_010.0) is None
    assert database.end_experiment(experiment_id) is False

    stored = database.experiments()[0]
    assert stored["fault"] == "latency"
    assert stored["target"] == "payments"
    assert stored["started"] == 1_000.0
    assert stored["ended"] == 1_010.0
    assert stored["fixes_on"] == 1


def test_samples_are_persisted_with_labels(tmp_path: Path) -> None:
    database = ChaosDatabase(tmp_path / "chaos.db")
    experiment_id = database.start_experiment("latency", "payments", started=100.0)

    inserted = database.insert_samples(
        [
            Sample(ts=101.0, service="gateway", up=True, latency_ms=12.5, error=False),
            Sample(
                ts=102.0,
                service="payments",
                up=False,
                latency_ms=2_000.0,
                error=True,
                label=1,
                experiment_id=experiment_id,
            ),
        ]
    )
    assert inserted == 2
    assert database.count_samples() == 2

    during = database.samples_between(100.0, 110.0, label=1)
    assert len(during) == 1
    assert during[0]["service"] == "payments"
    assert during[0]["up"] == 0
    assert during[0]["error"] == 1
    assert during[0]["experiment_id"] == experiment_id

    normal = database.samples_between(100.0, 110.0, service="gateway", label=0)
    assert len(normal) == 1
    assert normal[0]["latency_ms"] == 12.5
