"""Orders service: creates orders through payments and the database."""

from __future__ import annotations

import os
import uuid
from typing import Any

from common.service_base import create_app
from fastapi import FastAPI
from pydantic import BaseModel

PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments:8000")
DB_URL = os.getenv("DB_URL", "http://db:8000")
ORDER_AMOUNT = 42.50


class CreateOrderRequest(BaseModel):
    user: str = "anonymous"


def register_routes(app: FastAPI) -> None:
    client = app.state.dependency_client

    @app.post("/create")
    async def create_order(payload: CreateOrderRequest) -> dict[str, Any]:
        order_id = f"ord_{uuid.uuid4().hex[:10]}"

        payment = await client.post(
            f"{PAYMENTS_URL}/charge",
            payload={"order_id": order_id, "amount": ORDER_AMOUNT},
            fallback={"charge_id": None, "status": "unavailable"},
        )

        persisted = await client.post(
            f"{DB_URL}/records/orders/{order_id}",
            payload={
                "value": {
                    "order_id": order_id,
                    "user": payload.user,
                    "amount": ORDER_AMOUNT,
                    "payment_status": payment.get("status", "unknown"),
                }
            },
            fallback={"stored": False},
        )

        degraded = bool(
            payment.get("degraded")
            or persisted.get("degraded")
            or not persisted.get("stored")
        )
        return {
            "order_id": order_id,
            "status": "degraded" if degraded else "created",
            "degraded": degraded,
            "payment": payment,
            "stored": bool(persisted.get("stored")),
        }


app = create_app("orders", register_routes=register_routes)
