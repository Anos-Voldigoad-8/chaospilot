"""Simulator-based background experiment runner.

An experiment is driven by an agent-built scenario (fault type, target
service, duration) rather than a hand-picked fault. The in-process simulator
produces per-second telemetry for every service; those samples are written to
SQLite and broadcast over WebSocket. The run ends with a resilience score and
a postmortem that quotes the real incident title and source.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Protocol

from agent.data_agent import DataAgent
from api_config import ApiSettings
from db import ChaosDatabase, Sample
from ml.detector import AnomalyDetector
from ml.features import build_windows
from runtime import (
    baseline_from_rows,
    phase_stats,
    recent_metrics,
    resilience_breakdown,
    status_for_sample,
    statuses_from_rows,
    worst_status,
)
from sim.simulator import ExperimentPlan, Simulator
from sim.topology import affected_services
from ws import EventHub

LOGGER = logging.getLogger(__name__)

SUPPORTED_FAULTS = {"kill", "latency", "memory"}


class ExperimentBusyError(RuntimeError):
    """Raised when a run is already in progress."""


class UnknownScenarioError(ValueError):
    """Raised when the scenario id is not stored by the agent."""


class SimulatorLike(Protocol):
    def run(self, plan: ExperimentPlan) -> Any: ...


@dataclass
class RunContext:
    """Mutable in-memory state for one experiment task."""

    id: int
    scenario_id: int
    fault_type: str
    target_service: str
    fixes: bool
    started: float
    baseline_end: float | None = None
    fault_started: float | None = None
    fault_ended: float | None = None
    recovery_end: float | None = None
    baseline: dict[str, float] = field(default_factory=dict)
    recovered: bool = False


class ExperimentRunner:
    """Executes one simulator experiment at a time."""

    def __init__(
        self,
        database: ChaosDatabase,
        hub: EventHub,
        *,
        settings: ApiSettings | None = None,
        simulator: SimulatorLike | None = None,
        agent: DataAgent | None = None,
    ) -> None:
        self.database = database
        self.hub = hub
        self.settings = settings or ApiSettings.from_env()
        self.simulator = simulator or Simulator()
        self.agent = agent

        self._task: asyncio.Task[None] | None = None
        self._run: RunContext | None = None
        self._baseline: dict[str, float] = {}
        self._last_status: dict[str, str] = {}
        self._fault_status: dict[str, str] = {}
        self._recent: deque[Sample] = deque(maxlen=60)
        self._lock = asyncio.Lock()
        self._detector: Any | None = None
        self._detector_loaded = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def active_id(self) -> int | None:
        return self._run.id if self._run is not None else None

    async def start(self, *, scenario_id: int, fixes: bool) -> dict[str, Any]:
        scenario = self.database.get_scenario(scenario_id)
        if scenario is None:
            raise UnknownScenarioError(f"scenario #{scenario_id} is not stored by the agent")
        if scenario["fault_type"] not in SUPPORTED_FAULTS:
            raise ValueError(f"unsupported fault type: {scenario['fault_type']}")

        async with self._lock:
            if self.running:
                raise ExperimentBusyError(
                    f"experiment #{self.active_id} is already running"
                )
            started = time.time()
            experiment_id = self.database.start_experiment(
                scenario["fault_type"],
                scenario["target_service"],
                fixes_on=fixes,
                started=started,
            )
            self.database.create_run(experiment_id, resilient=fixes, status="pending")
            run = RunContext(
                id=experiment_id,
                scenario_id=scenario_id,
                fault_type=scenario["fault_type"],
                target_service=scenario["target_service"],
                fixes=fixes,
                started=started,
            )
            self._run = run
            self._task = asyncio.create_task(
                self._execute(run, scenario), name=f"experiment-{experiment_id}"
            )
            detail = self.database.run_detail(experiment_id)
        return {
            "id": experiment_id,
            "status": "pending",
            "scenario_id": scenario_id,
            "fault_type": scenario["fault_type"],
            "target_service": scenario["target_service"],
            "fixes": fixes,
            **(detail or {}),
        }

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

    # ------------------------------------------------------------------ #
    # Run lifecycle
    # ------------------------------------------------------------------ #
    async def _execute(self, run: RunContext, scenario: dict[str, Any]) -> None:
        failure: str | None = None
        status = "completed"
        final_score = 0.0
        result = None

        try:
            await self.hub.log(
                "info",
                f"Experiment #{run.id} started: {run.fault_type} on {run.target_service} "
                f"(scenario #{run.scenario_id}, fixes={'on' if run.fixes else 'off'})",
            )
            self.database.update_run(run.id, status="preparing")

            fault_seconds = min(float(scenario.get("duration_minutes") or 20) * 60.0, 30.0)
            plan = ExperimentPlan(
                fault=run.fault_type,
                target=run.target_service,
                fixes=run.fixes,
                baseline_seconds=8.0,
                fault_seconds=fault_seconds,
                recovery_seconds=8.0,
                seed=1000 + run.id,
            )
            result = await asyncio.to_thread(self.simulator.run, plan)

            samples = [
                Sample(
                    ts=sample.ts,
                    service=sample.service,
                    up=sample.up,
                    latency_ms=sample.latency_ms,
                    error=sample.error_rate > 0.02,
                    label=sample.label,
                    experiment_id=run.id,
                )
                for sample in result.samples
            ]

            self.database.update_run(run.id, status="baseline")
            await self.hub.log("info", "Baseline: collecting normal telemetry")
            # Broadcast baseline samples.
            baseline_samples = [s for s in samples if s.label == 0][: 8 * 6]
            await self._broadcast_samples(run, baseline_samples, fast=True)
            run.baseline_end = time.time()
            baseline_rows = self.database.samples_between(run.started, run.baseline_end)
            self._baseline = baseline_from_rows(baseline_rows)
            self.database.update_run(run.id, baseline_end=run.baseline_end)

            run.fault_started = time.time()
            self.database.update_run(
                run.id, status="fault", fault_started=run.fault_started
            )
            await self.hub.log(
                "warn",
                f"Fault active: {run.fault_type} on {run.target_service} "
                f"for {fault_seconds:.0f}s",
            )
            fault_samples = [s for s in samples if s.label == 1]
            await self._broadcast_samples(run, fault_samples, fast=False)
            await asyncio.sleep(0.2)

            run.fault_ended = time.time()
            self.database.update_run(run.id, status="recovery", fault_ended=run.fault_ended)
            await self.hub.log("info", "Fault window closed; observing recovery")
            recovery_samples = [s for s in samples if s.label == 0 and s.experiment_id is not None]
            await self._broadcast_samples(run, recovery_samples, fast=True)
            run.recovery_end = time.time()
            self.database.update_run(run.id, status="completed")
        except asyncio.CancelledError:
            failure = "cancelled during shutdown"
            status = "cancelled"
            await self._safe_log("warn", f"Experiment #{run.id} cancelled")
        except Exception as exc:  # a failed run still produces a report
            LOGGER.exception("experiment %s failed", run.id)
            failure = f"{type(exc).__name__}: {exc}"
            status = "failed"
            await self._safe_log("error", f"Experiment #{run.id} failed: {failure}")
        finally:
            # Persist all samples (some may not have been broadcast yet).
            all_db_samples = [
                Sample(
                    ts=sample.ts,
                    service=sample.service,
                    up=sample.up,
                    latency_ms=sample.latency_ms,
                    error=sample.error_rate > 0.02,
                    label=sample.label,
                    experiment_id=run.id,
                )
                for sample in result.samples
            ] if result is not None else []
            if all_db_samples:
                self.database.insert_samples(all_db_samples)

            run.recovery_end = run.recovery_end or time.time()
            if run.fault_started is not None and run.fault_ended is None:
                run.fault_ended = run.recovery_end
            self.database.end_experiment(run.id, ended=run.recovery_end)

            phases = self._phases_for_run(run)
            score = self._final_score(run)
            final_score = score["value"]
            postmortem = self._build_postmortem(run, scenario, phases, final_score, failure)
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
                f"Experiment #{run.id} {status}; resilience score {final_score:.0f}/100 "
                f"({len(score['failed'])} failed, {len(score['degraded'])} degraded, "
                f"contained={'yes' if score['contained'] else 'no'})",
            )
            await self._safe_broadcast({"type": "score", **score})
            agent_report = await self._agent_finish(run, scenario)
            if agent_report is None:
                await self._safe_broadcast(
                    {"type": "postmortem", "text": postmortem}
                )
            else:
                await self._safe_broadcast(
                    {
                        "type": "postmortem",
                        "text": agent_report.text,
                        "source": agent_report.source,
                        "structured": agent_report.model_dump(),
                    }
                )

            if self._run is run:
                self._run = None
            self._task = None

    async def _broadcast_samples(
        self, run: RunContext, samples: list[Sample], *, fast: bool
    ) -> None:
        """Insert and broadcast samples, grouped by timestamp."""
        grouped: dict[float, list[Sample]] = {}
        for sample in samples:
            grouped.setdefault(sample.ts, []).append(sample)
        delay = 0.0 if fast else 0.05
        for ts in sorted(grouped):
            batch = grouped[ts]
            self.database.insert_samples(batch)
            self._recent.extend(batch)
            for sample in batch:
                await self._emit_state(sample)
            metrics = recent_metrics(list(self._recent))
            await self.hub.broadcast({"type": "metrics", **metrics})
            anomalies = self._anomaly_scores()
            await self.hub.broadcast(
                {"type": "anomaly", "value": max(anomalies.values(), default=0.0), "services": anomalies}
            )
            await self.hub.broadcast({"type": "score", **self._live_score()})
            if delay:
                await asyncio.sleep(delay)

    async def _emit_state(self, sample: Sample) -> None:
        status = status_for_sample(sample, self._baseline.get(sample.service))
        previous = self._last_status.get(sample.service)
        self._last_status[sample.service] = status
        if sample.label == 1:
            self._fault_status[sample.service] = worst_status(
                self._fault_status.get(sample.service), status
            )
        if previous is not None and previous != status:
            await self.hub.log(
                "warn" if status != "ok" else "info",
                f"{sample.service} is {status} ({sample.latency_ms}ms)",
            )
        await self.hub.broadcast(
            {
                "type": "state",
                "service": sample.service,
                "status": status,
                "latency_ms": sample.latency_ms or 0.0,
            }
        )

    def _live_score(self) -> dict[str, Any]:
        run = self._run
        if run is None:
            return {
                "value": 100.0,
                "failed": [],
                "degraded": [],
                "contained": True,
                "bonus": 0.0,
            }
        return resilience_breakdown(
            self._fault_status or self._last_status,
            fixes=run.fixes,
            blast_radius=affected_services(run.target_service, resilient=run.fixes),
        )

    def _anomaly_scores(self) -> dict[str, float]:
        rows = [
            {
                "ts": sample.ts,
                "service": sample.service,
                "up": sample.up,
                "latency_ms": sample.latency_ms,
                "error": sample.error,
                "label": sample.label,
                "experiment_id": sample.experiment_id,
            }
            for sample in self._recent
        ]
        detector = self._load_detector()
        if detector is not None and rows:
            try:
                windows = build_windows(rows, {}, window_seconds=5.0, min_samples=3)
                latest: dict[str, float] = {}
                for window in windows:
                    latest[window.service] = round(float(detector.score(window)), 4)
                if latest:
                    return latest
            except Exception as exc:
                LOGGER.warning("live anomaly scoring failed: %s", type(exc).__name__)
        return self._heuristic_anomalies(rows)

    def _load_detector(self) -> Any | None:
        if self._detector_loaded:
            return self._detector
        self._detector_loaded = True
        try:
            self._detector = AnomalyDetector.load()
        except Exception:
            self._detector = None
        return self._detector

    def _heuristic_anomalies(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        cutoff = time.time() - 5.0
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if float(row["ts"]) >= cutoff:
                grouped.setdefault(str(row["service"]), []).append(row)
        scores: dict[str, float] = {}
        for service, samples in grouped.items():
            base = self._baseline.get(service) or 0.0
            latencies = [float(s["latency_ms"]) for s in samples if s.get("latency_ms") is not None]
            ratio = max(latencies) / base if latencies and base > 0 else 1.0
            error_rate = sum(1 for s in samples if s.get("error")) / len(samples)
            down = any(not s.get("up") for s in samples)
            scores[service] = round(
                min(1.0, max(0.0, (ratio - 1.0) / 2.0, error_rate, 0.8 if down else 0.0)),
                4,
            )
        return scores

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

    def _phases_from_row(self, run: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        now = time.time()
        gateway_samples = [row for row in samples if row.get("service") == "gateway"]
        windows: dict[str, tuple[float, float]] = {}
        if run.get("baseline_end") is not None:
            windows["baseline"] = (run["started"], run["baseline_end"])
        if run.get("fault_started") is not None:
            windows["fault"] = (run["fault_started"], run.get("fault_ended") or now)
        if run.get("fault_ended") is not None:
            windows["recovery"] = (run["fault_ended"], run.get("recovery_end") or now)
        return {
            phase: phase_stats(
                [row for row in gateway_samples if start <= row["ts"] < window_end]
            )
            for phase, (start, window_end) in windows.items()
        }

    def _final_score(self, run: RunContext) -> dict[str, Any]:
        start = run.fault_started or run.started
        end = run.fault_ended or run.recovery_end or time.time()
        rows = self.database.samples_between(start, end)
        statuses = statuses_from_rows(rows, self._baseline)
        if not statuses:
            return {
                "value": 0.0,
                "failed": [],
                "degraded": [],
                "contained": False,
                "bonus": 0.0,
            }
        return resilience_breakdown(
            statuses,
            fixes=run.fixes,
            blast_radius=affected_services(run.target_service, resilient=run.fixes),
        )

    def _build_postmortem(
        self,
        run: RunContext,
        scenario: dict[str, Any],
        phases: dict[str, dict[str, Any]],
        score: float,
        failure: str | None,
    ) -> str:
        parts = [
            f"Experiment #{run.id}: {run.fault_type} on {run.target_service} "
            f"from scenario #{run.scenario_id} "
            f"\"{scenario.get('title','')}\" "
            f"(source: {scenario.get('source','')}, data: {scenario.get('data_source','')}, "
            f"fixes={'on' if run.fixes else 'off'}).",
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

    async def _agent_finish(self, run: RunContext, scenario: dict[str, Any]):
        if self.agent is None:
            return None
        # DataAgent has no finish(); keep the deterministic postmortem unless
        # an agent with a finish() hook is provided later.
        return None

    async def _safe_log(self, level: str, text: str) -> None:
        with suppress(Exception):
            await self.hub.log(level, text)

    async def _safe_broadcast(self, event: dict[str, Any]) -> None:
        with suppress(Exception):
            await self.hub.broadcast(event)
