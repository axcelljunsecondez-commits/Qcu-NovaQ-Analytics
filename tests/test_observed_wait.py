"""R6c/R7: current-wait presentation never misleads.

R6c — Comparison states the basis of Current (analytical) and plan (simulation)
waits and returns no cross-basis difference. R7 — the modeled current wait is
shown next to the observed wait from event uploads, flagging periods where the
observed wait is far longer than the model explains. Aggregate uploads have no
observed wait: nothing is shown, never zero.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.api.workflow import (
    OBSERVED_WAIT_FLAG_MIN_GAP_MINUTES,
    OBSERVED_WAIT_FLAG_RATIO,
    _observed_wait_summary,
)
from tests.helpers import create_user, csrf_header, login
from tests.test_separate_comparison_select import _comparison
from tests.test_separate_comparison_select import _workspace as _separate_workspace
from tests.test_setup_derivation import novamart_workbook
from tests.test_upload_setup_api import _analysis, _upload
from tests.test_workflow_api import _workspace as _shared_workspace


def _frame(rows):
    return pd.DataFrame(rows)


def _validation(stats, days=None):
    report = {"ok": True, "derived_statistics": stats}
    if days is not None:
        report.update({"period_basis": "representative_day", "observation_days": days})
    return report


def test_flag_constants_live_in_one_place():
    assert OBSERVED_WAIT_FLAG_RATIO == 2.0
    assert OBSERVED_WAIT_FLAG_MIN_GAP_MINUTES == 5.0


def test_observed_close_to_modeled_is_not_flagged():
    records = [{"time": "08:00", "queue_id": "a", "lambda": 4.0}]
    frame = _frame([{"time": "08:00", "queue_id": "a", "lambda": 4.0, "Wq": 0.10}])
    stats = [{"time": "08:00", "queue_id": "a", "duration_minutes": 60.0,
              "mean_waiting_time_hours": 0.11}]
    summary = _observed_wait_summary(records, _validation(stats), frame)
    assert summary["available"] is True
    period = summary["periods"][0]
    assert period["modeled_wait"] == pytest.approx(0.10)
    assert period["observed_wait"] == pytest.approx(0.11)
    assert period["flagged"] is False
    assert summary["flagged_any"] is False


def test_flag_needs_both_ratio_and_gap():
    records = [{"time": "08:00", "queue_id": "a", "lambda": 4.0}]
    frame = _frame([{"time": "08:00", "queue_id": "a", "lambda": 4.0, "Wq": 1 / 60}])
    # 3x modeled but only 2 minutes longer: ratio passes, gap does not.
    small_gap = [{"time": "08:00", "queue_id": "a", "duration_minutes": 60.0,
                  "mean_waiting_time_hours": 3 / 60}]
    assert _observed_wait_summary(records, _validation(small_gap), frame)["periods"][0]["flagged"] is False
    # 10x modeled and 9 minutes longer: flagged.
    large = [{"time": "08:00", "queue_id": "a", "duration_minutes": 60.0,
              "mean_waiting_time_hours": 10 / 60}]
    summary = _observed_wait_summary(records, _validation(large), frame)
    assert summary["periods"][0]["flagged"] is True
    assert summary["flagged_any"] is True


def test_observed_wait_weights_queues_by_arrival_count():
    records = [
        {"time": "08:00", "queue_id": "a", "lambda": 3.0},
        {"time": "08:00", "queue_id": "b", "lambda": 1.0},
    ]
    frame = _frame([
        {"time": "08:00", "queue_id": "a", "lambda": 3.0, "Wq": 0.1},
        {"time": "08:00", "queue_id": "b", "lambda": 1.0, "Wq": 0.1},
    ])
    stats = [
        {"time": "08:00", "queue_id": "a", "duration_minutes": 30.0, "mean_waiting_time_hours": 0.2},
        {"time": "08:00", "queue_id": "b", "duration_minutes": 30.0, "mean_waiting_time_hours": 0.6},
    ]
    summary = _observed_wait_summary(records, _validation(stats, days=14), frame)
    assert summary["periods"][0]["observed_wait"] == pytest.approx((3 * 0.2 + 1 * 0.6) / 4)


def test_missing_derived_statistics_means_nothing_observed():
    records = [{"time": "08:00", "queue_id": "a", "lambda": 4.0}]
    frame = _frame([{"time": "08:00", "queue_id": "a", "lambda": 4.0, "Wq": 0.1}])
    summary = _observed_wait_summary(records, {"ok": True}, frame)
    assert summary == {"available": False, "periods": [], "flagged_any": False,
                       "day_modeled_wait": None, "day_observed_wait": None,
                       "ratio": OBSERVED_WAIT_FLAG_RATIO,
                       "min_gap_minutes": OBSERVED_WAIT_FLAG_MIN_GAP_MINUTES}


def test_unmatched_statistic_leaves_period_observed_unknown():
    records = [{"time": "08:00", "queue_id": "a", "lambda": 4.0}]
    frame = _frame([{"time": "08:00", "queue_id": "a", "lambda": 4.0, "Wq": 0.1}])
    stats = [{"time": "08:00", "queue_id": "zz", "duration_minutes": 60.0,
              "mean_waiting_time_hours": 0.9}]
    period = _observed_wait_summary(records, _validation(stats), frame)["periods"][0]
    assert period["observed_wait"] is None
    assert period["flagged"] is False


# --- API: NovaMart event upload ------------------------------------------------------

def _novamart(db_engine, client, email="nm@example.com"):
    create_user(db_engine, email, "pw")
    login(client, email, "pw")
    analysis = _analysis(client)
    response = _upload(client, analysis["id"], novamart_workbook(), apply=True)
    assert response.status_code == 201, response.text
    return analysis["id"]


NOVAMART_UNFLAGGED = {
    # time: (observed minutes, modeled minutes) against the displayed analytical wait
    "05:00-06:00": (10.84, 5.78),
    "17:00-18:00": (9.09, 7.00),
}


def _minutes(hours):
    return hours * 60.0


def test_novamart_eleven_of_thirteen_periods_flagged_with_banner(db_engine, client):
    analysis_id = _novamart(db_engine, client)
    response = client.get(f"/analyses/{analysis_id}/workflow/observed-wait",
                          headers=csrf_header(client))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True
    assert len(body["periods"]) == 13
    unflagged = {period["time"]: period for period in body["periods"] if not period["flagged"]}
    assert set(unflagged) == set(NOVAMART_UNFLAGGED)
    assert sum(period["flagged"] for period in body["periods"]) == 11
    for label, (observed, modeled) in NOVAMART_UNFLAGGED.items():
        assert _minutes(unflagged[label]["observed_wait"]) == pytest.approx(observed, abs=0.01)
        assert _minutes(unflagged[label]["modeled_wait"]) == pytest.approx(modeled, abs=0.01)
    assert body["flagged_any"] is True
    assert _minutes(body["day_observed_wait"]) == pytest.approx(41.47, abs=0.01)
    assert _minutes(body["day_modeled_wait"]) == pytest.approx(6.27, abs=0.01)
    current = client.get(f"/analyses/{analysis_id}/current").json()
    # The modeled figure is the same lambda-weighted analytical wait the pages show.
    by_time: dict[str, list[tuple[float, float]]] = {}
    for row in current["rows"]:
        by_time.setdefault(row["time"], []).append((row["lambda"], row["Wq"]))
    for period in body["periods"]:
        pairs = by_time[period["time"]]
        expected = sum(lam * wq for lam, wq in pairs) / sum(lam for lam, _ in pairs)
        assert period["modeled_wait"] == pytest.approx(expected)
        assert period["observed_wait"] > period["modeled_wait"]


def test_novamart_comparison_reports_bases_and_observed(db_engine, client):
    analysis_id = _novamart(db_engine, client, "nmc@example.com")
    body = _comparison(client, analysis_id).json()
    current = body["current"]
    assert current["wait_basis_kind"] == "analytical"
    assert current["observed_wait_flagged_any"] is True
    assert len(current["periods"]) == 13
    unflagged = {period["time"] for period in current["periods"] if not period["observed_flag"]}
    assert unflagged == set(NOVAMART_UNFLAGGED)
    for period in current["periods"]:
        assert period["observed_wait"] > period["wait_mean"]
        if period["time"] in NOVAMART_UNFLAGGED:
            observed, modeled = NOVAMART_UNFLAGGED[period["time"]]
            assert _minutes(period["observed_wait"]) == pytest.approx(observed, abs=0.01)
            assert _minutes(period["wait_mean"]) == pytest.approx(modeled, abs=0.01)
    forbidden = {"wait_delta", "wait_difference", "wait_improvement", "wait_savings"}
    assert not forbidden & set(current)
    for plan in body["plans"]:
        assert plan["wait_basis_kind"] in {"simulation", None}
        assert not forbidden & set(plan) and not forbidden & set(plan["totals"] or {})


# --- API: aggregate uploads have no observed wait ------------------------------------

def test_aggregate_shared_upload_has_no_observed_wait(db_engine, client):
    analysis_id, _ = _shared_workspace(db_engine)
    login(client, "owner@example.com", "pw")
    body = client.get(f"/analyses/{analysis_id}/workflow/observed-wait",
                      headers=csrf_header(client)).json()
    assert body["available"] is False
    assert body["periods"] == []
    assert body["flagged_any"] is False


def test_aggregate_separate_comparison_has_no_observed_wait_and_states_bases(db_engine, client):
    analysis_id, _, scenario_id = _separate_workspace(db_engine, "agg@example.com")
    login(client, "agg@example.com", "pw")
    body = _comparison(client, analysis_id).json()
    current = body["current"]
    assert current["wait_basis_kind"] == "analytical"
    assert current["observed_wait_available"] is False
    assert current["observed_wait_ratio"] == OBSERVED_WAIT_FLAG_RATIO
    assert current["observed_wait_min_gap_minutes"] == OBSERVED_WAIT_FLAG_MIN_GAP_MINUTES
    assert current["observed_wait_flagged_any"] is False
    for period in current["periods"]:
        assert period["observed_wait"] is None
        assert period["observed_flag"] is False
    plan = next(p for p in body["plans"] if p["scenario_id"] == scenario_id)
    assert plan["wait_basis_kind"] == "simulation"
    # No cross-basis difference is ever computed.
    forbidden = {"wait_delta", "wait_difference", "wait_improvement", "wait_savings"}
    assert not forbidden & set(plan) and not forbidden & set(plan["totals"] or {})
    assert not forbidden & set(current)


def test_observed_wait_requires_a_dataset(db_engine, client):
    create_user(db_engine, "none@example.com", "pw")
    login(client, "none@example.com", "pw")
    analysis = _analysis(client)
    response = client.get(f"/analyses/{analysis['id']}/workflow/observed-wait",
                          headers=csrf_header(client))
    assert response.status_code == 404


# --- Reports: modeled wording only -----------------------------------------------------

def test_separate_excel_current_sheet_labels_modeled_wait():
    import openpyxl

    from backend.reports.report_export import generate_separate_excel_report
    from backend.reports.separate_report import build_separate_report_model
    from tests.test_separate_report import _chain

    workbook = openpyxl.load_workbook(
        generate_separate_excel_report(build_separate_report_model(_chain())))
    header = [cell.value for cell in workbook["Current"][1]]
    assert "Wq, modeled (min)" in header
