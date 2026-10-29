"""Incident and agent endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from core.agent.agent import IncidentAgent
from core.api.deps import get_incident_agent
from core.api.schemas import DiagnoseRequest, IncidentOut
from core.services import store

router = APIRouter(tags=["agent"])


@router.get("/api/agent/status")
def agent_status(agent: IncidentAgent = Depends(get_incident_agent)) -> dict:
    return agent.status()


@router.post("/api/agent/diagnose", response_model=IncidentOut)
async def diagnose(
    request: DiagnoseRequest, agent: IncidentAgent = Depends(get_incident_agent)
) -> dict:
    try:
        return await agent.diagnose(request.service_id, request.anomaly_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/incidents", response_model=list[IncidentOut])
def list_incidents(
    limit: int = Query(default=20, ge=1, le=200),
    agent: IncidentAgent = Depends(get_incident_agent),
) -> list[dict]:
    return store.list_incidents(agent.database, limit=limit)


@router.get("/api/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(
    incident_id: str, agent: IncidentAgent = Depends(get_incident_agent)
) -> dict:
    incident = store.get_incident(agent.database, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident
