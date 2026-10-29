"""Notifications service: records simulated outbound notifications."""

from __future__ import annotations

import uuid
from typing import Any

from common.service_base import create_app
from fastapi import FastAPI
from pydantic import BaseModel, Field

SENT: list[dict[str, Any]] = []


class NotificationRequest(BaseModel):
    order_id: str
    channel: str = Field(default="email", pattern="^(email|sms|push)$")


def register_routes(app: FastAPI) -> None:
    @app.post("/notify")
    async def notify(payload: NotificationRequest) -> dict[str, Any]:
        record = {
            "notification_id": f"ntf_{uuid.uuid4().hex[:10]}",
            "order_id": payload.order_id,
            "channel": payload.channel,
            "status": "queued",
        }
        SENT.append(record)
        return record

    @app.get("/notifications")
    async def list_notifications() -> dict[str, Any]:
        return {"items": SENT[-50:], "count": len(SENT)}

    @app.get("/work")
    async def work() -> dict[str, Any]:
        return {"service": "notifications", "sent": len(SENT)}


app = create_app("notifications", routes=register_routes)
