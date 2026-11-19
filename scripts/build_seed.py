"""Build the offline seed dataset used when there is no internet.

Generates three committed artefacts in ``backend/data/seed/``:

* ``incidents_seed.json`` - 150+ incident records (component, impact level,
  duration minutes, title).
* ``load_seed.csv`` - 2000+ hourly request-load points.
* ``metrics_seed.csv`` - 5000+ labelled (healthy / fault) per-second,
  per-service metrics windows produced by the in-process simulator.

The script also loads the metrics into the SQLite database and trains the
Isolation Forest, writing ``backend/models/isolation_forest.joblib`` and
``docs/model_metrics.json``.

Run with zero internet: ``python scripts/build_seed.py``.
"""

from __future__ import annotations

import csv
import json
import math
import random
import sqlite3
import time
from pathlib import Path

# Allow running from the repo root or the backend directory.
import sys

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from db import ChaosDatabase  # noqa: E402
from ml.train import train_from_database  # noqa: E402
from sim.simulator import Simulator, ExperimentPlan  # noqa: E402

SEED_DIR = BACKEND_ROOT / "data" / "seed"
DB_PATH = BACKEND_ROOT / "data" / "ml_dataset.db"
MODEL_PATH = BACKEND_ROOT / "models" / "isolation_forest.joblib"
METRICS_PATH = Path(__file__).resolve().parent.parent / "docs" / "model_metrics.json"

RNG = random.Random(20260101)

SERVICES = ("gateway", "auth", "orders", "payments", "cache", "db")
FAULTS = ("kill", "latency", "memory")

COMPONENTS = {
    "gateway": "API Gateway",
    "auth": "Auth Service",
    "orders": "Orders Service",
    "payments": "Payments Service",
    "cache": "Session Cache",
    "db": "Database",
}

IMPACT_LEVELS = ("minor", "moderate", "major", "critical")

FAULT_TITLES = {
    "kill": [
        "{component} instance crashed",
        "{component} pod terminated by node pressure",
        "{component} process exited unexpectedly",
    ],
    "latency": [
        "{component} slow responses under load",
        "{component} elevated latency spike",
        "{component} degraded response times",
    ],
    "memory": [
        "{component} memory pressure",
        "{component} out-of-memory kill",
        "{component} heap exhaustion",
    ],
}


def _now_ts() -> float:
    return time.time()


def build_incidents() -> list[dict]:
    """Build 150+ synthetic incident records from real-world patterns."""
    incidents = []
    index = 1
    for cycle in range(25):  # 25 cycles x 6 services = 150 incidents
        for service in SERVICES:
            fault = RNG.choice(FAULTS)
            impact = RNG.choice(IMPACT_LEVELS)
            duration = {
                "minor": RNG.randint(5, 20),
                "moderate": RNG.randint(20, 60),
                "major": RNG.randint(60, 180),
                "critical": RNG.randint(180, 480),
            }[impact]
            template = RNG.choice(FAULT_TITLES[fault])
            title = template.format(component=COMPONENTS[service])
            incidents.append(
                {
                    "id": f"INC-{1000 + index}",
                    "component": service,
                    "component_name": COMPONENTS[service],
                    "impact": impact,
                    "duration_minutes": duration,
                    "fault_type": fault,
                    "title": title,
                    "occurred_at": _now_ts() - RNG.uniform(0, 365 * 86400),
                }
            )
            index += 1
    return incidents


def build_load_curve(hours: int = 2000) -> list[dict]:
    """Build hourly request-load points with daily/weekly seasonality."""
    points = []
    base = _now_ts() - hours * 3600
    for hour in range(hours):
        ts = base + hour * 3600
        # Daily sine wave + weekly dip on weekends + noise.
        day_of_hour = (hour % 24) / 24.0
        daily = 0.5 + 0.5 * math.sin(2 * math.pi * (day_of_hour - 0.25))
        weekly = 0.85 if (hour // 24) % 7 in (5, 6) else 1.0
        noise = RNG.uniform(0.9, 1.1)
        rps = max(10, int(500 * daily * weekly * noise))
        points.append(
            {
                "ts": ts,
                "hour": hour,
                "requests_per_second": rps,
            }
        )
    return points


def generate_metrics_rows() -> tuple[list[dict], list[dict]]:
    """Use the simulator to generate healthy + fault windows.

    Returns (sample_rows, run_rows) for insertion into SQLite.
    """
    samples: list[dict] = []
    runs: list[dict] = []

    # Start far enough in the past that timestamps look historical.
    cursor = _now_ts() - 40 * 86400
    rng = random.Random(99)

    BASELINE_LATENCY = {
        "gateway": 60.0,
        "auth": 10.0,
        "orders": 15.0,
        "payments": 80.0,
        "cache": 3.0,
        "db": 5.0,
    }
    BASELINE_ERROR_RATE = {
        "gateway": 0.005,
        "auth": 0.002,
        "orders": 0.003,
        "payments": 0.004,
        "cache": 0.001,
        "db": 0.001,
    }

    # Long healthy baseline (label 0, no experiment).
    healthy_seconds = 1200
    for second in range(healthy_seconds):
        ts = cursor + second
        for service in SERVICES:
            latency = max(
                0.5,
                BASELINE_LATENCY[service] * math.exp(rng.gauss(0.0, 0.14)),
            )
            up = rng.random() > 0.001
            error = rng.random() < BASELINE_ERROR_RATE[service]
            samples.append(
                {
                    "ts": ts,
                    "service": service,
                    "up": up,
                    "latency_ms": round(latency, 3),
                    "error": 1 if error else 0,
                    "label": 0,
                    "experiment_id": None,
                }
            )
    cursor += healthy_seconds

    # Inject fault windows using the simulator.
    experiment_id = 0
    plan = [
        ("kill", "payments", 20),
        ("latency", "orders", 25),
        ("memory", "auth", 20),
        ("kill", "db", 15),
        ("latency", "gateway", 30),
        ("memory", "payments", 20),
        ("kill", "cache", 10),
        ("latency", "db", 20),
    ]
    for fault, target, duration in plan:
        experiment_id += 1
        started = cursor
        sim = Simulator(seed=1000 + experiment_id)
        result = sim.run(
            ExperimentPlan(
                fault=fault,
                target=target,
                fixes=False,
                baseline_seconds=8.0,
                fault_seconds=float(duration),
                recovery_seconds=8.0,
                seed=1000 + experiment_id,
            )
        )
        # Shift simulator timestamps to the absolute timeline.
        offset = started - result.start_ts
        fault_rng = random.Random(2000 + experiment_id)
        for sample in result.samples:
            # Derive an actual per-sample error boolean from the error rate.
            error = fault_rng.random() < sample.error_rate
            samples.append(
                {
                    "ts": sample.ts + offset,
                    "service": sample.service,
                    "up": sample.up,
                    "latency_ms": sample.latency_ms,
                    "error": 1 if error else 0,
                    "label": sample.label,
                    "experiment_id": experiment_id,
                }
            )
        runs.append(
            {
                "id": experiment_id,
                "fault": fault,
                "target": target,
                "started": started,
                "baseline_end": started + 8.0,
                "fault_started": started + 8.0,
                "fault_ended": started + 8.0 + duration,
                "recovery_end": started + 8.0 + duration + 8.0,
            }
        )
        cursor = result.end_ts + offset + 5.0

    return samples, runs


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 1. Incidents
    incidents = build_incidents()
    (SEED_DIR / "incidents_seed.json").write_text(json.dumps(incidents, indent=2))
    print(f"wrote {SEED_DIR / 'incidents_seed.json'} ({len(incidents)} incidents)")

    # 2. Load curve
    load_points = build_load_curve()
    write_csv(
        SEED_DIR / "load_seed.csv",
        load_points,
        ["ts", "hour", "requests_per_second"],
    )
    print(f"wrote {SEED_DIR / 'load_seed.csv'} ({len(load_points)} points)")

    # 3. Metrics (simulator-generated healthy + fault windows)
    samples, runs = generate_metrics_rows()
    metrics_fields = [
        "ts", "service", "up", "latency_ms", "error", "label", "experiment_id",
    ]
    write_csv(SEED_DIR / "metrics_seed.csv", samples, metrics_fields)
    print(f"wrote {SEED_DIR / 'metrics_seed.csv'} ({len(samples)} rows)")

    # 4. Load into SQLite for training.
    if DB_PATH.exists():
        DB_PATH.unlink()
    database = ChaosDatabase(DB_PATH)
    for run in runs:
        eid = database.start_experiment(
            run["fault"], run["target"], fixes_on=False, started=run["started"]
        )
        database.create_run(eid, resilient=False, status="baseline")
        database.update_run(
            eid,
            status="completed",
            baseline_end=run["baseline_end"],
            fault_started=run["fault_started"],
            fault_ended=run["fault_ended"],
            recovery_end=run["recovery_end"],
        )
        database.end_experiment(eid, ended=run["recovery_end"])
    # Insert samples in batches.
    batch = []
    for row in samples:
        from db import Sample
        batch.append(
            Sample(
                ts=row["ts"],
                service=row["service"],
                up=bool(row["up"]),
                latency_ms=row["latency_ms"],
                error=bool(row["error"]),
                label=row["label"],
                experiment_id=row["experiment_id"],
            )
        )
        if len(batch) >= 1000:
            database.insert_samples(batch)
            batch = []
    if batch:
        database.insert_samples(batch)

    # 5. Train the model on healthy windows only.
    if MODEL_PATH.exists():
        MODEL_PATH.unlink()
    metrics = train_from_database(
        database_path=DB_PATH,
        model_path=MODEL_PATH,
        metrics_path=METRICS_PATH,
    )
    print(f"trained model -> {MODEL_PATH}")
    print(f"wrote metrics -> {METRICS_PATH}")
    print(
        "test precision={precision} recall={recall} f1={f1}".format(
            precision=metrics["test"]["precision"],
            recall=metrics["test"]["recall"],
            f1=metrics["test"]["f1"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
