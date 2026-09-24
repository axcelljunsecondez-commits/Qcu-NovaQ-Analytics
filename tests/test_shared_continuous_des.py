"""Phase 3 continuous shared-queue DES: exact, identity, statistical, and reproducibility checks.

Deterministic cases use prescribed arrivals and unit work with μ = 1 (so work = hours) and
binary-exact times, so every expected value below is computed by hand. Statistical checks
compare replication means with independent references within 4 standard errors.
"""

from __future__ import annotations

import logging
import math

import pytest

from backend.queueing_engine.services.shared_capacity import CapacityConfig, optimize_shared_capacity
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    timeline_from_aggregate_rows,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    simulate_prescribed,
    simulate_shared_day,
    staffing_from_capacity_result,
)
from tests.test_shared_segments import NOVAMART_AVERAGE_ROWS, erlang_reference


def hourly(*servers: int, lam: float = 1.0, mu: float = 1.0) -> tuple[OperatingHorizon, list, list]:
    """One demand period over the horizon and one staffing segment per hour."""
    hours = len(servers)
    horizon = OperatingHorizon(0, 60 * hours)
    periods = [DemandPeriod("d", 0, 60 * hours, lam, mu)]
    segments = [StaffingSegment(f"h{i}", 60 * i, 60 * (i + 1), c) for i, c in enumerate(servers)]
    return horizon, periods, segments


def by_id(result: dict) -> dict[int, dict]:
    return {row["customer_id"]: row for row in result["customers"]}


def assert_sample_path_identities(result: dict) -> None:
    """∫queue dt = Σ time spent waiting inside the horizon; busy hours = Σ service time inside it."""
    end = result["horizon_end"]["hours"]
    waiting = math.fsum(
        (row["service_start_hours"] if row["service_start_hours"] is not None else end) - row["arrival_hours"]
        for row in result["customers"]
    )
    serving = math.fsum(
        min(row["service_end_hours"], end) - row["service_start_hours"]
        for row in result["customers"] if row["service_start_hours"] is not None
    )
    totals = result["totals"]
    assert totals["queue_customer_hours"] == pytest.approx(waiting, rel=1e-9, abs=1e-12)
    assert totals["busy_server_hours"] == pytest.approx(serving, rel=1e-9, abs=1e-12)


def assert_conservation_and_identity(result: dict) -> None:
    totals = result["totals"]
    assert totals["customer_conservation"] is True
    assert totals["arrivals"] == totals["departed"] + totals["waiting_at_end"] + totals["in_service_at_end"]
    ids = [row["customer_id"] for row in result["customers"]]
    assert ids == list(range(1, len(ids) + 1))
    arrival_events = [event["customer_id"] for event in result["trace"] if event["type"] == "arrival"]
    assert sorted(arrival_events) == ids  # one arrival event per customer, never a replacement
    starts = [row for row in result["customers"] if row["service_start_hours"] is not None]
    assert all(row["wait_hours"] >= 0 for row in starts)
    # First come, first served: service starts follow arrival order.
    start_times = [row["service_start_hours"] for row in sorted(starts, key=lambda row: row["customer_id"])]
    assert start_times == sorted(start_times)
    # Nobody who started service is still counted as waiting.
    assert all(row["status"] != "waiting_at_end" for row in starts)


# ── Exact deterministic cases ───────────────────────────────────────────────


def test_constant_capacity_fcfs_waits_are_exact():
    result = simulate_prescribed(*hourly(1), [(0.125, 0.25), (0.1875, 0.0625), (0.25, 0.0625)])
    customers = by_id(result)
    assert [customers[i]["wait_hours"] for i in (1, 2, 3)] == [0.0, 0.1875, 0.1875]
    assert [customers[i]["service_end_hours"] for i in (1, 2, 3)] == [0.375, 0.4375, 0.5]
    assert result["totals"]["queue_customer_hours"] == 0.375
    assert result["segments"][0]["time_average_queue"] == 0.375
    assert result["totals"]["mean_wait_hours"] == pytest.approx(0.125)
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_capacity_increase_serves_the_backlog_at_the_boundary():
    # c = 1 then 2 at 1.0 h. Customer 2 waits from 0.25 to the increase, then uses server 2.
    result = simulate_prescribed(*hourly(1, 2), [(0.125, 1.5), (0.25, 0.125)])
    second = by_id(result)[2]
    assert second["service_start_hours"] == 1.0
    assert second["server_id"] == 2
    assert second["wait_hours"] == 0.75
    assert second["arrival_segment_id"] == "h0"
    opened = [t for t in result["capacity_transitions"] if t["kind"] == "open"]
    assert [(t["t"], t["server_id"]) for t in opened] == [(0.0, 1), (1.0, 2)]
    assert result["segments"][0]["time_average_queue"] == 0.75
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_capacity_decrease_drains_a_busy_server_without_interrupting_service():
    # c = 2 then 1 at 1.0 h; both servers busy, so server 2 (highest number) drains.
    result = simulate_prescribed(*hourly(2, 1), [(0.125, 1.25), (0.25, 1.0), (1.0625, 0.125)])
    customers = by_id(result)
    assert customers[2]["service_end_hours"] == 1.25  # finished, not cut at 1.0
    assert customers[2]["status"] == "departed"
    # Customer 3 must not go to draining server 2 when it frees at 1.25; it waits for server 1.
    assert customers[3]["server_id"] == 1
    assert customers[3]["service_start_hours"] == 1.375
    assert customers[3]["wait_hours"] == 0.3125
    assert result["drains"] == [
        {"server_id": 2, "customer_id": 2, "designated_at": 1.0, "released_at": 1.25, "segment_id": "h1"}
    ]
    later = result["segments"][1]
    assert later["scheduled_server_hours"] == 1.0
    assert later["present_server_hours"] == 1.25
    assert later["server_hours_above_schedule"] == 0.25
    assert later["busy_server_hours"] == 0.75
    assert later["utilization_of_present"] == 0.6
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_capacity_decrease_closes_idle_servers_first():
    result = simulate_prescribed(*hourly(2, 1), [(0.125, 1.5), (0.25, 0.125), (1.125, 0.125)])
    assert result["drains"] == []
    closes = [(t["t"], t["server_id"]) for t in result["capacity_transitions"] if t["kind"] == "close"]
    assert closes == [(1.0, 2)]
    assert by_id(result)[3]["service_start_hours"] == 1.625  # server 1 keeps working and takes it
    assert result["segments"][1]["server_hours_above_schedule"] == 0.0
    assert_conservation_and_identity(result)


def test_zero_capacity_segment_keeps_backlog_and_finishes_started_service():
    # c = 1, 0, 1 by 30 minutes. Customer 1 is in service across the closing boundary.
    horizon = OperatingHorizon(0, 90)
    periods = [DemandPeriod("d", 0, 90, 1.0, 1.0)]
    segments = [StaffingSegment("a", 0, 30, 1), StaffingSegment("b", 30, 60, 0), StaffingSegment("c", 60, 90, 1)]
    result = simulate_prescribed(horizon, periods, segments, [(0.375, 0.25), (0.5625, 0.125)])
    customers = by_id(result)
    assert customers[1]["service_end_hours"] == 0.625
    assert result["drains"][0]["designated_at"] == 0.5 and result["drains"][0]["released_at"] == 0.625
    assert customers[2]["service_start_hours"] == 1.0  # waits through the closed segment
    assert customers[2]["wait_hours"] == 0.4375
    closed = result["segments"][1]
    assert closed["scheduled_server_hours"] == 0.0
    assert closed["busy_server_hours"] == 0.125  # the drain, reported as time above schedule
    assert closed["server_hours_above_schedule"] == 0.125
    assert closed["time_average_queue"] == pytest.approx((1.0 - 0.5625) / 0.5)
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_zero_demand_period_still_serves_backlog():
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("busy", 0, 60, 1.0, 1.0), DemandPeriod("quiet", 60, 120, 0.0, 1.0)]
    segments = [StaffingSegment("busy", 0, 60, 1), StaffingSegment("quiet", 60, 120, 1)]
    result = simulate_prescribed(horizon, periods, segments, [(0.5, 0.625), (0.625, 0.25)])
    quiet = result["segments"][1]
    assert quiet["arrivals"] == 0
    assert quiet["time_average_queue"] == 0.125  # customer 2 waits 1.0 to 1.125 inside it
    assert by_id(result)[2]["service_start_hours"] == 1.125
    assert_sample_path_identities(result)
    with pytest.raises(SharedSegmentError, match="arrival rate is 0"):
        simulate_prescribed(horizon, periods, segments, [(1.5, 0.25)])


def test_completion_at_a_decrease_boundary_is_processed_first():
    # Server 1 finishes exactly at 1.0; the decrease then closes the now-idle server, no drain.
    result = simulate_prescribed(*hourly(2, 1), [(0.25, 0.75), (0.5, 1.0)])
    assert result["drains"] == []
    assert [(t["t"], t["kind"], t["server_id"]) for t in result["capacity_transitions"] if t["t"] == 1.0] == [
        (1.0, "close", 1)
    ]
    assert by_id(result)[2]["service_end_hours"] == 1.5


def test_arrival_at_an_increase_boundary_sees_the_new_capacity():
    result = simulate_prescribed(*hourly(1, 2), [(0.25, 1.0), (1.0, 0.25)])
    second = by_id(result)[2]
    assert (second["service_start_hours"], second["server_id"], second["wait_hours"]) == (1.0, 2, 0.0)
    at_boundary = [(event["type"], event["segment_id"]) for event in result["trace"] if event["t"] == 1.0]
    assert at_boundary.index(("capacity_change", "h1")) < at_boundary.index(("arrival", "h1"))


def test_arrival_at_a_decrease_boundary_sees_the_reduced_capacity():
    # c = 2 then 1 at 1.0 h. Server 2 is idle at 1.0, so the decrease closes it before the
    # arrival at 1.0 is handled; the arrival waits for server 1 instead of taking server 2.
    result = simulate_prescribed(*hourly(2, 1), [(0.25, 1.0), (1.0, 0.25)])
    second = by_id(result)[2]
    assert (second["service_start_hours"], second["server_id"], second["wait_hours"]) == (1.25, 1, 0.25)
    assert result["drains"] == []


def test_started_service_keeps_its_duration_when_mu_changes():
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("slow", 0, 60, 1.0, 1.0), DemandPeriod("fast", 60, 120, 1.0, 2.0)]
    segments = [StaffingSegment("slow", 0, 60, 2), StaffingSegment("fast", 60, 120, 2)]
    result = simulate_prescribed(horizon, periods, segments, [(0.75, 0.5), (1.25, 0.5)])
    customers = by_id(result)
    assert customers[1]["service_end_hours"] == 1.25  # 0.5 work / μ 1, started before the change
    assert customers[2]["service_end_hours"] == 1.5  # 0.5 work / μ 2, started after it


def test_reactivating_a_draining_server_before_opening_a_new_one():
    # c = 2, 1, 2: server 2 drains at 1.0 and is reactivated at 2.0 while still busy.
    result = simulate_prescribed(*hourly(2, 1, 2), [(0.125, 2.5), (0.25, 2.5)])
    kinds = [(t["t"], t["kind"], t["server_id"]) for t in result["capacity_transitions"]]
    assert (1.0, "drain_start", 2) in kinds and (2.0, "reactivate", 2) in kinds
    assert result["totals"]["servers_used"] == 2
    assert result["drains"][0]["reactivated_at"] == 2.0 and result["drains"][0]["released_at"] is None


def test_unfinished_customers_are_reported_at_the_horizon_end():
    result = simulate_prescribed(*hourly(1), [(0.5, 0.75), (0.75, 0.125)])
    end = result["horizon_end"]
    assert end["in_service_customer_ids"] == [1]
    assert end["waiting_customer_ids"] == [2]
    assert end["closing_policy"].startswith("UNRESOLVED")
    second = by_id(result)[2]
    assert second["wait_hours"] is None and second["elapsed_wait_at_end_hours"] == 0.25
    assert result["totals"]["mean_wait_hours"] == 0.0  # only customer 1 started service
    assert all(event["t"] < 1.0 for event in result["trace"])
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


# ── Seeded runs: conservation, identity, identities over many transitions ───


@pytest.mark.parametrize("seed", range(20))
def test_multi_transition_runs_conserve_customers(seed):
    horizon = OperatingHorizon(480, 780)
    periods = [
        DemandPeriod("08", 480, 540, 30.0, 12.0),
        DemandPeriod("09", 540, 600, 0.0, 12.0),
        DemandPeriod("10", 600, 660, 45.0, 15.0),
        DemandPeriod("11", 660, 780, 20.0, 10.0),
    ]
    segments = [
        StaffingSegment("a", 480, 510, 3), StaffingSegment("b", 510, 540, 0),
        StaffingSegment("c", 540, 600, 1), StaffingSegment("d", 600, 615, 4),
        StaffingSegment("e", 615, 660, 2), StaffingSegment("f", 660, 780, 3),
    ]
    result = simulate_shared_day(horizon, periods, segments, seed=seed)
    assert_conservation_and_identity(result)
    assert_sample_path_identities(result)
    assert result["segments"][2]["arrivals"] == 0  # 09:00-10:00 has no demand
    for row in result["segments"]:
        assert row["server_hours_above_schedule"] >= -1e-12


# ── Statistical checks against independent references ──────────────────────


def replication_stats(values: list[float]) -> tuple[float, float]:
    mean = math.fsum(values) / len(values)
    variance = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, math.sqrt(variance / len(values))


def test_constant_capacity_matches_erlang_c_within_statistical_error():
    # λ = 40 per hour, μ = 20 per hour per server, c = 3: Lq = 8/9, P(wait) = 4/9, Wq = 1/45 h.
    reference = erlang_reference(40.0, 20.0, 3)
    horizon, periods, segments = OperatingHorizon(0, 1440), [DemandPeriod("d", 0, 1440, 40.0, 20.0)], [
        StaffingSegment("s", 0, 1440, 3)
    ]
    lq, wait_share, wq = [], [], []
    for seed in range(100):
        totals = simulate_shared_day(horizon, periods, segments, seed=seed)["totals"]
        lq.append(totals["time_average_queue"])
        wait_share.append(totals["waited_count"] / totals["service_starts"])
        wq.append(totals["mean_wait_hours"])
    for values, expected in ((lq, reference["Lq"]), (wait_share, reference["P_wait"]), (wq, reference["Wq"])):
        mean, standard_error = replication_stats(values)
        assert abs(mean - expected) <= 4 * standard_error, (mean, expected, standard_error)


def test_arrival_counts_are_poisson_per_period():
    horizon = OperatingHorizon(0, 180)
    periods = [DemandPeriod("a", 0, 60, 30.0, 10.0), DemandPeriod("b", 60, 120, 0.0, 10.0),
               DemandPeriod("c", 120, 180, 12.0, 10.0)]
    segments = [StaffingSegment("a", 0, 60, 10), StaffingSegment("b", 60, 120, 10), StaffingSegment("c", 120, 180, 10)]
    counts: dict[str, list[float]] = {"a": [], "b": [], "c": []}
    for seed in range(300):
        for row in simulate_shared_day(horizon, periods, segments, seed=seed)["segments"]:
            counts[row["segment_id"]].append(float(row["arrivals"]))
    assert set(counts["b"]) == {0.0}
    for key, rate in (("a", 30.0), ("c", 12.0)):
        mean, standard_error = replication_stats(counts[key])
        assert abs(mean - rate) <= 4 * standard_error
        variance = math.fsum((value - mean) ** 2 for value in counts[key]) / (len(counts[key]) - 1)
        # Poisson counts have variance = mean; the dispersion index has SE ≈ sqrt(2/(n-1)).
        assert abs(variance / mean - 1.0) <= 4 * math.sqrt(2 / (len(counts[key]) - 1))


def test_service_times_are_exponential_with_the_starting_period_rate():
    # Ample servers, so service starts at arrival and the starting period is the arrival period.
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("slow", 0, 60, 60.0, 10.0), DemandPeriod("fast", 60, 120, 60.0, 40.0)]
    segments = [StaffingSegment("slow", 0, 60, 60), StaffingSegment("fast", 60, 120, 60)]
    durations: dict[str, list[float]] = {"slow": [], "fast": []}
    for seed in range(40):
        for row in simulate_shared_day(horizon, periods, segments, seed=seed)["customers"]:
            # Every started service has its full drawn end time, even past the horizon, so
            # in-service customers are included and long services are not selected out.
            if row["service_start_hours"] is not None:
                assert row["wait_hours"] == 0.0
                key = "slow" if row["service_start_hours"] < 1.0 else "fast"
                durations[key].append(row["service_end_hours"] - row["service_start_hours"])
    for key, mu in (("slow", 10.0), ("fast", 40.0)):
        values = durations[key]
        mean = math.fsum(values) / len(values)
        assert abs(mean - 1 / mu) <= 4 * (1 / mu) / math.sqrt(len(values))
        share_above = sum(1 for value in values if value > 1 / mu) / len(values)
        assert abs(share_above - math.exp(-1)) <= 4 * math.sqrt(math.exp(-1) * (1 - math.exp(-1)) / len(values))


# ── Reproducibility ─────────────────────────────────────────────────────────


def test_seeded_runs_are_reproducible_and_seeds_differ():
    args = hourly(2, 1, 3, lam=25.0, mu=12.0)
    first = simulate_shared_day(*args, seed=11)
    again = simulate_shared_day(*args, seed=11)
    other = simulate_shared_day(*args, seed=12)
    assert first == again
    assert first["customers"] != other["customers"]


def test_unseeded_run_records_entropy_that_reproduces_it():
    args = hourly(2, 2, lam=20.0, mu=12.0)
    free = simulate_shared_day(*args, seed=None)
    entropy = free["provenance"]["seed_entropy"]
    assert isinstance(entropy, int)
    replay = simulate_shared_day(*args, seed=entropy)
    assert replay["customers"] == free["customers"]


# ── Integration with Phase 2, validation, isolation ─────────────────────────


def test_simulates_a_complete_phase_two_plan():
    periods, current = timeline_from_aggregate_rows(NOVAMART_AVERAGE_ROWS)
    horizon = OperatingHorizon(300, 1080)
    logging.disable(logging.CRITICAL)
    try:
        plan = optimize_shared_capacity(horizon, periods, current, CapacityConfig(94.375, 100.0, 0.70, 1, 24))
    finally:
        logging.disable(logging.NOTSET)
    staffing = staffing_from_capacity_result(plan)
    assert [segment.servers for segment in staffing] == [2, 3, 3, 3, 3, 4, 3, 4, 4, 3, 3, 2, 2]
    result = simulate_shared_day(horizon, periods, staffing, seed=3)
    assert_conservation_and_identity(result)
    assert result["totals"]["scheduled_server_hours"] == pytest.approx(39.0)


def test_incomplete_phase_two_plan_is_refused():
    horizon = OperatingHorizon(0, 60)
    periods = [DemandPeriod("p", 0, 60, 8.2143, 4.3068)]
    plan = optimize_shared_capacity(horizon, periods, [StaffingSegment("p", 0, 60, 2)], CapacityConfig(1.0, 1.0, 0.7, 1, 2))
    with pytest.raises(SharedSegmentError, match="no feasible server count in: p"):
        staffing_from_capacity_result(plan)


@pytest.mark.parametrize(
    ("arrivals", "message"),
    [
        ([(1.0, 0.5)], "lie in the horizon"),
        ([(-0.1, 0.5)], "lie in the horizon"),
        ([(0.5, 0.5), (0.25, 0.5)], "earlier than the arrival before it"),
        ([(0.5, 0.0)], "work must be a finite number above 0"),
        ([(0.5, math.nan)], "work must be a finite number above 0"),
        ([(0.5,)], "must be an \\(hour, work\\) pair"),
    ],
)
def test_invalid_prescribed_arrivals(arrivals, message):
    with pytest.raises(SharedSegmentError, match=message):
        simulate_prescribed(*hourly(1), arrivals)


@pytest.mark.parametrize("seed", [-1, 1.5, True])
def test_invalid_seed(seed):
    with pytest.raises(SharedSegmentError, match="seed must be a whole number"):
        simulate_shared_day(*hourly(1), seed=seed)


def test_trace_cap_limits_only_the_trace():
    capped = simulate_shared_day(*hourly(2, lam=30.0, mu=12.0), seed=5, max_trace_events=10)
    full = simulate_shared_day(*hourly(2, lam=30.0, mu=12.0), seed=5)
    assert len(capped["trace"]) == 10 and capped["trace_truncated"] is True
    assert full["trace_truncated"] is False
    assert capped["totals"] == full["totals"]
