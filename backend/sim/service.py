"""Per-service simulation: baseline sampling and fault application.

Each service produces per-second samples of ``up``, ``latency_ms`` and
``error_rate``. Faults modify the healthy behaviour:

* ``kill``: the service is down (``up=False``, high latency, high error rate).
* ``latency``: added milliseconds on top of baseline latency.
* ``memory``: degrading load capacity, which raises latency and errors when
  load approaches capacity.

Fault impact decays with dependency depth so a fault on a downstream service
hurts its direct callers most and fades further upstream.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Literal

from sim.topology import ServiceConfig

FaultKind = Literal["kill", "latency", "memory"]

#: How much a fault's impact decays per dependency hop.
DECAY_PER_HOP = 0.55

#: Latency added to a killed service (ms).
KILL_LATENCY_MS = 2000.0

#: Error rate of a killed service.
KILL_ERROR_RATE = 0.9

#: Probability a healthy sample is down / errors (keeps baseline honest).
HEALTHY_DOWN_PROB = 0.001
HEALTHY_ERROR_PROB = 0.002

#: Occasional tail latency on healthy samples.
TAIL_LATENCY_PROB = 0.012


@dataclass(frozen=True)
class Fault:
    """An active fault on a service."""

    kind: FaultKind
    target: str
    latency_ms: float = 0.0
    memory_mb: int = 0


@dataclass(frozen=True)
class ServiceSample:
    """One second of telemetry for one service."""

    service: str
    ts: float
    up: bool
    latency_ms: float
    error_rate: float
    label: int = 0


class ServiceModel:
    """Simulates one service's telemetry given the active faults."""

    def __init__(self, config: ServiceConfig, rng: random.Random) -> None:
        self.config = config
        self.rng = rng

    def healthy_sample(self, ts: float) -> ServiceSample:
        """Produce a normal (no-fault) sample for ``ts``."""
        baseline = self.config.baseline_latency_ms
        latency = baseline * math.exp(self.rng.gauss(0.0, 0.14))
        if self.rng.random() < TAIL_LATENCY_PROB:
            latency *= self.rng.uniform(1.8, 3.2)
        error = self.rng.random() < HEALTHY_ERROR_PROB
        up = not error and self.rng.random() > HEALTHY_DOWN_PROB
        return ServiceSample(
            service=self.config.name,
            ts=ts,
            up=up,
            latency_ms=round(max(0.4, latency), 3),
            error_rate=self.config.baseline_error_rate,
            label=0,
        )

    def fault_sample(self, ts: float, fault: Fault, depth: int, ramp: float) -> ServiceSample:
        """Produce a sample while a fault is active.

        ``depth`` is the dependency distance from the fault target (0 = the
        target itself). ``ramp`` is 0-1 and grows during the fault window so
        the fault builds up rather than snapping instantly.
        """
        up, latency, error_rate = self._healthy_values()
        if depth is None:
            return ServiceSample(
                service=self.config.name,
                ts=ts,
                up=up,
                latency_ms=round(latency, 3),
                error_rate=error_rate,
                label=1,
            )

        decay = DECAY_PER_HOP ** depth
        impact = ramp * decay

        if fault.kind == "kill":
            if depth == 0:
                return ServiceSample(
                    service=self.config.name,
                    ts=ts,
                    up=False,
                    latency_ms=round(self.rng.uniform(1800.0, 2400.0), 3),
                    error_rate=KILL_ERROR_RATE,
                    label=1,
                )
            latency += self.rng.uniform(450.0, 950.0) * decay * impact
            error_probability = (0.85 if self.config.name == "gateway" else 0.03) * impact
            error = self.rng.random() < error_probability
            return ServiceSample(
                service=self.config.name,
                ts=ts,
                up=not error,
                latency_ms=round(max(0.4, latency), 3),
                error_rate=error_probability,
                label=1,
            )

        if fault.kind == "latency":
            added = fault.latency_ms * decay * impact
            latency += added
            error_probability = (
                0.012 if depth == 0 else 0.02 * (0.5 ** depth)
            ) * impact
        else:  # memory
            added = self.rng.uniform(300.0, 520.0) * decay * impact
            latency += added
            error_probability = (0.025 if depth == 0 else 0.012) * impact

        error = self.rng.random() < error_probability
        return ServiceSample(
            service=self.config.name,
            ts=ts,
            up=not error,
            latency_ms=round(max(0.4, latency), 3),
            error_rate=error_probability,
            label=1,
        )

    def _healthy_values(self) -> tuple[bool, float, float]:
        baseline = self.config.baseline_latency_ms
        latency = baseline * math.exp(self.rng.gauss(0.0, 0.14))
        if self.rng.random() < TAIL_LATENCY_PROB:
            latency *= self.rng.uniform(1.8, 3.2)
        error_rate = self.config.baseline_error_rate
        error = self.rng.random() < HEALTHY_ERROR_PROB
        up = not error and self.rng.random() > HEALTHY_DOWN_PROB
        return up, round(max(0.4, latency), 3), error_rate
