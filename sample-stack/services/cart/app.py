"""Cart service: in-memory cart operations."""

from __future__ import annotations

import uuid
from typing import Any

from common.service_base import create_app
from fastapi import FastAPI
from pydantic import BaseModel, Field

CARTS: dict[str, list[dict[str, Any]]] = {}


class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=99)


def register_routes(app: FastAPI) -> None:
    @app.post("/carts")
    async def create_cart() -> dict[str, str]:
        cart_id = f"cart_{uuid.uuid4().hex[:10]}"
        CARTS[cart_id] = []
        return {"cart_id": cart_id}

    @app.post("/carts/{cart_id}/items")
    async def add_item(cart_id: str, item: CartItem) -> dict[str, Any]:
        CARTS.setdefault(cart_id, []).append(item.model_dump())
        return {"cart_id": cart_id, "items": CARTS[cart_id]}

    @app.get("/carts/{cart_id}")
    async def get_cart(cart_id: str) -> dict[str, Any]:
        return {"cart_id": cart_id, "items": CARTS.get(cart_id, [])}

    @app.get("/work")
    async def work() -> dict[str, Any]:
        return {"service": "cart", "carts": len(CARTS)}


app = create_app("cart", routes=register_routes)
