"""Continuous-day Separate routing DES (representative day).

One run over the operating day: per-period arrival rates, scheduled lane
opening/closing (drain_existing), breaks at wall-clock offsets, and customer
and break state carried across period boundaries. Existing primitives only:
route_arrival, DedicatedQueueLifecycle, empirical resampling, trace schema.
"""
from __future__ import annotations

import pytest

from backend.queueing_engine.config import PRE_BREAK_CUTOFF_MINUTES
from backend.queueing_engine.services import separate_optimization as sep

SAMPLES = [0.1, 0.12, 0.15, 0.2]


def _period(label, start, end, active, lam=6.0, samples=SAMPLES, lanes=("a", "b", "c")):
    return {"time": label, "start_hours": start, "end_hours": end,
            "active_queue_ids": list(active),
            "queues_by_id": {q: {"queue_id": q, "lambda": lam / len(active) if q in active else 0.0,
                                 "service_samples_hours": list(samples)} for q in lanes}}


def _run(periods, breaks=None, seed=5):
    return sep.run_routing_day_des(periods, tie_order=["a", "b", "c"], seed=seed,
                                   max_events=100000, breaks=breaks)


def _events(result, queue_id, kind):
    return [e for e in result["trace_events"] if e["queue_id"] == queue_id and e["type"] == kind]


def test_lane_opens_only_when_scheduled():
    result = _run([_period("s1", 0.0, 1.0, ["a", "b"]), _period("s2", 1.0, 2.0, ["a", "b", "c"])])
    c_arrivals = [e["t"] for e in _events(result, "c", "arrival")]
    assert c_arrivals and min(c_arrivals) >= 1.0


def test_closing_lane_drains_its_own_queue_without_transfers():
    result = _run([_period("s1", 0.0, 1.0, ["a", "b", "c"], lam=30.0),
                   _period("s2", 1.0, 2.0, ["a", "b"], lam=6.0)])
    c_arr = [e for e in _events(result, "c", "arrival")]
    assert c_arr and max(e["t"] for e in c_arr) < 1.0          # no new arrivals after closure
    c_ids = {e["customer_id"] for e in c_arr}
    served_c = {e["customer_id"] for e in _events(result, "c", "service_end")}
    assert c_ids == served_c                                    # its own queue finished in place
    for other in ("a", "b"):                                    # never transferred elsewhere
        assert not c_ids & {e["customer_id"] for e in _events(result, other, "service_start")}


def test_break_crossing_a_period_boundary_runs_once_in_full():
    breaks = [{"queue_id": "a", "start_hours": 0.95, "duration_hours": 0.5}]
    result = _run([_period("s1", 0.0, 1.0, ["a", "b", "c"], lam=20.0),
                   _period("s2", 1.0, 2.0, ["a", "b", "c"], lam=20.0)], breaks=breaks)
    life = [e for e in result["trace_events"]
            if e["queue_id"] == "a" and e["type"] in ("draining_start", "break_start", "break_end")]
    assert [e["type"] for e in life] == ["draining_start", "break_start", "break_end"]
    drain, start, end = (e["t"] for e in life)
    assert drain == pytest.approx(0.95 - PRE_BREAK_CUTOFF_MINUTES / 60)
    assert start >= drain and end - start == pytest.approx(0.5)
    assert end > 1.0                                            # rest continues into s2
    assert not [e for e in _events(result, "a", "arrival") if drain < e["t"] < end]
    assert [e for e in _events(result, "a", "arrival") if e["t"] > end]


def test_all_customers_served_and_counted_by_arrival_period():
    periods = [_period("s1", 0.0, 1.0, ["a", "b"]), _period("s2", 1.0, 2.0, ["a", "b", "c"])]
    result = _run(periods)
    assert result["customer_conservation"] is True
    by_period = {p["time"]: p for p in result["periods"]}
    total = sum(lane["arrivals"] for p in by_period.values() for lane in p["lanes"])
    assert total == result["admitted"] == result["served"]
    assert all(lane["arrivals"] == 0 for lane in by_period["s1"]["lanes"] if lane["queue_id"] == "c")
    assert [e["t"] for e in result["trace_events"] if e["type"] == "arrival"][-1] < 2.0


def test_seeded_runs_are_reproducible():
    periods = [_period("s1", 0.0, 1.0, ["a", "b"]), _period("s2", 1.0, 2.0, ["a", "b", "c"])]
    assert _run(periods, seed=9)["trace_events"] == _run(periods, seed=9)["trace_events"]


def test_arrivals_wait_when_every_lane_is_unavailable_across_a_boundary():
    """All lanes resting past a period end: customers wait, nothing breaks."""
    breaks = [{"queue_id": q, "start_hours": 0.9, "duration_hours": 0.3} for q in ("a", "b", "c")]
    result = _run([_period("s1", 0.0, 1.0, ["a", "b", "c"], lam=12.0),
                   _period("s2", 1.0, 2.0, ["a", "b", "c"], lam=12.0)], breaks=breaks)
    assert result["customer_conservation"] is True
    rest_ends = [e["t"] for e in result["trace_events"] if e["type"] == "break_end"]
    first_open = min(rest_ends)
    stalled = [e for e in result["trace_events"] if e["type"] == "arrival"
               and 0.9 - PRE_BREAK_CUTOFF_MINUTES / 60 < e["t"] < first_open]
    assert not stalled  # nobody joins a draining or resting lane


def test_stalled_arrival_reaching_a_lane_unscheduled_in_its_period_is_rejected():
    """The only scheduled lane rests past the period end and a new lane opens in
    the next period: the stalled customer's arrival period has no service
    samples for that lane, so the run refuses with a reason instead of crashing."""
    breaks = [{"queue_id": "a", "start_hours": 0.9, "duration_hours": 0.3}]
    periods = [_period("s1", 0.0, 1.0, ["a"], lam=30.0), _period("s2", 1.0, 2.0, ["a", "b"], lam=30.0)]
    with pytest.raises(ValueError, match="no service samples"):
        sep.run_routing_day_des(periods, tie_order=["a", "b"], seed=0, max_events=100000, breaks=breaks)
