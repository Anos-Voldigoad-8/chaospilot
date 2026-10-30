"""Assemble the evidence sent to the postmortem LLM.

The context is deliberately compact: topology, per-service status transitions,
anomaly scores, phase timings and whether resilience fixes were enabled.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from statistics import median
from typing import Any

from db import ChaosDatabase
from ml.features import affected_services, build_windows
from runtime import derive_status
from topology import topology


def load_detector() -> Any | None:
    """Load the Phase 5 model when it exists, otherwise return None."""
    try:
        from ml.detector import AnomalyDetector

        return AnomalyDetector.load()
    except Exception:
        return None


def _baseline_latency(
    samples: Iterable[Mapping[str, Any]], run: Mapping[str, Any]
) -> dict[str, float]:
    baseline_end = run.get("baseline_end")
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in samples:
        if baseline_end is not None and float(row["ts"]) >= float(baseline_end):
            continue
        if row.get("latency_ms") is None or not row.get("up"):
            continue
        grouped[str(row["service"])].append(float(row["latency_ms"]))
    return {
        service: round(median(values), 3)
        for service, values in grouped.items()
        if values
    }


def _phase_for(timestamp: float, run: Mapping[str, Any]) -> str:
    if run.get("fault_ended") is not None and timestamp >= float(run["fault_ended"]):
        return "recovery"
    if run.get("fault_started") is not None and timestamp >= float(run["fault_started"]):
        return "fault"
    return "baseline"


def _status_timeline(
    samples: Iterable[Mapping[str, Any]],
    run: Mapping[str, Any],
    baseline: Mapping[str, float],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in samples:
        grouped[str(row["service"])].append(row)

    timeline: dict[str, list[dict[str, Any]]] = {}
    for service in sorted(grouped):
        previous: str | None = None
        events: list[dict[str, Any]] = []
        for row in sorted(grouped[service], key=lambda item: float(item["ts"])):
            status = derive_status(
                up=bool(row.get("up")),
                error=bool(row.get("error")),
                latency_ms=row.get("latency_ms"),
                baseline_ms=baseline.get(service),
            )
            if status == previous:
                continue
            events.append(
                {
                    "phase": _phase_for(float(row["ts"]), run),
                    "status": status,
                    "at": round(float(row["ts"]), 3),
                    "latency_ms": row.get("latency_ms"),
                }
            )
            previous = status
        timeline[service] = events[:8]
    return timeline


def _heuristic_scores(
    samples: Iterable[Mapping[str, Any]],
    run: Mapping[str, Any],
    baseline: Mapping[str, float],
) -> dict[str, float]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in samples:
        if _phase_for(float(row["ts"]), run) == "fault":
            grouped[str(row["service"])].append(row)

    scores: dict[str, float] = {}
    for service, rows in grouped.items():
        latencies = [
            float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None
        ]
        base = baseline.get(service) or 0.0
        ratio = (max(latencies) / base) if latencies and base > 0 else 1.0
        error_rate = sum(1 for row in rows if row.get("error")) / len(rows) if rows else 0.0
        down = any(not row.get("up") for row in rows)
        scores[service] = round(
            min(1.0, max(0.0, (ratio - 1.0) / 2.0, error_rate, 0.8 if down else 0.0)),
            4,
        )
    return scores


def _anomaly_scores(
    samples: Iterable[Mapping[str, Any]],
    run: Mapping[str, Any],
    baseline: Mapping[str, float],
    detector: Any | None,
) -> dict[str, float]:
    if detector is not None:
        try:
            windows = build_windows(
                samples, {int(run["id"]): run}, window_seconds=5.0, min_samples=3
            )
            scores: dict[str, float] = {}
            for window in windows:
                if not window.phase.startswith("fault"):
                    continue
                scores[window.service] = max(
                    scores.get(window.service, 0.0), float(detector.score(window))
                )
            if scores:
                return {
                    service: round(value, 4) for service, value in scores.items()
                }
        except Exception:
            # A missing or incompatible model must not stop the postmortem.
            pass
    return _heuristic_scores(samples, run, baseline)


def build_postmortem_context(
    database: ChaosDatabase,
    experiment_id: int,
    *,
    detector: Any | None = None,
) -> dict[str, Any]:
    """Build all grounded evidence for one experiment."""
    run = database.run_detail(experiment_id)
    if run is None:
        raise KeyError(f"experiment {experiment_id}")
    samples = database.samples_for_experiment(experiment_id)
    baseline = _baseline_latency(samples, run)
    graph = topology()
    target = str(run.get("target") or "")
    affected = sorted(affected_services(target)) if target else []

    return {
        "experiment": {
            "id": int(run["id"]),
            "fault": run.get("fault"),
            "target": target,
            "fixes": bool(run.get("fixes")),
            "status": run.get("status"),
            "score": run.get("score"),
            "error": run.get("error"),
            "started": run.get("started"),
            "baseline_end": run.get("baseline_end"),
            "fault_started": run.get("fault_started"),
            "fault_ended": run.get("fault_ended"),
            "recovery_end": run.get("recovery_end"),
        },
        "topology": graph,
        "baseline_latency_ms": baseline,
        "status_timeline": _status_timeline(samples, run, baseline),
        "anomaly_scores": _anomaly_scores(
            samples, run, baseline, detector if detector is not None else load_detector()
        ),
        "affected_services": affected,
        "sample_count": len(samples),
        "observed_at": time.time(),
    }
