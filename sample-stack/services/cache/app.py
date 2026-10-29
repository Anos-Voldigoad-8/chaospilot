"""Cache service: in-memory key/value store."""

from __future__ import annotations

from typing import Any

from common.service_base import create_app
from fastapi import FastAPI
from pydantic import BaseModel

CACHE: dict[str, str] = {}


class CacheValue(BaseModel):
    value: str


def register_routes(app: FastAPI) -> None:
    @app.get("/cache/{key}")
    async def read_cache(key: str) -> dict[str, Any]:
        found = key in CACHE
        return {"key": key, "found": found, "value": CACHE.get(key)}

    @app.post("/cache/{key}")
    async def write_cache(key: str, payload: CacheValue) -> dict[str, Any]:
        CACHE[key] = payload.value
        return {"key": key, "stored": True, "value": payload.value}


app = create_app("cache", register_routes=register_routes)
