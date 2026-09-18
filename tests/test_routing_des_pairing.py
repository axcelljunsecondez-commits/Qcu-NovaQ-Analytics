"""Common random numbers for the Separate routing DES (audit item #1).

Arrivals, service quantiles, and routing tie-breaks each come from their own
seed-derived stream, so two schedules run with the same seed face the same
customers: identical arrival times whenever the per-window total rate
sequence is identical, and customer k drawing the same service quantile
whichever lane serves them. Paired comparisons (break optimizer "better in X
of Y", candidate ranking) then differ only by the schedule itself.

Pairing holds while at least one lane can take arrivals: when no lane is
eligible, the arrival stream itself waits (unchanged lifecycle rule), so
schedules that leave every lane ineligible at different times can diverge.
"""
from __future__ import annotations

from backend.queueing_engine.services import separate_optimization as sep

SAMPLES = [0.05, 0.08, 0.1, 0.12, 0.15, 0.2]


def _period(label, start, end, lanes=("a", "b"), lam=8.0):
    return {"time": label, "start_hours": start, "end_hours": end,
            "active_queue_ids": list(lanes),
            "queues_by_id": {q: {"queue_id": q, "lambda": lam / len(lanes),
                                 "service_samples_hours": list(SAMPLES)} for q in lanes}}


PERIODS = [_period("s1", 0.0, 1.0), _period("s2", 1.0, 2.0), _period("s3", 2.0, 3.0, lam=12.0)]


def _break(queue, start, duration=0.25):
    return {"queue_id": queue, "start_hours": start, "duration_hours": duration}


def _day(breaks, seed):
    return sep.run_routing_day_des(PERIODS, tie_order=["a", "b"], seed=seed,
                                   max_events=1_000_000, breaks=breaks)


def _by_customer(trace, kind, field):
    return {e["customer_id"]: e[field] for e in trace if e["type"] == kind}


def test_day_des_moved_break_sees_identical_arrivals():
    current = [_break("a", 0.5)]
    moved = [_break("a", 1.75)]  # lane b stays open throughout: some lane is always eligible
    for seed in range(1, 11):
        before, after = _day(current, seed), _day(moved, seed)
        assert before["admitted"] == after["admitted"], seed
        assert _by_customer(before["trace_events"], "arrival", "t") == \
            _by_customer(after["trace_events"], "arrival", "t"), seed


def test_day_des_customer_service_quantile_is_paired():
    for seed in range(1, 11):
        before, after = _day([_break("a", 0.5)], seed), _day([_break("b", 2.25)], seed)
        first = _by_customer(before["trace_events"], "service_end", "service_time_hours")
        second = _by_customer(after["trace_events"], "service_end", "service_time_hours")
        shared = first.keys() & second.keys()
        assert shared and len(shared) == len(first) == len(second), seed
        assert {k: first[k] for k in shared} == {k: second[k] for k in shared}, seed


def _static(active, seed):
    return sep._run_routing_des(
        active_ids=list(active), tie_order=["a", "b", "c"],
        samples_by_id={q: list(SAMPLES) for q in active}, total_lambda=10.0,
        duration_hours=4.0, seed=seed, time_label="08:00", max_events=1_000_000)


def test_static_candidates_with_same_total_lambda_see_identical_arrivals():
    for seed in range(1, 11):
        _, two, _, two_summary = _static(("a", "b"), seed)
        _, three, _, three_summary = _static(("a", "b", "c"), seed)
        assert two_summary["admitted"] == three_summary["admitted"], seed
        assert _by_customer(two, "arrival", "t") == _by_customer(three, "arrival", "t"), seed
        first = _by_customer(two, "service_end", "service_time_hours")
        second = _by_customer(three, "service_end", "service_time_hours")
        shared = first.keys() & second.keys()
        assert shared, seed
        assert {k: first[k] for k in shared} == {k: second[k] for k in shared}, seed


def test_same_seed_is_deterministic_and_none_still_runs():
    breaks = [_break("a", 0.5)]
    assert _day(breaks, 42) == _day(breaks, 42)
    assert _static(("a", "b"), 42) == _static(("a", "b"), 42)
    unseeded = _day(breaks, None)
    assert unseeded["customer_conservation"] is True and unseeded["admitted"] > 0
    lanes, _, _, summary = _static(("a", "b"), None)
    assert summary["admitted"] > 0 and set(lanes) == {"a", "b"}


def test_stream_seeds_are_derived_deterministically():
    assert sep._paired_stream_seeds(42) == sep._paired_stream_seeds(42)
    assert len(set(sep._paired_stream_seeds(42))) == 3
    assert sep._paired_stream_seeds(42) != sep._paired_stream_seeds(43)
    assert sep._paired_stream_seeds(None) == (None, None, None)
