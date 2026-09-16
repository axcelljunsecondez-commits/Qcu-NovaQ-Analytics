"""Problem 3 gap evidence: congestion isolation, identity chains, shared path.

The parallel workstream's test_parallel_simulation.py already proves seed
reproducibility, per-queue empirical service, FIFO order, drain semantics,
reactivation gating, and explicit capability errors. These tests close the
remaining Problem 3 invariant gaps without touching that file:

- CASE B/F: a congested queue must not delay a light queue, which is also
  the strongest discriminator against a hidden pooled resource;
- CASE D: arbitrary (non-Q1/Q2) identifiers run as independent queues;
- CASE I: one customer's arrival -> service_start -> service_end chain keeps
  its queue and server identity end to end.
"""
from __future__ import annotations

from backend.queueing_engine.simulation.simulation import (
    simulate_segments,
    simulate_segments_with_trace,
)

SETUP = {
    "queue_structure": "separate_queues",
    "queue_ids": ["cashier-east", "express"],
    "staffing_varies_by_period": False,
    "separate_queue_closure_policy": "drain_existing",
    "segments": [{"id": "s1", "start_time": "07:00:00", "end_time": "08:00:00"}],
}


def _rows(east_lambda=60.0, express_lambda=3.0):
    return [
        {
            "segment_id": "s1", "time": "s1", "queue_id": "cashier-east",
            "queue_structure": "separate_queues", "model_id": "parallel_mg1",
            "lambda": east_lambda, "mu": 4.0, "c": 1,
            "service_time_source": "empirical", "service_samples_hours": [0.2, 0.3],
        },
        {
            "segment_id": "s1", "time": "s1", "queue_id": "express",
            "queue_structure": "separate_queues", "model_id": "parallel_mg1",
            "lambda": express_lambda, "mu": 8.0, "c": 1,
            "service_time_source": "empirical", "service_samples_hours": [0.1, 0.15],
        },
    ]


def test_congested_queue_does_not_delay_light_queue():
    """CASE B/F/D: overload in cashier-east leaves express flowing on its own server."""
    result = simulate_segments(_rows(), seed=7, queue_setup=SETUP)
    by_queue = {row["queue_id"]: row for row in result}
    assert set(by_queue) == {"cashier-east", "express"}
    assert by_queue["cashier-east"]["server_id"] == "server:cashier-east"
    assert by_queue["express"]["server_id"] == "server:express"
    # The congestion is real: arrivals pile up beyond service.
    assert by_queue["cashier-east"]["arrivals"] > by_queue["cashier-east"]["served"]
    # The light queue still drains fully and waits far less than the backlog.
    assert by_queue["express"]["arrivals"] > 0
    assert by_queue["express"]["served"] == by_queue["express"]["arrivals"]
    assert by_queue["express"]["Wq_sim"] < by_queue["cashier-east"]["Wq_sim"]
    assert all(row["customer_conservation"] for row in result)


def test_customer_chain_keeps_queue_and_server_identity():
    """CASE I: arrival -> service_start -> service_end agree per customer."""
    bundle = simulate_segments_with_trace(_rows(), seed=7, queue_setup=SETUP, max_events=10000)
    by_customer: dict[int, dict[str, object]] = {}
    for event in bundle["trace"]:
        record = by_customer.setdefault(event["customer_id"], {})
        if event["type"] == "arrival":
            record["queue_id"] = event.get("queue_id")
        if event["type"] == "service_start":
            record["start_queue"] = event.get("queue_id")
            record["server_id"] = event.get("server_id")
        if event["type"] == "service_end":
            record["end_queue"] = event.get("queue_id")
    assert by_customer
    complete = [record for record in by_customer.values() if "end_queue" in record]
    assert complete, "expected at least one fully observed service"
    for record in complete:
        assert record["start_queue"] == record["queue_id"] == record["end_queue"]
        assert record["server_id"] == f"server:{record['queue_id']}"
    # No event ever touches a foreign resource.
    assert not [
        event for event in bundle["trace"]
        if event.get("queue_id") is not None
        and event.get("server_id") is not None
        and event["server_id"] != f"server:{event['queue_id']}"
    ]


def test_shared_des_path_unchanged():
    """CASE G (spot): shared rows keep the pooled-resource path and shape."""
    result = simulate_segments([{"time": "08:00", "lambda": 20.0, "mu": 12.0, "c": 2}], seed=7)
    assert len(result) == 1
    row = result[0]
    assert row.get("queue_id") is None
    assert row["status"] in {"Normal", "Peak", "Critical", "Unstable", "Lean"}
    assert row["Wq_sim"] is not None and row["Wq_sim"] >= 0
