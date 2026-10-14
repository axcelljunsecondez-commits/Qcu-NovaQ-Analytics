"""OD-UX-13: a shared Decision from the full-day run and Many variations.

Spec: docs/superpowers/specs/2026-10-13-od-ux-13-full-day-decision.md (owner: rule "Day run + Monte Carlo",
basis "Full-day run first"). Data: SYNTHETIC (rates and plans made for the test).
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from sqlalchemy import select

from backend.api import shared_continuous, workflow
from backend.db.models import AnalysisProject, Dataset, Job, Scenario
from backend.queueing_engine.simulation.shared_replications import run_shared_replications
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

SETUP = {"queue_structure": "shared_queue", "fixed_server_count": 2, "staffing_varies_by_period": False,
         "capacity_mode": "unlimited", "total_system_capacity": None, "abandonment_mode": "not_modeled",
         "patience_rate_per_hour": None}
ROWS: list[dict[str, Any]] = [{"time": "08:00-09:00", "lambda": 4.0, "mu": 6.0, "c": 2},
        {"time": "09:00-10:00", "lambda": 9.0, "mu": 6.0, "c": 2}]


def _plan_rows(targets: tuple[float | None, float | None]) -> list[dict[str, Any]]:
    rows = []
    for row, c_optimal, rho, target in zip(ROWS, (1, 2), (4 / 6, 0.75), targets):
        rows.append({"time": row["time"], "lambda": row["lambda"], "mu": 6.0, "c_current": 2, "c_optimal": c_optimal,
                     "rho_current": row["lambda"] / 12, "rho_optimal": rho, "Wq_current": 0.01, "Wq_optimal": 0.1,
                     "Lq_current": 0.04, "Lq_optimal": 0.4, "cost_current": 300.0, "cost_optimal": 250.0,
                     "current_stable": True, "optimized_stable": True,
                     **({"effective_constraints": {"target_utilization": target}} if target is not None else {})})
    return rows


def _signed_in(db_engine, client, email="day@example.com", targets=(0.95, 0.95)) -> dict[str, int]:
    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Line", queue_setup_json=SETUP, setup_status="ready")
        db.add(analysis)
        db.flush()
        dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="Rates", source_filename="rates.csv",
                          source_format="csv", row_count=2, normalized_json=ROWS,
                          validation_report_json={"ok": True, "message": "Input data is valid."})
        db.add(dataset)
        db.flush()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id, name="Day plan",
            settings_json={"calculation": {"schema_version": 1, "engine_version": "novaq-2026-09-system-v2",
                                           "input_segments": ROWS, "options": {}, "what_if_multiplier": 1,
                                           "calculated_at": "2026-10-13T00:00:00+00:00"}},
            results_json={"results": _plan_rows(targets)})
        db.add(scenario)
        db.commit()
        ids = {"analysis_id": analysis.id, "scenario_id": scenario.id, "dataset_id": dataset.id}
    assert login(client, email, "pw") == 200
    headers = csrf_header(client)
    assert client.put(f"/analyses/{ids['analysis_id']}/closing-policy", headers=headers,
                      json={"closing_policy": "DRAIN"}).status_code == 200
    assert client.post(f"/analyses/{ids['analysis_id']}/workflow/selection", headers=headers,
                       json={"scenario_id": ids["scenario_id"]}).status_code == 200
    return ids


def _post(client, path: str, body: dict | None = None):
    response = client.post(path, headers=csrf_header(client), json=body if body is not None else {})
    assert response.status_code in (200, 201), response.text
    return response.json()


def _day_run(client, analysis_id: int, seed: int = 5) -> dict[str, Any]:
    return _post(client, f"/analyses/{analysis_id}/continuous/runs", {"plan": "suggested", "replications": 5, "seed": seed})


def _variations(client, analysis_id: int, threshold: float = 1.0, cap: float = 0.05) -> dict[str, Any]:
    return _post(client, f"/analyses/{analysis_id}/workflow/simulation/mc",
                 {"num_trials": 2000, "failure_threshold": threshold, "failure_rate_cap": cap, "seed": 3})


def _decide(client, analysis_id: int) -> dict[str, Any]:
    return _post(client, f"/analyses/{analysis_id}/workflow/decision")["decision"]


def _workflow(client, analysis_id: int) -> dict[str, Any]:
    return client.get(f"/analyses/{analysis_id}/workflow").json()


def test_the_run_keeps_per_period_server_hours_that_add_up_to_each_repeat():
    from backend.queueing_engine.services.shared_segments import (
        OperatingHorizon,
        timeline_from_aggregate_rows,
        validate_timeline,
    )

    periods, segments = timeline_from_aggregate_rows(ROWS)
    horizon = OperatingHorizon(480, 600)
    validate_timeline(horizon, periods, segments)
    result = run_shared_replications(horizon, periods, segments, replications=4, seed=9, closing_policy="DRAIN")
    by_period = result["period_utilization"]["segments"]
    assert [segment["segment_id"] for segment in by_period] == ["08:00-09:00", "09:00-10:00"]
    for index, row in enumerate(result["replications"]):
        assert math.fsum(segment["busy_server_hours"][index] for segment in by_period) == pytest.approx(
            row["busy_server_hours_in_horizon"], rel=1e-12)
        assert math.fsum(segment["present_server_hours"][index] for segment in by_period) == pytest.approx(
            row["available_server_hours_in_horizon"], rel=1e-12)
    for segment in by_period:
        values = [b / p for b, p in zip(segment["busy_server_hours"], segment["present_server_hours"])]
        assert segment["utilization"] == values
        assert segment["summary"]["mean"] == pytest.approx(math.fsum(values) / len(values))


def test_a_passing_plan_is_decided_from_the_full_day_run(db_engine, client):
    ids = _signed_in(db_engine, client)
    analysis_id = ids["analysis_id"]
    assert _workflow(client, analysis_id)["decision_basis"] == "period_by_period"
    run = _day_run(client, analysis_id)["evidence"]
    assert run["params"]["period_labels"] == {"08:00-09:00": "08:00-09:00", "09:00-10:00": "09:00-10:00"}
    state = _workflow(client, analysis_id)
    assert state["decision_basis"] == "full_day_run" and state["full_day_run_id"] == run["id"]
    variations = _variations(client, analysis_id)["evidence"]
    decision = _decide(client, analysis_id)
    assert decision["basis"] == "full_day_run" and decision["status"] == "adopt", decision
    assert decision["evidence_ids"] == {"selection": state["selection"]["id"], "des": None, "mc": variations["id"],
                                        "validation": None, "continuous": run["id"]}
    periods = decision["facts"]["periods"]
    assert [period["verdict"] for period in periods] == ["pass", "pass"]
    stored = {segment["segment_id"]: segment["summary"]["mean"]
              for segment in run["result"]["period_utilization"]["segments"]}
    assert [period["day_run_utilization"] for period in periods] == [stored["08:00-09:00"], stored["09:00-10:00"]]
    assert decision["facts"]["full_day_run"] == {"id": run["id"], "replications": 5, "closing_policy": "DRAIN",
                                                 "service_model": "exponential"}
    after = _workflow(client, analysis_id)
    assert after["decision_stale"] is False and after["decision"]["result"]["status"] == "adopt"


def test_a_period_busier_than_the_target_in_the_day_run_fails_even_when_variations_pass(db_engine, client):
    # The day starts empty and 08:00-09:00 is one hour, so its simulated busy share is below the
    # steady-state 4/6 (0.296 over these five repeats with seed 5): the target is set below it.
    ids = _signed_in(db_engine, client, email="busy@example.com", targets=(0.1, 0.95))
    run = _day_run(client, ids["analysis_id"])["evidence"]
    first = next(s for s in run["result"]["period_utilization"]["segments"] if s["segment_id"] == "08:00-09:00")
    assert first["summary"]["mean"] > 0.1
    _variations(client, ids["analysis_id"])
    decision = _decide(client, ids["analysis_id"])
    assert decision["status"] == "revise" and decision["facts"]["failed_periods"] == ["08:00-09:00"]
    period = decision["facts"]["periods"][0]
    assert (period["day_run"], period["variations"], period["verdict"]) == ("fail", "pass", "fail")


def test_many_variations_failing_gives_revise(db_engine, client):
    ids = _signed_in(db_engine, client, email="vary@example.com")
    _day_run(client, ids["analysis_id"])
    _variations(client, ids["analysis_id"], threshold=0.5)  # every variation is busier than half
    decision = _decide(client, ids["analysis_id"])
    assert decision["status"] == "revise"
    assert [p["variations"] for p in decision["facts"]["periods"]] == ["fail", "fail"]
    assert [p["day_run"] for p in decision["facts"]["periods"]] == ["pass", "pass"]


def test_missing_evidence_is_named(db_engine, client):
    ids = _signed_in(db_engine, client, email="missing@example.com")
    _day_run(client, ids["analysis_id"])
    decision = _decide(client, ids["analysis_id"])
    assert decision["status"] == "insufficient_evidence" and decision["basis"] == "full_day_run"
    assert decision["missing_evidence"] == ["a completed Many variations run for the selected plan"]


def test_a_plan_without_a_recorded_target_cannot_be_told(db_engine, client):
    ids = _signed_in(db_engine, client, email="target@example.com", targets=(None, 0.95))
    _day_run(client, ids["analysis_id"])
    _variations(client, ids["analysis_id"])
    decision = _decide(client, ids["analysis_id"])
    assert decision["status"] == "insufficient_evidence"
    assert decision["facts"]["insufficient_periods"] == ["08:00-09:00"]


def test_a_run_saved_before_period_results_asks_for_a_new_run(db_engine, client):
    ids = _signed_in(db_engine, client, email="old@example.com")
    run_id = _day_run(client, ids["analysis_id"])["evidence"]["id"]
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, run_id)
        job.result_json = {key: value for key, value in job.result_json.items() if key != "period_utilization"}
        db.commit()
    _variations(client, ids["analysis_id"])
    decision = _decide(client, ids["analysis_id"])
    assert decision["missing_evidence"] == ["a full-day run with results by period (run the full day again)"]


def test_the_basis_and_the_staleness_follow_the_eligible_run(db_engine, client):
    ids = _signed_in(db_engine, client, email="stale@example.com")
    analysis_id = ids["analysis_id"]
    _post(client, f"/analyses/{analysis_id}/workflow/simulation/validation",
          {"des_sim_hours": 4, "mc_trials": 500, "mc_failure_threshold": 1, "mc_failure_rate_cap": 1, "seed": 7})
    _post(client, f"/analyses/{analysis_id}/workflow/simulation/des", {"sim_hours": 4, "max_events": 50, "seed": 7})
    period_decision = _decide(client, analysis_id)
    assert period_decision["basis"] == "period_by_period"
    assert _workflow(client, analysis_id)["decision_stale"] is False
    _day_run(client, analysis_id)  # "Full-day run first": the period Decision is no longer the one to use
    assert _workflow(client, analysis_id)["decision_stale"] is True
    _variations(client, analysis_id)
    assert _decide(client, analysis_id)["basis"] == "full_day_run"
    assert _workflow(client, analysis_id)["decision_stale"] is False
    _day_run(client, analysis_id, seed=6)  # a newer run of the plan replaces the one decided on
    state = _workflow(client, analysis_id)
    assert state["decision_stale"] is True and state["decision"] is None
    _decide(client, analysis_id)
    with make_sessionmaker(db_engine)() as db:  # a Setup change makes the run ineligible
        analysis = db.get(AnalysisProject, analysis_id)
        analysis.queue_setup_json = {**SETUP, "fixed_server_count": 3}
        db.commit()
    state = _workflow(client, analysis_id)
    assert state["decision_basis"] == "period_by_period" and state["full_day_run_id"] is None


def test_a_run_for_another_plan_or_the_current_staffing_is_not_eligible(db_engine, client):
    ids = _signed_in(db_engine, client, email="other@example.com")
    _post(client, f"/analyses/{ids['analysis_id']}/continuous/runs", {"plan": "current", "replications": 2, "seed": 1})
    assert _workflow(client, ids["analysis_id"])["decision_basis"] == "period_by_period"
    with make_sessionmaker(db_engine)() as db:
        run = db.execute(select(Job).where(Job.kind == shared_continuous.JOB_KIND)).scalars().first()
        params = dict(run.params_json)
        run.params_json = {**params, "plan": "suggested", "scenario_id": ids["scenario_id"] + 1000}
        db.commit()
    assert _workflow(client, ids["analysis_id"])["decision_basis"] == "period_by_period"


def test_a_day_run_failure_is_not_hidden_by_too_few_variations(db_engine, client):
    ids = _signed_in(db_engine, client, email="few@example.com", targets=(0.1, 0.95))
    _day_run(client, ids["analysis_id"])
    _post(client, f"/analyses/{ids['analysis_id']}/workflow/simulation/mc",
          {"num_trials": 10, "failure_threshold": 1.0, "failure_rate_cap": 0.05, "seed": 3})  # too few to be adequate
    decision = _decide(client, ids["analysis_id"])
    first = decision["facts"]["periods"][0]
    assert (first["day_run"], first["variations"], first["verdict"]) == ("fail", "insufficient", "fail")
    assert decision["status"] == "revise"


def test_a_run_of_an_earlier_version_of_the_plan_or_of_todays_staffing_is_not_eligible(db_engine, client):
    ids = _signed_in(db_engine, client, email="version@example.com")
    run_id = _day_run(client, ids["analysis_id"])["evidence"]["id"]
    assert _workflow(client, ids["analysis_id"])["full_day_run_id"] == run_id
    with make_sessionmaker(db_engine)() as db:
        scenario = db.get(Scenario, ids["scenario_id"])
        job = db.get(Job, run_id)
        job.params_json = {**job.params_json, "plan": "current"}  # today's staffing, though it names the plan
        db.commit()
    assert _workflow(client, ids["analysis_id"])["full_day_run_id"] is None
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, run_id)
        job.params_json = {**job.params_json, "plan": "suggested", "scenario_generation": "0" * 32}
        db.commit()
        assert scenario.generation != "0" * 32
    assert _workflow(client, ids["analysis_id"])["full_day_run_id"] is None


def test_a_run_newer_than_the_decision_makes_it_stale(db_engine, client):
    from datetime import timedelta

    ids = _signed_in(db_engine, client, email="order@example.com")
    run_id = _day_run(client, ids["analysis_id"])["evidence"]["id"]
    _variations(client, ids["analysis_id"])
    _decide(client, ids["analysis_id"])
    assert _workflow(client, ids["analysis_id"])["decision_stale"] is False
    with make_sessionmaker(db_engine)() as db:  # the same id now names a record made after the Decision
        job = db.get(Job, run_id)
        job.created_at = job.created_at + timedelta(days=1)
        db.commit()
    assert _workflow(client, ids["analysis_id"])["decision_stale"] is True


def test_the_run_kind_named_in_workflow_is_the_full_day_run_kind():
    assert workflow.FULL_DAY_RUN_KIND == shared_continuous.JOB_KIND
