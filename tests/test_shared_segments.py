"""Phase 1 shared-queue segment foundation: independent math and boundary checks.

References are computed here with an Erlang-B recursion that shares no code with
``queue_models.mmc``, plus exact textbook cases.
"""

from __future__ import annotations

import math
import pathlib

import pytest

from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    evaluate_shared_segments,
    parse_clock,
    timeline_from_aggregate_rows,
    validate_timeline,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# NovaMart 14-day average (Daily data mmc/Avg_total_data_of_14_days.csv), copied verbatim.
NOVAMART_AVERAGE_ROWS = [
    {"time": "05:00-06:00", "lambda": 6.0000, "mu": 4.7731, "c": 3},
    {"time": "06:00-07:00", "lambda": 6.9286, "mu": 5.0008, "c": 5},
    {"time": "07:00-08:00", "lambda": 7.8571, "mu": 4.9358, "c": 5},
    {"time": "08:00-09:00", "lambda": 8.2857, "mu": 4.9106, "c": 5},
    {"time": "09:00-10:00", "lambda": 8.9286, "mu": 4.9145, "c": 5},
    {"time": "10:00-11:00", "lambda": 12.5714, "mu": 4.8669, "c": 5},
    {"time": "11:00-12:00", "lambda": 8.2143, "mu": 4.3068, "c": 2},
    {"time": "12:00-13:00", "lambda": 9.2143, "mu": 4.3428, "c": 3},
    {"time": "13:00-14:00", "lambda": 12.7857, "mu": 5.3242, "c": 5},
    {"time": "14:00-15:00", "lambda": 8.9286, "mu": 5.2016, "c": 5},
    {"time": "15:00-16:00", "lambda": 6.5000, "mu": 4.3528, "c": 5},
    {"time": "16:00-17:00", "lambda": 6.2857, "mu": 5.0884, "c": 5},
    {"time": "17:00-18:00", "lambda": 5.0000, "mu": 4.3443, "c": 2},
]


def erlang_reference(lambda_: float, mu: float, c: int) -> dict[str, float]:
    """Independent M/M/c reference through the Erlang-B recursion."""
    offered = lambda_ / mu
    blocking = 1.0
    for k in range(1, c + 1):
        blocking = offered * blocking / (k + offered * blocking)
    wait_probability = c * blocking / (c - offered * (1.0 - blocking))
    lq = wait_probability * offered / (c - offered)
    return {"rho": offered / c, "P_wait": wait_probability, "Lq": lq, "Wq": lq / lambda_}


def one_period(start: int, end: int, lambda_: float, mu: float, servers: int, ident: str = "p1"):
    horizon = OperatingHorizon(start, end)
    return horizon, [DemandPeriod(ident, start, end, lambda_, mu)], [StaffingSegment(ident, start, end, servers)]


def problems_of(error: pytest.ExceptionInfo[SharedSegmentError]) -> str:
    return " | ".join(error.value.problems)


# ── Mathematical references ─────────────────────────────────────────────────


def test_exact_erlang_c_textbook_case():
    # λ = 2 per hour, μ = 1 per hour per server, c = 3 (A = λ/μ = 2 Erlangs, ρ = 2/3):
    # P(wait) = 4/9 and Lq = 8/9 depend only on A and c; Wq = Lq/λ = 4/9 h needs λ = 2.
    result = evaluate_shared_segments(*one_period(540, 600, 2.0, 1.0, 3))
    row = result["segments"][0]
    assert row["selected_model"] == "M/M/c"
    assert row["status"] == "STABLE"
    assert row["rho"] == pytest.approx(2 / 3, abs=1e-15)
    assert row["Lq"] == pytest.approx(8 / 9, abs=1e-12)
    assert row["Wq_hours"] == pytest.approx(4 / 9, abs=1e-12)
    assert row["expected_waiting_customer_hours"] == pytest.approx(8 / 9, abs=1e-12)
    assert erlang_reference(2.0, 1.0, 3)["P_wait"] == pytest.approx(4 / 9, abs=1e-12)


def test_exact_mm1_case_uses_m_m_1():
    # λ = 3 per hour, μ = 4 per hour, c = 1: Lq = ρ²/(1-ρ) = 2.25, Wq = λ/(μ(μ-λ)) = 0.75 h.
    row = evaluate_shared_segments(*one_period(0, 60, 3.0, 4.0, 1))["segments"][0]
    assert row["selected_model"] == "M/M/1"
    assert row["Lq"] == pytest.approx(2.25, abs=1e-12)
    assert row["Wq_hours"] == pytest.approx(0.75, abs=1e-12)


def test_novamart_average_matches_independent_erlang_reference():
    periods, segments = timeline_from_aggregate_rows(NOVAMART_AVERAGE_ROWS)
    result = evaluate_shared_segments(OperatingHorizon(300, 1080), periods, segments)
    assert [row["segment_id"] for row in result["segments"]] == [row["time"] for row in NOVAMART_AVERAGE_ROWS]
    for source, row in zip(NOVAMART_AVERAGE_ROWS, result["segments"]):
        reference = erlang_reference(source["lambda"], source["mu"], source["c"])
        assert row["status"] == "STABLE"
        assert row["rho"] == pytest.approx(reference["rho"], rel=1e-12)
        assert row["Lq"] == pytest.approx(reference["Lq"], rel=1e-9)
        assert row["Wq_hours"] == pytest.approx(reference["Wq"], rel=1e-9)
    bottleneck = result["segments"][6]
    assert bottleneck["segment_id"] == "11:00-12:00"
    assert bottleneck["rho"] == pytest.approx(0.953643, abs=5e-7)
    assert bottleneck["Wq_hours"] * 60 == pytest.approx(139.897, abs=1e-3)
    totals = result["totals"]
    assert totals["duration_hours"] == pytest.approx(13.0)
    assert totals["server_hours"] == pytest.approx(55.0)
    assert totals["expected_arrivals"] == pytest.approx(math.fsum(r["lambda"] for r in NOVAMART_AVERAGE_ROWS))


def test_waiting_customer_hours_follow_littles_law_and_duration():
    # λ·Wq·T must equal Lq·T for every stable row; 30 minutes counts as half an hour.
    horizon = OperatingHorizon(660, 720)
    periods = [DemandPeriod("11:00-12:00", 660, 720, 8.2143, 4.3068)]
    segments = [StaffingSegment("a", 660, 690, 3), StaffingSegment("b", 690, 720, 4)]
    result = evaluate_shared_segments(horizon, periods, segments)
    for row in result["segments"]:
        assert row["duration_hours"] == pytest.approx(0.5)
        assert row["expected_waiting_customer_hours"] == pytest.approx(row["Lq"] * 0.5, rel=1e-12)
        assert row["offered_work_hours"] == pytest.approx(8.2143 / 4.3068 * 0.5, rel=1e-12)
    assert result["totals"]["server_hours"] == pytest.approx(3.5)


# ── Sub-hour staffing never creates sub-hour demand ─────────────────────────


def test_quarter_hour_staffing_inherits_the_hourly_rates():
    horizon = OperatingHorizon(660, 720)
    periods = [DemandPeriod("11:00-12:00", 660, 720, 8.2143, 4.3068)]
    segments = [StaffingSegment(f"q{i}", 660 + 15 * i, 675 + 15 * i, 2 + i % 2) for i in range(4)]
    result = evaluate_shared_segments(horizon, periods, segments)
    for row in result["segments"]:
        assert row["arrival_rate_per_hour"] == 8.2143
        assert row["service_rate_per_hour"] == 4.3068
        assert row["demand_period_id"] == "11:00-12:00"
        assert row["demand_resolution_minutes"] == 60
        assert row["demand_source"] == "inherited_from_demand_period"
        assert row["duration_minutes"] == 15
        reference = erlang_reference(8.2143, 4.3068, row["servers"])
        assert row["Lq"] == pytest.approx(reference["Lq"], rel=1e-9)
    # The quarters add back to exactly one hour of the supplied demand.
    assert result["totals"]["expected_arrivals"] == pytest.approx(8.2143, rel=1e-12)
    assert result["totals"]["duration_hours"] == pytest.approx(1.0)


def test_segment_matching_its_period_is_not_labelled_inherited():
    row = evaluate_shared_segments(*one_period(0, 60, 3.0, 4.0, 1))["segments"][0]
    assert row["demand_source"] == "same_as_demand_period"


def test_staffing_segment_crossing_a_demand_boundary_is_rejected():
    horizon = OperatingHorizon(600, 720)
    periods = [DemandPeriod("10", 600, 660, 12.5714, 4.8669), DemandPeriod("11", 660, 720, 8.2143, 4.3068)]
    segments = [StaffingSegment("a", 600, 630, 5), StaffingSegment("b", 630, 690, 4), StaffingSegment("c", 690, 720, 3)]
    with pytest.raises(SharedSegmentError) as error:
        validate_timeline(horizon, periods, segments)
    assert "crosses a demand-period boundary" in problems_of(error)
    assert "Staffing segment b" in problems_of(error)


# ── Zero demand, zero capacity, instability ─────────────────────────────────


def test_zero_demand_is_explicit():
    row = evaluate_shared_segments(*one_period(0, 60, 0.0, 4.0, 2))["segments"][0]
    assert row["status"] == "ZERO_DEMAND"
    assert (row["rho"], row["Lq"], row["Wq_hours"]) == (0.0, 0.0, 0.0)
    assert row["expected_arrivals"] == 0.0
    assert row["expected_waiting_customer_hours"] == 0.0
    assert row["server_hours"] == 2.0


def test_no_servers_with_demand_has_no_steady_state():
    result = evaluate_shared_segments(*one_period(0, 60, 5.0, 4.0, 0))
    row = result["segments"][0]
    assert row["status"] == "NO_CAPACITY"
    assert row["rho"] is None and row["Lq"] is None and row["Wq_hours"] is None
    assert row["expected_waiting_customer_hours"] is None
    assert row["server_hours"] == 0.0
    assert result["totals"]["expected_waiting_customer_hours"] is None
    assert result["totals"]["undefined_waiting_segments"] == ["p1"]


def test_closed_period_without_demand():
    row = evaluate_shared_segments(*one_period(0, 60, 0.0, 4.0, 0))["segments"][0]
    assert row["status"] == "CLOSED"
    # λ = 0 and c = 0: every state is absorbing, so no unique steady state exists.
    assert row["rho"] is None and row["Lq"] is None and row["Wq_hours"] is None
    # Only the waiting of customers arriving in the segment is known: none arrive.
    assert row["expected_waiting_customer_hours"] == 0.0
    assert row["waiting_attribution"] == "customers_arriving_in_segment"


def test_zero_demand_and_closed_rows_do_not_claim_an_empty_continuous_queue():
    result = evaluate_shared_segments(
        OperatingHorizon(0, 120),
        [DemandPeriod("a", 0, 60, 0.0, 4.0), DemandPeriod("b", 60, 120, 0.0, 4.0)],
        [StaffingSegment("a", 0, 60, 2), StaffingSegment("b", 60, 120, 0)],
    )
    for row in result["segments"]:
        assert row["backlog_represented"] is False
        assert "backlog is not represented" in row["note"]
    assert any("backlog" in assumption and "arrives" in assumption for assumption in result["assumptions"])


def test_unstable_segment_keeps_rho_and_withholds_waits():
    # Day 5, 11:00-12:00 (Daily data mmc/day 5.csv): λ = 18, μ ≈ 4.4883, c = 2.
    horizon = OperatingHorizon(600, 720)
    periods = [DemandPeriod("10", 600, 660, 12.5714, 4.8669), DemandPeriod("11", 660, 720, 18.0, 4.488320356)]
    segments = [StaffingSegment("10", 600, 660, 5), StaffingSegment("11", 660, 720, 2)]
    result = evaluate_shared_segments(horizon, periods, segments)
    unstable = result["segments"][1]
    assert unstable["status"] == "UNSTABLE"
    assert unstable["rho"] == pytest.approx(18.0 / (2 * 4.488320356), rel=1e-12)
    assert unstable["utilization_band"] == "Unstable"
    assert unstable["Lq"] is None and unstable["Wq_hours"] is None
    assert unstable["expected_waiting_customer_hours"] is None
    assert result["totals"]["expected_waiting_customer_hours"] is None
    assert result["totals"]["undefined_waiting_segments"] == ["11"]
    assert result["totals"]["status_counts"] == {"STABLE": 1, "UNSTABLE": 1}


def test_exactly_saturated_segment_is_unstable_despite_float_noise():
    # λ = 3.15, μ = 1.05, c = 3 is exactly ρ = 1 but computes as 0.9999999999999999.
    row = evaluate_shared_segments(*one_period(0, 60, 3.15, 1.05, 3))["segments"][0]
    assert row["status"] == "UNSTABLE"
    assert row["Wq_hours"] is None


# ── Validation ──────────────────────────────────────────────────────────────


def test_gap_overlap_and_coverage_are_reported_together():
    horizon = OperatingHorizon(540, 720)
    periods = [
        DemandPeriod("a", 560, 600, 5.0, 4.0),  # starts after the horizon
        DemandPeriod("b", 600, 640, 5.0, 4.0),
        DemandPeriod("c", 650, 700, 5.0, 4.0),  # gap 640-650
        DemandPeriod("d", 690, 710, 5.0, 4.0),  # overlaps c, ends before the horizon
    ]
    segments = [StaffingSegment("s", 540, 720, 2)]
    with pytest.raises(SharedSegmentError) as error:
        validate_timeline(horizon, periods, segments)
    text = problems_of(error)
    assert "starts at 09:20, not at the horizon start 09:00" in text
    assert "Gap between demand periods b and c: 10:40 to 10:50" in text
    assert "Demand periods c and d overlap" in text
    assert "ends at 11:50, not at the horizon end 12:00" in text


def test_out_of_order_items_are_rejected():
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("late", 60, 120, 1.0, 2.0), DemandPeriod("early", 0, 60, 1.0, 2.0)]
    segments = [StaffingSegment("s", 0, 120, 1)]
    with pytest.raises(SharedSegmentError, match="chronological order"):
        validate_timeline(horizon, periods, segments)


@pytest.mark.parametrize(
    ("period", "message"),
    [
        (DemandPeriod("p", 0, 60, -1.0, 4.0), "arrival rate"),
        (DemandPeriod("p", 0, 60, float("nan"), 4.0), "arrival rate"),
        (DemandPeriod("p", 0, 60, float("inf"), 4.0), "arrival rate"),
        (DemandPeriod("p", 0, 60, None, 4.0), "arrival rate"),  # type: ignore[arg-type]
        (DemandPeriod("p", 0, 60, True, 4.0), "arrival rate"),
        (DemandPeriod("p", 0, 60, 3.0, 0.0), "service rate"),
        (DemandPeriod("p", 0, 60, 3.0, -2.0), "service rate"),
        (DemandPeriod("p", 0, 0, 3.0, 4.0), "must end after it starts"),
        (DemandPeriod("p", 0, 30.5, 3.0, 4.0), "whole minute"),  # type: ignore[arg-type]
        (DemandPeriod("", 0, 60, 3.0, 4.0), "non-empty text id"),
    ],
)
def test_invalid_demand_periods(period, message):
    horizon = OperatingHorizon(0, 60)
    with pytest.raises(SharedSegmentError, match=message):
        validate_timeline(horizon, [period], [StaffingSegment("s", 0, 60, 1)])


@pytest.mark.parametrize("servers", [-1, 1.0, 2.5, True, None])
def test_invalid_server_counts(servers):
    horizon = OperatingHorizon(0, 60)
    with pytest.raises(SharedSegmentError, match="servers must be a whole number"):
        validate_timeline(horizon, [DemandPeriod("p", 0, 60, 3.0, 4.0)], [StaffingSegment("s", 0, 60, servers)])


@pytest.mark.parametrize(
    ("horizon", "message"),
    [
        (OperatingHorizon(600, 600), "must end after it starts"),
        (OperatingHorizon(1320, 120), "must end after it starts"),  # overnight is not supported
        (OperatingHorizon(0, 1441), "whole minute between 0 and 1440"),
    ],
)
def test_invalid_horizons(horizon, message):
    with pytest.raises(SharedSegmentError, match=message):
        validate_timeline(horizon, [DemandPeriod("p", 0, 60, 3.0, 4.0)], [StaffingSegment("s", 0, 60, 1)])


def test_duplicate_ids_and_missing_items():
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("p", 0, 60, 3.0, 4.0), DemandPeriod("p", 60, 120, 3.0, 4.0)]
    with pytest.raises(SharedSegmentError) as error:
        validate_timeline(horizon, periods, [])
    assert "Duplicate demand period ids: p." in problems_of(error)
    with pytest.raises(SharedSegmentError, match="At least one staffing segment is required"):
        validate_timeline(horizon, [DemandPeriod("p", 0, 120, 3.0, 4.0)], [])


def test_full_day_horizon_accepts_midnight_end():
    horizon = OperatingHorizon(0, parse_clock("24:00"))
    result = evaluate_shared_segments(horizon, [DemandPeriod("day", 0, 1440, 1.0, 2.0)], [StaffingSegment("day", 0, 1440, 1)])
    assert result["totals"]["duration_hours"] == 24.0


@pytest.mark.parametrize("value", ["7:00", "12:60", "24:01", "25:00", "noon", 540, None])
def test_parse_clock_rejects_malformed_times(value):
    with pytest.raises(SharedSegmentError):
        parse_clock(value)


def test_parse_clock_values():
    assert parse_clock("00:00") == 0
    assert parse_clock("11:30") == 690
    assert parse_clock("24:00") == 1440


# ── Aggregate rows ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ({"time": "morning", "lambda": 5.0, "mu": 4.0, "c": 2}, "must be a clock range"),
        ({"time": "11:00-12:00", "lambda": 5.0, "mu": 4.0, "c": 2, "variance": 0.01}, "variance supplied"),
        ({"time": "11:00-12:00", "lambda": 5.0, "mu": 4.0, "c": 2, "K": 10}, "K supplied"),
        ({"time": "11:00-12:00", "lambda": 5.0, "mu": 4.0, "c": 2, "theta": 1.5}, "theta supplied"),
        ({"time": "11:00-12:00", "lambda": 5.0, "mu": 4.0, "c": 1, "queue_structure": "separate_queues"}, "separate-queue"),
    ],
)
def test_aggregate_rows_outside_phase_one_are_rejected(row, message):
    with pytest.raises(SharedSegmentError, match=message):
        timeline_from_aggregate_rows([row])


def test_aggregate_rows_keep_null_optional_fields_and_integer_floats():
    periods, segments = timeline_from_aggregate_rows(
        [{"time": "11:00 - 12:00", "lambda": 8.2143, "mu": 4.3068, "c": 2.0, "variance": None, "K": None, "theta": None}]
    )
    assert periods == [DemandPeriod("11:00-12:00", 660, 720, 8.2143, 4.3068)]
    assert segments == [StaffingSegment("11:00-12:00", 660, 720, 2)]


def test_aggregate_rows_with_a_gap_fail_validation():
    rows = [NOVAMART_AVERAGE_ROWS[0], NOVAMART_AVERAGE_ROWS[2]]  # 06:00-07:00 missing
    periods, segments = timeline_from_aggregate_rows(rows)
    with pytest.raises(SharedSegmentError, match="06:00 to 07:00 is not covered"):
        evaluate_shared_segments(OperatingHorizon(300, 480), periods, segments)


# ── Isolation ───────────────────────────────────────────────────────────────


SHARED_QUEUE_ENHANCEMENT_MODULES = {
    "shared_segments.py", "shared_capacity.py", "shared_continuous_des.py", "shared_day_cost.py",
    "shared_replications.py", "shared_playback.py", "shared_workforce.py", "shared_rostering.py",
    "shared_integrated.py", "shared_employee_states.py", "shared_named_des.py", "shared_named_replications.py",
    "shared_named_playback.py", "shared_named_attribution.py", "shared_named_cost.py",
}


def test_no_existing_module_depends_on_the_new_foundation():
    # Only the new shared-queue enhancement modules may use each other; legacy code must not.
    names = [name.removesuffix(".py") for name in SHARED_QUEUE_ENHANCEMENT_MODULES]
    importers = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "backend").rglob("*.py")
        if any(name in path.read_text(encoding="utf-8") for name in names)
        and path.name not in SHARED_QUEUE_ENHANCEMENT_MODULES
    ]
    assert importers == []
