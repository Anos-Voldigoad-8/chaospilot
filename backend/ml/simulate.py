"""Deterministic simulated telemetry for Docker-less dataset generation.

The simulator follows the same six-service topology, phases and label rules as
the real experiment runner. It exists so the ML pipeline can be reproduced on a
laptop without Docker; ``scripts/generate_dataset.py --source stack`` records
the real stack instead.
"""

from __future__ import annotations

import json
import math
import random
import time
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from db import ChaosDatabase, Sample
from ml.data import write_metadata
from service_map import ALL_SERVICES
from topology import DEPENDENCIES

FAULTS: tuple[str, ...] = ("kill", "latency", "memory")
BASELINE_SECONDS = 5.0
FAULT_SECONDS = 10.0
RECOVERY_SECONDS = 5.0
EXPERIMENT_GAP_SECONDS = 1.0

BASELINE_LATENCY_MS: dict[str, float] = {
    "gateway": 62.0,
    "auth": 11.0,
    "orders": 14.0,
    "cache": 6.0,
    "payments": 8.0,
    "db": 5.5,
}

REVERSE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    target: tuple(source for source, dependency in DEPENDENCIES if dependency == target)
    for target in {dependency for _, dependency in DEPENDENCIES}
}


@dataclass(frozen=True)
class SimulatedDataset:
    """Summary returned by :func:`write_simulated_dataset`."""

    path: Path
    experiments: int
    samples: int
    healthy_seconds: float
    duration_seconds: float
    plan: list[tuple[str, str]]


def caller_depths(target: str) -> dict[str, int]:
    """Distance from ``target`` to every caller (target itself is 0)."""
    depth = {target: 0}
    frontier: deque[str] = deque([target])
    while frontier:
        service = frontier.popleft()
        for caller in REVERSE_DEPENDENCIES.get(service, ()):
            if caller not in depth:
                depth[caller] = depth[service] + 1
                frontier.append(caller)
    return depth


def build_experiment_plan(count: int) -> list[tuple[str, str]]:
    """Cover every fault/target pair, then add replicates up to ``count``."""
    plan = [(fault, service) for fault in FAULTS for service in ALL_SERVICES]
    if count <= len(plan):
        return plan[:count]
    for index in range(count - len(plan)):
        plan.append((FAULTS[index % len(FAULTS)], ALL_SERVICES[index % len(ALL_SERVICES)]))
    return plan


def _healthy_sample(service: str, rng: random.Random) -> tuple[bool, float, bool]:
    baseline = BASELINE_LATENCY_MS.get(service, 10.0)
    latency = baseline * math.exp(rng.gauss(0.0, 0.14))
    if rng.random() < 0.012:  # occasional tail latency keeps healthy data honest
        latency *= rng.uniform(1.8, 3.2)
    error = rng.random() < 0.002
    up = not error and rng.random() > 0.001
    return up, round(max(0.4, latency), 3), error


def _fault_sample(
    service: str,
    fault: str,
    target: str,
    depth: int | None,
    ramp: float,
    rng: random.Random,
) -> tuple[bool, float, bool]:
    up, latency, error = _healthy_sample(service, rng)
    if depth is None:
        return up, latency, error

    if fault == "kill":
        if depth == 0:
            return False, round(rng.uniform(1_800.0, 2_400.0), 3), True
        latency += rng.uniform(450.0, 950.0) * (0.6**depth)
        error = rng.random() < (0.85 if service == "gateway" else 0.03)
        return not error, round(latency, 3), error

    if fault == "latency":
        latency += rng.uniform(1_500.0, 2_100.0) * (0.55**depth) * ramp
        error_probability = (0.012 if depth == 0 else 0.02 * 0.5**depth) * ramp
    else:  # memory pressure
        latency += rng.uniform(300.0, 520.0) * (0.5**depth) * ramp
        error_probability = (0.025 if depth == 0 else 0.012) * ramp

    error = rng.random() < error_probability
    return not error, round(latency, 3), error


def _reset_database(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        candidate.unlink(missing_ok=True)


def _timeline_samples(
    start: float,
    end: float,
    *,
    experiment_id: int | None,
    fault: str | None,
    target: str | None,
    depths: Mapping[str, int],
    phase: str,
    label: int,
    rng: random.Random,
) -> Iterable[Sample]:
    moment = start
    while moment < end:
        if phase == "fault" and fault is not None:
            ramp = 1.0 if fault == "kill" else min(1.0, (moment - start + 1.0) / 2.0)
            for service in ALL_SERVICES:
                up, latency, error = _fault_sample(
                    service, fault, target or "", depths.get(service), ramp, rng
                )
                yield Sample(
                    ts=moment,
                    service=service,
                    up=up,
                    latency_ms=latency,
                    error=error,
                    label=label,
                    experiment_id=experiment_id,
                )
        else:
            for service in ALL_SERVICES:
                up, latency, error = _healthy_sample(service, rng)
                yield Sample(
                    ts=moment,
                    service=service,
                    up=up,
                    latency_ms=latency,
                    error=error,
                    label=0,
                    experiment_id=experiment_id,
                )
        moment += 1.0


def write_simulated_dataset(
    path: str | Path,
    *,
    experiments: int = 24,
    healthy_seconds: float = 600.0,
    baseline_seconds: float = BASELINE_SECONDS,
    fault_seconds: float = FAULT_SECONDS,
    recovery_seconds: float = RECOVERY_SECONDS,
    seed: int = 42,
) -> SimulatedDataset:
    """Write a complete simulated dataset to ``path`` and return a summary."""
    if experiments < 1:
        raise ValueError("experiments must be at least 1")
    if healthy_seconds < 0:
        raise ValueError("healthy_seconds must not be negative")

    dataset_path = Path(path)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    _reset_database(dataset_path)
    database = ChaosDatabase(dataset_path)
    rng = random.Random(seed)
    plan = build_experiment_plan(experiments)

    cycle = baseline_seconds + fault_seconds + recovery_seconds + EXPERIMENT_GAP_SECONDS
    total = healthy_seconds + len(plan) * cycle
    cursor = time.time() - total

    healthy_rows = list(
        _timeline_samples(
            cursor,
            cursor + healthy_seconds,
            experiment_id=None,
            fault=None,
            target=None,
            depths={},
            phase="baseline",
            label=0,
            rng=rng,
        )
    )
    database.insert_samples(healthy_rows)
    cursor += healthy_seconds

    written = len(healthy_rows)
    for fault, target in plan:
        depths = caller_depths(target)
        started = cursor
        baseline_end = started + baseline_seconds
        fault_started = baseline_end
        fault_ended = fault_started + fault_seconds
        recovery_end = fault_ended + recovery_seconds

        experiment_id = database.start_experiment(
            fault, target, fixes_on=False, started=started
        )
        database.create_run(experiment_id, resilient=False, status="baseline")
        database.update_run(
            experiment_id,
            status="completed",
            baseline_end=baseline_end,
            fault_started=fault_started,
            fault_ended=fault_ended,
            recovery_end=recovery_end,
        )

        rows = list(
            _timeline_samples(
                started,
                baseline_end,
                experiment_id=experiment_id,
                fault=None,
                target=None,
                depths={},
                phase="baseline",
                label=0,
                rng=rng,
            )
        )
        rows.extend(
            _timeline_samples(
                fault_started,
                fault_ended,
                experiment_id=experiment_id,
                fault=fault,
                target=target,
                depths=depths,
                phase="fault",
                label=1,
                rng=rng,
            )
        )
        rows.extend(
            _timeline_samples(
                fault_ended,
                recovery_end,
                experiment_id=experiment_id,
                fault=None,
                target=None,
                depths={},
                phase="recovery",
                label=0,
                rng=rng,
            )
        )
        database.insert_samples(rows)
        database.end_experiment(experiment_id, ended=recovery_end)
        written += len(rows)
        cursor = recovery_end + EXPERIMENT_GAP_SECONDS

    write_metadata(
        database,
        {
            "source": "simulated",
            "seed": seed,
            "experiments": len(plan),
            "healthy_seconds": healthy_seconds,
            "baseline_seconds": baseline_seconds,
            "fault_seconds": fault_seconds,
            "recovery_seconds": recovery_seconds,
            "window_seconds": 5.0,
            "plan": json.dumps(plan),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )

    return SimulatedDataset(
        path=dataset_path,
        experiments=len(plan),
        samples=written,
        healthy_seconds=healthy_seconds,
        duration_seconds=total,
        plan=plan,
    )
