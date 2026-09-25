"""Phase 3A day cost: caller-supplied rates, no defaults, no zero substitution.

Hours come from exact DES cases (μ = 1, binary-exact times), so every cost below is computed
by hand and compared exactly.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from backend.queueing_engine.services.shared_day_cost import (
    COSTED,
    NOT_APPLICABLE,
    RATE_MISSING,
    DayCostRates,
    cost_shared_day,
)
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    DRAIN,
    HARD_CUTOFF,
    simulate_prescribed,
    simulate_shared_day,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ONE_HOUR = (OperatingHorizon(0, 60), [DemandPeriod("d", 0, 60, 1.0, 1.0)], [StaffingSegment("h0", 0, 60, 1)])
# Customer 1 is in service across closing (to 1.25); customers 2 and 3 wait at closing.
BACKLOG = [(0.5, 0.75), (0.75, 0.125), (0.875, 0.25)]
RATES = DayCostRates(regular_server_rate=80.0, overtime_rate=120.0, waiting_rate=100.0, unserved_customer_rate=50.0)


def component(summary: dict, name: str) -> dict:
    return next(row for row in summary["components"] if row["component"] == name)


def test_drain_cost_by_hand():
    # Regular 1.0 h × 80 + overtime 0.625 h × 120 + waiting 1.0 customer-h × 100 = 255.
    summary = cost_shared_day(simulate_prescribed(*ONE_HOUR, BACKLOG, closing_policy=DRAIN), RATES)
    assert [(row["component"], row["quantity"], row["cost"], row["status"]) for row in summary["components"]] == [
        ("regular_server", 1.0, 80.0, COSTED),
        ("overtime_server", 0.625, 75.0, COSTED),
        ("waiting", 1.0, 100.0, COSTED),
        ("unserved_customer", 0, None, NOT_APPLICABLE),
    ]
    assert summary["total_cost"] == 255.0
    assert summary["total_withheld_reason"] is None
    unserved = component(summary, "unserved_customer")
    assert unserved["rate"] == 50.0 and "recorded but not used" in unserved["note"]


def test_hard_cutoff_cost_by_hand():
    # 1.0 × 80 + 0.25 × 120 + 0.375 × 100 + 2 unserved × 50 = 247.5.
    summary = cost_shared_day(simulate_prescribed(*ONE_HOUR, BACKLOG, closing_policy=HARD_CUTOFF), RATES)
    assert [(row["component"], row["quantity"], row["cost"]) for row in summary["components"]] == [
        ("regular_server", 1.0, 80.0),
        ("overtime_server", 0.25, 30.0),
        ("waiting", 0.375, 37.5),
        ("unserved_customer", 2, 100.0),
    ]
    assert summary["total_cost"] == 247.5
    assert summary["closing_policy"] == HARD_CUTOFF


def test_missing_unserved_rate_withholds_the_total_only_where_the_term_applies():
    no_unserved_rate = DayCostRates(80.0, 120.0, 100.0, None)
    drain = cost_shared_day(simulate_prescribed(*ONE_HOUR, BACKLOG, closing_policy=DRAIN), no_unserved_rate)
    assert drain["total_cost"] == 255.0  # DRAIN with a server on duty cannot leave anyone unserved
    assert component(drain, "unserved_customer")["status"] == NOT_APPLICABLE

    cutoff = cost_shared_day(simulate_prescribed(*ONE_HOUR, BACKLOG, closing_policy=HARD_CUTOFF), no_unserved_rate)
    assert cutoff["total_cost"] is None
    assert cutoff["total_withheld_reason"] == "Rates not supplied: unserved_customer_rate."
    missing = component(cutoff, "unserved_customer")
    assert (missing["status"], missing["cost"], missing["quantity"]) == (RATE_MISSING, None, 2)
    assert [component(cutoff, name)["cost"] for name in ("regular_server", "overtime_server", "waiting")] == [
        80.0, 30.0, 37.5
    ]


def test_the_unserved_term_follows_the_policy_not_the_realized_count():
    # HARD_CUTOFF with nobody waiting at closing: the term still applies, so its rate is required.
    empty = simulate_prescribed(*ONE_HOUR, [(0.25, 0.25)], closing_policy=HARD_CUTOFF)
    assert empty["cost_quantities"]["unserved_customer_count"] == 0
    summary = cost_shared_day(empty, DayCostRates(80.0, 120.0, 100.0, None))
    assert summary["total_cost"] is None and component(summary, "unserved_customer")["status"] == RATE_MISSING
    assert cost_shared_day(empty, RATES)["total_cost"] == 80.0


def test_drain_with_nobody_on_duty_at_closing_needs_the_unserved_rate():
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("d", 0, 120, 1.0, 1.0)]
    segments = [StaffingSegment("open", 0, 60, 1), StaffingSegment("closed", 60, 120, 0)]
    result = simulate_prescribed(horizon, periods, segments, [(0.5, 1.75), (1.5, 0.25)], closing_policy=DRAIN)
    assert result["cost_quantities"]["unserved_possible"] is True
    assert cost_shared_day(result, DayCostRates(80.0, 120.0, 100.0, None))["total_cost"] is None
    # Regular: server 1 present 0 to 2 h (1 h scheduled + 1 h draining) = 2.0; overtime 0.25 h;
    # waiting: customer 2 from 1.5 to closing = 0.5 customer-h; one unserved customer.
    summary = cost_shared_day(result, RATES)
    assert [row["quantity"] for row in summary["components"]] == [2.0, 0.25, 0.5, 1]
    assert summary["total_cost"] == 2.0 * 80 + 0.25 * 120 + 0.5 * 100 + 1 * 50


def test_missing_server_rates_are_never_zero():
    summary = cost_shared_day(
        simulate_prescribed(*ONE_HOUR, BACKLOG, closing_policy=HARD_CUTOFF), DayCostRates(None, None, 100.0, 50.0)
    )
    assert summary["total_cost"] is None
    assert summary["total_withheld_reason"] == "Rates not supplied: regular_server_rate, overtime_rate."
    assert component(summary, "regular_server")["cost"] is None
    assert component(summary, "overtime_server")["cost"] is None


def test_explicit_zero_rates_are_accepted_and_recorded():
    summary = cost_shared_day(
        simulate_prescribed(*ONE_HOUR, BACKLOG, closing_policy=HARD_CUTOFF), DayCostRates(0.0, 0, 0.0, 0.0)
    )
    assert summary["total_cost"] == 0.0
    assert all(row["status"] == COSTED for row in summary["components"])
    assert summary["rates"] == {
        "regular_server_rate": 0.0, "overtime_rate": 0, "waiting_rate": 0.0, "unserved_customer_rate": 0.0,
    }


@pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf, True, "80"])
def test_invalid_rates_are_rejected(bad):
    for field in ("regular_server_rate", "overtime_rate", "waiting_rate", "unserved_customer_rate"):
        values = {"regular_server_rate": 1.0, "overtime_rate": 1.0, "waiting_rate": 1.0, "unserved_customer_rate": 1.0}
        values[field] = bad
        result = simulate_prescribed(*ONE_HOUR, BACKLOG, closing_policy=HARD_CUTOFF)
        with pytest.raises(SharedSegmentError, match=field):
            cost_shared_day(result, DayCostRates(**values))


def test_rates_have_no_defaults():
    with pytest.raises(TypeError):
        DayCostRates()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        DayCostRates(80.0, 120.0, 100.0)  # type: ignore[call-arg]


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_cost_uses_the_des_quantities_on_a_seeded_day(policy):
    horizon = OperatingHorizon(480, 600)
    periods = [DemandPeriod("a", 480, 540, 40.0, 12.0), DemandPeriod("b", 540, 600, 30.0, 10.0)]
    segments = [StaffingSegment("a", 480, 540, 3), StaffingSegment("b", 540, 600, 2)]
    result = simulate_shared_day(horizon, periods, segments, seed=7, closing_policy=policy)
    quantities, totals, closing = result["cost_quantities"], result["totals"], result["closing"]
    assert quantities["regular_server_hours"] == totals["present_server_hours"]
    assert quantities["overtime_server_hours"] == closing["after_close_server_hours"]
    assert quantities["total_waiting_customer_hours"] == pytest.approx(
        totals["queue_customer_hours"] + closing["after_close_waiting_customer_hours"], rel=1e-12
    )
    assert quantities["unserved_customer_count"] == totals["unserved_at_close"]
    expected = math.fsum([
        quantities["regular_server_hours"] * 80.0,
        quantities["overtime_server_hours"] * 120.0,
        quantities["total_waiting_customer_hours"] * 100.0,
        quantities["unserved_customer_count"] * 50.0 if policy == HARD_CUTOFF else 0.0,
    ])
    assert cost_shared_day(result, RATES)["total_cost"] == pytest.approx(expected, rel=1e-12)


def test_the_des_holds_no_monetary_assumption():
    result = simulate_prescribed(*ONE_HOUR, BACKLOG, closing_policy=DRAIN)
    assert set(result["cost_quantities"]) == {
        "closing_policy", "regular_server_hours", "overtime_server_hours", "total_waiting_customer_hours",
        "unserved_customer_count", "unserved_possible", "definitions", "server_hours_meaning",
    }
    assert "not necessarily paid employee-hours" in result["cost_quantities"]["server_hours_meaning"]
    for module in ("backend/queueing_engine/simulation/shared_continuous_des.py",
                   "backend/queueing_engine/services/shared_day_cost.py"):
        source = (REPO_ROOT / module).read_text(encoding="utf-8")
        assert "queueing_engine.config" not in source
        assert "OT_RATE" not in source.replace("``OT_RATE``", "")
