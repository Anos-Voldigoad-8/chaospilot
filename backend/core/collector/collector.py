"""Async telemetry collector.

Each tick polls every service (or simulates a sample), stores it, expires due
faults and asks the anomaly service to score the newest data.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.collector import simulator
from core.config import AppSettings
from core.database import Database
from core.ml.service import AnomalyService
from core.services import store
from core.services.registry import SERVICES, ServiceDefinition

LOGGER = logging.getLogger(__name__)


@dataclass
class TickResult:
    samples: int = 0
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class TelemetryCollector:
    def __init__(
        self,
        database: Database,
        anomaly_service: AnomalyService,
        settings: AppSettings,
        *,
        interval_seconds: float | None = None,
    ) -> None:
        self.database = database
        self.anomaly_service = anomaly_service
        self.settings = settings
        self.interval_seconds = interval_seconds or settings.collector_interval_seconds
        self._stop = asyncio.Event()
        self._ticks = 0

    async def run_forever(self) -> None:
        LOGGER.info("Collector started (interval=%.1fs)", self.interval_seconds)
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception:  # pragma: no cover - keep the loop alive
                LOGGER.exception("Collector tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue
        LOGGER.info("Collector stopped")

    def stop(self) -> None:
        self._stop.set()

    def _faults_by_service(self) -> dict[str, list[dict[str, Any]]]:
        now = time.time()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for fault in store.active_faults(self.database):
            ends_at = fault.get("ends_at")
            if ends_at is not None and float(ends_at) <= now:
                store.set_fault_status(self.database, str(fault["id"]), "expired")
                continue
            grouped.setdefault(str(fault["service_id"]), []).append(fault)
        return grouped

    def _simulated_sample(
        self,
        service: ServiceDefinition,
        faults: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        dependency_faults: list[dict[str, Any]] = []
        for dependency in service.dependencies:
            dependency_faults.extend(faults.get(dependency, []))
        return simulator.generate_sample(
            service.id,
            faults.get(service.id, []),
            dependency_faults,
        )

    async def _fetch_real(self, client: httpx.AsyncClient, service: ServiceDefinition) -> dict[str, Any]:
        try:
            response = await client.get(f"{service.url}/metrics")
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            payload["timestamp"] = time.time()
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            LOGGER.debug("Metrics fetch failed for %s: %s", service.id, exc)
            return {
                "timestamp": time.time(),
                "latency_ms": 0.0,
                "error_rate": 1.0,
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "request_rate": 0.0,
                "unreachable": True,
            }

    async def tick(self) -> TickResult:
        result = TickResult()
        faults = self._faults_by_service()
        samples: dict[str, dict[str, Any]] = {}

        if self.settings.simulation_mode:
            for service in SERVICES:
                samples[service.id] = self._simulated_sample(service, faults)
        else:
            async with httpx.AsyncClient(timeout=3.0) as client:
                fetched = await asyncio.gather(
                    *(self._fetch_real(client, service) for service in SERVICES)
                )
            samples = {service.id: sample for service, sample in zip(SERVICES, fetched, strict=True)}

        for service in SERVICES:
            store.record_metric(self.database, service.id, samples[service.id])
            result.samples += 1

        result.anomalies = self.anomaly_service.detect()
        self._ticks += 1

        if self._ticks % 60 == 0:
            cutoff = time.time() - self.settings.history_minutes * 60
            store.prune_metrics(self.database, cutoff)

        return result


def create_collector(
    database: Database, anomaly_service: AnomalyService, settings: AppSettings
) -> TelemetryCollector:
    return TelemetryCollector(database, anomaly_service, settings)
