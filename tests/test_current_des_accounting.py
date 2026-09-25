"""D2: Current separate-queue DES accounting at the fixed horizon.

The Current DES (``_simulate_parallel_segments_core``) credits a lane server's busy time to
the period in which it occurs, up to the horizon H, and computes Wq over one population:
customers who arrived in the period and started service before H. Customers still waiting at
H are counted, never given invented waits.

The references never reuse the implementation's aggregation:

- hand-built service intervals with hand-computed busy time per period;
- a one-server FIFO recursion over the run's own arrival times and deterministic (or
  recorded) service times, which rebuilds every start and end without the simulator's
  service events;
- closed forms for single deterministic services.
"""

from __future__ import annotations

import math

import pytest

from backend.queueing_engine.simulation.simulation import (
    CURRENT_WAIT_POPULATION,
    _window_busy_hours,
    simulate_segments_with_trace,
    summarize_simulation,
)

HOURS = [
    ("p0", "08:00:00", "09:00:00"),
    ("p1", "09:00:00", "10:00:00"),
    ("p2", "10:00:00", "11:00:00"),
    ("p3", "11:00:00", "12:00:00"),
    ("p4", "12:00:00", "13:00:00"),
]


def _setup(lanes, periods, active=None):
    segments = []
    for index, (period, start, end) in enumerate(periods):
        segment = {"id": period, "start_time": start, "end_time": end}
        if active is not None:
            segment["active_queue_ids"] = active[index]
        segments.append(segment)
    return {
        "queue_structure": "separate_queues",
        "queue_ids": lanes,
        "staffing_varies_by_period": active is not None,
        "separate_queue_closure_policy": "drain_existing",
        "segments": segments,
    }


def _row(period, lane, lam, samples):
    return {
        "segment_id": period, "time": period, "queue_id": lane, "queue_structure": "separate_queues",
        "model_id": "parallel_mg1", "lambda": lam, "mu": len(samples) / sum(samples), "c": 1,
        "service_time_source": "empirical", "service_samples_hours": samples,
    }


def _run(rows, setup, seed):
    out = simulate_segments_with_trace(rows, seed=seed, max_events=100_000, queue_setup=setup)
    assert not out["truncated"]
    assert all(row["simulation_supported"] and not row["error"] for row in out["results"])
    return out


def _minutes(clock):
    hours, minutes, *_ = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _windows(periods):
    origin = _minutes(periods[0][1])
    return [(period, (_minutes(start) - origin) / 60, (_minutes(end) - origin) / 60) for period, start, end in periods]


def _fifo(out, lane, service=None):
    """Rebuild one lane from its arrival times alone: FIFO, one server, H = end of the run.

    ``service`` is the deterministic service time; None uses each customer's recorded
    service time (unknown for the customer still in service at H). start is None for a
    customer still waiting at H; end is None for a customer still in service at H.
    """
    horizon = out["total_hours"]
    arrivals = sorted(
        (event["t"], event["customer_id"], event["segment_id"])
        for event in out["trace"] if event["type"] == "arrival" and event["queue_id"] == lane
    )
    recorded = {
        event["customer_id"]: event["service_time_hours"]
        for event in out["trace"] if event["type"] == "service_end" and event["queue_id"] == lane
    }
    free, customers = 0.0, []
    for arrival, customer_id, period in arrivals:
        start = max(arrival, free)
        if start >= horizon:
            customers.append({"period": period, "arrival": arrival, "start": None, "end": None})
            continue
        duration = service if service is not None else recorded.get(customer_id)
        end = None if duration is None or start + duration >= horizon else start + duration
        free = math.inf if end is None else end
        customers.append({"period": period, "arrival": arrival, "start": start, "end": end})
    return customers


def _reference(customers, windows, horizon):
    busy = {period: 0.0 for period, _, _ in windows}
    cohort = {
        period: {"arrivals": 0, "started": 0, "completed": 0, "waits": [], "censored": 0, "censored_hours": 0.0}
        for period, _, _ in windows
    }
    for customer in customers:
        own = cohort[customer["period"]]
        own["arrivals"] += 1
        if customer["start"] is None:
            own["censored"] += 1
            own["censored_hours"] += horizon - customer["arrival"]
            continue
        own["started"] += 1
        own["waits"].append(customer["start"] - customer["arrival"])
        own["completed"] += customer["end"] is not None
        end = horizon if customer["end"] is None else customer["end"]
        for period, lo, hi in windows:
            busy[period] += max(0.0, min(end, hi, horizon) - max(customer["start"], lo))
    return busy, cohort


def _assert_lane(out, lane, periods, service=None):
    windows = _windows(periods)
    horizon = out["total_hours"]
    customers = _fifo(out, lane, service)
    busy, cohort = _reference(customers, windows, horizon)
    rows = {row["segment_id"]: row for row in out["results"] if row["queue_id"] == lane}
    for period, lo, hi in windows:
        row, own = rows[period], cohort[period]
        assert row["busy_time"] == pytest.approx(busy[period], abs=1e-5), period
        assert row["rho_sim"] == pytest.approx(busy[period] / (hi - lo), abs=1e-5), period
        assert row["arrivals"] == own["arrivals"], period
        assert row["started"] == own["started"], period
        assert row["served"] == own["completed"], period
        assert row["censored_customers"] == own["censored"], period
        assert row["censored_waiting_hours"] == pytest.approx(own["censored_hours"], abs=1e-5), period
        if own["started"]:
            assert row["Wq_sim"] == pytest.approx(math.fsum(own["waits"]) / own["started"], abs=1e-5), period
        else:
            assert row["Wq_sim"] is None, period
        assert row["wait_population"] == CURRENT_WAIT_POPULATION
    return customers, busy, cohort, rows


def _crosses(customers, boundary, horizon):
    return [
        c for c in customers
        if c["start"] is not None and c["start"] < boundary < (horizon if c["end"] is None else c["end"])
    ]


def test_window_busy_hours_matches_hand_computed_intervals():
    # One server: [0.2, 0.5), [0.9, 2.6), [3.5, running at H = 3.8) over four 1-hour periods.
    intervals = [(0.2, 0.5), (0.9, 2.6), (3.5, 3.8)]
    expected = [0.3 + 0.1, 1.0, 0.6, 0.3]
    for index, value in enumerate(expected):
        assert _window_busy_hours(intervals, index, index + 1, 3.8) == pytest.approx(value, abs=1e-12)
    # Service after the horizon is never credited, even if the interval says otherwise.
    assert _window_busy_hours([(3.5, 9.0)], 3.0, 4.0, 3.8) == pytest.approx(0.3, abs=1e-12)
    assert _window_busy_hours([], 0.0, 1.0, 1.0) == 0.0


def test_service_completed_inside_one_period():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 2.0, [0.05]), _row("p1", "a", 0.0, [0.05])], _setup(["a"], periods), seed=3)
    customers, busy, _, rows = _assert_lane(out, "a", periods, service=0.05)
    assert len(customers) >= 2 and all(c["end"] is not None and c["end"] < 1.0 for c in customers)
    assert busy["p0"] == pytest.approx(0.05 * len(customers), abs=1e-9)
    assert rows["p1"]["busy_time"] == 0.0 and rows["p1"]["Wq_sim"] is None


def test_service_crossing_two_periods_is_credited_where_it_occurs():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 1.5, [0.5]), _row("p1", "a", 0.0, [0.5])], _setup(["a"], periods), seed=3)
    customers, busy, _, rows = _assert_lane(out, "a", periods, service=0.5)
    assert _crosses(customers, 1.0, 2.0)
    # p1 had no arrivals but its server was busy finishing p0's customers.
    assert rows["p1"]["arrivals"] == 0 and rows["p1"]["busy_time"] > 0.0
    assert busy["p0"] + busy["p1"] == pytest.approx(
        sum((2.0 if c["end"] is None else c["end"]) - c["start"] for c in customers if c["start"] is not None), abs=1e-9)


def test_service_crossing_three_or_more_periods_closed_form():
    periods = HOURS[:4]
    rows_in = [_row("p0", "a", 0.8, [2.5])] + [_row(p, "a", 0.0, [2.5]) for p in ("p1", "p2", "p3")]
    out = _run(rows_in, _setup(["a"], periods), seed=4)
    customers, _, _, rows = _assert_lane(out, "a", periods, service=2.5)
    first, second = customers
    assert first["arrival"] < 0.5 and second["arrival"] < 1.0
    # First service [a1, a1 + 2.5) spans p0-p2; the second follows at once and runs past H = 4.
    assert rows["p0"]["busy_time"] == pytest.approx(1.0 - first["arrival"], abs=1e-5)
    for period in ("p1", "p2", "p3"):
        assert rows[period]["rho_sim"] == pytest.approx(1.0, abs=1e-9)
    assert rows["p0"]["served"] == 1 and rows["p0"]["started"] == 2
    assert rows["p0"]["Wq_sim"] == pytest.approx((0.0 + first["arrival"] + 2.5 - second["arrival"]) / 2, abs=1e-5)


def test_service_beyond_the_horizon_and_fully_occupied_period():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 0.8, [2.5]), _row("p1", "a", 0.0, [2.5])], _setup(["a"], periods), seed=1)
    customers, _, _, rows = _assert_lane(out, "a", periods, service=2.5)
    (only,) = customers
    assert only["start"] == only["arrival"] and only["end"] is None
    assert rows["p0"]["busy_time"] == pytest.approx(1.0 - only["arrival"], abs=1e-5)
    # A period entirely occupied by a service that has not finished is fully busy.
    assert rows["p1"]["rho_sim"] == pytest.approx(1.0, abs=1e-12)
    assert rows["p1"]["served"] == 0 and rows["p1"]["arrivals"] == 0
    # The started-but-unfinished customer's (zero) wait is complete and counted.
    assert rows["p0"]["started"] == 1 and rows["p0"]["served"] == 0 and rows["p0"]["Wq_sim"] == 0.0
    assert rows["p1"]["in_service"] == 1 and rows["p1"]["waiting"] == 0


def test_zero_arrivals_leave_wait_undefined_not_zero():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 0.0, [0.05]), _row("p1", "a", 3.0, [0.05])], _setup(["a"], periods), seed=0)
    _, _, _, rows = _assert_lane(out, "a", periods, service=0.05)
    empty = rows["p0"]
    assert (empty["arrivals"], empty["started"], empty["censored_customers"], empty["busy_time"]) == (0, 0, 0, 0.0)
    assert empty["Wq_sim"] is None and empty["rho_sim"] == 0.0
    assert rows["p1"]["started"] > 0 and rows["p1"]["Wq_sim"] is not None


def test_arrivals_without_service_are_censored_not_zero_filled():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 4.0, [10.0]), _row("p1", "a", 4.0, [10.0])], _setup(["a"], periods), seed=0)
    customers, _, _, rows = _assert_lane(out, "a", periods, service=10.0)
    late = [c for c in customers if c["period"] == "p1"]
    assert len(late) >= 2 and all(c["start"] is None for c in late)
    # Arrivals, none started: undefined Wq, every customer counted as still waiting.
    assert rows["p1"]["started"] == 0 and rows["p1"]["Wq_sim"] is None
    assert rows["p1"]["censored_customers"] == rows["p1"]["arrivals"] == len(late)
    assert rows["p1"]["censored_waiting_hours"] == pytest.approx(sum(2.0 - c["arrival"] for c in late), abs=1e-5)
    # p0: only the first customer started (zero wait); the rest are still waiting.
    assert rows["p0"]["started"] == 1 and rows["p0"]["Wq_sim"] == 0.0
    assert rows["p0"]["censored_customers"] == rows["p0"]["arrivals"] - 1
    assert rows["p0"]["rho_sim"] == pytest.approx(1.0 - customers[0]["arrival"], abs=1e-5)
    assert rows["p1"]["rho_sim"] == pytest.approx(1.0, abs=1e-12)
    # The horizon count on the last row equals the censored customers of both arrival periods.
    assert rows["p1"]["waiting"] == rows["p0"]["censored_customers"] + rows["p1"]["censored_customers"]


def test_started_but_unfinished_customer_is_in_the_wait_population():
    periods = HOURS[:1]
    out = _run([_row("p0", "a", 4.0, [0.4])], _setup(["a"], periods), seed=1)
    customers, _, cohort, rows = _assert_lane(out, "a", periods, service=0.4)
    running = [c for c in customers if c["start"] is not None and c["end"] is None]
    assert len(running) == 1 and running[0]["start"] - running[0]["arrival"] > 0.05
    row = rows["p0"]
    assert row["served"] < row["started"] < row["arrivals"]
    completed = [c["start"] - c["arrival"] for c in customers if c["end"] is not None]
    # Neither the completed-only mean nor started waits over completions is the Wq population.
    assert row["Wq_sim"] != pytest.approx(math.fsum(completed) / len(completed), abs=1e-4)
    assert row["Wq_sim"] != pytest.approx(math.fsum(cohort["p0"]["waits"]) / row["served"], abs=1e-4)


def test_true_zero_wait_is_zero_not_undefined():
    periods = HOURS[:1]
    out = _run([_row("p0", "a", 3.0, [0.01])], _setup(["a"], periods), seed=1)
    customers, _, _, rows = _assert_lane(out, "a", periods, service=0.01)
    assert len(customers) >= 2 and all(c["start"] == c["arrival"] for c in customers)
    assert rows["p0"]["Wq_sim"] == 0.0 and rows["p0"]["started"] == len(customers)


def test_multiple_independent_lanes():
    periods = HOURS[:3]
    lanes = {"a": (5.0, [0.15, 0.25, 0.4]), "b": (2.0, [0.05, 0.1]), "c": (1.2, [0.6, 0.9])}
    rows_in = [_row(p, lane, lam, samples) for p, _, _ in periods for lane, (lam, samples) in lanes.items()]
    out = _run(rows_in, _setup(list(lanes), periods), seed=7)
    crossing = 0
    for lane in lanes:
        customers, _, _, _ = _assert_lane(out, lane, periods)
        crossing += len(_crosses(customers, 1.0, 3.0)) + len(_crosses(customers, 2.0, 3.0))
    assert crossing > 0


def test_consecutive_periods_with_carried_backlog():
    periods = HOURS[:5]
    rates = [6.0, 1.0, 0.0, 3.0, 0.0]
    out = _run([_row(p, "a", lam, [0.2, 0.3]) for (p, _, _), lam in zip(periods, rates)], _setup(["a"], periods), seed=4)
    customers, _, _, rows = _assert_lane(out, "a", periods)
    assert sum(bool(_crosses(customers, float(b), 5.0)) for b in (1, 2, 3, 4)) >= 2
    # p2 had no arrivals but the carried backlog kept the server busy.
    assert rows["p2"]["arrivals"] == 0 and rows["p2"]["busy_time"] > 0.0 and rows["p2"]["Wq_sim"] is None


def test_different_period_durations_use_their_own_length():
    periods = [("q1", "08:00:00", "08:15:00"), ("q2", "08:15:00", "09:00:00"),
               ("q3", "09:00:00", "10:30:00"), ("q4", "10:30:00", "11:00:00")]
    rates = [8.0, 3.0, 2.5, 0.0]
    out = _run([_row(p, "a", lam, [0.1, 0.35]) for (p, _, _), lam in zip(periods, rates)], _setup(["a"], periods), seed=5)
    _, busy, _, rows = _assert_lane(out, "a", periods)
    for period, lo, hi in _windows(periods):
        assert rows[period]["duration_hours"] == pytest.approx(hi - lo)
        assert rows[period]["rho_sim"] == pytest.approx(busy[period] / (hi - lo), abs=1e-5)


def test_draining_lane_is_credited_in_the_period_it_works():
    periods = HOURS[:2]
    setup = _setup(["a", "b"], periods, active=[["a", "b"], ["a"]])
    rows_in = [_row("p0", "a", 1.0, [0.1]), _row("p0", "b", 8.0, [0.2, 0.3]), _row("p1", "a", 1.0, [0.1])]
    out = _run(rows_in, setup, seed=2)
    _, busy, _, rows = _assert_lane(out, "b", periods)
    assert rows["p1"]["active"] is False and rows["p0"]["active"] is True
    assert rows["p1"]["arrivals"] == 0 and busy["p1"] > 0.0
    _assert_lane(out, "a", periods)


def test_busy_time_and_customer_conservation_over_the_horizon():
    periods = HOURS[:3]
    lanes = {"a": (6.0, [0.2, 0.35]), "b": (2.0, [0.1, 0.5])}
    rows_in = [_row(p, lane, lam, samples) for p, _, _ in periods for lane, (lam, samples) in lanes.items()]
    out = _run(rows_in, _setup(list(lanes), periods), seed=13)
    horizon = out["total_hours"]
    for lane in lanes:
        rows = [row for row in out["results"] if row["queue_id"] == lane]
        # Whole-horizon busy time straight from the trace's own service events, no period split.
        starts = {e["customer_id"]: e["t"] for e in out["trace"] if e["type"] == "service_start" and e["queue_id"] == lane}
        ends = {e["customer_id"]: e["t"] for e in out["trace"] if e["type"] == "service_end" and e["queue_id"] == lane}
        whole = math.fsum(min(ends.get(c, horizon), horizon) - s for c, s in starts.items())
        assert math.fsum(row["busy_time"] for row in rows) == pytest.approx(whole, abs=1e-5)
        for row in rows:
            assert 0.0 <= row["busy_time"] <= row["duration_hours"] + 1e-12
            assert 0.0 <= row["rho_sim"] <= 1.0
            assert row["arrivals"] == row["started"] + row["censored_customers"]
            assert row["served"] <= row["started"]
        assert sum(row["censored_customers"] for row in rows) == sum(row["waiting"] for row in rows)
        assert sum(row["started"] - row["served"] for row in rows) == sum(row["in_service"] for row in rows)
        assert sum(row["arrivals"] for row in rows) == len(
            [e for e in out["trace"] if e["type"] == "arrival" and e["queue_id"] == lane])


def test_summary_wait_uses_the_started_population():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 4.0, [10.0]), _row("p1", "a", 4.0, [10.0])], _setup(["a"], periods), seed=0)
    customers = _fifo(out, "a", service=10.0)
    started = [c["start"] - c["arrival"] for c in customers if c["start"] is not None]
    summary = summarize_simulation(out["results"])
    assert summary["total_started"] == len(started) == 1
    assert summary["avg_Wq"] == pytest.approx(math.fsum(started) / len(started), abs=1e-9)
