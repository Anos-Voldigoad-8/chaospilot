"""Database service: in-memory tables exposed over HTTP."""

from __future__ import annotations

from typing import Any

from common.service_base import create_app
from fastapi import FastAPI
from pydantic import BaseModel

TABLES: dict[str, dict[str, dict[str, Any]]] = {}


class RecordValue(BaseModel):
    value: dict[str, Any]


def register_routes(app: FastAPI) -> None:
    @app.get("/records/{table}/{key}")
    async def read_record(table: str, key: str) -> dict[str, Any]:
        rows = TABLES.get(table, {})
        found = key in rows
        return {"table": table, "key": key, "found": found, "value": rows.get(key)}

    @app.post("/records/{table}/{key}")
    async def write_record(table: str, key: str, payload: RecordValue) -> dict[str, Any]:
        TABLES.setdefault(table, {})[key] = payload.value
        return {"table": table, "key": key, "stored": True}

    @app.get("/tables/{table}")
    async def list_table(table: str) -> dict[str, Any]:
        rows = TABLES.get(table, {})
        return {"table": table, "count": len(rows), "keys": sorted(rows)[-50:]}


app = create_app("db", register_routes=register_routes)
