"""Fault application backends: Docker SDK for real stacks, no-op simulation.

Every method returns True when the action was applied, False when the target
could not be reached. Callers decide whether that is fatal or a degraded-mode
warning, so the API never crashes because Docker is absent.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.chaos.models import FaultType
from app.config import AppSettings
from app.services.registry import ServiceDefinition

LOGGER = logging.getLogger(__name__)


class ChaosBackend(Protocol):
    name: str

    def apply(
        self, service: ServiceDefinition, fault_type: FaultType, parameters: dict[str, float]
    ) -> bool: ...

    def recover(
        self, service: ServiceDefinition, fault_type: FaultType, parameters: dict[str, float]
    ) -> bool: ...


class SimulationEngine:
    """Used when Docker is disabled; the collector simulates the effects."""

    name = "simulation"

    def apply(
        self, service: ServiceDefinition, fault_type: FaultType, parameters: dict[str, float]
    ) -> bool:
        LOGGER.info("Simulated %s fault on %s %s", fault_type.value, service.id, parameters)
        return True

    def recover(
        self, service: ServiceDefinition, fault_type: FaultType, parameters: dict[str, float]
    ) -> bool:
        LOGGER.info("Simulated recovery of %s on %s", fault_type.value, service.id)
        return True


class DockerEngine:
    """Applies faults through the Docker SDK and service admin endpoints."""

    name = "docker"

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._client = None

    def _docker(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            import docker

            self._client = docker.from_env()
        return self._client

    def _container(self, service: ServiceDefinition):  # type: ignore[no-untyped-def]
        containers = self._docker().containers.list(
            all=True,
            filters={
                "label": [
                    f"com.docker.compose.project={self.settings.compose_project}",
                    f"com.docker.compose.service={service.id}",
                ]
            },
        )
        return containers[0] if containers else None

    def _configure_app(self, service: ServiceDefinition, payload: dict[str, float]) -> bool:
        try:
            response = httpx.post(
                f"{service.url}/admin/fault", json=payload, timeout=5.0
            )
            return response.status_code == 200
        except httpx.HTTPError as exc:
            LOGGER.warning("Could not reach %s admin endpoint: %s", service.id, exc)
            return False

    def _network(self):  # type: ignore[no-untyped-def]
        return self._docker().networks.get(self.settings.docker_network)

    def apply(
        self, service: ServiceDefinition, fault_type: FaultType, parameters: dict[str, float]
    ) -> bool:
        try:
            if fault_type in {FaultType.LATENCY, FaultType.ERROR}:
                payload = {
                    "latency_ms": parameters.get("latency_ms", 0.0)
                    if fault_type is FaultType.LATENCY
                    else 0.0,
                    "error_rate": parameters.get("error_rate", 0.0)
                    if fault_type is FaultType.ERROR
                    else 0.0,
                }
                return self._configure_app(service, payload)

            container = self._container(service)
            if container is None:
                LOGGER.warning("No container found for service %s", service.id)
                return False

            if fault_type is FaultType.CRASH:
                container.stop(timeout=2)
                return True
            if fault_type is FaultType.CPU:
                container.exec_run(
                    "python -c 'while True: pass'",
                    detach=True,
                )
                return True
            if fault_type is FaultType.MEMORY:
                limit = int(parameters.get("memory_mb", 512) * 1024 * 1024)
                container.update(mem_limit=limit)
                return True
            if fault_type is FaultType.NETWORK:
                self._network().disconnect(container, force=True)
                return True
        except Exception as exc:  # docker errors are numerous; degrade cleanly
            LOGGER.warning("Docker fault %s on %s failed: %s", fault_type.value, service.id, exc)
        return False

    def recover(
        self, service: ServiceDefinition, fault_type: FaultType, parameters: dict[str, float]
    ) -> bool:
        try:
            if fault_type in {FaultType.LATENCY, FaultType.ERROR}:
                return self._configure_app(service, {})
            container = self._container(service)
            if container is None:
                return False
            if fault_type is FaultType.CRASH:
                container.start()
                return True
            if fault_type in {FaultType.CPU, FaultType.MEMORY}:
                container.restart(timeout=5)
                return True
            if fault_type is FaultType.NETWORK:
                self._network().connect(container)
                return True
        except Exception as exc:
            LOGGER.warning("Docker recovery %s on %s failed: %s", fault_type.value, service.id, exc)
        return False


def build_engine(settings: AppSettings) -> ChaosBackend:
    if settings.docker_enabled:
        return DockerEngine(settings)
    return SimulationEngine()
