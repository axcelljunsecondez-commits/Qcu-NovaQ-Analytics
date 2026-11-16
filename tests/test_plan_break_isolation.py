"""Suggested break schedules are verified per scenario and never overwrite Current inputs.

All operational inputs in this file are synthetic, using isolated test databases.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from backend.api.plan_breaks import resolve_scenario_plan_setup, setup_digest
from backend.db.models import AnalysisProject, Dataset, Scenario
from tests.helpers import csrf_header, login, make_sessionmaker
from tests.test_break_apply_api import _stored_setup
from tests.test_break_optimize_api import _setup, _workspace
from tests.test_supervisor_schedule_api import _body, _post


def _prepared(db_engine, client):
    setup = _setup()
    for segment in setup["segments"]:
        segment["id"] = f"{segment['start_time'][:5]}-{segment['end_time'][:5]}"
    aid, baseline = _workspace(db_engine, setup=setup)
    login(client, "brk@example.com", "pw")
    request = _body(db_engine, aid)
    response = _post(client, aid, "preview", request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["can_apply"], result["blockers"]
    return aid, baseline, request, result


def _save_body(db_engine, aid, request, preview):
    with make_sessionmaker(db_engine)() as db:
        rows = len(db.get(Dataset, request["dataset_id"]).normalized_json)
    options = {"target_utilization": request["target_utilization"], "server_cost_per_hr": 87.,
               "customer_waiting_cost": 100., "min_active_lanes": 2, "max_active_lanes": None,
               "lambda_multiplier": 1., "des": preview["schedule"]["des"]}
    return {
        "name": "Suggested breaks", "analysis_id": aid, "dataset_id": request["dataset_id"],
        "settings": {**options, "calculation": {
            "schema_version": 2, "engine_version": preview["engine_version"], "analysis_id": aid,
            "dataset_id": request["dataset_id"], "dataset_row_count": rows, "options": options,
            "calculated_at": "2026-11-16T00:00:00+00:00", "setup_hash": preview["setup_hash"],
            "break_optimization": {"max_shift_minutes": request.get("max_shift_minutes", 120)},
        }}, "results": {"schedule": preview["schedule"]},
    }


def test_draft_confirmation_is_idempotent_and_never_writes_current(db_engine, client):
    aid, baseline, request, preview = _prepared(db_engine, client)
    for _ in range(2):
        response = _post(client, aid, "apply", {**request, "preview_hash": preview["preview_hash"]})
        assert response.status_code == 200, response.text
        out = response.json()
        assert out["destination"] == "suggested_plan_draft"
        assert out["analysis"]["queue_setup"] == baseline
        assert out["plan_setup"]["breaks"] != baseline["breaks"]
        assert _stored_setup(db_engine, aid) == baseline
    with make_sessionmaker(db_engine)() as db:
        assert db.query(Scenario).count() == 0


def test_save_select_and_report_use_the_plan_breaks_without_changing_current(db_engine, client):
    aid, baseline, request, preview = _prepared(db_engine, client)
    current = client.post(f"/analyses/{aid}/workflow/simulation/des/current", headers=csrf_header(client),
                          json={"sim_hours": 1, "seed": 7, "max_events": 3000})
    assert current.status_code == 200, current.text
    current_job_id = current.json()["evidence"]["id"]
    initial_current = client.get(f"/analyses/{aid}/workflow").json()["des_current"]
    assert initial_current is not None, current.json()
    body = _save_body(db_engine, aid, request, preview)
    response = client.post("/scenarios", headers=csrf_header(client), json=body)
    assert response.status_code == 201, response.text
    scenario = response.json()["scenario"]
    calculation = scenario["settings"]["calculation"]
    assert calculation["setup_hash"] == setup_digest(baseline)
    assert calculation["plan_breaks"] != baseline["breaks"]
    plan_setup = resolve_scenario_plan_setup(baseline, calculation)
    assert calculation["plan_setup_hash"] == setup_digest(plan_setup)
    selected = client.post(f"/analyses/{aid}/workflow/selection", headers=csrf_header(client),
                           json={"scenario_id": scenario["id"]})
    assert selected.status_code == 200, selected.text
    report = client.get(f"/analyses/{aid}/reports/plan/preview")
    assert report.status_code == 200, report.text
    model = report.json()["model"]
    assert model["breaks"] == calculation["plan_breaks"]
    assert _stored_setup(db_engine, aid) == baseline
    # Resolving selected execution is shared by DES, MC, validation and Decision inputs.
    from backend.api.workflow import _require_selected_separate_plan
    from backend.db.models import User
    with make_sessionmaker(db_engine)() as db:
        analysis = db.get(AnalysisProject, aid)
        plan = _require_selected_separate_plan(db, db.get(User, analysis.user_id), analysis)
        assert plan["setup"]["breaks"] == calculation["plan_breaks"]
    baseline_preview = _post(client, aid, "preview", {**request, "allow_break_changes": False}).json()
    baseline_body = _save_body(db_engine, aid, request, baseline_preview)
    baseline_body["name"] = "Suggested staffing with original breaks"
    baseline_body["settings"]["calculation"].pop("break_optimization")
    saved_baseline = client.post("/scenarios", headers=csrf_header(client), json=baseline_body)
    assert saved_baseline.status_code == 201, saved_baseline.text
    baseline_scenario = saved_baseline.json()["scenario"]
    for chosen, expected_breaks in ((baseline_scenario, baseline["breaks"]), (scenario, calculation["plan_breaks"])):
        selected = client.post(f"/analyses/{aid}/workflow/selection", headers=csrf_header(client),
                               json={"scenario_id": chosen["id"]})
        assert selected.status_code == 200, selected.text
        report = client.get(f"/analyses/{aid}/reports/plan/preview")
        assert report.status_code == 200, report.text
        assert report.json()["model"]["breaks"] == expected_breaks
        assert client.get(f"/analyses/{aid}/workflow").json()["des_current"]["id"] == current_job_id
        assert _stored_setup(db_engine, aid) == baseline


@pytest.mark.parametrize("descriptor", [None, {}, {"max_shift_minutes": True}, {"max_shift_minutes": 20},
                                         {"max_shift_minutes": -15}, {"max_shift_minutes": 255},
                                         {"max_shift_minutes": 120, "proposed_breaks": []}])
def test_invalid_break_descriptor_cannot_create_a_suggested_plan(db_engine, client, descriptor):
    aid, baseline, request, preview = _prepared(db_engine, client)
    body = _save_body(db_engine, aid, request, preview)
    body["settings"]["calculation"]["break_optimization"] = descriptor
    response = client.post("/scenarios", headers=csrf_header(client), json=body)
    assert response.status_code == 422, response.text
    assert _stored_setup(db_engine, aid) == baseline


@pytest.mark.parametrize("field,value", [("plan_breaks", []), ("plan_setup_hash", "0" * 64)])
def test_client_cannot_supply_optimized_break_times_or_identity(db_engine, client, field, value):
    aid, baseline, request, preview = _prepared(db_engine, client)
    body = _save_body(db_engine, aid, request, preview)
    body["settings"]["calculation"][field] = value
    response = client.post("/scenarios", headers=csrf_header(client), json=body)
    assert response.status_code == 422, response.text
    assert _stored_setup(db_engine, aid) == baseline


def test_saved_plan_break_tampering_is_refused_and_leaves_baseline_intact(db_engine, client):
    aid, baseline, request, preview = _prepared(db_engine, client)
    response = client.post("/scenarios", headers=csrf_header(client), json=_save_body(db_engine, aid, request, preview))
    assert response.status_code == 201, response.text
    scenario = response.json()["scenario"]
    calculation = deepcopy(scenario["settings"]["calculation"])
    calculation["plan_breaks"][0]["scheduled_start_time"] = "08:15:00"
    with pytest.raises(ValueError, match="identity"):
        resolve_scenario_plan_setup(baseline, calculation)
    assert _stored_setup(db_engine, aid) == baseline


@pytest.mark.parametrize("change", ["setup", "new_dataset"])
def test_plan_save_refuses_a_changed_baseline_or_planning_file(db_engine, client, change):
    aid, baseline, request, preview = _prepared(db_engine, client)
    body = _save_body(db_engine, aid, request, preview)
    with make_sessionmaker(db_engine)() as db:
        if change == "setup":
            db.get(AnalysisProject, aid).queue_setup_json = {**baseline, "breaks": []}
        else:
            source = db.get(Dataset, request["dataset_id"])
            db.add(Dataset(user_id=source.user_id, analysis_id=aid, name="Replacement planning file",
                           source_filename="replacement.csv", source_format="csv", row_count=source.row_count,
                           normalized_json=source.normalized_json, validation_report_json=source.validation_report_json))
        db.commit()
    before = _stored_setup(db_engine, aid)
    response = client.post("/scenarios", headers=csrf_header(client), json=body)
    assert response.status_code in (409, 422), response.text
    assert _stored_setup(db_engine, aid) == before
    with make_sessionmaker(db_engine)() as db:
        assert db.query(Scenario).count() == 0
