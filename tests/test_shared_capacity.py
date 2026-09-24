"""Phase 2 shared-queue capacity optimizer: independent cost, boundary, and selection checks.

Expected values are computed by hand or with an Erlang-B recursion written here, which
shares no code with ``queue_models.mmc``.
"""

from __future__ import annotations

import logging
import math

import pytest

from backend.queueing_engine.services.optimization import optimize_segment
from backend.queueing_engine.services.shared_capacity import (
    MAX_CANDIDATE_SERVERS,
    CapacityConfig,
    optimize_shared_capacity,
    validate_config,
)
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    timeline_from_aggregate_rows,
)
from tests.test_shared_segments import NOVAMART_AVERAGE_ROWS, erlang_reference


def config(**overrides) -> CapacityConfig:
    values = dict(
        server_cost_per_hour=100.0,
        waiting_cost_per_customer_hour=50.0,
        target_utilization=0.7,
        min_servers=1,
        max_servers=6,
        max_wait_minutes=None,
    )
    values.update(overrides)
    return CapacityConfig(**values)  # type: ignore[arg-type]


def single(lambda_: float, mu: float, current: int, cfg: CapacityConfig, minutes: int = 60) -> dict:
    horizon = OperatingHorizon(0, minutes)
    result = optimize_shared_capacity(
        horizon, [DemandPeriod("p", 0, minutes, lambda_, mu)], [StaffingSegment("p", 0, minutes, current)], cfg
    )
    return result


def candidate(segment: dict, servers: int) -> dict:
    return next(item for item in segment["candidates"] if item["servers"] == servers)


def independent_cost(lambda_: float, mu: float, c: int, hours: float, server_cost: float, wait_cost: float) -> float:
    wq = erlang_reference(lambda_, mu, c)["Wq"]
    return c * server_cost * hours + lambda_ * wq * hours * wait_cost


# ── Duration-weighted costs ─────────────────────────────────────────────────


def test_duration_weighted_costs_match_hand_calculation():
    # λ = 2/h, μ = 1/h per server, c = 3, T = 30 min = 0.5 h, 100 per server-hour, 50 per customer-hour.
    # Wq = 4/9 h, so waiting customer-hours = 2 × 4/9 × 0.5 = 4/9 and waiting cost = 200/9.
    segment = single(2.0, 1.0, 3, config(min_servers=3, max_servers=3), minutes=30)["segments"][0]
    chosen = segment["selected"]
    assert chosen["servers"] == 3
    assert chosen["server_hours"] == pytest.approx(1.5)
    assert chosen["server_cost"] == pytest.approx(150.0)
    assert chosen["expected_waiting_customer_hours"] == pytest.approx(4 / 9, rel=1e-12)
    assert chosen["waiting_cost"] == pytest.approx(200 / 9, rel=1e-12)
    assert chosen["total_cost"] == pytest.approx(150.0 + 200 / 9, rel=1e-12)


def test_costs_scale_linearly_with_segment_duration():
    horizon = OperatingHorizon(660, 720)
    periods = [DemandPeriod("11:00-12:00", 660, 720, 8.2143, 4.3068)]
    segments = [StaffingSegment("quarter", 660, 675, 2), StaffingSegment("rest", 675, 720, 2)]
    result = optimize_shared_capacity(horizon, periods, segments, config(max_servers=5))
    quarter, rest = result["segments"]
    for servers in range(1, 6):
        a, b = candidate(quarter, servers), candidate(rest, servers)
        if a["total_cost"] is None:
            assert b["total_cost"] is None
            continue
        assert a["total_cost"] * 4 == pytest.approx(b["total_cost"] * 4 / 3, rel=1e-12)
        expected = independent_cost(8.2143, 4.3068, servers, 0.25, 100.0, 50.0)
        assert a["total_cost"] == pytest.approx(expected, rel=1e-9)
    # The same stationary segment has the same best count however long it lasts.
    assert quarter["selected"]["servers"] == rest["selected"]["servers"]


# ── Selection and tie-breaking ──────────────────────────────────────────────


def test_exact_tie_goes_to_fewer_servers():
    # λ = 1/h, μ = 2/h: M/M/1 Wq = 1/2 h, M/M/2 Wq = 1/30 h. With 7 per server-hour and
    # 15 per customer-hour: c = 1 → 7 + 7.5 = 14.5 and c = 2 → 14 + 0.5 = 14.5.
    segment = single(1.0, 2.0, 1, config(server_cost_per_hour=7.0, waiting_cost_per_customer_hour=15.0))["segments"][0]
    assert candidate(segment, 1)["total_cost"] == pytest.approx(14.5, rel=1e-12)
    assert candidate(segment, 2)["total_cost"] == pytest.approx(14.5, rel=1e-12)
    assert segment["selected"]["servers"] == 1


def test_tie_tolerance_does_not_absorb_a_real_difference():
    # 15.01 per customer-hour: c = 1 → 14.505, c = 2 → 14.5005, so two servers are cheaper.
    segment = single(1.0, 2.0, 1, config(server_cost_per_hour=7.0, waiting_cost_per_customer_hour=15.01))["segments"][0]
    assert segment["selected"]["servers"] == 2


def test_novamart_average_matches_independent_brute_force_and_legacy_optimizer():
    # Operating parameters are test inputs here (the repository's configured defaults).
    cfg = config(server_cost_per_hour=94.375, waiting_cost_per_customer_hour=100.0,
                 target_utilization=0.70, min_servers=1, max_servers=24)
    periods, segments = timeline_from_aggregate_rows(NOVAMART_AVERAGE_ROWS)
    result = optimize_shared_capacity(OperatingHorizon(300, 1080), periods, segments, cfg)
    logging.disable(logging.CRITICAL)
    try:
        for source, row in zip(NOVAMART_AVERAGE_ROWS, result["segments"]):
            lam, mu = source["lambda"], source["mu"]
            brute = [
                (independent_cost(lam, mu, c, 1.0, 94.375, 100.0), c)
                for c in range(1, 25)
                if lam / (c * mu) < 1 and lam / (c * mu) <= 0.70
            ]
            best_cost, best_c = min(brute)
            assert row["selected"]["servers"] == best_c
            assert row["selected"]["total_cost"] == pytest.approx(best_cost, rel=1e-9)
            legacy = optimize_segment(
                {"time": source["time"], "lambda": lam, "mu": mu, "c": source["c"]},
                target_utilization=0.70, default_server_cost=94.375, max_servers=24,
                customer_waiting_cost=100.0, min_servers=1,
            )
            assert legacy["c_optimal"] == best_c
            assert legacy["cost_optimal"] == pytest.approx(row["selected"]["total_cost"], rel=1e-12)
            assert legacy["cost_current"] == pytest.approx(row["current"]["total_cost"], rel=1e-12)
    finally:
        logging.disable(logging.NOTSET)
    assert [row["selected"]["servers"] for row in result["segments"]] == [2, 3, 3, 3, 3, 4, 3, 4, 4, 3, 3, 2, 2]
    totals = result["totals"]
    assert totals["current"]["server_hours"] == pytest.approx(55.0)
    assert totals["selected"]["server_hours"] == pytest.approx(39.0)
    assert totals["plan_complete"] is True
    assert totals["cost_change"] == pytest.approx(
        totals["selected"]["total_cost"] - totals["current"]["total_cost"], rel=1e-12
    )


# ── Constraint boundaries ───────────────────────────────────────────────────


def test_utilization_exactly_at_target_is_feasible():
    # λ = 7, μ = 5, c = 2: ρ = 0.7 exactly. No waiting cost, so the cheapest feasible count wins.
    segment = single(7.0, 5.0, 2, config(waiting_cost_per_customer_hour=0.0))["segments"][0]
    assert candidate(segment, 2)["rho"] == 0.7
    assert segment["selected"]["servers"] == 2


def test_float_noise_at_the_utilization_target_is_tolerated():
    # λ = 2.1, μ = 1, c = 3 is exactly ρ = 0.7 but computes as 0.7000000000000001.
    segment = single(2.1, 1.0, 3, config(waiting_cost_per_customer_hour=0.0))["segments"][0]
    assert candidate(segment, 3)["rho"] > 0.7
    assert candidate(segment, 3)["feasible"] is True
    assert segment["selected"]["servers"] == 3


def test_utilization_just_above_target_is_rejected():
    segment = single(2.1 * (1 + 1e-6), 1.0, 3, config(waiting_cost_per_customer_hour=0.0))["segments"][0]
    assert candidate(segment, 3)["violations"] == ["target_utilization"]
    assert segment["selected"]["servers"] == 4


def test_max_wait_boundary_in_minutes():
    # M/M/1 λ = 3, μ = 4: Wq = 0.75 h = 45 min exactly.
    at_limit = single(3.0, 4.0, 1, config(target_utilization=0.8, waiting_cost_per_customer_hour=0.0,
                                         max_wait_minutes=45.0))["segments"][0]
    assert candidate(at_limit, 1)["Wq_hours"] * 60 == 45.0
    assert at_limit["selected"]["servers"] == 1
    below = single(3.0, 4.0, 1, config(target_utilization=0.8, waiting_cost_per_customer_hour=0.0,
                                      max_wait_minutes=44.99))["segments"][0]
    assert candidate(below, 1)["violations"] == ["max_wait_minutes"]
    assert below["selected"]["servers"] == 2


# ── Zero demand, zero capacity, instability, infeasibility ──────────────────


def test_zero_demand_selects_the_minimum_servers_with_zero_waiting_cost():
    segment = single(0.0, 4.0, 3, config(min_servers=1))["segments"][0]
    chosen = segment["selected"]
    assert (chosen["servers"], chosen["status"]) == (1, "ZERO_DEMAND")
    assert chosen["waiting_cost"] == 0.0
    assert chosen["total_cost"] == pytest.approx(100.0)
    assert segment["server_change"] == -2


def test_closing_is_chosen_only_when_allowed_and_nobody_arrives():
    closed = single(0.0, 4.0, 1, config(min_servers=0))["segments"][0]
    assert (closed["selected"]["servers"], closed["selected"]["status"]) == (0, "CLOSED")
    assert closed["selected"]["total_cost"] == 0.0
    busy = single(5.0, 4.0, 2, config(min_servers=0))["segments"][0]
    assert candidate(busy, 0)["status"] == "NO_CAPACITY"
    assert candidate(busy, 0)["violations"] == ["no_capacity"]
    assert candidate(busy, 0)["total_cost"] is None
    assert busy["selected"]["servers"] > 0


def test_unstable_current_staffing_has_no_cost_and_no_savings_claim():
    # Day 5, 11:00-12:00: λ = 18, μ ≈ 4.4883, c = 2 (ρ ≈ 2.005).
    result = single(18.0, 4.488320356, 2, config(max_servers=24))
    segment = result["segments"][0]
    assert segment["current"]["status"] == "UNSTABLE"
    assert segment["current"]["total_cost"] is None
    assert segment["current"]["waiting_cost"] is None
    assert segment["outcome"] == "OPTIMIZED"
    assert segment["cost_change"] is None
    totals = result["totals"]
    assert totals["current"]["total_cost"] is None
    assert totals["current"]["segments_with_undefined_cost"] == ["p"]
    assert totals["cost_change"] is None
    assert "no finite cost in: p" in totals["cost_change_unavailable_reason"]


def test_no_feasible_candidate_is_reported_not_zeroed():
    result = single(8.2143, 4.3068, 2, config(min_servers=1, max_servers=2))
    segment = result["segments"][0]
    assert segment["outcome"] == "NO_FEASIBLE_CANDIDATE"
    assert segment["selected"] is None
    assert segment["violations_seen"] == ["stability", "target_utilization"]
    assert segment["server_change"] is None and segment["cost_change"] is None
    totals = result["totals"]
    assert totals["plan_complete"] is False
    assert totals["selected"]["total_cost"] is None
    assert totals["selected"]["segments_without_selection"] == ["p"]
    assert totals["cost_change"] is None
    assert "No feasible server count exists in: p" in totals["cost_change_unavailable_reason"]


def test_all_unstable_candidates():
    segment = single(18.0, 4.488320356, 2, config(max_servers=3))["segments"][0]
    assert segment["outcome"] == "NO_FEASIBLE_CANDIDATE"
    assert segment["violations_seen"] == ["stability"]


def test_current_staffing_outside_the_candidate_range_is_still_evaluated():
    segment = single(3.0, 4.0, 8, config(max_servers=4))["segments"][0]
    assert segment["current"]["servers"] == 8
    assert segment["current"]["within_candidate_range"] is False
    assert segment["current"]["total_cost"] == pytest.approx(independent_cost(3.0, 4.0, 8, 1.0, 100.0, 50.0), rel=1e-9)


def test_every_candidate_and_the_inputs_are_kept():
    cfg = config(min_servers=2, max_servers=5, max_wait_minutes=10.0)
    result = single(8.2143, 4.3068, 2, cfg)
    assert [item["servers"] for item in result["segments"][0]["candidates"]] == [2, 3, 4, 5]
    provenance = result["provenance"]
    assert provenance["engine_version"] == "novaq-shared-capacity-v1"
    assert provenance["metric_provenance"] == "analytical_steady_state"
    assert provenance["config"]["max_wait_minutes"] == 10.0
    assert provenance["inputs"]["demand_periods"][0]["arrival_rate_per_hour"] == 8.2143
    assert provenance["inputs"]["staffing_segments"][0]["servers"] == 2
    assert any("backlog" in text for text in provenance["assumptions"])


def test_limits_and_stability_share_one_tolerance():
    # The optimizer's limit margin is the same constant is_saturated uses for stability.
    from backend.queueing_engine import utilization
    from backend.queueing_engine.services import shared_capacity

    assert shared_capacity.THRESHOLD_TOLERANCE is utilization.THRESHOLD_TOLERANCE == 1e-9
    assert utilization.is_saturated(1 - 1e-9) and not utilization.is_saturated(1 - 2e-9)
    # Behavior at the utilization limit: 5e-10 above the target passes, 2e-9 above fails.
    base = 2.1 / 3  # ρ for λ = 2.1, μ = 1, c = 3
    inside = single(2.1, 1.0, 3, config(target_utilization=base - 5e-10, waiting_cost_per_customer_hour=0.0))
    outside = single(2.1, 1.0, 3, config(target_utilization=base - 2e-9, waiting_cost_per_customer_hour=0.0))
    assert candidate(inside["segments"][0], 3)["feasible"] is True
    assert candidate(outside["segments"][0], 3)["violations"] == ["target_utilization"]
    assert "1e-12" in inside["provenance"]["tolerance_policy"]


# ── Configuration validation ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"server_cost_per_hour": 0.0}, "Server cost"),
        ({"server_cost_per_hour": float("nan")}, "Server cost"),
        ({"waiting_cost_per_customer_hour": -1.0}, "Waiting cost"),
        ({"target_utilization": 0.0}, "Target utilization"),
        ({"target_utilization": 1.01}, "Target utilization"),
        ({"min_servers": -1}, "Minimum servers"),
        ({"min_servers": True}, "Minimum servers"),
        ({"max_servers": MAX_CANDIDATE_SERVERS + 1}, "Maximum servers"),
        ({"min_servers": 5, "max_servers": 4}, "must not exceed"),
        ({"max_wait_minutes": -0.5}, "Maximum wait"),
        ({"max_wait_minutes": math.inf}, "Maximum wait"),
    ],
)
def test_invalid_configuration_is_rejected(overrides, message):
    with pytest.raises(SharedSegmentError, match=message):
        validate_config(config(**overrides))


def test_invalid_timeline_is_rejected_before_optimizing():
    with pytest.raises(SharedSegmentError, match="not covered"):
        optimize_shared_capacity(
            OperatingHorizon(0, 120),
            [DemandPeriod("a", 0, 60, 3.0, 4.0), DemandPeriod("b", 90, 120, 3.0, 4.0)],
            [StaffingSegment("a", 0, 120, 1)],
            config(),
        )
