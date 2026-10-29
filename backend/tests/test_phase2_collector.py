"""Phase 2 collector behaviour against an in-process ASGI stack."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from collector import Collector
from db import ChaosDatabase
from service_map import COLLECTOR_SERVICES, GATEWAY_SERVICE

SERVICES = (GATEWAY_SERVICE, *COLLECTOR_SERVICES)
URLS = {name: f"http://{name}.test" for name in SERVICES}


def make_app(*, failing: set[str] | None = None) -> FastAPI:
    failing = failing or set()
    app = FastAPI()

    @app.get("/health")
    async def health(request: Request) -> Response:
        host = request.headers.get("host", "").split(":")[0]
        if host.split(".")[0] in failing:
            return JSONResponse({"status": "error"}, status_code=503)
        return JSONResponse({"status": "ok", "p50_latency_ms": 1.0})

    @app.get("/checkout")
    async def checkout() -> Response:
        if GATEWAY_SERVICE in failing:
            return JSONResponse({"status": "dependency_error"}, status_code=502)
        return JSONResponse({"status": "ok", "degraded": False})

    return app


def probe(
    database: ChaosDatabase,
    *,
    app: FastAPI | None = None,
):
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app or make_app()))
    collector = Collector(database, urls=URLS, client=client)

    async def run():
        try:
            return await collector.probe_once()
        finally:
            await client.aclose()

    return asyncio.run(run())


def test_probe_once_covers_every_service_and_checkout(tmp_path: Path) -> None:
    database = ChaosDatabase(tmp_path / "chaos.db")
    samples = probe(database)

    assert len(samples) == len(SERVICES)
    assert {sample.service for sample in samples} == set(SERVICES)
    assert all(sample.up for sample in samples)
    assert all(sample.error is False for sample in samples)
    assert all(sample.label == 0 for sample in samples)
    assert GATEWAY_SERVICE in {sample.service for sample in samples}

    database.insert_samples(samples)
    assert database.count_samples() == len(SERVICES)


def test_probe_once_labels_active_experiment(tmp_path: Path) -> None:
    database = ChaosDatabase(tmp_path / "chaos.db")
    experiment_id = database.start_experiment("latency", "payments")

    samples = probe(database)
    database.insert_samples(samples)

    assert all(sample.label == 1 for sample in samples)
    assert all(sample.experiment_id == experiment_id for sample in samples)
    assert len(database.samples_between(0.0, 10**12, label=1)) == len(SERVICES)


def test_probe_once_marks_failures(tmp_path: Path) -> None:
    database = ChaosDatabase(tmp_path / "chaos.db")
    samples = probe(database, app=make_app(failing={"payments", GATEWAY_SERVICE}))
    by_service = {sample.service: sample for sample in samples}

    assert by_service["payments"].up is False
    assert by_service["payments"].error is True
    assert by_service[GATEWAY_SERVICE].up is False
    assert by_service[GATEWAY_SERVICE].error is True
    assert by_service["auth"].up is True
    assert by_service["auth"].error is False
