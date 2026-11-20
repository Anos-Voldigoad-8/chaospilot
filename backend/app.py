"""ChaosPilot API: simulator-based topology, scenarios and experiments.

All chaos is now produced by the in-process simulator (``backend/sim``) instead
of Docker. Experiments are driven by agent-built scenarios stored in SQLite.

Endpoints:
  GET    /health
  GET    /topology
  GET    /scenarios
  POST   /agent/collect        (streams progress over WebSocket)
  POST   /experiments/run      {scenario_id, fixes}
  GET    /experiments
  GET    /experiments/{id}
  WS     /ws
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.data_agent import DataAgent
from api_config import ApiSettings
from db import ChaosDatabase
from experiments import (
    ExperimentBusyError,
    ExperimentRunner,
    UnknownExperimentError,
    UnknownScenarioError,
)
from sim.simulator import Simulator
from sim.topology import topology
from ws import EventHub

LOGGER = logging.getLogger(__name__)

MAX_HISTORY = 500


class ExperimentRequest(BaseModel):
    scenario_id: int = Field(..., description="Scenario stored by the data agent")
    fixes: bool = False


class ExperimentResponse(BaseModel):
    id: int
    status: str
    scenario_id: int
    fault_type: str
    target_service: str
    fixes: bool


class CollectRequest(BaseModel):
    pass


def create_app(
    settings: ApiSettings | None = None,
    *,
    database: ChaosDatabase | None = None,
    runner: ExperimentRunner | None = None,
    agent: DataAgent | None = None,
) -> FastAPI:
    config = settings or ApiSettings.from_env()
    hub = EventHub()
    database = database or ChaosDatabase(config.db_path)
    agent_service = agent or DataAgent(database, hub=hub)
    experiment_runner = (
        runner
        or ExperimentRunner(
            database,
            hub,
            settings=config,
            simulator=Simulator(),
            agent=agent_service,
        )
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.database = database
        application.state.runner = experiment_runner
        application.state.hub = hub
        application.state.agent = agent_service
        LOGGER.info("ChaosPilot API ready (db=%s)", database.path)
        try:
            yield
        finally:
            await experiment_runner.shutdown()

    application = FastAPI(
        title="ChaosPilot API",
        description="Simulator-based chaos experiments and live telemetry",
        version="0.4.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    router = APIRouter()

    @router.get("/health")
    async def health(request: Request) -> dict[str, object]:
        runner: ExperimentRunner = request.app.state.runner
        return {
            "status": "ok",
            "service": "chaospilot-api",
            "experiment_running": runner.running,
            "active_experiment": runner.active_id,
            "websocket_clients": hub.connection_count,
        }

    @router.get("/topology")
    async def get_topology() -> dict[str, object]:
        return topology()

    @router.get("/scenarios")
    async def list_scenarios(request: Request, limit: int = 100) -> dict[str, object]:
        database: ChaosDatabase = request.app.state.database
        capped = max(1, min(limit, MAX_HISTORY))
        scenarios = database.list_scenarios(limit=capped)
        return {"scenarios": scenarios, "count": len(scenarios)}

    @router.post("/agent/collect")
    async def agent_collect(request: Request) -> dict[str, object]:
        service: DataAgent = request.app.state.agent
        scenarios = await service.collect()
        return {"scenarios": scenarios, "count": len(scenarios)}

    @router.post(
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
                scenario_id=payload.scenario_id,
                fixes=payload.fixes,
            )
        except UnknownScenarioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ExperimentBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/experiments")
    async def list_experiments(
        request: Request, limit: int = 50
    ) -> dict[str, object]:
        runner: ExperimentRunner = request.app.state.runner
        capped = max(1, min(limit, MAX_HISTORY))
        experiments = runner.history(limit=capped)
        return {"experiments": experiments, "count": len(experiments)}

    @router.get("/experiments/{experiment_id}")
    async def get_experiment(request: Request, experiment_id: int) -> dict[str, object]:
        runner: ExperimentRunner = request.app.state.runner
        detail = runner.detail(experiment_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="experiment not found")
        return detail

    @router.post("/experiments/{experiment_id}/resolve")
    async def resolve_experiment(
        experiment_id: int, request: Request
    ) -> dict[str, object]:
        runner: ExperimentRunner = request.app.state.runner
        try:
            return await runner.resolve(experiment_id)
        except UnknownExperimentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/experiments/{experiment_id}/stop")
    async def stop_experiment(
        experiment_id: int, request: Request
    ) -> dict[str, object]:
        runner: ExperimentRunner = request.app.state.runner
        try:
            return await runner.stop(experiment_id)
        except UnknownExperimentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    application.include_router(router)
    application.include_router(router, prefix="/api")

    @application.websocket("/ws")
    @application.websocket("/api/ws")
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
