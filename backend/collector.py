"""One-second telemetry collector for the ChaosPilot sample stack.

Every tick probes ``/health`` on the five backend services and performs a
synthetic user checkout through the gateway. Both kinds of observation are
written to SQLite with a ``label`` of ``1`` while an experiment window is open
and ``0`` otherwise.

The collector is independent of the FastAPI app: it can be started from the
smoke test, a worker process or the Phase 5 API lifespan.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

import httpx

from db import ChaosDatabase, Sample
from service_map import COLLECTOR_SERVICES, GATEWAY_SERVICE, service_url

LOGGER = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 10.0
SUCCESS_STATUSES = {"ok", "degraded"}


class Collector:
    """Async loop that records liveness, latency and errors once per second."""

    def __init__(
        self,
        database: ChaosDatabase,
        *,
        host: str = "127.0.0.1",
        interval: float = DEFAULT_INTERVAL_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        urls: Mapping[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.database = database
        self.interval = interval
        self.timeout = timeout
        self.urls = (
            dict(urls)
            if urls is not None
            else {
                name: service_url(name, host)
                for name in (GATEWAY_SERVICE, *COLLECTOR_SERVICES)
            }
        )
        missing = {GATEWAY_SERVICE, *COLLECTOR_SERVICES} - set(self.urls)
        if missing:
            raise ValueError(f"missing collector URLs for: {', '.join(sorted(missing))}")

        self._client = client
        self._owns_client = client is None
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Launch the background loop (idempotent)."""
        if self.running:
            return
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="chaospilot-collector")
        LOGGER.info("collector started (interval=%ss)", self.interval)

    async def stop(self) -> None:
        """Stop the background loop and close an internally created client."""
        self._stopping.set()
        if self._task is not None:
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
        LOGGER.info("collector stopped")

    async def __aenter__(self) -> Collector:
        await self.start()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.stop()

    async def _run(self) -> None:
        while not self._stopping.is_set():
            started = time.perf_counter()
            try:
                samples = await self.probe_once()
                self.database.insert_samples(samples)
            except Exception:  # keep collecting through transient DB/network errors
                LOGGER.exception("collector tick failed")

            elapsed = time.perf_counter() - started
            with suppress(TimeoutError):
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=max(0.0, self.interval - elapsed)
                )

    async def probe_once(self) -> list[Sample]:
        """Probe every service plus the gateway checkout and return the samples."""
        client = self._client
        if client is None:
            raise RuntimeError("collector client is not initialised; call start() first")

        # One timestamp and one experiment lookup per tick keeps every sample
        # aligned with the label decision, even when a probe is slow.
        tick_ts = time.time()
        experiment = self.database.active_experiment(at=tick_ts)
        experiment_id = int(experiment["id"]) if experiment else None
        label = 1 if experiment else 0

        probes = [
            self._probe_service(client, service, tick_ts, label, experiment_id)
            for service in COLLECTOR_SERVICES
        ]
        probes.append(self._probe_checkout(client, tick_ts, label, experiment_id))
        return list(await asyncio.gather(*probes))

    async def _probe_service(
        self,
        client: httpx.AsyncClient,
        service: str,
        ts: float,
        label: int,
        experiment_id: int | None,
    ) -> Sample:
        url = f"{self.urls[service]}/health"
        started = time.perf_counter()
        try:
            response = await client.get(url)
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            body = _json_dict(response)
            up = response.status_code == 200 and body.get("status") in SUCCESS_STATUSES
            return Sample(
                ts=ts,
                service=service,
                up=up,
                latency_ms=latency_ms,
                error=not up,
                label=label,
                experiment_id=experiment_id,
            )
        except Exception as exc:
            LOGGER.debug("health probe failed for %s: %s", service, exc)
            return Sample(
                ts=ts,
                service=service,
                up=False,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error=True,
                label=label,
                experiment_id=experiment_id,
            )

    async def _probe_checkout(
        self,
        client: httpx.AsyncClient,
        ts: float,
        label: int,
        experiment_id: int | None,
    ) -> Sample:
        url = f"{self.urls[GATEWAY_SERVICE]}/checkout"
        started = time.perf_counter()
        try:
            response = await client.get(url)
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            body = _json_dict(response)
            success = response.status_code == 200 and body.get("status") in SUCCESS_STATUSES
            if not success:
                LOGGER.debug(
                    "synthetic checkout failed: status=%s body=%s",
                    response.status_code,
                    body or response.text[:200],
                )
            return Sample(
                ts=ts,
                service=GATEWAY_SERVICE,
                up=success,
                latency_ms=latency_ms,
                error=not success,
                label=label,
                experiment_id=experiment_id,
            )
        except Exception as exc:
            LOGGER.debug("synthetic checkout failed: %s", exc)
            return Sample(
                ts=ts,
                service=GATEWAY_SERVICE,
                up=False,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error=True,
                label=label,
                experiment_id=experiment_id,
            )


def _json_dict(response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}
