"""Why savings/ROI is not shown: overload (rho >= 1) versus incompatible cost bases.

Explanation text only; no savings or ROI number is added or changed.
"""
from __future__ import annotations

from backend.api.reports import (
    BASIS_ROI_REASON,
    overload_ranges,
    separate_break_overload_note,
    separate_roi_reason,
)
from backend.data.setup_derivation import derive_setup
from backend.queueing_engine.services.optimization import (
    build_recommendations,
    summarize_optimization,
    unstable_current_reason,
)
from tests.test_break_optimization import _records as small_records
from tests.test_break_optimization import _setup as small_setup
from tests.test_setup_derivation import sheets

NOVAMART_NOTE = (
    "Note: from 11:00 to 12:00 the cashiers on duty during breaks cannot keep up with demand "
    "(pooled 15-minute ρ = 1.01); the break optimizer addresses this."
)


def _novamart():
    result = derive_setup(sheets(), None)
    assert result.errors == []
    return result.setup, result.records


# --- separate queues ------------------------------------------------------------------------


def test_novamart_reason_is_the_basis_and_overload_is_a_separate_note():
    setup, records = _novamart()
    assert separate_roi_reason(setup, records) == BASIS_ROI_REASON
    assert separate_break_overload_note(setup, records) == NOVAMART_NOTE


def _slot(start, rho, *, lam=10.0, mu=5.0, working=2.0):
    return {"start": float(start), "end": float(start + 15), "lambda": lam, "mu": mu,
            "working": working, "rho": rho}


def test_overload_ranges_merge_consecutive_slots_and_list_every_range():
    rows = [_slot(480, 0.9), _slot(495, 1.0), _slot(510, 1.2), _slot(525, 0.5),
            _slot(540, None, working=0.0), _slot(555, 0.4)]
    # 09:00 slot: demand with nobody working (rho = inf) is an overload.
    assert overload_ranges(rows) == [("08:15", "08:45"), ("09:00", "09:15")]


def test_closed_slot_is_not_an_overload():
    rows = [_slot(480, 0.0, lam=0.0, working=0.0), _slot(495, 0.5)]
    assert overload_ranges(rows) == []


def test_uncomputable_slot_is_never_claimed_as_overload():
    rows = [_slot(480, None, mu=0.0), _slot(495, 1.5)]
    assert overload_ranges(rows) is None


def test_separate_all_slots_below_one_gives_basis_reason():
    setup = small_setup()
    assert separate_roi_reason(setup, small_records(setup)) == BASIS_ROI_REASON
    assert separate_break_overload_note(setup, small_records(setup)) is None


def test_separate_missing_inputs_give_basis_reason_without_crash():
    setup, records = _novamart()
    assert separate_roi_reason({**setup, "breaks": []}, records) == BASIS_ROI_REASON
    assert separate_roi_reason({**setup, "event_period_basis": "per_date"}, records) == BASIS_ROI_REASON
    assert separate_roi_reason(setup, []) == BASIS_ROI_REASON
    assert separate_roi_reason({}, None) == BASIS_ROI_REASON
    assert separate_break_overload_note({**setup, "breaks": []}, records) is None
    assert separate_break_overload_note({}, None) is None


# --- shared queues --------------------------------------------------------------------------


def _row(time, *, current_stable=True, cost_current=100.0, cost_optimal=80.0):
    return {"time": time, "current_stable": current_stable, "optimized_stable": True,
            "c_optimal": 3, "c_current": 2, "delta_c": 1,
            "cost_current": cost_current, "cost_optimal": cost_optimal,
            "rho_current": 0.8, "rho_optimal": 0.6, "Wq_current": 0.2, "Wq_optimal": 0.1,
            "recommendation": f"{time}: add 1 server"}


def test_shared_unstable_current_segment_is_named_and_savings_stay_none():
    rows = [_row("09:00-10:00"), _row("11:00-12:00", current_stable=False, cost_current=None),
            _row("12:00-13:00", current_stable=False, cost_current=None)]
    reason = ("ROI can't be declared: in 11:00-12:00, 12:00-13:00, customers arrive faster than the "
              "current staff can serve them (ρ ≥ 1), so today's waiting cost has no finite value.")
    assert unstable_current_reason(rows) == reason
    assert summarize_optimization(rows)["total_savings"] is None
    assert build_recommendations(rows) == [
        "Comparison incomplete: no aggregate savings or staffing assurance is available.", reason]


def test_shared_all_stable_has_no_reason_and_unchanged_savings():
    rows = [_row("09:00-10:00"), _row("10:00-11:00", cost_current=150.0, cost_optimal=90.0)]
    assert unstable_current_reason(rows) is None
    assert summarize_optimization(rows)["total_savings"] == 80.0
    assert "Comparison incomplete" not in " ".join(build_recommendations(rows))


def test_shared_incomplete_for_other_causes_keeps_only_existing_message():
    rows = [_row("09:00-10:00"), {**_row("10:00-11:00"), "optimized_stable": False, "c_optimal": None}]
    assert unstable_current_reason(rows) is None
    assert build_recommendations(rows) == [
        "Comparison incomplete: no aggregate savings or staffing assurance is available."]


# --- scenario output ------------------------------------------------------------------------


def _scenario(results):
    from datetime import datetime, timezone

    from backend.db.models import Scenario
    return Scenario(id=1, analysis_id=None, dataset_id=None, name="s", settings_json={},
                    results_json=results, created_at=datetime.now(timezone.utc))


def test_scenario_out_carries_shared_reason_and_null_otherwise():
    from backend.api.scenarios import _to_out
    unstable = [_row("09:00-10:00"), _row("11:00-12:00", current_stable=False, cost_current=None)]
    assert _to_out(_scenario({"results": unstable}))["roi_unavailable_reason"] == unstable_current_reason(unstable)
    assert _to_out(_scenario({"comparison": [_row("09:00-10:00")]}))["roi_unavailable_reason"] is None
    assert _to_out(_scenario({"schedule": {"periods": []}}))["roi_unavailable_reason"] is None
