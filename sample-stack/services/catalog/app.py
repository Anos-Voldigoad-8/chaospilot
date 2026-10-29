"""Catalog service: product listing and detail endpoints."""

from __future__ import annotations

import random
from typing import Any

from common.service_base import create_app
from fastapi import FastAPI

PRODUCTS = [
    {"id": "sku-001", "name": "Mechanical keyboard", "price": 129.0},
    {"id": "sku-002", "name": "Noise-cancelling headphones", "price": 249.0},
    {"id": "sku-003", "name": "USB-C dock", "price": 89.0},
    {"id": "sku-004", "name": "4K monitor", "price": 399.0},
]


def register_routes(app: FastAPI) -> None:
    @app.get("/products")
    async def list_products() -> dict[str, Any]:
        return {"items": PRODUCTS, "count": len(PRODUCTS)}

    @app.get("/products/{product_id}")
    async def get_product(product_id: str) -> dict[str, Any]:
        product = next((item for item in PRODUCTS if item["id"] == product_id), None)
        if product is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="product not found")
        return product

    @app.get("/work")
    async def work() -> dict[str, Any]:
        return {"service": "catalog", "served": random.choice(PRODUCTS)["id"]}


app = create_app("catalog", routes=register_routes)
