"""D2: Current separate-lanes DES accounting at the fixed horizon (spec 2026-11-17, owner 2026-11-17).

Ported from the archived D2 test (``archive/fix-d1-replication-costs-20261117``) and extended for the PR58
break windows, per-date days and the compact result. All data here is SYNTHETIC.

The references never reuse the implementation's aggregation:

- hand-built service intervals with hand-computed busy time per period;
- a one-server FIFO recursion over the run's own arrival times only, with deterministic (or recorded)
  service times and the lane's break windows (a service may not start inside a window, so its start
  moves to the window's end; a service already under way continues), which rebuilds every start and
  end without the simulator's service events;
- closed forms for single deterministic services.
"""

from __future__ import annotations

import math

import pytest

from backend.api.workflow import _wait_and_line
from backend.queueing_engine.simulation.simulation import (
    COMPACT_ROW_FIELDS,
    _window_busy_hours,
    simulate_parallel_days_compact,
    simulate_parallel_days_with_trace,
    simulate_segments_with_trace,
    summarize_simulation,
)
from tests.helpers import create_user, csrf_header, login

HOURS = [
    ("p0", "08:00:00", "09:00:00"),
    ("p1", "09:00:00", "10:00:00"),
    ("p2", "10:00:00", "11:00:00"),
    ("p3", "11:00:00", "12:00:00"),
    ("p4", "12:00:00", "13:00:00"),
]


def _setup(lanes, periods, active=None, breaks=None, basis=None):
    segments = []
    for index, (period, start, end) in enumerate(periods):
        segment = {"id": period, "start_time": start, "end_time": end}
        if active is not None:
            segment["active_queue_ids"] = active[index]
        segments.append(segment)
    setup = {
        "queue_structure": "separate_queues",
        "queue_ids": lanes,
        "staffing_varies_by_period": active is not None,
        "separate_queue_closure_policy": "drain_existing",
        "segments": segments,
    }
    if breaks is not None:
        setup["breaks"] = breaks
    if basis is not None:
        setup["event_period_basis"] = basis
    return setup


def _row(period, lane, lam, samples, label=None):
    return {
        "segment_id": period, "time": label or period, "queue_id": lane, "queue_structure": "separate_queues",
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


def _break_windows(periods, breaks, lane):
    """A lane's break windows in run hours, from the Setup's wall-clock breaks (independent of the engine)."""
    origin = _minutes(periods[0][1])
    return sorted(((_minutes(b["scheduled_start_time"]) - origin) / 60,
                   (_minutes(b["scheduled_start_time"]) - origin + b["duration_minutes"]) / 60)
                  for b in breaks or [] if b["queue_id"] == lane)


def _fifo(trace, lane, horizon, service=None, breaks=()):
    """Rebuild one lane from its arrival times alone: FIFO, one server, fixed horizon, break windows.

    ``service`` is the deterministic service time; None uses each customer's recorded service time
    (unknown for the customer still in service at H). ``breaks`` are [lo, hi) windows in which no service
    may start. start is None for a customer still waiting at H; end is None for one in service at H.
    """
    arrivals = sorted(
        (event["t"], event["customer_id"], event["segment_id"])
        for event in trace if event["type"] == "arrival" and event["queue_id"] == lane
    )
    recorded = {
        event["customer_id"]: event["service_time_hours"]
        for event in trace if event["type"] == "service_end" and event["queue_id"] == lane
    }
    free, customers = 0.0, []
    for arrival, customer_id, period in arrivals:
        start = max(arrival, free)
        moved = True
        while moved:
            moved = False
            for lo, hi in breaks:
                if lo <= start < hi:
                    start, moved = hi, True
        if start >= horizon:
            customers.append({"period": period, "arrival": arrival, "start": None, "end": None})
            free = math.inf
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


def _assert_lane(out, lane, periods, service=None, breaks=None, rows=None, trace=None, horizon=None):
    windows = _windows(periods)
    horizon = out["total_hours"] if horizon is None else horizon
    trace = out["trace"] if trace is None else trace
    customers = _fifo(trace, lane, horizon, service, _break_windows(periods, breaks, lane))
    busy, cohort = _reference(customers, windows, horizon)
    rows = {row["segment_id"]: row for row in (out["results"] if rows is None else rows) if row["queue_id"] == lane}
    for period, lo, hi in windows:
        row, own = rows[period], cohort[period]
        assert row["busy_time"] == pytest.approx(busy[period], abs=1e-5), period
        assert row["rho_sim"] == pytest.approx(min(1.0, busy[period] / (hi - lo)), abs=1e-5), period
        assert row["arrivals"] == own["arrivals"], period
        assert row["started"] == own["started"], period
        assert row["served"] == own["completed"], period
        assert row["censored_customers"] == own["censored"], period
        assert row["censored_waiting_hours"] == pytest.approx(own["censored_hours"], abs=1e-5), period
        if own["started"]:
            assert row["Wq_sim"] == pytest.approx(math.fsum(own["waits"]) / own["started"], abs=1e-5), period
        else:
            assert row["Wq_sim"] is None, period
    return customers, busy, cohort, rows


def _assert_conservation(out, lanes, rows=None, trace=None, horizon=None):
    """Per lane: arrivals = started + censored, waiting at H = censored, busy = the trace's busy time."""
    horizon = out["total_hours"] if horizon is None else horizon
    trace = out["trace"] if trace is None else trace
    for lane in lanes:
        lane_rows = [row for row in (out["results"] if rows is None else rows) if row["queue_id"] == lane]
        starts = {e["customer_id"]: e["t"] for e in trace if e["type"] == "service_start" and e["queue_id"] == lane}
        ends = {e["customer_id"]: e["t"] for e in trace if e["type"] == "service_end" and e["queue_id"] == lane}
        whole = math.fsum(min(ends.get(c, horizon), horizon) - s for c, s in starts.items())
        assert math.fsum(row["busy_time"] for row in lane_rows) == pytest.approx(whole, abs=1e-5), lane
        for row in lane_rows:
            assert 0.0 <= row["busy_time"] <= row["duration_hours"] + 1e-12
            assert 0.0 <= row["rho_sim"] <= 1.0
            assert row["arrivals"] == row["started"] + row["censored_customers"]
            assert row["served"] <= row["started"]
            assert (row["Wq_sim"] is None) is (row["started"] == 0)
        assert sum(row["censored_customers"] for row in lane_rows) == sum(row["waiting"] for row in lane_rows)
        assert sum(row["started"] - row["served"] for row in lane_rows) == sum(row["in_service"] for row in lane_rows)
        assert sum(row["arrivals"] for row in lane_rows) == len(
            [e for e in trace if e["type"] == "arrival" and e["queue_id"] == lane])
        assert sum(row["arrivals"] for row in lane_rows) == sum(
            row["started"] + row["censored_customers"] for row in lane_rows)


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


def test_case1_deterministic_service_crossing_two_periods_is_credited_where_it_occurs():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 1.5, [0.5]), _row("p1", "a", 0.0, [0.5])], _setup(["a"], periods), seed=3)
    customers, busy, _, rows = _assert_lane(out, "a", periods, service=0.5)
    assert _crosses(customers, 1.0, 2.0)
    # p1 had no arrivals but its server was busy finishing p0's customers.
    assert rows["p1"]["arrivals"] == 0 and rows["p1"]["busy_time"] > 0.0
    assert busy["p0"] + busy["p1"] == pytest.approx(
        sum((2.0 if c["end"] is None else c["end"]) - c["start"] for c in customers if c["start"] is not None), abs=1e-9)
    _assert_conservation(out, ["a"])


def test_case2_service_crossing_three_or_more_periods_closed_form():
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
    _assert_conservation(out, ["a"])


def test_case3_service_beyond_the_horizon_and_fully_occupied_period():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 0.8, [2.5]), _row("p1", "a", 0.0, [2.5])], _setup(["a"], periods), seed=1)
    customers, _, _, rows = _assert_lane(out, "a", periods, service=2.5)
    (only,) = customers
    assert only["start"] == only["arrival"] and only["end"] is None
    assert rows["p0"]["busy_time"] == pytest.approx(1.0 - only["arrival"], abs=1e-5)
    # A period entirely occupied by a service that has not finished is fully busy (rho 1.0, owner: Unstable).
    assert rows["p1"]["rho_sim"] == pytest.approx(1.0, abs=1e-12)
    assert rows["p1"]["served"] == 0 and rows["p1"]["arrivals"] == 0
    # The started-but-unfinished customer's (zero) wait is complete and counted.
    assert rows["p0"]["started"] == 1 and rows["p0"]["served"] == 0 and rows["p0"]["Wq_sim"] == 0.0
    assert rows["p1"]["in_service"] == 1 and rows["p1"]["waiting"] == 0
    _assert_conservation(out, ["a"])


def test_case4_consecutive_periods_with_carried_backlog():
    periods = HOURS[:5]
    rates = [6.0, 1.0, 0.0, 3.0, 0.0]
    out = _run([_row(p, "a", lam, [0.2, 0.3]) for (p, _, _), lam in zip(periods, rates)], _setup(["a"], periods), seed=4)
    customers, _, _, rows = _assert_lane(out, "a", periods)
    assert sum(bool(_crosses(customers, float(b), 5.0)) for b in (1, 2, 3, 4)) >= 2
    # p2 had no arrivals but the carried backlog kept the server busy.
    assert rows["p2"]["arrivals"] == 0 and rows["p2"]["busy_time"] > 0.0 and rows["p2"]["Wq_sim"] is None
    _assert_conservation(out, ["a"])


def test_case5_break_window_with_backlog():
    """New: a 08:45-09:15 break with a backlog. Nothing starts inside the window, the service under way when
    it opens continues, the backlog is served in p1 after the window (busy time in p+1) and the time the
    customers wait through the window is part of their wait."""
    periods = HOURS[:2]
    breaks = [{"queue_id": "a", "scheduled_start_time": "08:45", "duration_minutes": 30}]
    setup = _setup(["a"], periods, breaks=breaks)
    out = _run([_row("p0", "a", 8.0, [0.125]), _row("p1", "a", 0.0, [0.125])], setup, seed=2)
    customers, busy, cohort, rows = _assert_lane(out, "a", periods, service=0.125, breaks=breaks)
    starts = [e["t"] for e in out["trace"] if e["type"] == "service_start"]
    assert starts and not [t for t in starts if 0.75 < t < 1.25 - 1e-9]  # nothing starts inside the window
    assert any(c["start"] == pytest.approx(1.25) for c in customers)  # the backlog resumes at the window's end
    assert [e["type"] for e in out["trace"] if e["type"] in {"draining_start", "break_start", "break_end"}]
    assert rows["p1"]["arrivals"] == 0 and busy["p1"] > 0.0 and rows["p1"]["busy_time"] > 0.0
    # The break time is inside the waits: some p0 customer waited across the whole window.
    assert max(cohort["p0"]["waits"]) > 0.5
    assert rows["p0"]["Wq_sim"] == pytest.approx(math.fsum(cohort["p0"]["waits"]) / rows["p0"]["started"], abs=1e-5)
    _assert_conservation(out, ["a"])


def test_case6_unequal_period_lengths_use_their_own_length():
    periods = [("q1", "08:00:00", "08:30:00"), ("q2", "08:30:00", "10:00:00")]
    rates = [8.0, 3.0]
    out = _run([_row(p, "a", lam, [0.1, 0.35]) for (p, _, _), lam in zip(periods, rates)], _setup(["a"], periods), seed=5)
    _, busy, _, rows = _assert_lane(out, "a", periods)
    for period, lo, hi in _windows(periods):
        assert rows[period]["duration_hours"] == pytest.approx(hi - lo)
        assert rows[period]["rho_sim"] == pytest.approx(min(1.0, busy[period] / (hi - lo)), abs=1e-5)
    assert rows["q1"]["duration_hours"] == pytest.approx(0.5) and rows["q2"]["duration_hours"] == pytest.approx(1.5)
    _assert_conservation(out, ["a"])


def test_different_period_durations_four_periods():
    periods = [("q1", "08:00:00", "08:15:00"), ("q2", "08:15:00", "09:00:00"),
               ("q3", "09:00:00", "10:30:00"), ("q4", "10:30:00", "11:00:00")]
    rates = [8.0, 3.0, 2.5, 0.0]
    out = _run([_row(p, "a", lam, [0.1, 0.35]) for (p, _, _), lam in zip(periods, rates)], _setup(["a"], periods), seed=5)
    _assert_lane(out, "a", periods)
    _assert_conservation(out, ["a"])


def test_case7_draining_lane_is_credited_in_the_period_it_works():
    periods = HOURS[:2]
    setup = _setup(["a", "b"], periods, active=[["a", "b"], ["a"]])
    rows_in = [_row("p0", "a", 1.0, [0.1]), _row("p0", "b", 8.0, [0.2, 0.3]), _row("p1", "a", 1.0, [0.1])]
    out = _run(rows_in, setup, seed=2)
    _, busy, _, rows = _assert_lane(out, "b", periods)
    assert rows["p1"]["active"] is False and rows["p0"]["active"] is True
    assert rows["p1"]["arrivals"] == 0 and busy["p1"] > 0.0
    _assert_lane(out, "a", periods)
    _assert_conservation(out, ["a", "b"])


def test_case8_zero_arrivals_leave_wait_undefined_not_zero():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 0.0, [0.05]), _row("p1", "a", 3.0, [0.05])], _setup(["a"], periods), seed=0)
    _, _, _, rows = _assert_lane(out, "a", periods, service=0.05)
    empty = rows["p0"]
    assert (empty["arrivals"], empty["started"], empty["censored_customers"], empty["busy_time"]) == (0, 0, 0, 0.0)
    assert empty["Wq_sim"] is None and empty["rho_sim"] == 0.0
    assert rows["p1"]["started"] > 0 and rows["p1"]["Wq_sim"] is not None
    _assert_conservation(out, ["a"])


def test_case9_arrivals_without_service_are_censored_not_zero_filled():
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
    _assert_conservation(out, ["a"])


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


def test_case10_true_zero_wait_is_zero_not_undefined():
    periods = HOURS[:1]
    out = _run([_row("p0", "a", 3.0, [0.01])], _setup(["a"], periods), seed=1)
    customers, _, _, rows = _assert_lane(out, "a", periods, service=0.01)
    assert len(customers) >= 2 and all(c["start"] == c["arrival"] for c in customers)
    assert rows["p0"]["Wq_sim"] == 0.0 and rows["p0"]["started"] == len(customers)


def test_multiple_independent_lanes_with_breaks():
    periods = HOURS[:3]
    lanes = {"a": (5.0, [0.15, 0.25, 0.4]), "b": (2.0, [0.05, 0.1]), "c": (1.2, [0.6, 0.9])}
    breaks = [{"queue_id": "a", "scheduled_start_time": "08:40", "duration_minutes": 30},
              {"queue_id": "c", "scheduled_start_time": "09:30", "duration_minutes": 15}]
    rows_in = [_row(p, lane, lam, samples) for p, _, _ in periods for lane, (lam, samples) in lanes.items()]
    for seed in (7, 8, 9):
        out = _run(rows_in, _setup(list(lanes), periods, breaks=breaks), seed=seed)
        for lane in lanes:
            _assert_lane(out, lane, periods, breaks=breaks)
        _assert_conservation(out, list(lanes))


DATE_PERIODS = HOURS[:2]
DATE_BREAKS = [{"queue_id": "a", "scheduled_start_time": "08:30", "duration_minutes": 20}]
DATE_SETUP = _setup(["a", "b"], DATE_PERIODS, breaks=DATE_BREAKS, basis="per_date")
DATE_DAYS = [
    (date, [_row(p, lane, lam, samples, f"{date} {p} UTC") for p, _, _ in DATE_PERIODS
            for lane, lam, samples in (("a", rate, [0.2, 0.3]), ("b", 2.0, [0.1, 0.6]))])
    for date, rate in (("2026-08-03", 5.0), ("2026-08-04", 7.0))
]


def test_case11_per_date_two_dates_and_compact_rows_carry_started():
    full = simulate_parallel_days_with_trace(DATE_DAYS, DATE_SETUP, 1.0, [11, 12], 100_000)
    assert not full["truncated"]
    for date, _ in DATE_DAYS:
        rows = [row for row in full["results"] if row["date"] == date]
        trace = [event for event in full["trace"] if event["date"] == date]
        day = next(day for day in full["days"] if day["date"] == date)
        horizon = day["day_hours"]
        for lane in ("a", "b"):
            _assert_lane(full, lane, DATE_PERIODS, breaks=DATE_BREAKS, rows=rows, trace=trace, horizon=horizon)
        _assert_conservation(full, ["a", "b"], rows=rows, trace=trace, horizon=horizon)
        assert all(isinstance(row["started"], int) for row in rows)
    compact = simulate_parallel_days_compact(DATE_DAYS, DATE_SETUP, 1.0, [11, 12], 100_000)
    assert "started" in COMPACT_ROW_FIELDS and "censored_customers" in COMPACT_ROW_FIELDS
    assert compact["results"] == [{field: row.get(field) for field in COMPACT_ROW_FIELDS} for row in full["results"]]
    assert all(isinstance(row["started"], int) and isinstance(row["censored_customers"], int)
               for row in compact["results"])


def test_summary_wait_uses_the_started_population():
    periods = HOURS[:2]
    out = _run([_row("p0", "a", 4.0, [10.0]), _row("p1", "a", 4.0, [10.0])], _setup(["a"], periods), seed=0)
    customers = _fifo(out["trace"], "a", out["total_hours"], service=10.0)
    started = [c["start"] - c["arrival"] for c in customers if c["start"] is not None]
    summary = summarize_simulation(out["results"])
    assert summary["total_started"] == len(started) == 1
    assert summary["avg_Wq"] == pytest.approx(math.fsum(started) / len(started), abs=1e-9)


def test_summary_with_nobody_started_is_undefined_not_an_error():
    periods = HOURS[:1]
    out = _run([_row("p0", "a", 0.0, [0.1])], _setup(["a"], periods), seed=0)
    summary = summarize_simulation(out["results"])
    assert summary["total_started"] == 0 and summary["avg_Wq"] is None


def test_wait_and_line_weights_current_rows_by_started_and_others_by_served():
    # Hand-built rows: started 4 at 0.1 h, started 2 served 0 at 0.4 h, started 0 (None) is left out.
    current = [{"started": 4, "served": 3, "Wq_sim": 0.1, "max_queue": 2},
               {"started": 2, "served": 0, "Wq_sim": 0.4, "max_queue": 5},
               {"started": 0, "served": 0, "Wq_sim": None, "max_queue": 0}]
    assert _wait_and_line(current) == (pytest.approx((4 * 0.1 + 2 * 0.4) / 6), 5)
    # Rows without ``started`` (selected plan, stored earlier) keep the served weighting.
    plan = [{"served": 3, "Wq_sim": 0.1, "max_queue": 1}, {"served": 1, "Wq_sim": 0.5, "max_queue": 3}]
    assert _wait_and_line(plan) == (pytest.approx((3 * 0.1 + 0.5) / 4), 3)


def test_public_des_routes_return_null_wait_where_nobody_started(db_engine, client):
    """OD-D2-1 (owner 2026-11-17): POST /simulation/des and /simulation/des/trace return Wq_sim null too."""
    create_user(db_engine, "d2-public@example.com", "pw")
    login(client, "d2-public@example.com", "pw")
    headers = csrf_header(client)
    periods = HOURS[:2]
    setup = _setup(["a"], periods)
    rows_in = [_row("p0", "a", 0.0, [0.05]), _row("p1", "a", 3.0, [0.05])]
    des = client.post("/simulation/des", headers=headers, json={"segments": rows_in, "sim_hours": 1, "seed": 0,
                                                                 "queue_setup": setup})
    trace = client.post("/simulation/des/trace", headers=headers, json={
        "segments": rows_in, "trace_hours": 1, "max_events": 1000, "seed": 0, "queue_setup": setup})
    assert des.status_code == 200 and trace.status_code == 200, (des.text, trace.text)
    for body in (des.json(), trace.json()):
        empty = next(row for row in body["results"] if row["segment_id"] == "p0")
        assert empty["started"] == 0 and empty["Wq_sim"] is None
        assert next(row for row in body["results"] if row["segment_id"] == "p1")["Wq_sim"] is not None


def test_compact_and_full_rows_of_one_run_give_the_same_summary_wait():
    """K-D2-1: compact rows keep no wait_sum; the summary uses Wq_sim * started for them, never zero."""
    full = simulate_parallel_days_with_trace(DATE_DAYS, DATE_SETUP, 1.0, [11, 12], 100_000)
    compact = simulate_parallel_days_compact(DATE_DAYS, DATE_SETUP, 1.0, [11, 12], 100_000)
    assert all("wait_sum" not in row for row in compact["results"])
    from_full = summarize_simulation(full["results"])["avg_Wq"]
    from_compact = summarize_simulation(compact["results"])["avg_Wq"]
    assert from_full is not None and from_full > 0.0
    assert from_compact == pytest.approx(from_full, abs=1e-9)


def test_compact_summary_with_nobody_started_is_undefined():
    days = [(date, [{**row, "lambda": 0.0} for row in records]) for date, records in DATE_DAYS]
    compact = simulate_parallel_days_compact(days, DATE_SETUP, 1.0, [11, 12], 100_000)
    assert compact["results"] and all(row["started"] == 0 for row in compact["results"])
    summary = summarize_simulation(compact["results"])
    assert summary["total_started"] == 0 and summary["avg_Wq"] is None


def test_summary_wait_is_unknown_when_a_started_row_has_no_wait():
    rows = [{"queue_structure": "separate", "queue_id": "a", "started": 2, "served": 2, "Wq_sim": None},
            {"queue_structure": "separate", "queue_id": "a", "started": 1, "served": 1, "Wq_sim": 0.2}]
    assert summarize_simulation(rows)["avg_Wq"] is None
