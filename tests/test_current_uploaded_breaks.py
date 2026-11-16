"""Owner-approved Current baseline breaks: deterministic, explicitly synthetic references."""
from __future__ import annotations

from copy import deepcopy

import pytest

from backend.queueing_engine.simulation import simulation as engine


def setup(breaks=None):
    return {
        "queue_structure": "separate_queues", "queue_ids": ["a"],
        "fixed_server_count": 1, "staffing_varies_by_period": False,
        "capacity_mode": "unlimited", "abandonment_mode": "not_modeled",
        "event_period_basis": "representative_day", "separate_queue_closure_policy": "drain_existing",
        "segments": [{"id": "s1", "start_time": "08:00", "end_time": "09:00"}],
        "breaks": breaks if breaks is not None else [
            {"queue_id": "a", "scheduled_start_time": "08:15", "duration_minutes": 15}],
    }


def records(config, service=0.1875):
    return [{"segment_id": segment["id"], "time": segment["id"], "queue_id": "a",
             "queue_structure": "separate_queues", "model_id": "parallel_mg1", "lambda": 1,
             "service_time_source": "empirical", "service_samples_hours": [service]}
            for segment in config["segments"]]


def run(monkeypatch, config=None, intervals=(0.125, 0.0625, 0.125, 2), service=0.1875, max_events=1000):
    config = config or setup()
    arrivals = iter(intervals)
    monkeypatch.setattr(engine, "_exponential", lambda _rate, _rng: next(arrivals, 2))
    return engine.simulate_segments_with_trace(records(config, service), queue_setup=config,
                                              sim_hours=1, seed=7, max_events=max_events)


def times(result, kind):
    return [event["t"] for event in result["trace"] if event["type"] == kind]


def test_reference_finishes_ongoing_service_and_keeps_waiting_and_new_arrivals(monkeypatch):
    # Arrivals 08:07:30, 08:11:15, 08:18:45; every service 11m15s.
    # Break 08:15-08:30; first service finishes 08:18:45, waiting customers
    # start 08:30 and 08:41:15. Total wait = 18m45s + 22m30s = 41m15s.
    result = run(monkeypatch)
    assert times(result, "arrival") == [0.125, 0.1875, 0.3125]
    assert times(result, "service_start") == [0.125, 0.5, 0.6875]
    assert times(result, "service_end") == [0.3125, 0.6875, 0.875]
    assert times(result, "draining_start") == [0.25]
    assert times(result, "break_start") == [0.3125]
    assert times(result, "break_end") == [0.5]
    row = result["results"][0]
    assert row["arrivals"] == row["served"] == 3
    assert row["waiting"] == row["in_service"] == 0
    assert row["Wq_sim"] == pytest.approx(0.6875 / 3)
    assert row["busy_time"] == pytest.approx(3 * 0.1875)
    assert row["customer_conservation"] is True
    assert {event["queue_id"] for event in result["trace"]} == {"a"}
    assert result["break_policy"] == engine.CURRENT_BREAK_POLICY


@pytest.mark.parametrize("arrival,expected", [(0.25, 0.5), (0.5, 0.5)])
def test_half_open_boundaries_start_blocks_and_end_allows_service(monkeypatch, arrival, expected):
    result = run(monkeypatch, intervals=(arrival, 2), service=0.0625)
    assert times(result, "service_start") == [expected]
    assert times(result, "break_start") == [0.25]
    assert times(result, "break_end") == [0.5]


def test_touching_breaks_do_not_allow_service_at_their_shared_boundary(monkeypatch):
    config = setup([
        {"queue_id": "a", "scheduled_start_time": "08:15", "duration_minutes": 15},
        {"queue_id": "a", "scheduled_start_time": "08:30", "duration_minutes": 15},
    ])
    result = run(monkeypatch, config, intervals=(0.25, 2), service=0.0625)
    assert times(result, "service_start") == [0.75]
    assert times(result, "break_start") == [0.25, 0.5]


def test_service_crossing_whole_window_does_not_fabricate_idle_break_time(monkeypatch):
    result = run(monkeypatch, intervals=(0.125, 2), service=0.625)
    assert times(result, "service_start") == [0.125]
    assert times(result, "service_end") == [0.75]
    assert times(result, "draining_start") == [0.25]
    assert times(result, "break_start") == []
    assert times(result, "break_end") == [0.5]


def test_break_crosses_operating_segments_without_resetting_queue(monkeypatch):
    config = setup([{"queue_id": "a", "scheduled_start_time": "08:15", "duration_minutes": 30}])
    config["segments"] = [
        {"id": "s1", "start_time": "08:00", "end_time": "08:30"},
        {"id": "s2", "start_time": "08:30", "end_time": "09:00"},
    ]
    result = run(monkeypatch, config, intervals=(0.25, 2, 0.125, 2), service=0.0625)
    assert times(result, "arrival") == [0.25, 0.625]
    assert times(result, "service_start") == [0.75, 0.8125]
    assert all(row["customer_conservation"] for row in result["results"])


def test_trace_cap_does_not_change_aggregate_results(monkeypatch):
    full = run(monkeypatch)
    capped = run(monkeypatch, max_events=2)
    assert capped["results"] == full["results"]
    assert capped["truncated"] is True
    assert len(capped["trace"]) == 2


@pytest.mark.parametrize("change,reason", [
    ({"queue_id": "missing"}, "unknown queue"),
    ({"scheduled_start_time": "07:45"}, "outside every configured operating segment"),
    ({"scheduled_start_time": "08:45", "duration_minutes": 30}, "staffed operating hours"),
    ({"duration_minutes": 0}, "positive duration"),
    ({"duration_minutes": 1.5}, "whole number"),
])
def test_invalid_stored_breaks_are_refused(monkeypatch, change, reason):
    config = setup()
    config["breaks"][0].update(change)
    result = run(monkeypatch, config)
    assert all(row["simulation_supported"] is False for row in result["results"])
    assert reason in result["results"][0]["error"]
    assert result["trace"] == []


def test_overlapping_stored_breaks_are_refused(monkeypatch):
    config = setup()
    config["breaks"].append({"queue_id": "a", "scheduled_start_time": "08:20", "duration_minutes": 15})
    result = run(monkeypatch, config)
    assert "overlap" in result["results"][0]["error"]


def test_breaks_refuse_a_concatenated_clock_with_real_wall_clock_gaps(monkeypatch):
    config = setup()
    config["segments"].append({"id": "s2", "start_time": "10:00", "end_time": "11:00"})
    result = run(monkeypatch, config)
    assert "contiguous" in result["results"][0]["error"]


def test_empty_break_schedule_preserves_unconfigured_result_shape(monkeypatch):
    config = setup([])
    empty = run(monkeypatch, config)
    del config["breaks"]
    missing = run(monkeypatch, config)
    assert missing == empty
    assert "break_policy" not in empty


def test_full_compact_and_regenerated_day_use_same_breaks_and_fingerprints():
    config = setup()
    config["event_period_basis"] = "per_date"
    day_records = records(config, service=0.0625)
    day_records[0]["time"] = "2026-08-03 s1 UTC"
    days = [("2026-08-03", day_records)]
    full = engine.simulate_parallel_days_with_trace(days, config, 1, [7], 1000)
    compact = engine.simulate_parallel_days_compact(days, config, 1, [7], 1000)
    regenerated = engine.simulate_parallel_days_with_trace(deepcopy(days), config, 1, [7], 1000)
    assert full == regenerated
    assert compact["break_policy"] == full["break_policy"] == engine.CURRENT_BREAK_POLICY
    assert compact["days"][0]["trace_digest"] == engine.canonical_digest(regenerated["trace"])
    assert compact["days"][0]["rows_digest"] == engine.canonical_digest(regenerated["results"])
    assert all(row["customer_conservation"] for row in full["results"])
