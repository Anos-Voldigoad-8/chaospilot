"""Gateway service: the only public entry point."""

from __future__ import annotations

import os
from typing import Any

from common.service_base import create_app
from fastapi import FastAPI

AUTH_URL = os.getenv("AUTH_URL", "http://auth:8000")
ORDERS_URL = os.getenv("ORDERS_URL", "http://orders:8000")


def register_routes(app: FastAPI) -> None:
    client = app.state.dependency_client

    @app.get("/checkout")
    async def checkout() -> dict[str, Any]:
        auth = await client.get(
            f"{AUTH_URL}/verify",
            fallback={"verified": False, "user": "anonymous"},
        )
        order = await client.post(
            f"{ORDERS_URL}/create",
            payload={"user": auth.get("user", "anonymous")},
            fallback={"order_id": None, "status": "unavailable"},
        )
        degraded = bool(auth.get("degraded") or order.get("degraded"))
        return {
            "status": "degraded" if degraded else "ok",
            "degraded": degraded,
            "auth": auth,
            "order": order,
        }


app = create_app("gateway", register_routes=register_routes)
