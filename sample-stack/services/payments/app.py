"""Payments service: simulated charges and refunds."""

from __future__ import annotations

import uuid
from typing import Any

from common.service_base import create_app
from fastapi import FastAPI
from pydantic import BaseModel, Field

CHARGES: dict[str, dict[str, Any]] = {}


class ChargeRequest(BaseModel):
    order_id: str
    amount: float = Field(gt=0)


def register_routes(app: FastAPI) -> None:
    @app.post("/charge")
    async def charge(payload: ChargeRequest) -> dict[str, Any]:
        charge_id = f"ch_{uuid.uuid4().hex[:12]}"
        CHARGES[charge_id] = {
            "charge_id": charge_id,
            "order_id": payload.order_id,
            "amount": payload.amount,
            "status": "captured",
        }
        return CHARGES[charge_id]

    @app.post("/refund/{charge_id}")
    async def refund(charge_id: str) -> dict[str, Any]:
        charge = CHARGES.get(charge_id)
        if charge is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="charge not found")
        charge["status"] = "refunded"
        return charge

    @app.get("/work")
    async def work() -> dict[str, Any]:
        return {"service": "payments", "charges": len(CHARGES)}


app = create_app("payments", routes=register_routes)
