"""Pure helpers for live status, resilience score and postmortem text."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from statistics import median
from typing import Any

from db import Sample
from service_map import GATEWAY_SERVICE

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_BAD = "bad"

WARN_LATENCY_FACTOR = 3.0
MAX_LATENCY_PENALTY = 60.0
MAX_ERROR_PENALTY = 40.0


def derive_status(
    *,
    up: bool,
    error: bool,
    latency_ms: float | None,
    baseline_ms: float | None,
) -> str:
    """bad if the service is down/failing, warn above 3x baseline, else ok."""
    if not up or error:
        return STATUS_BAD
    if baseline_ms and latency_ms is not None and latency_ms > WARN_LATENCY_FACTOR * baseline_ms:
        return STATUS_WARN
    return STATUS_OK


def status_for_sample(sample: Sample, baseline_ms: float | None) -> str:
    return derive_status(
        up=sample.up,
        error=sample.error,
        latency_ms=sample.latency_ms,
        baseline_ms=baseline_ms,
    )


def baseline_from_rows(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    """Median latency per service over successful baseline samples."""
    grouped: dict[str, list[float]] = {}
    for row in rows:
        if row.get("up") and row.get("latency_ms") is not None:
            grouped.setdefault(str(row["service"]), []).append(float(row["latency_ms"]))
    return {service: round(median(values), 3) for service, values in grouped.items()}


def phase_stats(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]
    return {
        "samples": len(rows),
        "errors": sum(1 for row in rows if row.get("error")),
        "fault_labels": sum(1 for row in rows if row.get("label") == 1),
        "p50_ms": round(median(latencies), 1) if latencies else None,
        "max_ms": round(max(latencies), 1) if latencies else None,
    }


def recent_metrics(samples: Sequence[Sample]) -> dict[str, float]:
    """Latest gateway latency plus error rate across the rolling window."""
    if not samples:
        return {"gateway_latency": 0.0, "error_rate": 0.0}
    gateway = [
        sample.latency_ms
        for sample in samples
        if sample.service == GATEWAY_SERVICE and sample.latency_ms is not None
    ]
    error_rate = sum(1 for sample in samples if sample.error) / len(samples)
    return {
        "gateway_latency": round(float(gateway[-1]), 1) if gateway else 0.0,
        "error_rate": round(error_rate, 4),
    }


def resilience_score(
    *,
    gateway_latency: float,
    baseline_gateway: float | None,
    error_rate: float,
) -> float:
    """0-100 score: latency inflation and failed requests both subtract."""
    baseline = baseline_gateway or 0.0
    if baseline > 0:
        ratio = max(1.0, gateway_latency / baseline)
        latency_penalty = min(MAX_LATENCY_PENALTY, (ratio - 1.0) * 30.0)
    else:
        latency_penalty = 0.0
    error_penalty = min(MAX_ERROR_PENALTY, error_rate * 100.0)
    return round(max(0.0, 100.0 - latency_penalty - error_penalty), 1)


def build_postmortem(
    *,
    experiment_id: int,
    fault: str,
    target: str,
    fixes: bool,
    phases: dict[str, dict[str, Any]],
    score: float,
    failure: str | None = None,
) -> str:
    """Deterministic, evidence-based summary of one experiment."""
    parts = [
        f"Experiment #{experiment_id}: injected {fault} on {target} "
        f"(fixes={'on' if fixes else 'off'})."
    ]
    if failure:
        parts.append(f"Run ended with an error: {failure}")

    for name in ("baseline", "fault", "recovery"):
        stats = phases.get(name)
        if not stats or not stats.get("samples"):
            continue
        p50 = stats.get("p50_ms")
        parts.append(
            f"{name.capitalize()}: gateway p50 {p50}ms, "
            f"errors {stats['errors']}/{stats['samples']}."
        )

    baseline_p50 = (phases.get("baseline") or {}).get("p50_ms")
    fault_p50 = (phases.get("fault") or {}).get("p50_ms")
    if baseline_p50 is not None and fault_p50 is not None:
        delta = float(fault_p50) - float(baseline_p50)
        parts.append(
            f"Gateway latency moved {delta:+.0f}ms during the fault "
            f"({float(fault_p50) / max(float(baseline_p50), 1.0):.1f}x baseline)."
        )

    parts.append(f"Resilience score: {score:.0f}/100.")
    return " ".join(parts)
