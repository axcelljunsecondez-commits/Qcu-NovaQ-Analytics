"""U10: the shared Decision when today's staffing cannot keep up in a period.

Spec: docs/superpowers/specs/2026-10-13-u10-today-overloaded-decision.md.
"""

from __future__ import annotations

from backend.api.workflow import _derive_decision
from backend.db.models import AnalysisProject, Scenario

PERIODS = ("08:00", "09:00", "10:00")


def _inputs(rows: list[dict], failing: frozenset[str] = frozenset()):
    analysis = AnalysisProject(id=1, user_id=1, name="Line", setup_status="ready", queue_setup_json={})
    scenario = Scenario(id=3, user_id=1, analysis_id=1, dataset_id=2, name="Plan A", settings_json={},
                        results_json={"results": rows})
    evidence = {
        "selection": {"id": 10},
        "des": {"id": 11, "result": {"results": [
            {"time": row["time"], "simulation_supported": True, "error": None} for row in rows]}},
        "mc": None,
        "validation": {"id": 12, "params": {"mc_failure_rate_cap": 0.05}, "result": {"results": [
            {"time": row["time"], "simulation_supported": True, "validation_reason": None,
             "sim_status": "Critical" if row["time"] in failing else "Normal",
             "mc_failure_rate": 0.01, "mc_failure_rate_adequate": True} for row in rows]}},
    }
    return analysis, scenario, evidence


def _row(time: str, *, current_cost=100.0, plan_cost=90.0, stable=True, c_current=3, c_optimal=3):
    return {"time": time, "c_current": c_current, "c_optimal": c_optimal, "cost_current": current_cost,
            "cost_optimal": plan_cost, "current_stable": stable}


def _overloaded_plan():
    # 10:00: today 3 counters cannot keep up (no finite today cost); the plan uses 5.
    return [_row("08:00"), _row("09:00"),
            _row("10:00", current_cost=None, plan_cost=150.0, stable=False, c_optimal=5)]


def test_a_passing_plan_that_fixes_an_overloaded_period_is_conditional_not_insufficient():
    decision = _derive_decision(*_inputs(_overloaded_plan()))
    assert decision["status"] == "conditional"
    assert decision["missing_evidence"] == []
    facts = decision["facts"]
    assert facts["current_modeled_cost"] is None and facts["modeled_savings"] is None
    assert facts["selected_modeled_cost"] == 330.0
    assert facts["today_overloaded_periods"] == ["10:00"]
    assert facts["server_delta"] == 2
    assert "cost change cannot be calculated" in decision["recommendation"] and "10:00" in decision["recommendation"]
    assert "Today's staffing cannot keep up (ρ ≥ 1) in: 10:00." in decision["rationale"]


def test_a_failing_check_still_gives_revise():
    decision = _derive_decision(*_inputs(_overloaded_plan(), failing=frozenset({"09:00"})))
    assert decision["status"] == "revise"
    assert decision["facts"]["failed_intervals"] == 1


def test_never_adopt_without_a_finite_today_cost():
    rows = [_row("08:00", plan_cost=10.0), _row("09:00", current_cost=None, plan_cost=10.0, stable=False)]
    assert _derive_decision(*_inputs(rows))["status"] == "conditional"


def test_other_cost_gaps_stay_missing_evidence():
    cases = {
        "today cost missing although today keeps up": [_row("08:00", current_cost=None, stable=True)],
        "today stability unknown": [_row("08:00", current_cost=None, stable=None)],
        "plan cost missing": [_row("08:00", current_cost=None, stable=False), _row("09:00", plan_cost=None)],
        "plan cost missing in the overloaded period": [_row("08:00", current_cost=None, plan_cost=None, stable=False)],
        "negative plan cost": [_row("08:00", current_cost=None, stable=False), _row("09:00", plan_cost=-1.0)],
    }
    for name, rows in cases.items():
        decision = _derive_decision(*_inputs(rows))
        assert decision["status"] == "insufficient_evidence", name
        assert "a complete modeled cost comparison" in decision["missing_evidence"], name


def test_complete_costs_keep_the_existing_rule():
    assert _derive_decision(*_inputs([_row(t) for t in PERIODS]))["status"] == "adopt"
    decision = _derive_decision(*_inputs([_row(t, plan_cost=120.0) for t in PERIODS]))
    assert decision["status"] == "conditional" and decision["facts"]["modeled_savings"] == -60.0
    assert "today_overloaded_periods" not in decision["facts"]
