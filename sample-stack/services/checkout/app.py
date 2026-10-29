"""Checkout service: orchestrates cart and payments."""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from common.service_base import create_app
from fastapi import FastAPI
from pydantic import BaseModel

CART_URL = os.getenv("CART_URL", "http://cart:8000")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments:8000")
NOTIFICATIONS_URL = os.getenv("NOTIFICATIONS_URL", "http://notifications:8000")


class CheckoutRequest(BaseModel):
    cart_id: str
    amount: float


def register_routes(app: FastAPI) -> None:
    @app.post("/checkout")
    async def checkout(payload: CheckoutRequest) -> dict[str, Any]:
        order_id = f"ord_{uuid.uuid4().hex[:10]}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            cart = await client.get(f"{CART_URL}/carts/{payload.cart_id}")
            payment = await client.post(
                f"{PAYMENTS_URL}/charge",
                json={"order_id": order_id, "amount": payload.amount},
            )
            await client.post(
                f"{NOTIFICATIONS_URL}/notify",
                json={"order_id": order_id, "channel": "email"},
            )
        return {
            "order_id": order_id,
            "cart_status": cart.status_code,
            "payment_status": payment.status_code,
            "status": "confirmed" if payment.status_code == 200 else "failed",
        }

    @app.get("/work")
    async def work() -> dict[str, Any]:
        return {"service": "checkout", "order": f"ord_{uuid.uuid4().hex[:10]}"}


app = create_app("checkout", routes=register_routes)
