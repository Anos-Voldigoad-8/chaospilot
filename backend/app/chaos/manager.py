"""Fault lifecycle orchestration."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from app.chaos.engine import ChaosBackend, SimulationEngine, build_engine
from app.chaos.models import FaultRequest, FaultType
from app.config import AppSettings
from app.database import Database
from app.services import store
from app.services.registry import get_definition

LOGGER = logging.getLogger(__name__)


class ChaosError(RuntimeError):
    """Raised when a fault cannot be applied and simulation is disabled."""


class ChaosManager:
    def __init__(
        self,
        database: Database,
        settings: AppSettings,
        *,
        engine: ChaosBackend | None = None,
    ) -> None:
        self.database = database
        self.settings = settings
        self.engine = engine or build_engine(settings)

    def inject(self, request: FaultRequest) -> dict[str, Any]:
        definition = get_definition(request.service_id)
        if definition is None:
            raise ChaosError(f"unknown service: {request.service_id}")

        fault_id = f"fault_{uuid.uuid4().hex[:12]}"
        started_at = time.time()
        ends_at = started_at + request.duration_seconds
        parameters = request.as_parameters()

        store.create_fault(
            self.database,
            fault_id=fault_id,
            service_id=request.service_id,
            fault_type=request.fault_type.value,
            parameters=parameters,
            started_at=started_at,
            ends_at=ends_at,
        )

        applied = self.engine.apply(definition, request.fault_type, parameters)
        engine_name = self.engine.name
        if not applied:
            if not self.settings.simulation_mode and self.engine.name == "docker":
                store.set_fault_status(
                    self.database, fault_id, "failed", recovered_at=time.time()
                )
                raise ChaosError(
                    f"could not apply {request.fault_type.value} fault to {request.service_id}"
                )
            LOGGER.warning(
                "Falling back to simulation for %s on %s",
                request.fault_type.value,
                request.service_id,
            )
            SimulationEngine().apply(definition, request.fault_type, parameters)
            engine_name = "simulation"

        fault = store.get_fault(self.database, fault_id) or {}
        fault["engine"] = engine_name
        return fault

    def recover(self, fault_id: str) -> dict[str, Any]:
        fault = store.get_fault(self.database, fault_id)
        if fault is None:
            raise KeyError(fault_id)
        if fault["status"] == "active":
            definition = get_definition(str(fault["service_id"]))
            if definition is not None:
                self.engine.recover(
                    definition,
                    FaultType(str(fault["fault_type"])),
                    fault.get("parameters") or {},
                )
            store.set_fault_status(self.database, fault_id, "recovered", time.time())
        updated = store.get_fault(self.database, fault_id) or fault
        updated["engine"] = self.engine.name
        return updated

    def expire_due(self) -> int:
        now = time.time()
        expired = 0
        for fault in store.active_faults(self.database):
            ends_at = fault.get("ends_at")
            if ends_at is not None and float(ends_at) <= now:
                store.set_fault_status(self.database, str(fault["id"]), "expired", now)
                expired += 1
        return expired

    def active(self) -> list[dict[str, Any]]:
        self.expire_due()
        return store.active_faults(self.database)
