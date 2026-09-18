"""Multi-period Separate-Queue breaks: ownership and runtime lifecycle.

Approved rule: a configured break belongs to exactly one period, the one
whose operating segment contains its scheduled start. It must not be
duplicated into other periods' simulations. Within the owning run the
lifecycle (DRAINING at start - 3 min, ON_BREAK once empty, full duration
from the actual start, then ACTIVE) is continuous: a period boundary on the
wall clock is not a DES event and never truncates or restarts the break.
"""
from __future__ import annotations

import types

import pytest

import backend.api.workflow as workflow_api
from backend.queueing_engine.config import PRE_BREAK_CUTOFF_MINUTES
from backend.queueing_engine.services import separate_optimization as sep

SAMPLES = [0.05, 0.08, 0.10, 0.12]
BREAK_TYPES = ("draining_start", "break_start", "break_end")
# Segments 05:00-09:00 (s1) and 09:00-13:00 (s2); DES t=0 is 05:00.
BOUNDARY_H = 4.0


def _setup(breaks):
    return {
        "queue_structure": "separate_queues",
        "fixed_server_count": 2,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [
            {"id": "s1", "start_time": "05:00:00", "end_time": "09:00:00", "active_queue_ids": None},
            {"id": "s2", "start_time": "09:00:00", "end_time": "13:00:00", "active_queue_ids": None},
        ],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": ["a", "b"],
        "breaks": breaks,
    }


def _row(time, segment_id, queue_id, lam, samples=SAMPLES):
    return {"time": time, "segment_id": segment_id, "queue_id": queue_id,
            "lambda": lam, "mu": 11.0, "c": 1, "service_samples_hours": list(samples)}


def _records():
    return [_row("05:00", "s1", "a", 4.0), _row("05:00", "s1", "b", 3.0),
            _row("09:00", "s2", "a", 4.0), _row("09:00", "s2", "b", 3.0)]


BREAK_0855 = [{"queue_id": "a", "scheduled_start_time": "08:55:00", "duration_minutes": 30}]


def _break_events(events, queue_id="a"):
    return [e for e in events if e["type"] in BREAK_TYPES and e["queue_id"] == queue_id]


# --- ownership ------------------------------------------------------------------

def test_break_is_owned_only_by_the_period_containing_its_start():
    setup = _setup(BREAK_0855)
    owned_s1 = sep.period_des_breaks(setup, [r for r in _records() if r["segment_id"] == "s1"])
    owned_s2 = sep.period_des_breaks(setup, [r for r in _records() if r["segment_id"] == "s2"])
    assert owned_s1 == sep.breaks_to_des_offsets(BREAK_0855, 5 * 60)
    assert owned_s2 is None


def test_break_outside_every_segment_is_rejected_not_dropped():
    with pytest.raises(ValueError, match="outside every configured operating segment"):
        sep.resolve_des_breaks(_setup([{"queue_id": "a", "scheduled_start_time": "14:00:00",
                                        "duration_minutes": 15}]))


def test_optimizer_applies_break_only_in_owning_period():
    schedule = sep.optimize_separate_schedule(
        _setup(BREAK_0855), _records(), target=0.70, min_lanes=2, max_lanes=2,
        des_settings={"replications": 1, "base_seed": 7, "duration_hours": 8.0,
                      "max_events": 10000})
    assert schedule["overall"] == "COMPLETE"
    by_time = {}
    for period in schedule["periods"]:
        events = []
        for candidate in period["candidates"]:
            events += (candidate.get("evidence") or {}).get("representative_trace", {}).get("events") or []
        by_time[period["time"]] = _break_events(events)
    assert [e["type"] for e in by_time["05:00"]] == list(BREAK_TYPES)
    assert by_time["09:00"] == []


def _selected_plan(setup):
    return {
        "scenario": types.SimpleNamespace(id=9, analysis_id=7, dataset_id=2),
        "schedule": {"periods": [
            {"time": t, "optimum": {"active_queue_ids": ["a", "b"], "inactive_queue_ids": [],
                                    "active_lane_count": 2}}
            for t in ("05:00", "09:00")]},
        "dataset": types.SimpleNamespace(normalized_json=_records()),
        "setup": setup, "target": 0.70, "server_cost": 87.0, "waiting_cost": 100.0,
        "multiplier": 1.0, "duration_hours": 8.0, "max_events": 10000,
    }


def test_selected_plan_runs_one_break_lifecycle_across_all_periods():
    result = workflow_api._run_selected_plan_des(_selected_plan(_setup(BREAK_0855)), seed=7)
    assert result["overall_status"] == "COMPLETED"
    per_period = {p["time"]: _break_events(p["trace"]["trace"]) for p in result["periods"]}
    assert [e["type"] for e in per_period["05:00"]] == list(BREAK_TYPES)
    assert per_period["09:00"] == []


def test_selected_plan_without_breaks_is_unchanged_per_period():
    result = workflow_api._run_selected_plan_des(_selected_plan(_setup([])), seed=7)
    for period in result["periods"]:
        assert not [e for e in period["trace"]["trace"] if e["type"] in BREAK_TYPES]


# --- lifecycle crossing the wall-clock period boundary ---------------------------

def test_break_draining_and_rest_cross_the_period_boundary_without_reset():
    """Owning-run lifecycle: delayed start past 09:00, full duration, then ACTIVE."""
    setup = _setup(BREAK_0855)
    owned = sep.period_des_breaks(setup, [r for r in _records() if r["segment_id"] == "s1"])
    # Deterministic overload (30-minute services, seed 11) keeps lane a busy at its
    # cutoff; the DES core used by both production paths runs it directly.
    stats, events, truncated, _ = sep._run_routing_des(
        active_ids=["a", "b"], tie_order=["a", "b"], samples_by_id={"a": [0.5], "b": [0.5]},
        total_lambda=4.0, duration_hours=12.0, seed=11, time_label="05:00",
        max_events=100000, breaks=owned)
    assert truncated is False
    (record,) = stats["a"]["breaks"]  # exactly one lifecycle in the lane state
    assert record["actual_end"] - record["actual_start"] == pytest.approx(0.5)
    lifecycle = _break_events(events)
    assert [e["type"] for e in lifecycle] == list(BREAK_TYPES)  # exactly one lifecycle
    drain, start, end = (e["t"] for e in lifecycle)
    scheduled = 3 + 55 / 60  # 08:55 relative to 05:00
    assert drain == pytest.approx(scheduled - PRE_BREAK_CUTOFF_MINUTES / 60)
    assert start > BOUNDARY_H  # actual rest begins after the 09:00 period boundary
    assert end - start == pytest.approx(0.5)  # full configured duration from actual start
    lane_a = [e for e in events if e["queue_id"] == "a"]
    assert not [e for e in lane_a if e["type"] == "arrival" and drain < e["t"] < end]
    assert not [e for e in lane_a if e["type"] == "service_start" and start <= e["t"] < end]
    # Existing waiting customers were served in place during DRAINING.
    assert [e for e in lane_a if e["type"] == "service_start" and drain < e["t"] < start]
    # After the full rest the lane is ACTIVE again and accepts new arrivals.
    assert [e for e in lane_a if e["type"] == "arrival" and e["t"] > end]
