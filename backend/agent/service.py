"""Agent orchestration: planning, live observation and postmortem steps."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

from agent.context import build_postmortem_context
from agent.llm import default_client
from agent.models import ExperimentPlan, Postmortem
from agent.planner import Planner
from agent.postmortem import PostmortemWriter
from agent.tools import get_topology, read_logs, read_metrics
from chaos.engine import ChaosEngine
from db import ChaosDatabase
from service_map import SERVICE_PORTS
from ws import EventHub

LOGGER = logging.getLogger(__name__)

_DEFAULT_DETECTOR = object()
_DEFAULT_LLM = object()


class RunLike(Protocol):
    """The subset of ``RunContext`` the agent needs."""

    id: int
    fault: str
    target: str
    fixes: bool


class AgentService:
    """Coordinates the planner, tools and postmortem writer for one API."""

    def __init__(
        self,
        database: ChaosDatabase,
        hub: EventHub | None = None,
        *,
        llm: Any | None | object = _DEFAULT_LLM,
        engine: ChaosEngine | None = None,
        detector: Any | None = _DEFAULT_DETECTOR,
    ) -> None:
        self.database = database
        self.hub = hub
        self.llm = default_client() if llm is _DEFAULT_LLM else llm
        self.engine = engine or ChaosEngine()
        self.detector = None if detector is _DEFAULT_DETECTOR else detector
        self.planner = Planner(self.llm)
        self.postmortem = PostmortemWriter(self.llm)

    def status(self) -> dict[str, Any]:
        """Describe the active provider without ever exposing a key."""
        return {
            "provider": getattr(self.llm, "name", "fallback"),
            "model": getattr(self.llm, "model", None),
            "mode": "llm" if self.llm is not None else "fallback",
        }

    async def _log(self, level: str, text: str) -> None:
        if self.hub is not None:
            await self.hub.log(level, text)
        else:
            LOGGER.log({"error": logging.ERROR, "warn": logging.WARNING}.get(level, logging.INFO), text)

    async def plan(self) -> ExperimentPlan:
        """Ask the planner for one experiment and stream the steps."""
        topology = get_topology()
        await self._log(
            "info",
            f"agent: tool get_topology() -> {len(topology.get('nodes', []))} services, "
            f"{len(topology.get('edges', []))} edges",
        )
        plan = await self.planner.plan()
        await self._log(
            "info",
            f"agent: plan {plan.fault} on {plan.target} ({plan.source}): {plan.hypothesis}",
        )
        return plan

    async def on_start(self, run: RunLike) -> None:
        await self._log(
            "info",
            f"agent: observing experiment #{run.id} ({run.fault} on {run.target}, "
            f"fixes={'on' if run.fixes else 'off'})",
        )

    async def on_baseline(self, run: RunLike) -> None:
        await self._log("info", "agent: tool read_metrics(all services) during baseline")
        snapshot = await asyncio.to_thread(self._snapshot)
        summary = ", ".join(
            f"{service} {metrics['latency_mean']:.0f}ms"
            for service, metrics in sorted(snapshot.items())
            if metrics.get("samples")
        )
        await self._log("info", f"agent: baseline metrics {summary or 'not ready'}")

        abnormal = [
            service
            for service, metrics in snapshot.items()
            if metrics.get("error_rate", 0.0) > 0.0 or metrics.get("up_ratio", 1.0) < 1.0
        ]
        for service in abnormal[:3]:
            logs = await asyncio.to_thread(read_logs, service, self.database)
            await self._log(
                "warn",
                f"agent: tool read_logs({service}) -> {logs['count']} entries",
            )

    async def on_fault(self, run: RunLike) -> None:
        await self._log(
            "warn",
            f"agent: inject_fault({run.target}, {run.fault}) active; "
            "collecting the anomaly window",
        )

    async def on_recovery(self, run: RunLike) -> None:
        await self._log(
            "info",
            f"agent: rollback path active for {run.target}; sampling recovery telemetry",
        )

    async def finish(self, run: RunLike) -> Postmortem:
        """Build the grounded context and stream the postmortem."""
        await self._log(
            "info",
            "agent: collecting topology, status timeline and anomaly scores",
        )
        context = await asyncio.to_thread(
            build_postmortem_context, self.database, run.id, detector=self.detector
        )
        report = await self.postmortem.generate(context)
        await self._log(
            "info",
            f"agent: postmortem ready ({report.source}, {report.word_count} words)",
        )
        return report

    def _snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            service: read_metrics(service, self.database, window_seconds=60.0)
            for service in SERVICE_PORTS
        }
