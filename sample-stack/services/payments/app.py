"""Payments service: simulates charges and records them in the database."""

from __future__ import annotations

import os
import uuid
from typing import Any

from common.service_base import create_app
from fastapi import FastAPI
from pydantic import BaseModel, Field

DB_URL = os.getenv("DB_URL", "http://db:8000")


class ChargeRequest(BaseModel):
    order_id: str
    amount: float = Field(gt=0)


def register_routes(app: FastAPI) -> None:
    client = app.state.dependency_client

    @app.post("/charge")
    async def charge(payload: ChargeRequest) -> dict[str, Any]:
        charge_id = f"ch_{uuid.uuid4().hex[:12]}"
        record = {
            "charge_id": charge_id,
            "order_id": payload.order_id,
            "amount": payload.amount,
            "status": "captured",
        }
        persisted = await client.post(
            f"{DB_URL}/records/payments/{charge_id}",
            payload={"value": record},
            fallback={"stored": False},
        )
        degraded = bool(persisted.get("degraded") or not persisted.get("stored"))
        return {
            **record,
            "status": "captured" if not degraded else "captured_unpersisted",
            "degraded": degraded,
            "stored": bool(persisted.get("stored")),
        }


app = create_app("payments", register_routes=register_routes)
