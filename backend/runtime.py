"""Pure helpers for live status, resilience score and postmortem text."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from statistics import median
from typing import Any

from db import Sample
from service_map import GATEWAY_SERVICE

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_BAD = "bad"
STATUS_RANK = {STATUS_OK: 0, STATUS_WARN: 1, STATUS_BAD: 2}

WARN_LATENCY_FACTOR = 3.0
FAILED_PENALTY = 15.0
DEGRADED_PENALTY = 6.0
CONTAINMENT_BONUS = 10.0


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


def worst_status(current: str | None, status: str) -> str:
    """Keep the more severe of two statuses so live scoring never improves."""
    if current is None:
        return status
    return status if STATUS_RANK[status] > STATUS_RANK[current] else current


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


def statuses_from_rows(
    rows: Iterable[Mapping[str, Any]], baseline: Mapping[str, float]
) -> dict[str, str]:
    """Worst status per service across the supplied samples."""
    worst: dict[str, str] = {}
    for row in rows:
        service = str(row["service"])
        status = derive_status(
            up=bool(row.get("up")),
            error=bool(row.get("error")),
            latency_ms=row.get("latency_ms"),
            baseline_ms=baseline.get(service),
        )
        worst[service] = worst_status(worst.get(service), status)
    return worst


def resilience_breakdown(
    statuses: Mapping[str, str],
    *,
    fixes: bool,
    blast_radius: Iterable[str],
) -> dict[str, Any]:
    """Resilience score from service statuses and blast-radius containment.

    Formula: ``100 - 15 per failed - 6 per degraded``, plus a 10 point bonus
    when resilience fixes were enabled and no service outside the fault's
    blast radius failed or degraded.
    """
    failed = sorted(
        service for service, status in statuses.items() if status == STATUS_BAD
    )
    degraded = sorted(
        service for service, status in statuses.items() if status == STATUS_WARN
    )
    affected = set(blast_radius)
    contained = all(
        status == STATUS_OK
        for service, status in statuses.items()
        if service not in affected
    )
    bonus = CONTAINMENT_BONUS if fixes and contained else 0.0
    raw = 100.0 - FAILED_PENALTY * len(failed) - DEGRADED_PENALTY * len(degraded)
    raw += bonus
    return {
        "value": round(max(0.0, min(100.0, raw)), 1),
        "failed": failed,
        "degraded": degraded,
        "contained": contained,
        "bonus": bonus,
    }


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
