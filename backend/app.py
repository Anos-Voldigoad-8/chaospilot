"""ChaosPilot Phase 3 API: topology, experiments and a live WebSocket stream."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.llm import default_client
from agent.service import AgentService
from api_config import ApiSettings
from chaos.engine import ChaosEngine
from db import ChaosDatabase
from experiments import (
    CollectorFactory,
    ExperimentBusyError,
    ExperimentRunner,
    UnknownTargetError,
)
from stack import StackController
from topology import topology
from ws import EventHub

LOGGER = logging.getLogger(__name__)

MAX_HISTORY = 500
DEFAULT_AGENT_LLM = object()


class ExperimentRequest(BaseModel):
    fault: Literal["kill", "latency", "memory"]
    target: str
    fixes: bool = False


class ExperimentResponse(BaseModel):
    id: int
    status: str
    fault: str
    target: str
    fixes: bool


def create_app(
    settings: ApiSettings | None = None,
    *,
    engine: ChaosEngine | None = None,
    stack: StackController | None = None,
    collector_factory: CollectorFactory | None = None,
    agent: AgentService | None = None,
    agent_llm: object | None = DEFAULT_AGENT_LLM,
) -> FastAPI:
    config = settings or ApiSettings.from_env()
    hub = EventHub()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = ChaosDatabase(config.db_path)
        llm = default_client() if agent_llm is DEFAULT_AGENT_LLM else agent_llm
        agent_service = agent or AgentService(
            database, hub, llm=llm, engine=engine
        )
        runner = ExperimentRunner(
            database,
            hub,
            settings=config,
            engine=engine,
            stack=stack,
            collector_factory=collector_factory,
            agent=agent_service,
        )
        application.state.database = database
        application.state.runner = runner
        application.state.hub = hub
        application.state.agent = agent_service
        LOGGER.info(
            "ChaosPilot API ready (db=%s, stack=%s, baseline=%ss, fault=%ss)",
            database.path,
            config.host,
            config.baseline_seconds,
            config.fault_seconds,
        )
        try:
            yield
        finally:
            await runner.shutdown()

    application = FastAPI(
        title="ChaosPilot API",
        description="Topology, chaos experiments and live telemetry",
        version="0.3.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    async def health(request: Request) -> dict[str, object]:
        runner: ExperimentRunner = request.app.state.runner
        return {
            "status": "ok",
            "service": "chaospilot-api",
            "experiment_running": runner.running,
            "active_experiment": runner.active_id,
            "websocket_clients": hub.connection_count,
        }

    @application.get("/topology")
    async def get_topology() -> dict[str, object]:
        return topology()

    @application.post(
        "/experiments/run",
        status_code=202,
        response_model=ExperimentResponse,
    )
    async def run_experiment(
        payload: ExperimentRequest, request: Request
    ) -> dict[str, object]:
        runner: ExperimentRunner = request.app.state.runner
        try:
            return await runner.start(
                fault=payload.fault,
                target=payload.target,
                fixes=payload.fixes,
            )
        except UnknownTargetError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ExperimentBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.get("/agent/status")
    async def agent_status(request: Request) -> dict[str, object]:
        service: AgentService = request.app.state.agent
        return service.status()

    @application.post("/agent/plan")
    async def agent_plan(request: Request) -> dict[str, object]:
        service: AgentService = request.app.state.agent
        plan = await service.plan()
        return plan.model_dump()

    @application.get("/experiments")
    async def list_experiments(
        request: Request, limit: int = 50
    ) -> dict[str, object]:
        runner: ExperimentRunner = request.app.state.runner
        capped = max(1, min(limit, MAX_HISTORY))
        experiments = runner.history(limit=capped)
        return {"experiments": experiments, "count": len(experiments)}

    @application.get("/experiments/{experiment_id}")
    async def get_experiment(request: Request, experiment_id: int) -> dict[str, object]:
        runner: ExperimentRunner = request.app.state.runner
        detail = runner.detail(experiment_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="experiment not found")
        return detail

    @application.websocket("/ws")
    async def websocket_stream(websocket: WebSocket) -> None:
        await hub.connect(websocket)
        with suppress(Exception):
            await websocket.send_json(
                {
                    "type": "log",
                    "level": "info",
                    "text": "connected to ChaosPilot live stream",
                }
            )
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(websocket)

    return application


app = create_app()
