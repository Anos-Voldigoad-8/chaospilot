"""Incident diagnosis agent: context assembly, LLM call, deterministic fallback."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

from core.agent.llm import LLMClient, LLMUnavailable, build_client
from core.agent.prompts import SYSTEM_PROMPT, build_diagnosis_prompt
from core.config import LLMSettings
from core.database import Database
from core.services import store
from core.services.registry import get_definition

LOGGER = logging.getLogger(__name__)

METRIC_KEYS = ("latency_ms", "error_rate", "cpu_percent", "memory_mb", "request_rate")


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in response")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("response is not a JSON object")
    return payload


def _string_list(value: Any, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:500] for item in value if str(item).strip()][:limit]


class IncidentAgent:
    def __init__(self, database: Database, settings: LLMSettings) -> None:
        self.database = database
        self.settings = settings
        self.client: LLMClient | None = build_client(settings)

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.settings.provider,
            "model": self.settings.model_label,
            "client_configured": self.client is not None,
            "mode": "llm" if self.client else "fallback",
            "timeout_seconds": self.settings.timeout_seconds,
        }

    def _context(self, service_id: str, anomaly: dict[str, Any] | None) -> dict[str, Any]:
        definition = get_definition(service_id)
        service = store.get_service(self.database, service_id) or {}
        metrics = store.recent_metrics(self.database, service_id, limit=15)
        faults = [
            fault
            for fault in store.list_faults(self.database, limit=20)
            if fault["service_id"] in {service_id, *(definition.dependencies if definition else ())}
        ]
        return {
            "service": {
                "id": service_id,
                "name": service.get("name", service_id),
                "description": service.get("description", ""),
                "dependencies": list(definition.dependencies) if definition else [],
            },
            "anomaly": anomaly,
            "recent_metrics": metrics,
            "recent_faults": faults,
            "active_faults": [
                fault for fault in faults if fault.get("status") == "active"
            ],
            "recent_incidents": store.list_incidents(self.database, limit=3),
        }

    def _fallback(
        self, service_id: str, anomaly: dict[str, Any] | None, context: dict[str, Any]
    ) -> dict[str, Any]:
        active = context["active_faults"]
        target_faults = [f for f in active if f["service_id"] == service_id]
        dependency_faults = [f for f in active if f["service_id"] != service_id]
        metric = (anomaly or {}).get("metric", "latency_ms")
        latest = (context["recent_metrics"] or [{}])[-1]

        evidence: list[str] = []
        if target_faults:
            fault = target_faults[0]
            evidence.append(
                f"active {fault['fault_type']} fault injected on {service_id} {fault.get('parameters')}"
            )
        if dependency_faults:
            names = ", ".join(sorted({str(f["service_id"]) for f in dependency_faults}))
            evidence.append(f"active faults on upstream/dependency services: {names}")
        if anomaly:
            details = anomaly.get("details") or {}
            evidence.append(
                f"{metric} = {anomaly.get('value')} (score {anomaly.get('score')}, "
                f"{anomaly.get('severity')})"
            )
            if details.get("explanation"):
                evidence.append(str(details["explanation"]))
        if latest:
            values = ", ".join(
                f"{key}={latest.get(key)}" for key in METRIC_KEYS if latest.get(key) is not None
            )
            evidence.append(f"latest sample: {values}")

        if target_faults:
            fault_type = str(target_faults[0]["fault_type"])
            root_cause = (
                f"The injected {fault_type} fault on {service_id} directly explains the "
                f"anomalous {metric}."
            )
        elif dependency_faults:
            names = ", ".join(sorted({str(f["service_id"]) for f in dependency_faults}))
            root_cause = (
                f"The anomaly on {service_id} is most likely propagated from faults on "
                f"{names}; the service's own resource usage does not explain it alone."
            )
        else:
            root_cause = {
                "latency_ms": "Latency is elevated without an injected fault, pointing to "
                "resource saturation, downstream waits or a slow dependency.",
                "error_rate": "Error rate is elevated; check recent deploys, dependency "
                "failures and timeouts.",
                "cpu_percent": "CPU usage is abnormal for this service; investigate hot "
                "loops, traffic bursts or noisy neighbours.",
                "memory_mb": "Memory usage is abnormal; look for leaks, oversized caches "
                "or a low container limit.",
                "request_rate": "Traffic volume changed sharply; verify load patterns and "
                "autoscaling.",
            }.get(metric, "A metric deviated from its learned baseline.")

        recommendations = [
            f"Recover or let the fault on {service_id} expire, then confirm the metric returns "
            "to baseline." if target_faults else "Confirm the anomaly persists before acting.",
            "Add a timeout and retry budget around calls to dependencies.",
            "Alert on the learned baseline rather than a fixed global threshold.",
        ]
        if metric == "memory_mb":
            recommendations.insert(1, "Cap memory, profile allocations and restart leaking pods.")
        if metric == "error_rate":
            recommendations.insert(1, "Inspect error logs and add circuit breakers.")

        return {
            "summary": f"{service_id} shows an anomalous {metric} reading.",
            "root_cause": root_cause,
            "evidence": evidence[:8],
            "recommendations": recommendations[:5],
            "confidence": 0.62 if (target_faults or dependency_faults) else 0.35,
            "provider": "fallback",
        }

    async def diagnose(
        self, service_id: str, anomaly_id: int | None = None
    ) -> dict[str, Any]:
        if store.get_service(self.database, service_id) is None:
            raise KeyError(service_id)

        anomaly: dict[str, Any] | None
        if anomaly_id is not None:
            anomaly = store.get_anomaly(self.database, anomaly_id)
            if anomaly is None:
                raise KeyError(f"anomaly {anomaly_id}")
        else:
            anomalies = store.list_anomalies(self.database, limit=1, service_id=service_id)
            anomaly = anomalies[0] if anomalies else None

        context = self._context(service_id, anomaly)
        diagnosis: dict[str, Any] | None = None
        if self.client is not None:
            try:
                raw = await self.client.complete(
                    SYSTEM_PROMPT, build_diagnosis_prompt(context)
                )
                payload = _extract_json(raw)
                diagnosis = {
                    "summary": str(payload.get("summary", "")).strip(),
                    "root_cause": str(payload.get("root_cause", "")).strip(),
                    "evidence": _string_list(payload.get("evidence")),
                    "recommendations": _string_list(payload.get("recommendations")),
                    "confidence": max(0.0, min(1.0, float(payload.get("confidence", 0.5)))),
                    "provider": self.client.name,
                }
                if not diagnosis["summary"] or not diagnosis["root_cause"]:
                    raise ValueError("LLM response missing required fields")
            except (LLMUnavailable, ValueError, TypeError) as exc:
                LOGGER.warning("LLM diagnosis failed (%s); using fallback", type(exc).__name__)

        if diagnosis is None:
            diagnosis = self._fallback(service_id, anomaly, context)

        incident_id = f"inc_{uuid.uuid4().hex[:12]}"
        created_at = time.time()
        store.create_incident(
            self.database,
            incident_id=incident_id,
            service_id=service_id,
            anomaly_id=int(anomaly["id"]) if anomaly else None,
            summary=diagnosis["summary"],
            root_cause=diagnosis["root_cause"],
            evidence=diagnosis["evidence"],
            recommendations=diagnosis["recommendations"],
            confidence=float(diagnosis["confidence"]),
            provider=str(diagnosis["provider"]),
            created_at=created_at,
        )
        incident = store.get_incident(self.database, incident_id) or {}
        return incident
