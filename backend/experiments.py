"""Background experiment runner for the Phase 3 API.

One run is: optional resilient restart, baseline, fault injection, recovery.
Samples are collected every second and written to SQLite; every tick is also
broadcast over WebSocket as state/metrics/score events. The run ends with a
stored postmortem.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Protocol

from api_config import ApiSettings
from chaos.engine import ChaosEngine
from collector import Collector
from db import ChaosDatabase, Sample
from runtime import (
    baseline_from_rows,
    build_postmortem,
    phase_stats,
    recent_metrics,
    resilience_score,
    status_for_sample,
)
from service_map import GATEWAY_SERVICE, SERVICE_PORTS
from stack import StackController
from ws import EventHub

LOGGER = logging.getLogger(__name__)

SUPPORTED_FAULTS = {"kill", "latency", "memory"}
UNKNOWN_SERVICE = "unknown service"


class ExperimentBusyError(RuntimeError):
    """Raised when a run is already in progress."""


class UnknownTargetError(ValueError):
    """Raised when the target service is not part of the sample stack."""


class CollectorLike(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


CollectorFactory = Callable[..., CollectorLike]


@dataclass
class RunContext:
    """Mutable in-memory state for one experiment task."""

    id: int
    fault: str
    target: str
    fixes: bool
    started: float
    baseline_end: float | None = None
    fault_started: float | None = None
    fault_ended: float | None = None
    recovery_end: float | None = None
    baseline: dict[str, float] = field(default_factory=dict)
    recovered: bool = False


class ExperimentRunner:
    """Starts, executes and reports one experiment at a time."""

    def __init__(
        self,
        database: ChaosDatabase,
        hub: EventHub,
        *,
        settings: ApiSettings | None = None,
        engine: ChaosEngine | None = None,
        stack: StackController | None = None,
        collector_factory: CollectorFactory | None = None,
    ) -> None:
        self.database = database
        self.hub = hub
        self.settings = settings or ApiSettings.from_env()
        self.engine = engine or ChaosEngine(host=self.settings.host)
        self.stack = stack or StackController(
            directory=self.settings.stack_directory, host=self.settings.host
        )
        self.collector_factory = collector_factory or self._default_collector_factory

        self._task: asyncio.Task[None] | None = None
        self._run: RunContext | None = None
        self._window: tuple[float, float] | None = None
        self._baseline: dict[str, float] = {}
        self._last_status: dict[str, str] = {}
        self._recent: deque[Sample] = deque(maxlen=60)
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def active_id(self) -> int | None:
        return self._run.id if self._run is not None else None

    async def start(self, *, fault: str, target: str, fixes: bool) -> dict[str, Any]:
        if target not in SERVICE_PORTS:
            raise UnknownTargetError(f"{UNKNOWN_SERVICE}: {target}")
        if fault not in SUPPORTED_FAULTS:
            raise ValueError(f"unsupported fault: {fault}")

        async with self._lock:
            if self.running:
                raise ExperimentBusyError(
                    f"experiment #{self.active_id} is already running"
                )
            started = time.time()
            experiment_id = self.database.start_experiment(
                fault, target, fixes_on=fixes, started=started
            )
            self.database.create_run(experiment_id, resilient=fixes, status="pending")
            run = RunContext(
                id=experiment_id,
                fault=fault,
                target=target,
                fixes=fixes,
                started=started,
            )
            self._run = run
            self._task = asyncio.create_task(
                self._execute(run), name=f"experiment-{experiment_id}"
            )
            detail = self.database.run_detail(experiment_id)
        return detail or {"id": experiment_id, "status": "pending"}

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.database.list_runs(limit=limit)

    def detail(self, experiment_id: int) -> dict[str, Any] | None:
        run = self.database.run_detail(experiment_id)
        if run is None:
            return None
        samples = self.database.samples_for_experiment(experiment_id)
        run["samples"] = samples
        run["phases"] = self._phases_from_row(run, samples)
        run["labels"] = {
            "normal": sum(1 for sample in samples if sample["label"] == 0),
            "fault": sum(1 for sample in samples if sample["label"] == 1),
        }
        return run

    async def shutdown(self) -> None:
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------
    async def _execute(self, run: RunContext) -> None:
        collector: CollectorLike | None = None
        failure: str | None = None
        status = "completed"
        final_score = 0.0

        try:
            await self.hub.log(
                "info",
                f"Experiment #{run.id} started: {run.fault} on {run.target} "
                f"(fixes={'on' if run.fixes else 'off'})",
            )
            self.database.update_run(run.id, status="preparing")

            healthy = await self._prepare_stack(run)
            if not healthy:
                raise RuntimeError("sample stack is not healthy")

            self._reset_live_state()
            collector = self.collector_factory(
                self.database,
                label_resolver=self._label_for,
                on_samples=self._on_samples,
            )
            await collector.start()

            self.database.update_run(run.id, status="baseline")
            await self.hub.log(
                "info",
                f"Baseline for {self.settings.baseline_seconds:.0f}s: "
                "collecting normal traffic",
            )
            await asyncio.sleep(self.settings.baseline_seconds)
            run.baseline_end = time.time()
            baseline_rows = self.database.samples_between(run.started, run.baseline_end)
            self._baseline = baseline_from_rows(baseline_rows)
            self.database.update_run(run.id, baseline_end=run.baseline_end)
            await self.hub.log(
                "info",
                f"Baseline complete: gateway p50 "
                f"{self._baseline.get('gateway', 'n/a')}ms",
            )

            run.fault_started = time.time()
            self._window = (
                run.fault_started,
                run.fault_started + self.settings.fault_seconds,
            )
            self.database.update_run(
                run.id, status="fault", fault_started=run.fault_started
            )
            await self.hub.log(
                "warn",
                f"Injecting {run.fault} on {run.target} "
                f"for {self.settings.fault_seconds:.0f}s",
            )
            injection = await self._inject(run)
            if not injection.get("ok"):
                raise RuntimeError(
                    f"{run.fault} injection failed: "
                    f"{injection.get('error') or injection.get('response')}"
                )
            await self.hub.log(
                "warn",
                f"Fault active: {injection.get('action', run.fault)} on {run.target}",
            )

            await asyncio.sleep(self.settings.fault_seconds)

            self._window = None
            run.fault_ended = time.time()
            self.database.update_run(
                run.id, status="recovery", fault_ended=run.fault_ended
            )
            await self.hub.log("info", "Fault window closed; applying recovery")
            recovery = await self._recover(run)
            run.recovered = bool(recovery.get("ok"))
            if not recovery.get("ok"):
                raise RuntimeError(
                    f"recovery failed: {recovery.get('error') or recovery.get('response')}"
                )
            await self.hub.log(
                "info",
                f"Recovery applied; observing for {self.settings.recovery_seconds:.0f}s",
            )
            await asyncio.sleep(self.settings.recovery_seconds)
            run.recovery_end = time.time()
            self.database.update_run(run.id, status="completed")
        except asyncio.CancelledError:
            failure = "cancelled during shutdown"
            status = "cancelled"
            await self._safe_log("warn", f"Experiment #{run.id} cancelled")
        except Exception as exc:  # a failed run must still produce a report
            LOGGER.exception("experiment %s failed", run.id)
            failure = f"{type(exc).__name__}: {exc}"
            status = "failed"
            await self._safe_log("error", f"Experiment #{run.id} failed: {failure}")
        finally:
            self._window = None
            if collector is not None:
                with suppress(Exception):
                    await collector.stop()
            await self._ensure_recovered(run)

            run.recovery_end = run.recovery_end or time.time()
            if run.fault_started is not None and run.fault_ended is None:
                run.fault_ended = run.recovery_end
            self.database.end_experiment(run.id, ended=run.recovery_end)

            phases = self._phases_for_run(run)
            final_score = self._final_score(phases)
            postmortem = build_postmortem(
                experiment_id=run.id,
                fault=run.fault,
                target=run.target,
                fixes=run.fixes,
                phases=phases,
                score=final_score,
                failure=failure,
            )
            self.database.update_run(
                run.id,
                status=status,
                recovery_end=run.recovery_end,
                fault_ended=run.fault_ended,
                score=final_score,
                postmortem=postmortem,
                error=failure,
            )
            await self._safe_log(
                "info",
                f"Experiment #{run.id} {status}; resilience score {final_score:.0f}/100",
            )
            await self._safe_broadcast({"type": "score", "value": final_score})
            await self._safe_broadcast({"type": "postmortem", "text": postmortem})

            if self._run is run:
                self._run = None
            self._task = None

    async def _prepare_stack(self, run: RunContext) -> bool:
        if run.fixes:
            await self.hub.log(
                "info", "Restarting sample stack with RESILIENT=true"
            )
            restart = await self.stack.restart(resilient=True)
            if not restart.get("ok"):
                await self.hub.log(
                    "error",
                    f"Stack restart failed: "
                    f"{restart.get('error') or restart.get('output')}",
                )
                return False
            await self.hub.log(
                "info",
                f"Stack restarted with RESILIENT=true "
                f"in {restart.get('duration_ms')}ms",
            )
            healthy = await self.stack.wait_healthy()
        else:
            healthy = await self.stack.wait_healthy(timeout=15.0)

        if not healthy.get("ok"):
            await self.hub.log(
                "error",
                f"Sample stack unhealthy: {healthy.get('unreachable')}",
            )
            return False
        return True

    async def _inject(self, run: RunContext) -> dict[str, Any]:
        if run.fault == "kill":
            return await asyncio.to_thread(self.engine.kill, run.target)
        if run.fault == "latency":
            return await asyncio.to_thread(
                self.engine.latency, run.target, self.settings.latency_ms
            )
        return await asyncio.to_thread(
            self.engine.memory, run.target, self.settings.memory_mb
        )

    async def _recover(self, run: RunContext) -> dict[str, Any]:
        if run.fault == "kill":
            return await asyncio.to_thread(self.engine.restore, run.target)
        return await asyncio.to_thread(self.engine.reset_all)

    async def _ensure_recovered(self, run: RunContext) -> None:
        if run.fault_started is None or run.recovered:
            return
        with suppress(Exception):
            await self._recover(run)

    # ------------------------------------------------------------------
    # Live samples and events
    # ------------------------------------------------------------------
    def _label_for(self, timestamp: float) -> tuple[int | None, int]:
        if self._run is None:
            return None, 0
        if self._window is None:
            return self._run.id, 0
        start, end = self._window
        return self._run.id, 1 if start <= timestamp < end else 0

    async def _on_samples(self, samples: list[Sample]) -> None:
        self._recent.extend(samples)
        for sample in samples:
            status = status_for_sample(
                sample, self._baseline.get(sample.service)
            )
            previous = self._last_status.get(sample.service)
            self._last_status[sample.service] = status
            if previous is not None and previous != status:
                await self.hub.log(
                    "warn" if status != "ok" else "info",
                    f"{sample.service} is {status} "
                    f"({self._latency(sample)}ms)",
                )
            await self.hub.broadcast(
                {
                    "type": "state",
                    "service": sample.service,
                    "status": status,
                    "latency_ms": self._latency(sample),
                }
            )

        metrics = recent_metrics(list(self._recent))
        await self.hub.broadcast({"type": "metrics", **metrics})
        await self.hub.broadcast(
            {
                "type": "score",
                "value": resilience_score(
                    gateway_latency=metrics["gateway_latency"],
                    baseline_gateway=self._baseline.get("gateway"),
                    error_rate=metrics["error_rate"],
                ),
            }
        )

    def _reset_live_state(self) -> None:
        self._baseline = {}
        self._last_status = {}
        self._recent.clear()

    @staticmethod
    def _latency(sample: Sample) -> float:
        return round(sample.latency_ms, 1) if sample.latency_ms is not None else 0.0

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def _phases_for_run(self, run: RunContext) -> dict[str, dict[str, Any]]:
        end = run.recovery_end or time.time()
        rows = self.database.samples_between(run.started, end, service="gateway")
        windows: dict[str, tuple[float, float]] = {}
        if run.baseline_end is not None:
            windows["baseline"] = (run.started, run.baseline_end)
        if run.fault_started is not None:
            windows["fault"] = (run.fault_started, run.fault_ended or end)
        if run.fault_ended is not None:
            windows["recovery"] = (run.fault_ended, end)

        return {
            phase: phase_stats(
                [row for row in rows if start <= row["ts"] < window_end]
            )
            for phase, (start, window_end) in windows.items()
        }

    def _phases_from_row(
        self, run: dict[str, Any], samples: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        now = time.time()
        gateway_samples = [
            row for row in samples if row.get("service") == GATEWAY_SERVICE
        ]
        windows: dict[str, tuple[float, float]] = {}
        if run.get("baseline_end") is not None:
            windows["baseline"] = (run["started"], run["baseline_end"])
        if run.get("fault_started") is not None:
            windows["fault"] = (
                run["fault_started"],
                run.get("fault_ended") or now,
            )
        if run.get("fault_ended") is not None:
            windows["recovery"] = (
                run["fault_ended"],
                run.get("recovery_end") or now,
            )
        return {
            phase: phase_stats(
                [row for row in gateway_samples if start <= row["ts"] < window_end]
            )
            for phase, (start, window_end) in windows.items()
        }

    def _final_score(self, phases: dict[str, dict[str, Any]]) -> float:
        fault = phases.get("fault") or {}
        samples = int(fault.get("samples") or 0)
        if samples == 0:
            return 0.0
        error_rate = float(fault.get("errors") or 0) / samples
        return resilience_score(
            gateway_latency=float(fault.get("p50_ms") or 0.0),
            baseline_gateway=self._baseline.get("gateway"),
            error_rate=error_rate,
        )

    async def _safe_log(self, level: str, text: str) -> None:
        with suppress(Exception):
            await self.hub.log(level, text)

    async def _safe_broadcast(self, event: dict[str, Any]) -> None:
        with suppress(Exception):
            await self.hub.broadcast(event)

    def _default_collector_factory(
        self,
        database: ChaosDatabase,
        *,
        label_resolver: Callable[[float], tuple[int | None, int]],
        on_samples: Callable[[list[Sample]], Any],
    ) -> Collector:
        return Collector(
            database,
            host=self.settings.host,
            interval=self.settings.collector_interval,
            label_resolver=label_resolver,
            on_samples=on_samples,
        )
