"""In-process chaos simulator.

Runs one experiment: baseline, fault injection, recovery. Produces per-second
telemetry samples for every simulated service. Fully deterministic given a
seed, so the same scenario always reproduces the same metrics.

Faults:
* ``kill``      - the target service goes down.
* ``latency``   - added milliseconds on the target.
* ``memory``    - degrading capacity on the target.

With ``resilient=True`` (retry, timeout, circuit breaker) the blast radius is
contained to one hop: only the target and its direct callers degrade.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

from sim.service import Fault, FaultKind, ServiceModel, ServiceSample
from sim.topology import ALL_SERVICES, CALLERS_BY_SERVICE, SERVICE_CONFIGS, affected_services

DEFAULT_BASELINE_SECONDS = 10.0
DEFAULT_FAULT_SECONDS = 20.0
DEFAULT_RECOVERY_SECONDS = 10.0


@dataclass(frozen=True)
class ExperimentPlan:
    fault: FaultKind
    target: str
    fixes: bool
    baseline_seconds: float = DEFAULT_BASELINE_SECONDS
    fault_seconds: float = DEFAULT_FAULT_SECONDS
    recovery_seconds: float = DEFAULT_RECOVERY_SECONDS
    seed: int = 42


@dataclass
class ExperimentResult:
    plan: ExperimentPlan
    samples: list[ServiceSample] = field(default_factory=list)
    start_ts: float = 0.0
    end_ts: float = 0.0


class Simulator:
    """Deterministic in-process chaos simulator."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def _models(self, rng: random.Random) -> dict[str, ServiceModel]:
        return {
            name: ServiceModel(SERVICE_CONFIGS[name], rng) for name in ALL_SERVICES
        }

    def _depths(self, target: str, resilient: bool) -> dict[str, int | None]:
        """Dependency depth of every service relative to ``target``.

        Services not affected get ``None``. With resilient mode, only direct
        callers (depth 1) and the target (depth 0) are affected.
        """
        depths: dict[str, int | None] = {name: None for name in ALL_SERVICES}
        affected = affected_services(target, resilient=resilient)
        depth_map: dict[str, int] = {target: 0}
        frontier: list[str] = [target]
        while frontier:
            service = frontier.pop(0)
            for caller in CALLERS_BY_SERVICE.get(service, ()):
                if caller in affected and caller not in depth_map:
                    depth_map[caller] = depth_map[service] + 1
                    frontier.append(caller)
        for name, depth in depth_map.items():
            depths[name] = depth
        return depths

    def run(self, plan: ExperimentPlan) -> ExperimentResult:
        """Run one experiment and return every per-second sample."""
        # Combine the simulator seed with the plan seed so both contribute to
        # determinism: the same (simulator, plan) seed pair always reproduces
        # the same metrics.
        rng = random.Random(self.seed * 1_000_003 + plan.seed)
        models = self._models(rng)
        depths = self._depths(plan.target, plan.fixes)

        start_ts = math.floor(time.time())
        fault: Fault
        if plan.fault == "latency":
            fault = Fault(kind="latency", target=plan.target, latency_ms=2000.0)
        elif plan.fault == "memory":
            fault = Fault(kind="memory", target=plan.target, memory_mb=256)
        else:
            fault = Fault(kind="kill", target=plan.target)

        samples: list[ServiceSample] = []
        moment = start_ts

        # ---------- baseline ----------
        baseline_end = moment + plan.baseline_seconds
        while moment < baseline_end:
            for name in ALL_SERVICES:
                samples.append(models[name].healthy_sample(moment))
            moment += 1.0

        # ---------- fault ----------
        fault_started = moment
        fault_ended = moment + plan.fault_seconds
        ramp_step = 2.0  # seconds to reach full impact
        while moment < fault_ended:
            ramp = 1.0 if plan.fault == "kill" else min(1.0, (moment - fault_started + 1.0) / ramp_step)
            for name in ALL_SERVICES:
                depth = depths.get(name)
                samples.append(models[name].fault_sample(moment, fault, depth, ramp))
            moment += 1.0

        # ---------- recovery ----------
        recovery_end = moment + plan.recovery_seconds
        while moment < recovery_end:
            for name in ALL_SERVICES:
                samples.append(models[name].healthy_sample(moment))
            moment += 1.0

        return ExperimentResult(
            plan=plan,
            samples=samples,
            start_ts=start_ts,
            end_ts=recovery_end,
        )
