"""B5: break states for separate lines come from the selected plan's stored trace (spec D26, G8).

The routing DES records ``draining_start``, ``break_start`` and ``break_end``. These checks pin
that the selected-plan run keeps them in the evidence it stores, that the per-period traces of a
continuous day are exactly the one execution's events, and that the trace never changes the
numbers (no engine change; the playback only reads the trace).

Data: SYNTHETIC (setup, rates and service samples made for the test).
"""

from __future__ import annotations

import json
import types
from collections import Counter

import pytest

import backend.api.workflow as workflow_api
from backend.queueing_engine.services import separate_optimization as sep
from tests.test_separate_day_feasibility import LABELS, _per_date_records, _records, _setup

BREAK_EVENTS = ("draining_start", "break_start", "break_end")


def _plan(setup: dict, max_events: int = 200000) -> dict:
    return {
        "scenario": types.SimpleNamespace(id=9, analysis_id=7, dataset_id=2),
        "schedule": {"periods": [{"time": label, "optimum": {"active_queue_ids": ["a", "b"], "inactive_queue_ids": [],
                                                             "active_lane_count": 2}} for label in LABELS]},
        "dataset": types.SimpleNamespace(normalized_json=_records()),
        "setup": setup, "target": 0.70, "server_cost": 87.0, "waiting_cost": 100.0, "multiplier": 1.0,
        "duration_hours": 1.0, "max_events": max_events,
    }


def _per_date_plan(setup: dict, max_events: int = 200000, dates: tuple[str, ...] = ("2026-09-08",)) -> dict:
    """A selected per-date plan as ingestion and the optimizer write it: periods labelled by date."""
    plan = _plan(setup, max_events)
    labels = [f"{date} {label} UTC" for date in dates for label in LABELS]
    plan["schedule"] = {"periods": [{"time": label, "optimum": {"active_queue_ids": ["a", "b"], "inactive_queue_ids": [],
                                                                "active_lane_count": 2}} for label in labels]}
    plan["dataset"] = types.SimpleNamespace(normalized_json=_per_date_records(dates))
    return plan


def _day_events(setup: dict, seed: int) -> list[dict]:
    """The continuous day run once, directly, with the inputs the selected-plan run builds."""
    origin = sep.des_day_start_minutes(setup)
    assert origin is not None
    windows = []
    for segment in setup["segments"]:
        key, low, high = sep._segment_window(segment)
        windows.append({"time": key, "start_hours": (low - origin) / 60, "end_hours": (high - origin) / 60,
                        "active_queue_ids": ["a", "b"], "queues_by_id": sep.index_period_queues(_records(), key)})
    day = sep.run_routing_day_des(windows, tie_order=list(setup["queue_ids"]), seed=seed, max_events=200000,
                                  breaks=sep.resolve_des_breaks(setup))
    return day["trace_events"]


def _period_events(result: dict) -> list[dict]:
    return [event for period in result["periods"] for event in period["trace"]["trace"]]


def _numbers(result: dict) -> list[dict]:
    return [{key: value for key, value in row.items()} for period in result["periods"] for row in period["results"]]


def test_the_stored_day_trace_carries_each_break_once_in_order():
    result = workflow_api._run_selected_plan_des(_plan(_setup()), seed=7)
    stored = json.loads(json.dumps(result, allow_nan=False))  # what _save_job writes
    events = sorted((e for e in _period_events(stored) if e["type"] in BREAK_EVENTS), key=lambda e: e["t"])
    assert [(e["type"], e["queue_id"]) for e in events] == [(kind, "b") for kind in BREAK_EVENTS]
    drain, start, end = (e["t"] for e in events)
    assert drain <= start < end and end - start == pytest.approx(1.0)
    assert all(e["server_id"] is not None for e in events)


def test_the_period_traces_are_exactly_the_one_executions_events():
    setup = _setup()
    result = workflow_api._run_selected_plan_des(_plan(setup), seed=7)
    joined = _period_events(result)
    day = _day_events(setup, seed=7)
    assert Counter(json.dumps(e, sort_keys=True) for e in joined) == Counter(json.dumps(e, sort_keys=True) for e in day)
    assert [e["t"] for e in day] == sorted(e["t"] for e in day)
    arrivals = {e["customer_id"] for e in joined if e["type"] == "arrival"}
    assert arrivals and arrivals == {e["customer_id"] for e in joined if e["type"] == "service_end"}
    # The replay places each period on the day clock from its stored start.
    origin = sep.des_day_start_minutes(setup)
    assert origin is not None
    starts = {sep._segment_window(s)[0]: (sep._segment_window(s)[1] - origin) / 60 for s in setup["segments"]}
    assert [p["start_hours"] for p in result["periods"]] == pytest.approx([starts[p["time"]] for p in result["periods"]])
    assert len({p["start_hours"] for p in result["periods"]}) == len(result["periods"])


def test_per_date_selected_runs_place_each_break_inside_its_own_date():
    # B13: every date is one continuous day from empty, so its 11:00 break starts at 11:00 of that date.
    dates = ("2026-09-08", "2026-09-09")
    result = workflow_api._run_selected_plan_des(_per_date_plan(_setup(basis="per_date"), dates=dates), seed=7)
    assert [day["date"] for day in result["days"]] == list(dates)
    assert result["admitted"] == sum(day["admitted"] for day in result["days"])
    for date in dates:
        events = [e for p in result["periods"] if p["time"].startswith(date) for e in p["trace"]["trace"]]
        drain, start, end = ([e["t"] for e in events if e["type"] == kind] for kind in BREAK_EVENTS)
        # On a day that opens at 10:00, lane b stops taking customers 3 minutes before its 11:00 break
        # (PRE_BREAK_CUTOFF_MINUTES), goes on break when its current customer is done, for 60 minutes.
        assert drain == [pytest.approx(1.0 - 3 / 60)]
        assert len(start) == len(end) == 1 and drain[0] <= start[0] < 2.0 and end[0] - start[0] == pytest.approx(1.0)
        assert [p["start_hours"] for p in result["periods"] if p["time"].startswith(date)] == [0.0, 1.0, 2.0]


@pytest.mark.parametrize("basis", ["representative_day", "per_date"])
def test_the_trace_cap_never_changes_the_numbers(basis):
    build = _per_date_plan if basis == "per_date" else _plan
    full = workflow_api._run_selected_plan_des(build(_setup(basis=basis)), seed=7)
    capped = workflow_api._run_selected_plan_des(build(_setup(basis=basis), max_events=5), seed=7)
    assert any(period["trace"]["truncated"] for period in capped["periods"])
    assert not any(period["trace"]["truncated"] for period in full["periods"])
    assert _numbers(capped) == _numbers(full)
    assert capped["overall_status"] == full["overall_status"] == "COMPLETED"


def test_without_breaks_there_are_no_break_events():
    result = workflow_api._run_selected_plan_des(_plan({**_setup(), "breaks": []}), seed=7)
    assert not [e for e in _period_events(result) if e["type"] in BREAK_EVENTS]
