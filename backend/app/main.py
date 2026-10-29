"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agent.agent import IncidentAgent
from app.api import agent as agent_routes
from app.api import anomalies as anomaly_routes
from app.api import chaos as chaos_routes
from app.api import services as service_routes
from app.api import system as system_routes
from app.chaos.manager import ChaosManager
from app.collector import simulator
from app.collector.collector import TelemetryCollector
from app.config import AppSettings, LLMSettings, get_llm_settings, get_settings
from app.database import get_database
from app.ml.service import AnomalyService
from app.services.registry import seed_services

LOGGER = logging.getLogger(__name__)


def _configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        )


def create_app(
    settings: AppSettings | None = None,
    llm_settings: LLMSettings | None = None,
) -> FastAPI:
    _configure_logging()
    app_settings = settings or get_settings()
    llm_config = llm_settings or get_llm_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = get_database(app_settings.db_file)
        seed_services(database)

        seeded = simulator.seed_history(database)
        if seeded:
            LOGGER.info("Seeded %s historical metric samples", seeded)

        anomaly_service = AnomalyService(database, app_settings.model_path)
        if not anomaly_service.is_ready:
            result = anomaly_service.train()
            LOGGER.info("Initial detector training: %s", result.reason or "ok")

        chaos = ChaosManager(database, app_settings)
        agent = IncidentAgent(database, llm_config)
        collector = TelemetryCollector(database, anomaly_service, app_settings)

        app.state.settings = app_settings
        app.state.llm_settings = llm_config
        app.state.database = database
        app.state.anomaly_service = anomaly_service
        app.state.chaos = chaos
        app.state.agent = agent
        app.state.collector = collector

        task: asyncio.Task[None] | None = None
        if app_settings.collector_enabled:
            task = asyncio.create_task(collector.run_forever(), name="chaospilot-collector")

        LOGGER.info(
            "ChaosPilot %s ready (simulation=%s, docker=%s, llm=%s)",
            __version__,
            app_settings.simulation_mode,
            app_settings.docker_enabled,
            llm_config.provider,
        )
        try:
            yield
        finally:
            collector.stop()
            if task is not None:
                with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                    await asyncio.wait_for(task, timeout=5)

    app = FastAPI(
        title="ChaosPilot API",
        version=__version__,
        description=(
            "Chaos engineering, anomaly detection and LLM incident analysis "
            "for the ChaosPilot sample stack."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system_routes.router)
    app.include_router(service_routes.router)
    app.include_router(anomaly_routes.router)
    app.include_router(chaos_routes.router)
    app.include_router(agent_routes.router)
    return app


app = create_app()
