"""LLM-driven experiment planner with a deterministic rule-based fallback."""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from agent.llm import extract_json_object
from agent.models import ExperimentPlan
from agent.tools import get_topology
from core.agent.llm import LLMClient

LOGGER = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are ChaosPilot's chaos-engineering planner.
Given a six-service topology, choose one safe, small experiment that teaches
something about resilience.

Rules:
- Return one JSON object with exactly: "fault", "target", "hypothesis".
- "fault" is one of: kill, latency, memory.
- "target" is one of the topology node ids.
- "hypothesis" is ONE sentence, at most 25 words, explaining what the injected
  fault should reveal.
- Prefer a target whose failure propagates to callers, and avoid repeating the
  same target every time.
- Do not include markdown fences or any prose outside the JSON object.

Example:
{"fault": "latency", "target": "payments", "hypothesis": "Delaying payments should expose missing timeouts in orders and checkout."}
"""

TopologyFn = Callable[[], dict[str, Any]]


def _prompt(topology: dict[str, Any]) -> str:
    faults = ("kill", "latency", "memory")
    targets = [node["id"] for node in topology.get("nodes", [])]
    return (
        "Plan the next chaos experiment.\n"
        f"Allowed faults: {', '.join(faults)}\n"
        f"Allowed targets: {', '.join(targets)}\n"
        f"Topology JSON:\n{json.dumps(topology, indent=2)}\n\n"
        "Return only the JSON object."
    )


def rule_based_plan(topology: dict[str, Any]) -> ExperimentPlan:
    """Fallback: target the service with the most direct callers."""
    nodes = [str(node["id"]) for node in topology.get("nodes", [])]
    callers = Counter(
        str(edge["target"]) for edge in topology.get("edges", []) if edge.get("target")
    )
    target = max(nodes, key=lambda name: callers.get(name, 0)) if nodes else "db"
    count = callers.get(target, 0)
    hypothesis = (
        f"{target} has the most callers ({count}), so delaying it should show "
        "how a local stall propagates through the stack."
    )
    return ExperimentPlan(
        fault="latency",
        target=target,
        hypothesis=hypothesis,
        source="rule",
    )


class Planner:
    """Ask the LLM for a plan and fall back after two invalid responses."""

    def __init__(
        self,
        llm: LLMClient | None,
        *,
        topology_fn: TopologyFn = get_topology,
        attempts: int = 2,
    ) -> None:
        self.llm = llm
        self.topology_fn = topology_fn
        self.attempts = max(1, attempts)

    async def plan(self, topology: dict[str, Any] | None = None) -> ExperimentPlan:
        topology = topology if topology is not None else self.topology_fn()
        if self.llm is None:
            LOGGER.info("planner: no LLM configured; using rule-based plan")
            return rule_based_plan(topology)

        targets = {str(node["id"]) for node in topology.get("nodes", [])}
        prompt = _prompt(topology)
        for attempt in range(1, self.attempts + 1):
            try:
                raw = await self.llm.complete(PLANNER_SYSTEM_PROMPT, prompt)
            except Exception as exc:  # provider failures always degrade safely
                LOGGER.warning(
                    "planner: LLM call failed (%s); using fallback", type(exc).__name__
                )
                break

            try:
                payload = extract_json_object(raw)
                plan = ExperimentPlan.model_validate({**payload, "source": "llm"})
                if plan.target not in targets:
                    raise ValueError(f"target {plan.target!r} is not in the topology")
                LOGGER.info(
                    "planner: LLM plan %s on %s (attempt %s)",
                    plan.fault,
                    plan.target,
                    attempt,
                )
                return plan
            except (ValueError, ValidationError) as exc:
                LOGGER.warning(
                    "planner: invalid LLM plan on attempt %s/%s (%s)",
                    attempt,
                    self.attempts,
                    type(exc).__name__,
                )

        LOGGER.info("planner: using rule-based fallback")
        return rule_based_plan(topology)


async def plan_experiment(
    llm: LLMClient | None,
    *,
    topology: dict[str, Any] | None = None,
    attempts: int = 2,
) -> ExperimentPlan:
    """Convenience wrapper for callers that do not need a Planner object."""
    return await Planner(llm, attempts=attempts).plan(topology)
