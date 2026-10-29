"""Fault injection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from core.api.deps import get_chaos_manager
from core.api.schemas import FaultOut
from core.chaos.manager import ChaosError, ChaosManager
from core.chaos.models import FaultRequest
from core.services import store

router = APIRouter(tags=["chaos"])


@router.get("/api/faults", response_model=list[FaultOut])
def list_faults(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    chaos: ChaosManager = Depends(get_chaos_manager),
) -> list[dict]:
    chaos.expire_due()
    return store.list_faults(chaos.database, status=status, limit=limit)


@router.post("/api/faults", response_model=FaultOut, status_code=201)
def inject_fault(
    request: FaultRequest, chaos: ChaosManager = Depends(get_chaos_manager)
) -> dict:
    try:
        return chaos.inject(request)
    except ChaosError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/faults/{fault_id}/recover", response_model=FaultOut)
def recover_fault(
    fault_id: str, chaos: ChaosManager = Depends(get_chaos_manager)
) -> dict:
    try:
        return chaos.recover(fault_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="fault not found") from exc
