"""Health, capability and dashboard overview endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request

from core import __version__
from core.agent.agent import IncidentAgent
from core.api.deps import (
    get_agent_or_none,
    get_app_settings,
    get_chaos_manager,
    get_db,
    get_incident_agent,
    get_llm_settings,
)
from core.api.schemas import (
    HealthOut,
    OverviewOut,
    OverviewSummary,
)
from core.api.serializers import to_metric, to_service
from core.chaos.manager import ChaosManager
from core.config import AppSettings, LLMSettings
from core.database import Database
from core.services import store

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthOut)
def health(
    settings: AppSettings = Depends(get_app_settings),
    llm_settings: LLMSettings = Depends(get_llm_settings),
) -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.env,
        "simulation_mode": settings.simulation_mode,
        "docker_enabled": settings.docker_enabled,
        "llm_provider": llm_settings.provider,
    }


@router.get("/api/config")
def config(
    settings: AppSettings = Depends(get_app_settings),
    llm_settings: LLMSettings = Depends(get_llm_settings),
    agent: IncidentAgent | None = Depends(get_agent_or_none),
) -> dict:
    return {
        "simulation_mode": settings.simulation_mode,
        "docker_enabled": settings.docker_enabled,
        "collector_interval_seconds": settings.collector_interval_seconds,
        "history_minutes": settings.history_minutes,
        "llm": agent.status()
        if agent
        else {"provider": llm_settings.provider, "mode": "unavailable"},
    }


@router.get("/api/overview", response_model=OverviewOut)
def overview(
    database: Database = Depends(get_db),
    chaos: ChaosManager = Depends(get_chaos_manager),
    agent: IncidentAgent = Depends(get_incident_agent),
) -> dict:
    chaos.expire_due()
    latest_by_service = {row["service_id"]: row for row in store.latest_metrics(database)}
    active_faults = store.active_faults(database)
    fault_counts: dict[str, int] = {}
    for fault in active_faults:
        fault_counts[fault["service_id"]] = fault_counts.get(fault["service_id"], 0) + 1

    services = [
        to_service(row, latest_by_service.get(row["id"]), fault_counts.get(row["id"], 0))
        for row in store.list_services(database)
    ]
    anomalies = store.list_anomalies(database, limit=15)
    incidents = store.list_incidents(database, limit=5)

    healthy = sum(1 for service in services if service["status"] == "healthy")
    degraded = sum(1 for service in services if service["status"] in {"degraded", "down"})

    return {
        "generated_at": time.time(),
        "summary": OverviewSummary(
            services_total=len(services),
            services_healthy=healthy,
            services_degraded=degraded,
            active_faults=len(active_faults),
            anomalies_recent=len(anomalies),
            incidents_recent=len(incidents),
        ),
        "services": services,
        "latest_metrics": [to_metric(row) for row in latest_by_service.values()],
        "anomalies": anomalies,
        "active_faults": active_faults,
        "incidents": incidents,
        "llm": agent.status(),
    }


@router.get("/")
def root(request: Request) -> dict:
    return {
        "name": "ChaosPilot",
        "version": __version__,
        "docs": str(request.url_for("swagger_ui_html")),
        "health": str(request.url_for("health")),
    }
