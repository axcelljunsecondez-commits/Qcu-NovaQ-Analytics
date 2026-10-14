"""B4a: the continuous shared-line run (preview) for ordinary analyses.

Spec: docs/superpowers/specs/2026-10-09-b4a-continuous-shared-run-preview.md (owner answers OD-B4a-1..3 = A),
section 7 tests 2-8. The engine is unchanged (its own pin tests cover test 1); mutation testing (test 9)
runs from the session scratchpad.

Data: SYNTHETIC (rates, setups and plans made for the test).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select

from backend.api import shared_continuous
from backend.api.scenarios import setup_fingerprint
from backend.db.models import AnalysisProject, Dataset, Job, Scenario, User
from backend.queueing_engine.simulation.shared_playback import playback_from_replications
from tests.helpers import clear_cookies, create_user, csrf_header, login, make_sessionmaker

SHARED_SETUP = {
    "queue_structure": "shared_queue",
    "fixed_server_count": 1,
    "staffing_varies_by_period": False,
    "capacity_mode": "unlimited",
    "total_system_capacity": None,
    "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None,
}
ROWS = [
    {"time": "08:00-09:00", "lambda": 4.0, "mu": 6.0, "c": 1},
    {"time": "09:00-10:00", "lambda": 9.0, "mu": 6.0, "c": 1},
]
PLAN_RESULTS = [
    {"time": "08:00-09:00", "lambda_": 4.0, "mu": 6.0, "c_current": 1, "c_optimal": 1, "rho_current": 0.67,
     "rho_optimal": 0.67, "Wq_current": 0.33, "Wq_optimal": 0.33, "Lq_current": 1.33, "Lq_optimal": 1.33,
     "cost_current": 100, "cost_optimal": 100, "current_stable": True, "optimized_stable": True},
    {"time": "09:00-10:00", "lambda_": 9.0, "mu": 6.0, "c_current": 1, "c_optimal": 2, "rho_current": 1.5,
     "rho_optimal": 0.75, "Wq_current": None, "Wq_optimal": 0.16, "Lq_current": None, "Lq_optimal": 1.43,
     "cost_current": 5000, "cost_optimal": 300, "current_stable": False, "optimized_stable": True},
]


def _workspace(db_engine, *, email: str = "owner@example.com", setup: dict | None = None,
               rows: list[dict] | None = None, plan: bool = True) -> dict[str, int]:
    with make_sessionmaker(db_engine)() as db:
        existing = db.execute(select(User).where(User.email_normalized == email)).scalar_one_or_none()
    user = existing or create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Shared line", queue_setup_json=setup or SHARED_SETUP,
                                   setup_status="ready")
        db.add(analysis)
        db.flush()
        data = rows if rows is not None else ROWS
        dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="Rates", source_filename="rates.csv",
                          source_format="csv", row_count=len(data), normalized_json=data,
                          validation_report_json={"ok": True, "message": "Input data is valid."})
        db.add(dataset)
        db.flush()
        ids = {"user_id": user.id, "analysis_id": analysis.id, "dataset_id": dataset.id}
        if plan:
            scenario = Scenario(
                user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id, name="Two at nine",
                settings_json={"calculation": {
                    "schema_version": 1, "engine_version": "novaq-2026-09-system-v2", "input_segments": data,
                    "options": {}, "what_if_multiplier": 1, "calculated_at": "2026-10-12T00:00:00+00:00"}},
                results_json={"results": PLAN_RESULTS},
            )
            db.add(scenario)
            db.flush()
            ids["scenario_id"] = scenario.id
        db.commit()
        return ids


def _signed_in(client, db_engine, **options: Any) -> dict[str, int]:
    ids = _workspace(db_engine, **options)
    assert login(client, options.get("email", "owner@example.com"), "pw") == 200
    return ids


def _choose_rule(client, analysis_id: int, rule: str = "DRAIN") -> None:
    response = client.put(f"/analyses/{analysis_id}/closing-policy", headers=csrf_header(client),
                          json={"closing_policy": rule})
    assert response.status_code == 200, response.text


def _select_plan(client, ids: dict[str, int]) -> None:
    response = client.post(f"/analyses/{ids['analysis_id']}/workflow/selection", headers=csrf_header(client),
                           json={"scenario_id": ids["scenario_id"]})
    assert response.status_code == 200, response.text


def _compat(client, analysis_id: int) -> dict[str, Any]:
    response = client.post(f"/analyses/{analysis_id}/continuous/compatibility", headers=csrf_header(client), json={})
    assert response.status_code == 200, response.text
    return response.json()


def _run(client, analysis_id: int, **body: Any):
    return client.post(f"/analyses/{analysis_id}/continuous/runs", headers=csrf_header(client),
                       json={"plan": "current", **body})


def _job_count(db_engine) -> int:
    with make_sessionmaker(db_engine)() as db:
        return db.execute(select(func.count()).select_from(Job).where(Job.kind == shared_continuous.JOB_KIND)).scalar_one()


def _codes(plan: dict[str, Any]) -> list[str]:
    return [reason["code"] for reason in plan["reasons"]]


# ── Closing rule (OD-B4a-1 A) ───────────────────────────────────────────────


def test_the_closing_rule_starts_unchosen_and_is_saved_outside_the_setup(db_engine, client):
    ids = _signed_in(client, db_engine)
    _select_plan(client, ids)
    before = client.get(f"/analyses/{ids['analysis_id']}/closing-policy").json()
    assert before["closing_policy"] is None
    assert [choice["value"] for choice in before["choices"]] == ["DRAIN", "HARD_CUTOFF"]
    with make_sessionmaker(db_engine)() as db:
        fingerprint = setup_fingerprint(db.get(AnalysisProject, ids["analysis_id"]).queue_setup_json)
    _choose_rule(client, ids["analysis_id"], "HARD_CUTOFF")
    assert client.get(f"/analyses/{ids['analysis_id']}/closing-policy").json()["closing_policy"] == "HARD_CUTOFF"
    with make_sessionmaker(db_engine)() as db:
        assert setup_fingerprint(db.get(AnalysisProject, ids["analysis_id"]).queue_setup_json) == fingerprint
    # Existing evidence stays current: the selected plan is still served by the workflow.
    workflow = client.get(f"/analyses/{ids['analysis_id']}/workflow").json()
    assert workflow["scenario"]["id"] == ids["scenario_id"]


def test_an_unknown_closing_rule_is_refused(db_engine, client):
    ids = _signed_in(client, db_engine)
    response = client.put(f"/analyses/{ids['analysis_id']}/closing-policy", headers=csrf_header(client),
                          json={"closing_policy": "drain"})
    assert response.status_code == 422
    assert client.get(f"/analyses/{ids['analysis_id']}/closing-policy").json()["closing_policy"] is None


# ── Compatibility (test 2) ──────────────────────────────────────────────────


def test_a_compatible_analysis_reports_its_expected_customers(db_engine, client):
    ids = _signed_in(client, db_engine)
    _choose_rule(client, ids["analysis_id"])
    _select_plan(client, ids)
    compat = _compat(client, ids["analysis_id"])
    assert compat["plans"]["current"]["compatible"] is True
    assert compat["plans"]["current"]["expected_customers_per_day"] == pytest.approx(13.0)  # 4 x 1 h + 9 x 1 h
    assert compat["plans"]["current"]["horizon"] == {"start_minute": 480, "end_minute": 600}
    assert compat["plans"]["suggested"]["compatible"] is True
    assert compat["plans"]["suggested"]["scenario_id"] == ids["scenario_id"]
    assert compat["closing_policy"] == "DRAIN"
    assert compat["default_replications"] == 5
    assert compat["limits"]["max_expected_customers_per_run"] == 2900


@pytest.mark.parametrize(("setup_change", "row_change", "code"), [
    ({"queue_structure": "separate_queues", "queue_ids": ["a"]}, {}, "separate_lines"),
    ({}, {"variance": 0.01}, "service_time_variation"),
    ({}, {"K": 5}, "capacity_or_abandonment"),
    ({"abandonment_mode": "modeled", "patience_rate_per_hour": 2.0}, {}, "capacity_or_abandonment"),
    ({"capacity_mode": "finite", "total_system_capacity": 9, "abandonment_mode": "unknown"}, {}, "capacity_or_abandonment"),
    ({"capacity_mode": "unknown"}, {}, "capacity_or_abandonment_unknown"),
    ({"abandonment_mode": "unknown"}, {}, "capacity_or_abandonment_unknown"),
])
def test_out_of_scope_analyses_are_refused_with_their_code(db_engine, client, setup_change, row_change, code):
    ids = _signed_in(client, db_engine, setup={**SHARED_SETUP, **setup_change},
                     rows=[{**row, **row_change} for row in ROWS], plan=False)
    _choose_rule(client, ids["analysis_id"])
    compat = _compat(client, ids["analysis_id"])
    assert compat["plans"]["current"]["compatible"] is False
    assert code in _codes(compat["plans"]["current"])
    if code == "capacity_or_abandonment_unknown":  # F12: an unanswered question is not reported as an enabled feature
        assert "capacity_or_abandonment" not in _codes(compat["plans"]["current"])
    response = _run(client, ids["analysis_id"])
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "not_compatible"
    assert _job_count(db_engine) == 0


def test_a_gap_between_periods_is_refused_with_the_engine_message(db_engine, client):
    ids = _signed_in(client, db_engine, rows=[ROWS[0], {**ROWS[1], "time": "09:30-10:00"}], plan=False)
    _choose_rule(client, ids["analysis_id"])
    current = _compat(client, ids["analysis_id"])["plans"]["current"]
    reason = next(item for item in current["reasons"] if item["code"] == "timeline_invalid")
    assert any("09:00" in problem for problem in reason["problems"])
    assert _run(client, ids["analysis_id"]).status_code == 422
    assert _job_count(db_engine) == 0


def test_no_closing_rule_and_no_plan_are_each_named(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    compat = _compat(client, ids["analysis_id"])
    assert "no_closing_policy" in _codes(compat["plans"]["current"])
    assert "no_selected_plan" in _codes(compat["plans"]["suggested"])
    assert _run(client, ids["analysis_id"]).status_code == 422
    assert _run(client, ids["analysis_id"], plan="suggested").status_code == 422
    assert _job_count(db_engine) == 0


def test_a_review_only_file_is_never_run(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    with make_sessionmaker(db_engine)() as db:
        db.get(Dataset, ids["dataset_id"]).purpose = "review"
        db.commit()
    _choose_rule(client, ids["analysis_id"])
    assert "no_planning_dataset" in _codes(_compat(client, ids["analysis_id"])["plans"]["current"])
    assert _run(client, ids["analysis_id"]).status_code == 422


# ── Staffing sources (test 3) and stored runs (tests 4, 5) ──────────────────


def test_current_and_suggested_take_their_counters_from_the_data_and_the_plan(db_engine, client):
    ids = _signed_in(client, db_engine)
    _choose_rule(client, ids["analysis_id"])
    _select_plan(client, ids)
    current = _run(client, ids["analysis_id"], replications=2, seed=7)
    suggested = _run(client, ids["analysis_id"], plan="suggested", replications=2, seed=7)
    assert current.status_code == 200, current.text
    assert suggested.status_code == 200, suggested.text
    staffing = {
        name: [item["servers"] for item in response.json()["evidence"]["result"]["provenance"]["inputs"]["staffing_segments"]]
        for name, response in (("current", current), ("suggested", suggested))
    }
    assert staffing == {"current": [1, 1], "suggested": [1, 2]}
    params = suggested.json()["evidence"]["params"]
    assert params["plan"] == "suggested" and params["scenario_id"] == ids["scenario_id"]
    assert current.json()["evidence"]["params"]["scenario_id"] is None


def test_a_stored_run_keeps_the_closing_rule_it_used(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    _choose_rule(client, ids["analysis_id"], "HARD_CUTOFF")
    run = _run(client, ids["analysis_id"], replications=1).json()["evidence"]
    _choose_rule(client, ids["analysis_id"], "DRAIN")
    stored = client.get(f"/analyses/{ids['analysis_id']}/continuous/runs/{run['id']}").json()
    assert stored["evidence"]["params"]["closing_policy"] == "HARD_CUTOFF"
    assert stored["evidence"]["result"]["provenance"]["closing_policy"] == "HARD_CUTOFF"
    listed = client.get(f"/analyses/{ids['analysis_id']}/continuous/runs").json()["runs"]
    assert [(item["id"], item["closing_policy"]) for item in listed] == [(run["id"], "HARD_CUTOFF")]


def test_the_same_seed_gives_the_same_summary_and_the_same_replay(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    _choose_rule(client, ids["analysis_id"])
    first = _run(client, ids["analysis_id"], replications=3, seed=11).json()["evidence"]
    second = _run(client, ids["analysis_id"], replications=3, seed=11).json()["evidence"]
    assert first["result"]["summary"] == second["result"]["summary"]
    replays = [client.get(f"/analyses/{ids['analysis_id']}/continuous/runs/{run['id']}/replications/1/playback").json()
               for run in (first, second)]
    assert replays[0]["playback"]["events"] == replays[1]["playback"]["events"]
    assert replays[0]["playback"] == playback_from_replications(first["result"], 1)


def test_the_replay_totals_by_period_add_up_to_the_stored_day(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    _choose_rule(client, ids["analysis_id"])
    run = _run(client, ids["analysis_id"], replications=2, seed=3).json()["evidence"]
    body = client.get(f"/analyses/{ids['analysis_id']}/continuous/runs/{run['id']}/replications/0/playback").json()
    periods = body["by_period"]
    assert [period["period_id"] for period in periods] == ["08:00-09:00", "09:00-10:00"]
    row = run["result"]["replications"][0]
    assert sum(period["arrivals"] for period in periods) == row["arrivals"]
    assert sum(period["served"] for period in periods) == row["served"]
    waits = [c for c in body["playback"]["customers"] if c["wait_hours"] is not None and c["arrival_hours"] < 1.0]
    first = periods[0]
    expected = sum(c["wait_hours"] for c in waits) / len(waits) if waits else None
    assert first["mean_wait_hours"] == pytest.approx(expected)


def test_a_missing_replication_is_not_found(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    _choose_rule(client, ids["analysis_id"])
    run = _run(client, ids["analysis_id"], replications=1).json()["evidence"]
    response = client.get(f"/analyses/{ids['analysis_id']}/continuous/runs/{run['id']}/replications/1/playback")
    assert response.status_code == 404


# ── Limits (test 6) ─────────────────────────────────────────────────────────


def test_one_customer_over_the_cap_is_refused_before_simulating(db_engine, client, monkeypatch):
    ids = _signed_in(client, db_engine, rows=[{**ROWS[0], "lambda": 2900.0, "mu": 3000.0, "c": 1}], plan=False)
    _choose_rule(client, ids["analysis_id"])
    called: list[int] = []
    monkeypatch.setattr(shared_continuous, "run_shared_replications", lambda *a, **k: called.append(1))
    response = _run(client, ids["analysis_id"], replications=2)
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "limit_exceeded", "limit": "expected_customers", "value": 5800.0,
                                         "max": 2900, "replications": 2, "max_replications": 1}
    assert called == [] and _job_count(db_engine) == 0


@pytest.mark.parametrize("replications", [0, 10])
def test_repeats_outside_one_to_nine_are_refused(db_engine, client, replications):
    ids = _signed_in(client, db_engine, plan=False)
    _choose_rule(client, ids["analysis_id"])
    assert _run(client, ids["analysis_id"], replications=replications).status_code == 422
    assert _job_count(db_engine) == 0


def test_a_result_over_the_byte_cap_is_refused_and_not_stored(db_engine, client, app, monkeypatch):
    ids = _signed_in(client, db_engine, plan=False)
    _choose_rule(client, ids["analysis_id"])
    monkeypatch.setattr(app.state.settings, "result_jsonb_max_bytes", 1024)
    response = _run(client, ids["analysis_id"], replications=1)
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "evidence_too_large"
    assert _job_count(db_engine) == 0


def test_an_archived_analysis_is_not_run(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    _choose_rule(client, ids["analysis_id"])
    assert client.post(f"/analyses/{ids['analysis_id']}/archive", headers=csrf_header(client)).status_code == 200
    response = _run(client, ids["analysis_id"])
    assert response.status_code == 409
    assert _job_count(db_engine) == 0


# ── Owner isolation and CSRF (test 8) ───────────────────────────────────────


def test_another_user_cannot_read_or_run(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    _choose_rule(client, ids["analysis_id"])
    run = _run(client, ids["analysis_id"], replications=1).json()["evidence"]
    clear_cookies(client)
    create_user(db_engine, "other@example.com", "pw")
    assert login(client, "other@example.com", "pw") == 200
    base = f"/analyses/{ids['analysis_id']}"
    assert client.get(f"{base}/closing-policy").status_code == 404
    assert client.put(f"{base}/closing-policy", headers=csrf_header(client), json={"closing_policy": "DRAIN"}).status_code == 404
    assert client.post(f"{base}/continuous/compatibility", headers=csrf_header(client), json={}).status_code == 404
    assert _run(client, ids["analysis_id"]).status_code == 404
    assert client.get(f"{base}/continuous/runs/{run['id']}").status_code == 404
    assert client.get(f"{base}/continuous/runs/{run['id']}/replications/0/playback").status_code == 404


def test_every_write_needs_the_csrf_header(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    base = f"/analyses/{ids['analysis_id']}"
    assert client.put(f"{base}/closing-policy", json={"closing_policy": "DRAIN"}).status_code == 403
    assert client.post(f"{base}/continuous/compatibility", json={}).status_code == 403
    assert client.post(f"{base}/continuous/runs", json={"plan": "current"}).status_code == 403
    assert client.get(f"{base}/closing-policy").json()["closing_policy"] is None


def test_a_run_from_another_analysis_is_not_found(db_engine, client):
    first = _signed_in(client, db_engine, plan=False)
    second = _workspace(db_engine, plan=False)
    _choose_rule(client, first["analysis_id"])
    run = _run(client, first["analysis_id"], replications=1).json()["evidence"]
    assert client.get(f"/analyses/{second['analysis_id']}/continuous/runs/{run['id']}").status_code == 404
    assert client.get(f"/analyses/999999/continuous/runs/{run['id']}").status_code == 404


def test_a_run_says_when_the_setup_or_data_changed_since(db_engine, client):
    ids = _signed_in(client, db_engine, plan=False)
    _choose_rule(client, ids["analysis_id"])
    run = _run(client, ids["analysis_id"], replications=1).json()["evidence"]
    fresh = client.get(f"/analyses/{ids['analysis_id']}/continuous/runs/{run['id']}").json()
    assert (fresh["setup_matches_current"], fresh["dataset_is_current"]) == (True, True)
    with make_sessionmaker(db_engine)() as db:
        db.add(Dataset(user_id=ids["user_id"], analysis_id=ids["analysis_id"], name="Newer", source_filename="n.csv",
                       source_format="csv", row_count=2, normalized_json=ROWS,
                       validation_report_json={"ok": True, "message": "Input data is valid."}))
        db.commit()
    later = client.get(f"/analyses/{ids['analysis_id']}/continuous/runs/{run['id']}").json()
    assert later["dataset_is_current"] is False
