"""Break-aware Separate-queue DES: ACTIVE → DRAINING → ON_BREAK → ACTIVE.

Configured breaks drive per-lane draining with a 3-minute operational
pre-break cutoff; draining lanes finish existing customers in place (never
transferred), breaks start only on empty queues with full configured
duration from the actual start, and lanes return to ACTIVE afterwards.
Routing, service sampling, and conservation semantics are unchanged.
"""
from __future__ import annotations

import pytest

from backend.queueing_engine import config as engine_config
from backend.queueing_engine.services import separate_optimization as sep
from backend.queueing_engine.simulation.queue_lifecycle import (
    DedicatedQueueLifecycle,
    DedicatedQueueState,
)


def _queue(queue_id="a"):
    return DedicatedQueueLifecycle(queue_id, f"server:{queue_id}")


def _samples():
    return {"a": [0.10, 0.20, 0.15, 0.25, 0.12],
            "b": [0.10, 0.20, 0.15, 0.25, 0.12]}


def _run(breaks, seed=7, total_lambda=20.0, duration=8.0):
    return sep._run_routing_des(
        active_ids=["a", "b"], tie_order=["a", "b"],
        samples_by_id=_samples(), total_lambda=total_lambda,
        duration_hours=duration, seed=seed, time_label="08:00",
        max_events=100000, breaks=breaks)


# Long enough that lane a's queue at the 4 h cutoff (served at <= 0.25 h per
# customer under the overloaded 20/h demand) drains and its 1 h break ends
# inside the run, independent of the particular random draws.
BREAK_COMPLETES_HORIZON = 16.0


def _break(start=4.0, duration=1.0, queue="a"):
    return {"queue_id": queue, "start_hours": start, "duration_hours": duration}


CUTOFF = 4.0 - 3.0 / 60.0


# --- lifecycle unit contract -------------------------------------------------

def test_break_lifecycle_api_exists():
    assert hasattr(DedicatedQueueLifecycle, "begin_draining")
    assert hasattr(DedicatedQueueLifecycle, "begin_break")
    assert hasattr(DedicatedQueueLifecycle, "end_break")
    assert hasattr(DedicatedQueueState, "ON_BREAK")
    assert engine_config.PRE_BREAK_CUTOFF_MINUTES == 3.0


def test_draining_keeps_existing_customers_and_rejects_new_arrivals():
    queue = _queue()
    queue.enqueue("1")
    queue.enqueue("2")
    queue.begin_draining()
    assert queue.state == DedicatedQueueState.DRAINING
    assert queue.accepts_arrivals is False
    assert list(queue.waiting_customer_ids) == ["1", "2"]
    assert queue.enqueue("3") is False
    assert queue.begin_service() == "1"
    assert queue.complete_service() == "1"
    assert queue.state == DedicatedQueueState.DRAINING


def test_break_starts_only_when_empty_and_ends_back_active():
    queue = _queue()
    queue.enqueue("1")
    queue.begin_draining()
    with pytest.raises(ValueError):
        queue.begin_break()
    queue.begin_service()
    queue.complete_service()
    queue.begin_break()
    assert queue.state == DedicatedQueueState.ON_BREAK
    assert queue.accepts_arrivals is False
    queue.end_break()
    assert queue.state == DedicatedQueueState.ACTIVE
    assert queue.enqueue("9") is True


def test_drained_break_queue_does_not_auto_close():
    queue = _queue()
    queue.enqueue("1")
    queue.begin_draining()
    queue.begin_service()
    queue.complete_service()
    assert queue.state == DedicatedQueueState.DRAINING


# --- integrated break execution -----------------------------------------------

def _events(trace, event_type=None, queue_id=None):
    return [event for event in trace
            if (event_type is None or event["type"] == event_type)
            and (queue_id is None or event["queue_id"] == queue_id)]


def test_lane_active_before_cutoff_and_draining_exactly_at_cutoff():
    _, trace, _, _ = _run([_break()])
    early = [event for event in trace if event["t"] < CUTOFF]
    assert early
    assert {event["type"] for event in early} <= {"arrival", "service_start", "service_end"}
    assert [event for event in early if event["queue_id"] == "a"]
    draining = _events(trace, "draining_start", "a")
    assert len(draining) == 1
    assert draining[0]["t"] == CUTOFF


def test_draining_lane_gets_no_new_arrivals_while_other_lane_serves():
    lanes, trace, _, _ = _run([_break()], duration=BREAK_COMPLETES_HORIZON)
    breaks_a = lanes["a"]["breaks"]
    assert breaks_a
    returned = breaks_a[0]["actual_end"]
    window = [event for event in trace
              if event["type"] == "arrival" and CUTOFF < event["t"] < returned]
    assert window
    assert {event["queue_id"] for event in window} == {"b"}
    assert lanes["b"]["served"] > 0


def test_waiting_customers_stay_and_service_finishes_without_transfer():
    _, trace, _, _ = _run([_break()])
    arrivals: dict[int, str] = {}
    for event in trace:
        if event["type"] == "arrival":
            arrivals[event["customer_id"]] = event["queue_id"]
    for event in trace:
        if event["type"] == "service_end":
            assert arrivals[event["customer_id"]] == event["queue_id"]
    a_ends = [event for event in trace
              if event["type"] == "service_end" and event["queue_id"] == "a"
              and event["t"] > CUTOFF]
    assert a_ends


def test_every_service_start_pairs_with_later_service_end():
    _, trace, _, _ = _run([_break()])
    starts: dict[int, float] = {}
    for event in trace:
        if event["type"] == "service_start":
            starts[event["customer_id"]] = event["t"]
    for event in trace:
        if event["type"] == "service_end":
            assert event["customer_id"] in starts
            assert event["t"] >= starts[event["customer_id"]]


def test_break_starts_only_when_empty_with_full_duration_from_actual():
    lanes, trace, _, _ = _run([_break()], duration=BREAK_COMPLETES_HORIZON)
    (record,) = lanes["a"]["breaks"]
    assert record["scheduled_start"] == 4.0
    assert record["cutoff"] == CUTOFF
    assert record["actual_start"] >= CUTOFF
    if record["actual_start"] > CUTOFF:
        assert [event for event in trace
                if event["type"] == "service_end" and event["queue_id"] == "a"
                and CUTOFF < event["t"] <= record["actual_start"]]
    assert record["actual_end"] - record["actual_start"] == 1.0
    ends = _events(trace, "break_end", "a")
    assert len(ends) == 1
    assert ends[0]["t"] == pytest.approx(record["actual_end"])


def test_returned_lane_accepts_arrivals_and_other_lane_untouched():
    lanes, trace, _, _ = _run([_break()], duration=BREAK_COMPLETES_HORIZON)
    returned = lanes["a"]["breaks"][0]["actual_end"]
    assert [event for event in trace
            if event["type"] == "arrival" and event["queue_id"] == "a"
            and event["t"] > returned]
    assert lanes["a"]["lifecycle"].state == DedicatedQueueState.ACTIVE
    assert not _events(trace, "draining_start", "b")
    assert not [event for event in trace
                if event["type"] in ("break_start", "break_end") and event["queue_id"] == "b"]
    assert lanes["b"]["lifecycle"].state == DedicatedQueueState.ACTIVE


def test_multiple_breaks_stay_independent():
    lanes, trace, _, _ = _run([
        _break(start=3.0, duration=0.5, queue="a"),
        _break(start=6.0, duration=0.5, queue="b"),
    ], total_lambda=12.0)
    for queue_id, start in (("a", 3.0), ("b", 6.0)):
        (record,) = lanes[queue_id]["breaks"]
        assert record["scheduled_start"] == start
        assert record["actual_end"] - record["actual_start"] == pytest.approx(0.5)
        assert record["actual_start"] >= start - 3.0 / 60.0


def test_no_break_path_is_unchanged():
    lanes, trace, truncated, summary = sep._run_routing_des(
        active_ids=["a", "b"], tie_order=["a", "b"],
        samples_by_id=_samples(), total_lambda=20.0,
        duration_hours=8.0, seed=7, time_label="08:00",
        max_events=100000)
    assert {event["type"] for event in trace} <= {"arrival", "service_start", "service_end"}
    assert truncated is False
    assert summary["unrouted_at_horizon"] == 0
    assert summary["admitted"] == sum(stats["arrivals"] for stats in lanes.values())


def test_malformed_breaks_raise():
    with pytest.raises(ValueError):
        _run([{"queue_id": "ghost", "start_hours": 1.0, "duration_hours": 1.0}])
    with pytest.raises(ValueError):
        _run([{"queue_id": "a", "start_hours": 1.0, "duration_hours": 0.0}])
    with pytest.raises(ValueError):
        _run([{"queue_id": "a", "start_hours": -1.0, "duration_hours": 1.0}])
