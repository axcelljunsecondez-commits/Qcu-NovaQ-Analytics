"""Simulation run totals added up on the server (B12 pattern for Queue simulation, spec §7.8 D30).

The Key results cards (average wait, longest line, customers served, still in the system at
closing) must never be summed in the browser. A continuous day reports customers; a run that
simulates each period on its own reports only the served-weighted wait and the longest line.

Data: SYNTHETIC (rates, setups and service samples made for the test).
"""

from __future__ import annotations

import math

import pytest

import backend.api.workflow as workflow_api
from backend.api.workflow import _run_summary
from backend.queueing_engine.services import separate_optimization as sep
from tests.helpers import create_user, csrf_header, login, make_sessionmaker
from tests.test_b5_break_events import _plan
from tests.test_separate_day_des import _period
from tests.test_separate_day_feasibility import _setup


def test_the_day_run_counts_customers_still_in_the_system_at_closing():
    result = sep.run_routing_day_des([_period("s1", 0.0, 1.0, ["a", "b", "c"], lam=30.0),
                                      _period("s2", 1.0, 2.0, ["a", "b"], lam=30.0)],
                                     tie_order=["a", "b", "c"], seed=5, max_events=100000)
    ends = {e["customer_id"]: e["t"] for e in result["trace_events"] if e["type"] == "service_end"}
    arrived = {e["customer_id"]: e["t"] for e in result["trace_events"] if e["type"] == "arrival"}
    expected = sum(1 for customer, t in arrived.items() if t <= 2.0 and ends[customer] > 2.0)
    assert result["in_system_at_close"] == expected > 0
    assert result["admitted"] == result["served"]  # everyone is still finished after closing


def test_a_continuous_day_summary_is_added_up_from_the_run():
    result = workflow_api._run_selected_plan_des(_plan(_setup()), seed=7)
    summary = _run_summary(result)
    rows = [row for period in result["periods"] for row in period["results"]]
    served = [row for row in rows if row["served"]]
    assert summary["basis"] == "continuous_day"
    assert summary["arrivals"] == result["admitted"] == sum(row["arrivals"] for row in rows)
    assert summary["served"] == result["served"]
    assert summary["in_system_at_close"] == result["in_system_at_close"]
    assert summary["average_wait_hours"] == pytest.approx(
        math.fsum(row["Wq_sim"] * row["served"] for row in served) / sum(row["served"] for row in served))
    assert summary["longest_line"] == max(row["max_queue"] for row in rows)
    assert [p["time"] for p in summary["periods"]] == [p["time"] for p in result["periods"]]
    for period, totals in zip(result["periods"], summary["periods"], strict=True):
        assert totals["arrivals"] == sum(row["arrivals"] for row in period["results"])
        assert totals["longest_line"] == max(row["max_queue"] for row in period["results"])


def test_a_period_by_period_run_reports_no_customer_totals():
    # Without operating segments a per-date plan still runs each period on its own (OD-B13-3).
    plan = _plan({**_setup(basis="per_date"), "segments": [], "breaks": []})
    plan["duration_hours"] = 24.0
    summary = _run_summary(workflow_api._run_selected_plan_des(plan, seed=7))
    assert summary["basis"] == "per_period"
    assert (summary["arrivals"], summary["served"], summary["in_system_at_close"]) == (None, None, None)
    assert all(p["arrivals"] is None and p["served"] is None for p in summary["periods"])
    assert summary["average_wait_hours"] is not None
    # Even a per-period result that carried day-level counts must not report them as one day.
    relabelled = _run_summary({**workflow_api._run_selected_plan_des(plan, seed=7), "served": 99, "admitted": 99})
    assert (relabelled["arrivals"], relabelled["served"]) == (None, None)


def test_an_unknown_wait_is_never_averaged_away():
    result = {"results": [
        {"time": "08:00", "served": 10, "Wq_sim": 0.1, "max_queue": 3},
        {"time": "08:00", "served": 5, "Wq_sim": None, "max_queue": 7},
        {"time": "09:00", "served": 0, "Wq_sim": None, "max_queue": 0},
    ]}
    summary = _run_summary(result)
    assert summary["average_wait_hours"] is None
    assert summary["longest_line"] == 7
    assert summary["periods"][0]["average_wait_hours"] is None
    assert summary["periods"][1] == {"time": "09:00", "average_wait_hours": None, "longest_line": 0,
                                     "arrivals": None, "served": None}


def test_the_current_run_endpoint_stores_a_summary(db_engine, client):
    from backend.db.models import AnalysisProject, Dataset

    user = create_user(db_engine, "owner@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Branch", setup_status="ready", queue_setup_json={
            "queue_structure": "shared_queue", "fixed_server_count": 2, "staffing_varies_by_period": False,
            "capacity_mode": "unlimited", "abandonment_mode": "not_modeled"})
        db.add(analysis)
        db.flush()
        db.add(Dataset(user_id=user.id, analysis_id=analysis.id, name="rates", source_filename="rates.csv",
                       source_format="csv", row_count=2, validation_report_json={"ok": True, "message": "ok"},
                       normalized_json=[{"time": "08:00-09:00", "lambda": 6, "mu": 4, "c": 2},
                                        {"time": "09:00-10:00", "lambda": 3, "mu": 4, "c": 2}]))
        db.commit()
        analysis_id = analysis.id
    assert login(client, "owner@example.com", "pw") == 200
    response = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/current", headers=csrf_header(client),
                           json={"sim_hours": 2, "max_events": 200, "seed": 7})
    assert response.status_code == 200, response.text
    summary = response.json()["evidence"]["result"]["summary"]
    assert summary["basis"] == "per_period"
    assert [p["time"] for p in summary["periods"]] == ["08:00-09:00", "09:00-10:00"]
    assert summary["served"] is None and summary["longest_line"] is not None
