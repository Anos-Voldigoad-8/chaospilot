"""Auth service: verifies a demo session through the cache."""

from __future__ import annotations

import os
from typing import Any

from common.service_base import create_app
from fastapi import FastAPI

CACHE_URL = os.getenv("CACHE_URL", "http://cache:8000")
SESSION_KEY = "session:demo"
DEFAULT_USER = "user-42"


def register_routes(app: FastAPI) -> None:
    client = app.state.dependency_client

    @app.get("/verify")
    async def verify() -> dict[str, Any]:
        cached = await client.get(
            f"{CACHE_URL}/cache/{SESSION_KEY}",
            fallback={"found": False, "value": None},
        )

        if not cached.get("found") and not cached.get("degraded"):
            stored = await client.post(
                f"{CACHE_URL}/cache/{SESSION_KEY}",
                payload={"value": DEFAULT_USER},
                fallback={"stored": False},
            )
            if stored.get("stored"):
                cached = {"found": True, "value": DEFAULT_USER}

        degraded = bool(cached.get("degraded")) or not cached.get("found")
        return {
            "verified": True,
            "user": cached.get("value") or "anonymous",
            "cached": bool(cached.get("found")),
            "degraded": degraded,
        }


app = create_app("auth", register_routes=register_routes)
