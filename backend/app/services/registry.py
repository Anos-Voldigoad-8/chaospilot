"""Canonical service catalogue shared by collector, chaos and agent code."""

from __future__ import annotations

from dataclasses import dataclass

from app.database import Database


@dataclass(frozen=True)
class ServiceDefinition:
    id: str
    name: str
    port: int
    dependencies: tuple[str, ...]
    description: str

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


SERVICES: tuple[ServiceDefinition, ...] = (
    ServiceDefinition(
        id="catalog",
        name="Catalog",
        port=8001,
        dependencies=(),
        description="Product catalogue and search",
    ),
    ServiceDefinition(
        id="cart",
        name="Cart",
        port=8002,
        dependencies=(),
        description="Shopping cart state",
    ),
    ServiceDefinition(
        id="checkout",
        name="Checkout",
        port=8003,
        dependencies=("cart", "payments", "notifications"),
        description="Order orchestration",
    ),
    ServiceDefinition(
        id="payments",
        name="Payments",
        port=8004,
        dependencies=(),
        description="Charge and refund simulation",
    ),
    ServiceDefinition(
        id="notifications",
        name="Notifications",
        port=8005,
        dependencies=(),
        description="Outbound notification queue",
    ),
)

SERVICE_IDS: frozenset[str] = frozenset(service.id for service in SERVICES)


def get_definition(service_id: str) -> ServiceDefinition | None:
    return next((service for service in SERVICES if service.id == service_id), None)


def seed_services(database: Database) -> None:
    for service in SERVICES:
        database.execute(
            """
            INSERT INTO services (id, name, port, url, dependencies, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, strftime('%s','now'))
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                port = excluded.port,
                url = excluded.url,
                dependencies = excluded.dependencies,
                description = excluded.description
            """,
            (
                service.id,
                service.name,
                service.port,
                service.url,
                ",".join(service.dependencies),
                service.description,
            ),
        )
