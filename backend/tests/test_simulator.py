"""Simulator tests: propagation, blast-radius containment, determinism."""

from __future__ import annotations

from sim.simulator import ExperimentPlan, Simulator


def _fault_samples(result, service: str):
    return [s for s in result.samples if s.service == service and s.label == 1]


def test_fault_on_payments_raises_orders_and_gateway_latency() -> None:
    result = Simulator(seed=1).run(
        ExperimentPlan(fault="latency", target="payments", fixes=False)
    )
    payments = _fault_samples(result, "payments")
    orders = _fault_samples(result, "orders")
    gateway = _fault_samples(result, "gateway")
    assert payments and orders and gateway
    # Target is hit hardest; callers upstream degrade too.
    assert max(s.latency_ms for s in payments) > 500
    assert max(s.latency_ms for s in orders) > 100
    assert max(s.latency_ms for s in gateway) > 50


def test_kill_payment_brings_gateway_down() -> None:
    result = Simulator(seed=2).run(
        ExperimentPlan(fault="kill", target="payments", fixes=False)
    )
    payments_down = [s for s in _fault_samples(result, "payments") if not s.up]
    gateway_down = [s for s in _fault_samples(result, "gateway") if not s.up]
    assert payments_down, "target should go down"
    assert gateway_down, "gateway upstream should go down"


def test_resilient_contains_blast_radius_to_one_hop() -> None:
    result = Simulator(seed=3).run(
        ExperimentPlan(fault="kill", target="payments", fixes=True)
    )
    # payments and its direct caller orders are affected.
    payments_down = [s for s in _fault_samples(result, "payments") if not s.up]
    orders_degraded = [
        s for s in _fault_samples(result, "orders") if s.latency_ms > 150
    ]
    # gateway is two hops upstream (gateway -> orders -> payments) so it is
    # contained when resilient: it stays up (healthy tail latency may still
    # spike, but it never goes down).
    assert payments_down
    assert orders_degraded
    gateway = _fault_samples(result, "gateway")
    assert all(s.up for s in gateway), "gateway should stay up (contained)"


def test_simulator_is_deterministic_given_seed() -> None:
    plan = ExperimentPlan(fault="memory", target="db", fixes=False)
    first = Simulator(seed=42).run(plan)
    second = Simulator(seed=42).run(plan)
    assert first.samples == second.samples
    other = Simulator(seed=7).run(plan)
    assert first.samples != other.samples
