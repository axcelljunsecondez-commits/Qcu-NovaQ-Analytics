"""Production wiring for persisted Separate-Queue break schedules.

Persisted QueueSetup.breaks (wall-clock) convert once per run, relative to
the earliest configured operating-segment start, into routing-DES offsets.
Both production paths (optimizer evaluation and selected-plan simulation)
share the identical conversion; no-break behavior is unchanged.
"""
from __future__ import annotations

import pytest

from backend.queueing_engine.services import separate_optimization as sep

SAMPLES = [0.05, 0.08, 0.10, 0.12]


def _setup(**over):
    base = {
        "queue_structure": "separate_queues",
        "fixed_server_count": 1,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [{"id": "s1", "start_time": "05:00:00", "end_time": "13:00:00",
                      "active_queue_ids": None}],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": ["a", "b"],
        "breaks": [{"queue_id": "a", "scheduled_start_time": "07:30",
                    "duration_minutes": 60}],
    }
    base.update(over)
    return base


def _row(time, queue_id, lam):
    return {"time": time, "segment_id": "s1", "queue_id": queue_id,
            "lambda": lam, "mu": 11.0, "c": 1,
            "service_samples_hours": list(SAMPLES)}


def _config(**over):
    base = {"replications": 1, "base_seed": 7, "duration_hours": 8.0,
            "max_events": 10000}
    base.update(over)
    return base


# --- origin + conversion ------------------------------------------------------

def test_day_start_is_earliest_segment_start():
    assert sep.des_day_start_minutes(_setup()) == 5 * 60
    shuffled = _setup(segments=[
        {"id": "s2", "start_time": "09:00:00", "end_time": "13:00:00",
         "active_queue_ids": None},
        {"id": "s1", "start_time": "05:00:00", "end_time": "09:00:00",
         "active_queue_ids": None},
    ])
    assert sep.des_day_start_minutes(shuffled) == 5 * 60
    assert sep.des_day_start_minutes(_setup(segments=[])) is None


def test_break_converts_to_des_offset():
    converted = sep.breaks_to_des_offsets(
        [{"queue_id": "a", "scheduled_start_time": "07:30",
          "duration_minutes": 60}],
        5 * 60)
    assert converted == [{"queue_id": "a", "start_hours": 2.5,
                          "duration_hours": 1.0}]
    assert sep.breaks_to_des_offsets(
        [{"queue_id": "b", "scheduled_start_time": "07:15",
          "duration_minutes": 30}],
        5 * 60) == [{"queue_id": "b", "start_hours": 2.25,
                     "duration_hours": 0.5}]


def test_break_conversion_rejects_unmappable():
    with pytest.raises(ValueError):
        sep.breaks_to_des_offsets(
            [{"queue_id": "a", "scheduled_start_time": "04:00",
              "duration_minutes": 60}], 5 * 60)
    with pytest.raises(ValueError):
        sep.breaks_to_des_offsets(
            [{"queue_id": "a", "scheduled_start_time": "noon",
              "duration_minutes": 60}], 5 * 60)
    with pytest.raises(ValueError):
        sep.breaks_to_des_offsets(
            [{"queue_id": "a", "scheduled_start_time": "07:30",
              "duration_minutes": 0}], 5 * 60)
    with pytest.raises(ValueError):
        sep.breaks_to_des_offsets("not-a-list", 5 * 60)


def test_resolve_des_breaks_needs_origin_only_when_breaks_exist():
    assert sep.resolve_des_breaks(_setup(breaks=[])) is None
    assert sep.resolve_des_breaks(_setup()) == [
        {"queue_id": "a", "start_hours": 2.5, "duration_hours": 1.0}]
    with pytest.raises(ValueError):
        sep.resolve_des_breaks(_setup(segments=[], breaks=[
            {"queue_id": "a", "scheduled_start_time": "07:30",
             "duration_minutes": 60}]))
    with pytest.raises(ValueError):
        sep.resolve_des_breaks(_setup(breaks=[
            {"queue_id": "ghost", "scheduled_start_time": "07:30",
             "duration_minutes": 60}]))


# --- optimizer path ------------------------------------------------------------

def _draining_at(events, queue_id):
    return sorted(event["t"] for event in events
                  if event["type"] == "draining_start"
                  and event["queue_id"] == queue_id)


def test_optimizer_path_fires_break_at_converted_offset():
    records = [_row("08:00", "a", 4.0), _row("08:00", "b", 3.0)]
    schedule = sep.optimize_separate_schedule(
        _setup(), records, target=0.70, server_cost=87.0, waiting_cost=100.0,
        min_lanes=2, max_lanes=2, lambda_multiplier=1.0,
        des_settings=_config())
    assert schedule["overall"] == "COMPLETE"
    (period,) = schedule["periods"]
    assert period["overall"] == "OPTIMAL"
    assert period["optimal_active_lanes"] == 2
    draining = []
    for candidate in period["candidates"]:
        events = (candidate.get("evidence") or {}).get(
            "representative_trace", {}).get("events") or []
        draining.extend(_draining_at(events, "a"))
    assert draining
    assert draining[0] == 2.5 - 3.0 / 60.0
    assert all(t < 7.4 for t in draining)


def test_optimizer_path_without_breaks_has_no_break_events():
    records = [_row("08:00", "a", 4.0), _row("08:00", "b", 3.0)]
    schedule = sep.optimize_separate_schedule(
        _setup(breaks=[]), records, target=0.70, server_cost=87.0,
        waiting_cost=100.0, min_lanes=2, max_lanes=2, lambda_multiplier=1.0,
        des_settings=_config())
    assert schedule["overall"] == "COMPLETE"
    assert schedule["periods"][0]["overall"] == "OPTIMAL"
    types = set()
    for candidate in schedule["periods"][0]["candidates"]:
        events = (candidate.get("evidence") or {}).get(
            "representative_trace", {}).get("events") or []
        types.update(event["type"] for event in events)
    assert types <= {"arrival", "service_start", "service_end"}


# --- selected-plan path ----------------------------------------------------------

def _selected_plan(time="08:00"):
    import types

    scenario = types.SimpleNamespace(id=9, analysis_id=7, dataset_id=2)
    dataset = types.SimpleNamespace(normalized_json=[
        _row(time, "a", 4.0), _row(time, "b", 3.0)])
    return {
        "scenario": scenario,
        "schedule": {"periods": [{
            "time": time,
            "optimum": {
                "active_queue_ids": ["a", "b"],
                "inactive_queue_ids": [],
                "active_lane_count": 2,
            },
        }]},
        "dataset": dataset,
        "setup": _setup(),
        "target": 0.70,
        "server_cost": 87.0,
        "waiting_cost": 100.0,
        "multiplier": 1.0,
        "duration_hours": 8.0,
        "max_events": 10000,
    }


def test_selected_path_fires_break_at_converted_offset():
    import backend.api.workflow as workflow_api

    result = workflow_api._run_selected_plan_des(_selected_plan(), seed=7)
    assert result["overall_status"] == "COMPLETED"
    assert result["overall_conservation"] is True
    (period,) = result["periods"]
    draining = _draining_at(period["trace"]["trace"], "a")
    assert draining
    assert draining[0] == 2.5 - 3.0 / 60.0
    assert all(t < 7.4 for t in draining)


def test_both_paths_agree_on_converted_break_time():
    import backend.api.workflow as workflow_api

    records = [_row("08:00", "a", 4.0), _row("08:00", "b", 3.0)]
    schedule = sep.optimize_separate_schedule(
        _setup(), records, target=0.70, server_cost=87.0, waiting_cost=100.0,
        min_lanes=2, max_lanes=2, lambda_multiplier=1.0,
        des_settings=_config())
    optimizer_times = set()
    for candidate in schedule["periods"][0]["candidates"]:
        events = (candidate.get("evidence") or {}).get(
            "representative_trace", {}).get("events") or []
        optimizer_times.update(_draining_at(events, "a"))
    result = workflow_api._run_selected_plan_des(_selected_plan(), seed=7)
    selected_times = set(_draining_at(result["periods"][0]["trace"]["trace"], "a"))
    assert optimizer_times == selected_times != set()
    assert optimizer_times == {2.5 - 3.0 / 60.0}


def test_evaluator_rejects_malformed_breaks_and_unknown_queues():
    by_id = {"a": _row("08:00", "a", 4.0), "b": _row("08:00", "b", 3.0)}
    candidate = {"time": "08:00", "available_queue_ids": ["a", "b"],
                 "active_queue_ids": ["a", "b"], "inactive_queue_ids": [],
                 "breaks": [{"queue_id": "ghost", "start_hours": 1.0,
                             "duration_hours": 1.0}]}
    outcome = sep.evaluate_candidate_with_des(
        candidate, by_id, duration_hours=8.0, seed=7)
    assert outcome["status"] == "INVALID_INPUT"
    candidate["breaks"] = "not-a-list"
    outcome = sep.evaluate_candidate_with_des(
        candidate, by_id, duration_hours=8.0, seed=7)
    assert outcome["status"] == "INVALID_INPUT"
