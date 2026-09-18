"""Period-by-period Separate-Queue optimization schedule over persisted evidence.

Groups persisted dataset rows by time label, resolves current active lanes
from the authoritative queue setup, runs the routing-capable optimizer per
period, and rolls periods into one conservative schedule status. Traces are
pruned for API/persistence transfer; metrics and provenance are preserved.
"""
from __future__ import annotations

from backend.queueing_engine.services import separate_optimization as sep

SAMPLES = [0.05, 0.08, 0.10, 0.12]


def _row(time, queue_id, lam, samples=SAMPLES, segment_id="s1"):
    return {"time": time, "segment_id": segment_id, "queue_id": queue_id,
            "lambda": lam, "mu": 11.0, "c": 1, "service_samples_hours": list(samples)}


def _setup(queue_ids, varying=False):
    return {
        "queue_structure": "separate_queues",
        "fixed_server_count": 1,
        "staffing_varies_by_period": varying,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [{"id": "s1", "start_time": "08:00:00", "end_time": "09:00:00",
                      "active_queue_ids": None if not varying else list(queue_ids)}],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": list(queue_ids),
    }


def _config(**over):
    base = {"replications": 2, "base_seed": 101, "duration_hours": 4.0, "max_events": 500}
    base.update(over)
    return base


# --- schedule builder ---------------------------------------------------------------

def test_schedule_optimizes_each_period_with_current_lanes():
    assert hasattr(sep, "optimize_separate_schedule")
    records = [
        _row("08:00", "a", 4.0),
        _row("08:00", "b", 3.0),
        _row("08:00", "c", 2.0),
        _row("09:00", "a", 1.0),
        _row("09:00", "b", 1.0),
        _row("09:00", "c", 1.0),
    ]
    schedule = sep.optimize_separate_schedule(
        _setup(["a", "b", "c"]), records, target=0.70,
        server_cost=87.0, waiting_cost=100.0,
        min_lanes=None, max_lanes=None, lambda_multiplier=1.0,
        des_settings=_config())
    assert schedule["overall"] == "COMPLETE"
    assert schedule["evaluation_method"] == "DES_REPLICATIONS"
    assert [period["time"] for period in schedule["periods"]] == ["08:00", "09:00"]
    for period in schedule["periods"]:
        assert period["overall"] == "OPTIMAL"
        assert period["current_active_lanes"] == ["a", "b", "c"]
        assert period["optimal_active_lanes"] == period["optimum"]["active_lane_count"]
        assert period["evaluation_method"] == "DES_REPLICATIONS"
        assert period["replication_seeds"] == [101, 102]
    busy = schedule["periods"][0]
    assert busy["optimal_active_lanes"] == 2
    assert busy["adjustment"] == -1


def test_schedule_blocks_when_a_period_is_incomplete_and_maps_infeasible():
    heavy = [_row("08:00", "a", 6.0), _row("08:00", "b", 5.0)]
    schedule = sep.optimize_separate_schedule(
        _setup(["a", "b"]), heavy, target=0.40,
        server_cost=87.0, waiting_cost=100.0,
        min_lanes=None, max_lanes=None, lambda_multiplier=1.0,
        des_settings=_config())
    assert schedule["overall"] == "INFEASIBLE"
    assert schedule["periods"][0]["overall"] == "INFEASIBLE"
    assert schedule["periods"][0]["optimal_active_lanes"] is None

    broken = [_row("08:00", "a", 4.0), {"time": "08:00", "segment_id": "s1",
                                        "queue_id": "b", "lambda": -3.0, "mu": 11.0, "c": 1,
                                        "service_samples_hours": SAMPLES}]
    schedule = sep.optimize_separate_schedule(
        _setup(["a", "b"]), broken, target=0.70,
        server_cost=87.0, waiting_cost=100.0,
        min_lanes=None, max_lanes=None, lambda_multiplier=1.0,
        des_settings=_config())
    assert schedule["overall"] == "INVALID_INPUT"

    aggregate_only = [_row("08:00", "a", 4.0),
                      {"time": "08:00", "segment_id": "s1", "queue_id": "b",
                       "lambda": 3.0, "mu": 11.0, "c": 1, "variance": 0.001}]
    schedule = sep.optimize_separate_schedule(
        _setup(["a", "b"]), aggregate_only, target=0.70,
        server_cost=87.0, waiting_cost=100.0,
        min_lanes=None, max_lanes=None, lambda_multiplier=1.0,
        des_settings=_config())
    assert schedule["overall"] == "BLOCKED"
    assert "08:00" in schedule["reason"]
    assert schedule["periods"][0]["optimal_active_lanes"] is None
