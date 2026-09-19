"""Selected-plan Decision: deterministic interpretation of persisted evidence.

Rule table derived from the frozen shared Decision semantics
(_derive_decision): missing evidence blocks, failed checks revise, and the
adopt/conditional split keys off modeled savings. Separate plans have no
comparable Current cost basis (frozen since Comparison), so the savings term
is unknowable: all-pass yields CONDITIONAL with an explicit reason, never
ADOPT. Nothing here optimizes, simulates, validates, or decides beyond the
selected evidence.
"""
from __future__ import annotations

from typing import Any

from backend.api.scenarios import setup_fingerprint
from backend.api.workflow import _derive_selected_decision
from backend.db.models import AnalysisProject, Dataset, Scenario, User
from backend.queueing_engine.services.separate_optimization import SEPARATE_DES_ENGINE_VERSION
from tests.helpers import create_user, csrf_header, login, make_sessionmaker


def _inputs(verdict="pass", conservation=True, failed=None, inadequate=None):
    failed = failed or []
    inadequate = inadequate or []
    return {
        "scenario": {"id": 9, "name": "Optimal @ 70%", "dataset_id": 2},
        "schedule": {
            "target_utilization": 0.70,
            "periods": [
                {"time": "08:00", "current_active_lanes": ["east-07", "lane-A"],
                 "optimal_active_lanes": 1, "adjustment": -1},
                {"time": "09:00", "current_active_lanes": ["east-07"],
                 "optimal_active_lanes": 1, "adjustment": 0},
            ],
        },
        "des_result": {"overall_conservation": conservation,
                       "overall_status": "COMPLETED" if conservation else "ERROR"},
        "validation_result": {
            "periods": [],
            "verdict": {"status": verdict, "failed": failed,
                        "inadequate": inadequate, "total": 2},
        },
        "failure_cap": 0.05,
    }


def test_pass_with_conserved_des_is_conditional_not_adopt():
    decision = _derive_selected_decision(**_inputs())
    assert decision["status"] == "conditional"
    assert decision["scenario_id"] == 9
    assert "savings" in " ".join(decision["rationale"]).lower()
    assert decision["facts"]["lane_delta"] == -1
    assert decision["facts"]["validation_checks"] == 2
    assert decision["facts"]["failed_checks"] == 0


def test_failed_validation_revises_without_cost_override():
    decision = _derive_selected_decision(
        **_inputs(verdict="fail", failed=[["10:00", "east-07"]]))
    assert decision["status"] == "revise"
    assert "10:00" in decision["recommendation"]
    assert decision["facts"]["failed_checks"] == 1


def test_insufficient_validation_stays_insufficient():
    decision = _derive_selected_decision(
        **_inputs(verdict="insufficient", inadequate=[["08:00", "east-07"]]))
    assert decision["status"] == "insufficient_evidence"
    assert decision["missing_evidence"] != []


def test_conservation_contradiction_cannot_adopt_or_pass_through():
    decision = _derive_selected_decision(**_inputs(conservation=False))
    assert decision["status"] == "insufficient_evidence"
    assert "conservation" in " ".join(decision["rationale"]).lower()


def test_malformed_validation_verdict_is_insufficient():
    inputs = _inputs()
    inputs["validation_result"] = {"periods": [], "verdict": {"status": "mystery"}}
    decision = _derive_selected_decision(**inputs)
    assert decision["status"] == "insufficient_evidence"


# --- API layer -----------------------------------------------------------------------

SAMPLES = [0.05, 0.08, 0.10, 0.12]


def _setup(queue_ids=("east-07", "lane-A")):
    return {
        "queue_structure": "separate_queues",
        "fixed_server_count": 1,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [{"id": "s1", "start_time": "08:00:00",
                      "end_time": "09:00:00", "active_queue_ids": None}],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": list(queue_ids),
    }


def _dataset_rows():
    return [
        {"time": "08:00", "segment_id": "s1", "queue_id": "east-07",
         "lambda": 2.0, "mu": 11.0, "c": 1, "variance": 0.0009,
         "service_samples_hours": list(SAMPLES)},
        {"time": "08:00", "segment_id": "s1", "queue_id": "lane-A",
         "lambda": 1.0, "mu": 11.0, "c": 1, "variance": 0.0009,
         "service_samples_hours": list(SAMPLES)},
    ]


def _api_schedule():
    period = {
        "time": "08:00",
        "overall": "OPTIMAL",
        "reason": None,
        "current_active_lanes": ["east-07", "lane-A"],
        "optimal_active_lanes": 1,
        "adjustment": -1,
        "optimum": {
            "active_lane_count": 1,
            "recommendation": "REDUCE",
            "total_cost": 120.0,
            "candidate_utilization": 0.45,
            "estimated_optimal": True,
            "active_queue_ids": ["east-07"],
            "inactive_queue_ids": ["lane-A"],
        },
        "candidates": [],
        "evaluation_method": "DES_REPLICATIONS",
        "replication_seeds": [42, 43, 44, 45, 46],
        "target_utilization": 0.70,
    }
    return {"overall": "COMPLETE", "reason": None, "target_utilization": 0.70,
            "evaluation_method": "DES_REPLICATIONS", "periods": [period],
            "des": {"replications": 5, "base_seed": 42,
                    "duration_hours": 8.0, "max_events": 5000}}


def _api_calculation(dataset_id):
    options = {
        "target_utilization": 0.70,
        "server_cost_per_hr": 87.0,
        "customer_waiting_cost": 100.0,
        "min_active_lanes": None,
        "max_active_lanes": None,
        "lambda_multiplier": 1.0,
        "des": {"replications": 5, "base_seed": 42,
                "duration_hours": 8.0, "max_events": 5000},
    }
    return {**options, "calculation": {
        "schema_version": 2,
        "engine_version": SEPARATE_DES_ENGINE_VERSION,
        "dataset_id": dataset_id, "dataset_row_count": 2,
        "options": options, "calculated_at": "2026-09-18T00:00:00+00:00",
        "setup_hash": setup_fingerprint(_setup())}}


def _api_workspace(db_engine, email):
    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(
            user_id=user.id, name="Separate lanes",
            queue_setup_json=_setup(), setup_status="ready")
        db.add(analysis)
        db.flush()
        dataset = Dataset(
            user_id=user.id, analysis_id=analysis.id, name="Lanes",
            source_filename="lanes.csv", source_format="csv", row_count=2,
            normalized_json=_dataset_rows(),
            validation_report_json={"ok": True, "message": "ok"})
        db.add(dataset)
        db.flush()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id,
            name="Optimal @ 70%", settings_json=_api_calculation(dataset.id),
            results_json={"schedule": _api_schedule()})
        db.add(scenario)
        db.commit()
        return analysis.id, dataset.id, scenario.id


def _decide(client, analysis_id, headers):
    return client.post(
        f"/analyses/{analysis_id}/workflow/decision/selected",
        headers=headers,
        json={},
    )


def test_decision_gate_blocks_without_selection_or_validation(db_engine, client):
    from tests.helpers import login

    analysis_id, _, _ = _api_workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    headers = csrf_header(client)
    assert _decide(client, analysis_id, headers).status_code == 409


def test_decision_conditional_on_pass_with_full_identity(db_engine, client):
    from tests.helpers import login

    analysis_id, _, scenario_id = _api_workspace(db_engine, "v@example.com")
    login(client, "v@example.com", "pw")
    headers = csrf_header(client)
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": scenario_id}).status_code == 200
    assert _decide(client, analysis_id, headers).status_code == 404
    des = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/selected",
        headers=headers, json={"seed": 7})
    assert des.status_code == 200, des.text
    mc = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
        headers=headers, json={})
    assert mc.status_code == 200, mc.text
    validated = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation/selected",
        headers=headers, json={})
    assert validated.status_code == 200, validated.text
    decided = _decide(client, analysis_id, headers)
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["persisted"] is True
    decision = body["decision"]
    assert decision["status"] == "conditional"
    assert decision["scenario_id"] == scenario_id
    assert decision["evidence_ids"]["validation"] == validated.json()["evidence"]["id"]
    assert decision["evidence_ids"]["des"] == des.json()["evidence"]["id"]
    assert decision["evidence_ids"]["mc"] == mc.json()["evidence"]["id"]
    workflow = client.get(f"/analyses/{analysis_id}/workflow", headers=headers).json()
    assert workflow["decision"]["id"] == body["evidence"]["id"]


def _full_chain(client, analysis_id, headers, seed=7):
    des = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/selected",
        headers=headers, json={"seed": seed})
    assert des.status_code == 200, des.text
    mc = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
        headers=headers, json={})
    assert mc.status_code == 200, mc.text
    validated = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation/selected",
        headers=headers, json={})
    assert validated.status_code == 200, validated.text
    decided = _decide(client, analysis_id, headers)
    assert decided.status_code == 200, decided.text
    return decided.json()


def test_stale_evidence_blocks_and_old_decision_not_current(db_engine, client):
    analysis_id, _, scenario_id = _api_workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    headers = csrf_header(client)
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": scenario_id}).status_code == 200
    _full_chain(client, analysis_id, headers)
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="u@example.com").one()
        newer = Dataset(
            user_id=user.id, analysis_id=analysis_id, name="Recut",
            source_filename="r.csv", source_format="csv", row_count=2,
            normalized_json=_dataset_rows(),
            validation_report_json={"ok": True, "message": "ok"})
        db.add(newer)
        db.commit()
    assert _decide(client, analysis_id, headers).status_code == 422
    workflow = client.get(f"/analyses/{analysis_id}/workflow", headers=headers).json()
    assert workflow["decision"] is None
    assert workflow["scenario"] is None


def test_selection_change_and_validation_rerun_rescope_decision(db_engine, client):
    from backend.db.models import Job

    analysis_id, dataset_id, first_id = _api_workspace(db_engine, "w@example.com")
    login(client, "w@example.com", "pw")
    headers = csrf_header(client)
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": first_id}).status_code == 200
    first = _full_chain(client, analysis_id, headers)
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="w@example.com").one()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis_id, dataset_id=dataset_id,
            name="Optimal @ 60%", settings_json=_api_calculation(dataset_id),
            results_json={"schedule": _api_schedule()})
        db.add(scenario)
        db.commit()
        second_id = scenario.id
        before = {row.id: dict(row.result_json) for row in db.query(Job).all()}
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": second_id}).status_code == 200
    workflow = client.get(f"/analyses/{analysis_id}/workflow", headers=headers).json()
    assert workflow["decision"] is None
    assert workflow["scenario"]["id"] == second_id
    second = _full_chain(client, analysis_id, headers)
    assert second["decision"]["scenario_id"] == second_id
    assert second["evidence"]["id"] != first["evidence"]["id"]
    with make_sessionmaker(db_engine)() as db:
        for row in db.query(Job).all():
            if row.id in before:
                assert dict(row.result_json) == before[row.id]


def test_decision_path_makes_no_engine_or_decision_calls():
    import inspect

    import backend.api.workflow as workflow_api

    for name in ("create_selected_decision", "_derive_selected_decision",
                 "_require_selected_separate_plan"):
        source = inspect.getsource(getattr(workflow_api, name))
        assert "optimize_separate" not in source
        assert "_optimize_separate_des" not in source
        assert "rank_des_candidates" not in source
        assert "evaluate_candidate_with_des" not in source
        assert "mc_simulate_segments" not in source
    source = inspect.getsource(workflow_api.create_selected_decision)
    assert "_run_selected_plan_des" not in source
    assert "run_selected_validation" not in source
    assert "validate_selected_plan" not in source
    assert "create_decision" not in source
    assert "_derive_decision" not in source


# --- R6a: stored verdicts do not survive Setup edits ---------------------------------

SETUP_STALE = "Setup changed since this evidence was produced. Rerun Simulation."


def _patch_break(client, analysis_id, headers, start="08:40:00"):
    setup = {**_setup(), "breaks": [
        {"queue_id": "east-07", "scheduled_start_time": start, "duration_minutes": 10}]}
    response = client.patch(f"/analyses/{analysis_id}", headers=headers,
                            json={"queue_setup": setup})
    assert response.status_code == 200, response.text


def _select_first(db_engine, client, email):
    analysis_id, _, scenario_id = _api_workspace(db_engine, email)
    login(client, email, "pw")
    headers = csrf_header(client)
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": scenario_id}).status_code == 200
    return analysis_id, scenario_id, headers


def _run_stages(client, analysis_id, headers, stages):
    response = None
    for path, body in stages:
        response = client.post(
            f"/analyses/{analysis_id}/workflow/simulation/{path}",
            headers=headers, json=body)
        assert response.status_code == 200, response.text
    return response.json()["evidence"]["id"]


DES: tuple[str, dict[str, Any]] = ("des/selected", {"seed": 7})
MC: tuple[str, dict[str, Any]] = ("mc/selected", {})
VALIDATION: tuple[str, dict[str, Any]] = ("validation/selected", {})


def _clear_setup_hash(db_engine, job_id):
    from backend.db.models import Job

    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, job_id)
        params = dict(job.params_json)
        params.pop("setup_hash", None)
        job.params_json = params
        db.commit()


def test_evidence_records_setup_hash_and_unchanged_setup_keeps_decision(db_engine, client):
    analysis_id, _, headers = _select_first(db_engine, client, "h@example.com")
    body = _full_chain(client, analysis_id, headers)
    with make_sessionmaker(db_engine)() as db:
        expected = setup_fingerprint(db.get(AnalysisProject, analysis_id).queue_setup_json)
    assert body["evidence"]["params"]["setup_hash"] == expected
    workflow = client.get(f"/analyses/{analysis_id}/workflow", headers=headers).json()
    assert workflow["decision"]["id"] == body["evidence"]["id"]
    assert workflow["decision_stale"] is False
    for key in ("des", "mc", "validation"):
        assert workflow[key]["params"]["setup_hash"] == expected


def test_setup_edit_hides_selected_decision_and_report(db_engine, client):
    analysis_id, _, headers = _select_first(db_engine, client, "p@example.com")
    _full_chain(client, analysis_id, headers)
    assert client.get(f"/reports/analyses/{analysis_id}/selected/preview",
                      headers=headers).status_code == 200
    _patch_break(client, analysis_id, headers)
    workflow = client.get(f"/analyses/{analysis_id}/workflow", headers=headers).json()
    assert workflow["decision"] is None
    assert workflow["decision_stale"] is True
    preview = client.get(f"/reports/analyses/{analysis_id}/selected/preview", headers=headers)
    assert preview.status_code != 200
    assert "model" not in preview.json()


def test_setup_edit_blocks_selected_decision(db_engine, client):
    analysis_id, _, headers = _select_first(db_engine, client, "q@example.com")
    _run_stages(client, analysis_id, headers, (DES, MC, VALIDATION))
    _patch_break(client, analysis_id, headers)
    decided = _decide(client, analysis_id, headers)
    assert decided.status_code == 409, decided.text
    assert decided.json()["detail"] == SETUP_STALE


def test_selected_mc_rejects_des_without_current_setup_hash(db_engine, client):
    analysis_id, _, headers = _select_first(db_engine, client, "m@example.com")
    _clear_setup_hash(db_engine, _run_stages(client, analysis_id, headers, (DES,)))
    mc = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
                     headers=headers, json={})
    assert mc.status_code == 409, mc.text
    assert mc.json()["detail"] == SETUP_STALE


def test_selected_validation_rejects_mc_without_current_setup_hash(db_engine, client):
    analysis_id, _, headers = _select_first(db_engine, client, "n@example.com")
    _clear_setup_hash(db_engine, _run_stages(client, analysis_id, headers, (DES, MC)))
    validated = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation/selected",
        headers=headers, json={})
    assert validated.status_code == 409, validated.text
    assert validated.json()["detail"] == SETUP_STALE


def test_selected_decision_rejects_validation_without_current_setup_hash(db_engine, client):
    analysis_id, _, headers = _select_first(db_engine, client, "o@example.com")
    _clear_setup_hash(db_engine, _run_stages(client, analysis_id, headers, (DES, MC, VALIDATION)))
    decided = _decide(client, analysis_id, headers)
    assert decided.status_code == 409, decided.text
    assert decided.json()["detail"] == SETUP_STALE
