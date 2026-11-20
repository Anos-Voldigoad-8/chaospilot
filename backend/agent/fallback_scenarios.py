"""Hardcoded fallback data for every attack-catalog scenario.

The backend agent / simulator may be unavailable during a live classroom
presentation, so every fault-type × target-service combination carries a
guaranteed fallback: a broken (fault-phase) snapshot, a healed
(recovery-phase) snapshot and a detailed, presentation-ready postmortem.

These values are authoritative for the live demo: the fault-phase broadcast
uses them so the gauge, anomaly card, telemetry chart and topology always
show an obvious broken state, and the recovery-phase broadcast shows an
obvious healed state. They are also used as the postmortem source so the
incident report is detailed and consistent regardless of LLM availability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FaultKind = Literal["kill", "latency", "memory"]
ServiceStatus = Literal["ok", "warn", "bad"]

ALL_SERVICES: tuple[str, ...] = (
    "gateway",
    "auth",
    "orders",
    "payments",
    "cache",
    "db",
)

#: Baseline per-service latency (ms) used for "ok" services.
BASELINE_LATENCY_MS: dict[str, float] = {
    "gateway": 60.0,
    "auth": 10.0,
    "orders": 15.0,
    "payments": 80.0,
    "cache": 3.0,
    "db": 5.0,
}

#: Baseline per-service error rate used for "ok" services.
BASELINE_ERROR_RATE: dict[str, float] = {
    "gateway": 0.005,
    "auth": 0.002,
    "orders": 0.003,
    "payments": 0.004,
    "cache": 0.001,
    "db": 0.001,
}


@dataclass(frozen=True)
class PhaseSnapshot:
    """One phase (fault or recovery) of a scenario."""

    latency_ms: float
    error_rate: float
    anomaly_score: float
    resilience_score: float
    service_statuses: dict[str, ServiceStatus]
    service_latencies: dict[str, float]
    service_error_rates: dict[str, float]


@dataclass(frozen=True)
class FallbackScenario:
    """One attack-catalog scenario with fault + recovery snapshots."""

    fault_type: FaultKind
    target_service: str
    title: str
    fault: PhaseSnapshot
    recovery: PhaseSnapshot
    postmortem: str


def _snapshot(
    *,
    fault_type: FaultKind,
    target_service: str,
    statuses: dict[str, ServiceStatus],
    fault_latency_ms: float,
    fault_error_rate: float,
    anomaly_score: float,
    resilience_score: float,
    recovery: bool = False,
) -> PhaseSnapshot:
    """Build a phase snapshot from per-service statuses."""

    def latency_for(service: str) -> float:
        status = statuses[service]
        if recovery:
            return BASELINE_LATENCY_MS[service]
        if status == "bad":
            return fault_latency_ms
        if status == "warn":
            return round(fault_latency_ms * 0.65, 1)
        return BASELINE_LATENCY_MS[service]

    def error_rate_for(service: str) -> float:
        status = statuses[service]
        if recovery:
            return 0.0  # fully healed
        if status == "bad":
            return fault_error_rate
        if status == "warn":
            return round(fault_error_rate * 0.5, 3)
        return BASELINE_ERROR_RATE[service]

    return PhaseSnapshot(
        latency_ms=BASELINE_LATENCY_MS[target_service] if recovery else fault_latency_ms,
        error_rate=0.0 if recovery else fault_error_rate,
        anomaly_score=anomaly_score,
        resilience_score=resilience_score,
        service_statuses=dict(statuses),
        service_latencies={s: latency_for(s) for s in ALL_SERVICES},
        service_error_rates={s: error_rate_for(s) for s in ALL_SERVICES},
    )


# --------------------------------------------------------------------------- #
# Attack catalog: fault_type × target_service -> fallback scenario
# --------------------------------------------------------------------------- #

FALLBACK_SCENARIOS: dict[tuple[FaultKind, str], FallbackScenario] = {
    ("kill", "gateway"): FallbackScenario(
        fault_type="kill",
        target_service="gateway",
        title="Gateway kill — total stack blackout",
        fault=_snapshot(
            fault_type="kill",
            target_service="gateway",
            statuses={
                "gateway": "bad",
                "auth": "bad",
                "orders": "bad",
                "payments": "bad",
                "cache": "bad",
                "db": "bad",
            },
            fault_latency_ms=5000.0,
            fault_error_rate=0.25,
            anomaly_score=0.95,
            resilience_score=15,
        ),
        recovery=_snapshot(
            fault_type="kill",
            target_service="gateway",
            statuses={s: "ok" for s in ALL_SERVICES},
            fault_latency_ms=5000.0,
            fault_error_rate=0.25,
            anomaly_score=0.04,
            resilience_score=94,
            recovery=True,
        ),
        postmortem=(
            "Root cause: the gateway (public entry point) was killed, so every "
            "downstream caller lost its route to the stack.\n"
            "Impact: all six services (gateway, auth, orders, payments, cache, db) "
            "returned bad; gateway latency spiked to 5000 ms with a 25% error rate.\n"
            "Detection: the Isolation Forest anomaly detector flagged a score of 0.95 "
            "at T+12 s, well above the 0.5 threshold.\n"
            "Resolution: the gateway container was restarted and health checks passed; "
            "circuit breakers and retry budgets were enabled to absorb future loss.\n"
            "Metrics: gateway latency 5000 ms -> 62 ms; error rate 0.25 -> 0.005; "
            "resilience score 12 -> 94.\n"
            "Recommendation: deploy the gateway behind a load balancer with active "
            "health checks and a warm standby to eliminate single-point-of-failure."
        ),
    ),
    ("kill", "payments"): FallbackScenario(
        fault_type="kill",
        target_service="payments",
        title="Payments kill — orders stall at checkout",
        fault=_snapshot(
            fault_type="kill",
            target_service="payments",
            statuses={
                "gateway": "warn",
                "auth": "ok",
                "orders": "warn",
                "payments": "bad",
                "cache": "ok",
                "db": "ok",
            },
            fault_latency_ms=2200.0,
            fault_error_rate=0.20,
            anomaly_score=0.88,
            resilience_score=28,
        ),
        recovery=_snapshot(
            fault_type="kill",
            target_service="payments",
            statuses={s: "ok" for s in ALL_SERVICES},
            fault_latency_ms=2200.0,
            fault_error_rate=0.20,
            anomaly_score=0.05,
            resilience_score=90,
            recovery=True,
        ),
        postmortem=(
            "Root cause: the payments service was killed, so orders could not "
            "complete the payment-charge step of checkout.\n"
            "Impact: payments went bad (2200 ms, 20% errors); orders and gateway "
            "degraded to warn as the failure cascaded upstream.\n"
            "Detection: anomaly score reached 0.88 at T+14 s; payments latency and "
            "error rate crossed warn thresholds within two seconds.\n"
            "Resolution: payments was restored; orders drained pending charges and "
            "retried with exponential backoff once payments was healthy.\n"
            "Metrics: payments latency 2200 ms -> 80 ms; error rate 0.20 -> 0.004; "
            "resilience score 28 -> 90.\n"
            "Recommendation: add a circuit breaker around the payments client and a "
            "fallback checkout flow so a payments outage does not block all orders."
        ),
    ),
    ("latency", "auth"): FallbackScenario(
        fault_type="latency",
        target_service="auth",
        title="Auth latency — every authenticated request delayed",
        fault=_snapshot(
            fault_type="latency",
            target_service="auth",
            statuses={
                "gateway": "warn",
                "auth": "bad",
                "orders": "warn",
                "payments": "ok",
                "cache": "warn",
                "db": "ok",
            },
            fault_latency_ms=1100.0,
            fault_error_rate=0.12,
            anomaly_score=0.82,
            resilience_score=22,
        ),
        recovery=_snapshot(
            fault_type="latency",
            target_service="auth",
            statuses={s: "ok" for s in ALL_SERVICES},
            fault_latency_ms=1100.0,
            fault_error_rate=0.12,
            anomaly_score=0.03,
            resilience_score=88,
            recovery=True,
        ),
        postmortem=(
            "Root cause: injected 1100 ms latency on the auth service slowed session "
            "verification for every inbound request.\n"
            "Impact: auth went bad; gateway, orders and cache degraded to warn as "
            "verification calls timed out.\n"
            "Detection: anomaly score reached 0.82 at T+10 s; auth latency crossed "
            "the 3x-baseline warn threshold immediately.\n"
            "Resolution: the latency injection was removed; session verification "
            "returned to baseline and the gateway resumed normal routing.\n"
            "Metrics: auth latency 1100 ms -> 10 ms; error rate 0.12 -> 0.002; "
            "resilience score 22 -> 88.\n"
            "Recommendation: enforce per-endpoint timeouts on the auth client and "
            "cache verified sessions to reduce repeated verification calls."
        ),
    ),
    ("latency", "payments"): FallbackScenario(
        fault_type="latency",
        target_service="payments",
        title="Payments latency — orders time out awaiting confirmation",
        fault=_snapshot(
            fault_type="latency",
            target_service="payments",
            statuses={
                "gateway": "warn",
                "auth": "ok",
                "orders": "warn",
                "payments": "bad",
                "cache": "ok",
                "db": "ok",
            },
            fault_latency_ms=950.0,
            fault_error_rate=0.07,
            anomaly_score=0.78,
            resilience_score=30,
        ),
        recovery=_snapshot(
            fault_type="latency",
            target_service="payments",
            statuses={s: "ok" for s in ALL_SERVICES},
            fault_latency_ms=950.0,
            fault_error_rate=0.07,
            anomaly_score=0.04,
            resilience_score=92,
            recovery=True,
        ),
        postmortem=(
            "Root cause: injected 950 ms latency on payments caused orders to time "
            "out waiting for payment confirmation.\n"
            "Impact: payments degraded to bad (950 ms, 7% errors); orders and "
            "gateway degraded to warn as the checkout path stalled.\n"
            "Detection: anomaly score reached 0.78 at T+11 s; payments latency "
            "exceeded 3x baseline within the fault window.\n"
            "Resolution: latency was cleared; orders retried failed payment charges "
            "and the checkout path recovered.\n"
            "Metrics: payments latency 950 ms -> 80 ms; error rate 0.07 -> 0.004; "
            "resilience score 30 -> 92.\n"
            "Recommendation: set a hard timeout on the payments client in orders and "
            "surface payment timeouts to the user rather than hanging checkout."
        ),
    ),
    ("latency", "db"): FallbackScenario(
        fault_type="latency",
        target_service="db",
        title="Database latency — cache misses cascade and all reads slow",
        fault=_snapshot(
            fault_type="latency",
            target_service="db",
            statuses={
                "gateway": "warn",
                "auth": "warn",
                "orders": "warn",
                "payments": "warn",
                "cache": "warn",
                "db": "bad",
            },
            fault_latency_ms=1400.0,
            fault_error_rate=0.09,
            anomaly_score=0.85,
            resilience_score=25,
        ),
        recovery=_snapshot(
            fault_type="latency",
            target_service="db",
            statuses={s: "ok" for s in ALL_SERVICES},
            fault_latency_ms=1400.0,
            fault_error_rate=0.09,
            anomaly_score=0.04,
            resilience_score=91,
            recovery=True,
        ),
        postmortem=(
            "Root cause: injected 1400 ms latency on the database slowed every read "
            "and write path across the stack.\n"
            "Impact: db went bad; gateway, auth, orders, payments and cache all "
            "degraded to warn as queries queued.\n"
            "Detection: anomaly score reached 0.85 at T+13 s; database latency "
            "crossed 3x baseline and the cache layer began missing under load.\n"
            "Resolution: the latency injection was removed; the connection pool was "
            "drained and refreshed and read traffic returned to baseline.\n"
            "Metrics: db latency 1400 ms -> 5 ms; error rate 0.09 -> 0.001; "
            "resilience score 25 -> 91.\n"
            "Recommendation: add query timeouts, read replicas and cache warming so a "
            "slow database does not stall the entire stack."
        ),
    ),
    ("memory", "cache"): FallbackScenario(
        fault_type="memory",
        target_service="cache",
        title="Cache memory pressure — evictions spike read latency and overload db",
        fault=_snapshot(
            fault_type="memory",
            target_service="cache",
            statuses={
                "gateway": "warn",
                "auth": "warn",
                "orders": "warn",
                "payments": "ok",
                "cache": "bad",
                "db": "warn",
            },
            fault_latency_ms=520.0,
            fault_error_rate=0.10,
            anomaly_score=0.80,
            resilience_score=32,
        ),
        recovery=_snapshot(
            fault_type="memory",
            target_service="cache",
            statuses={s: "ok" for s in ALL_SERVICES},
            fault_latency_ms=520.0,
            fault_error_rate=0.10,
            anomaly_score=0.04,
            resilience_score=93,
            recovery=True,
        ),
        postmortem=(
            "Root cause: memory pressure on the session cache triggered evictions, "
            "forcing reads to fall through to the database.\n"
            "Impact: cache went bad (520 ms, 10% errors); db degraded to warn under "
            "the added read load and gateway/auth/orders degraded to warn.\n"
            "Detection: anomaly score reached 0.80 at T+9 s; cache latency and error "
            "rate rose as evictions climbed.\n"
            "Resolution: cache memory was freed and eviction policy adjusted; the db "
            "load returned to baseline once cache hits recovered.\n"
            "Metrics: cache latency 520 ms -> 3 ms; error rate 0.10 -> 0.001; "
            "resilience score 32 -> 93.\n"
            "Recommendation: right-size cache memory, add eviction alerts and cap per-"
            "key sizes so a single bloated session cannot evict the whole cache."
        ),
    ),
    ("memory", "orders"): FallbackScenario(
        fault_type="memory",
        target_service="orders",
        title="Orders memory pressure — order processing OOMs and partially fails",
        fault=_snapshot(
            fault_type="memory",
            target_service="orders",
            statuses={
                "gateway": "warn",
                "auth": "ok",
                "orders": "bad",
                "payments": "warn",
                "cache": "ok",
                "db": "warn",
            },
            fault_latency_ms=760.0,
            fault_error_rate=0.14,
            anomaly_score=0.84,
            resilience_score=20,
        ),
        recovery=_snapshot(
            fault_type="memory",
            target_service="orders",
            statuses={s: "ok" for s in ALL_SERVICES},
            fault_latency_ms=760.0,
            fault_error_rate=0.14,
            anomaly_score=0.04,
            resilience_score=89,
            recovery=True,
        ),
        postmortem=(
            "Root cause: memory pressure on orders caused out-of-memory kills and "
            "partial order-processing failures.\n"
            "Impact: orders went bad (760 ms, 14% errors); gateway and payments "
            "degraded to warn and db saw elevated write latency.\n"
            "Detection: anomaly score reached 0.84 at T+12 s; orders error rate and "
            "latency crossed fail thresholds within the fault window.\n"
            "Resolution: the orders process was restarted and memory limits raised; "
            "in-flight orders were reconciled and retried.\n"
            "Metrics: orders latency 760 ms -> 15 ms; error rate 0.14 -> 0.003; "
            "resilience score 20 -> 89.\n"
            "Recommendation: set container memory limits with OOM kills, add order "
            "idempotency keys and shed load when memory approaches the limit."
        ),
    ),
}


def get_fallback(fault_type: FaultKind, target_service: str) -> FallbackScenario | None:
    """Return the fallback scenario for ``(fault_type, target_service)``."""
    return FALLBACK_SCENARIOS.get((fault_type, target_service))
