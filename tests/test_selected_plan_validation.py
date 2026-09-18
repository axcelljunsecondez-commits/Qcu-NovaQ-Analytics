"""Selected-plan Validation: pure verdict core over persisted evidence.

Consumes the immutable schedule, the selected-plan DES result, and the
selected-plan MC rows. Returns per-period and overall verdicts with the
verified FAIL > INSUFFICIENT > PASS precedence. Never reruns engines,
never averages away failures, never converts missing evidence to success.
"""
from __future__ import annotations

from backend.api.workflow import validate_selected_plan
from tests.helpers import csrf_header, login


def _schedule(active_by_time):
    return {"periods": [
        {"time": time, "optimum": {"active_queue_ids": list(active)}}
        for time, active in active_by_time.items()
    ]}


def _des(time, lanes, conservation=True):
    return {"periods": [{
        "time": time,
        "conservation": conservation,
        "results": [
            {"queue_id": qid, "active": True, "simulation_supported": True,
             "rho_sim": 0.5, "Wq_sim": 0.05, "served": 10, "arrivals": 10}
            for qid in lanes
        ],
    }]}


def _mc_row(time, qid, rate=0.01, adequate=True, supported=True):
    return {"time": time, "queue_id": qid, "mc_failure_rate": rate,
            "mc_failure_rate_adequate": adequate,
            "simulation_supported": supported, "selected_model": "Parallel M/G/1"}


def test_all_pass_periods_yield_overall_pass():
    schedule = _schedule({"08:00": ["east-07", "lane-A"], "09:00": ["east-07"]})
    des = {"periods": _des("08:00", ["east-07", "lane-A"])["periods"]
           + _des("09:00", ["east-07"])["periods"]}
    mc = [_mc_row("08:00", "east-07"), _mc_row("08:00", "lane-A"),
          _mc_row("09:00", "east-07")]
    outcome = validate_selected_plan(schedule, des, mc, 0.05)
    assert outcome["verdict"]["status"] == "pass"
    assert all(p["status"] == "pass" for p in outcome["periods"])
    assert outcome["verdict"]["total"] == 3


def test_one_fail_forces_overall_fail_without_majority_vote():
    schedule = _schedule({"08:00": ["a"], "09:00": ["b"], "10:00": ["c"]})
    des = {"periods": _des("08:00", ["a"])["periods"] + _des("09:00", ["b"])["periods"]
           + _des("10:00", ["c"])["periods"]}
    mc = [_mc_row("08:00", "a"), _mc_row("09:00", "b", rate=0.40),
          _mc_row("10:00", "c")]
    outcome = validate_selected_plan(schedule, des, mc, 0.05)
    assert outcome["verdict"]["status"] == "fail"
    by_time = {p["time"]: p["status"] for p in outcome["periods"]}
    assert by_time == {"08:00": "pass", "09:00": "fail", "10:00": "pass"}


def test_missing_lane_evidence_is_insufficient_not_pass():
    schedule = _schedule({"08:00": ["east-07", "blue_checkout"]})
    des = _des("08:00", ["east-07", "blue_checkout"])
    mc = [_mc_row("08:00", "east-07")]
    outcome = validate_selected_plan(schedule, des, mc, 0.05)
    assert outcome["verdict"]["status"] == "insufficient"
    assert outcome["periods"][0]["status"] == "insufficient"


def test_fail_outranks_insufficient_across_periods():
    schedule = _schedule({"08:00": ["a"], "09:00": ["b"], "10:00": ["c"]})
    des = {"periods": _des("08:00", ["a"])["periods"] + _des("09:00", ["b"])["periods"]
           + _des("10:00", ["c"])["periods"]}
    mc = [_mc_row("08:00", "a", rate=0.50)]
    outcome = validate_selected_plan(schedule, des, mc, 0.05)
    assert outcome["verdict"]["status"] == "fail"
    by_time = {p["time"]: p["status"] for p in outcome["periods"]}
    assert by_time["08:00"] == "fail"
    assert by_time["09:00"] == "insufficient"
    assert by_time["10:00"] == "insufficient"


def test_conservation_failure_and_inactive_lanes():
    schedule = _schedule({"08:00": ["east-07", "blue_checkout"]})
    des = _des("08:00", ["east-07", "blue_checkout"], conservation=False)
    mc = [_mc_row("08:00", "east-07"), _mc_row("08:00", "blue_checkout")]
    outcome = validate_selected_plan(schedule, des, mc, 0.05)
    assert outcome["verdict"]["status"] != "pass"
    assert outcome["periods"][0]["status"] == "insufficient"
    # Inactive lanes never create requirements: only active lanes are required.
    assert outcome["verdict"]["total"] == 2


# --- API layer ---------------------------------------------------------------------

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
        "engine_version": "novaq-2026-09-separate-des-v1",
        "dataset_id": dataset_id, "dataset_row_count": 2,
        "options": options, "calculated_at": "2026-09-18T00:00:00+00:00"}}


def _api_workspace(db_engine, email):
    from backend.db.models import AnalysisProject, Dataset, Scenario, User
    from tests.helpers import create_user, make_sessionmaker

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


def _post(client, analysis_id, path):
    from tests.helpers import csrf_header

    return client.post(
        f"/analyses/{analysis_id}/workflow/{path}",
        headers=csrf_header(client),
        json={},
    )


def test_validation_gate_blocks_each_missing_stage(db_engine, client):
    analysis_id, _, scenario_id = _api_workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    assert _post(client, analysis_id, "simulation/validation/selected").status_code == 409
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=csrf_header(client),
        json={"scenario_id": scenario_id},
    ).status_code == 200
    assert _post(client, analysis_id, "simulation/validation/selected").status_code == 404


def test_validation_passes_and_persists_with_full_identity(db_engine, client):
    analysis_id, dataset_id, scenario_id = _api_workspace(db_engine, "v@example.com")
    login(client, "v@example.com", "pw")
    headers = csrf_header(client)
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": scenario_id}).status_code == 200
    des = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/selected",
        headers=headers, json={"seed": 7})
    assert des.status_code == 200, des.text
    des_id = des.json()["evidence"]["id"]
    mc = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
        headers=headers, json={})
    assert mc.status_code == 200, mc.text
    mc_id = mc.json()["evidence"]["id"]
    validated = _post(client, analysis_id, "simulation/validation/selected")
    assert validated.status_code == 200, validated.text
    result = validated.json()["evidence"]["result"]
    assert result["scenario_id"] == scenario_id
    assert result["des_job_id"] == des_id
    assert result["mc_job_id"] == mc_id
    assert result["dataset_id"] == dataset_id
    assert result["provenance"] == "SELECTED"
    assert result["verdict"]["status"] == "pass"
    assert result["periods"][0]["status"] == "pass"
    assert result["periods"][0]["active_queue_ids"] == ["east-07"]
    workflow = client.get(f"/analyses/{analysis_id}/workflow", headers=headers).json()
    assert workflow["validation"]["id"] == validated.json()["evidence"]["id"]


def _craft_mc_job(db_engine, email, analysis_id, scenario_id, des_job_id, rows):
    from datetime import datetime, timezone

    from backend.db.models import Job, User
    from tests.helpers import make_sessionmaker

    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email=email).one()
        job = Job(
            user_id=user.id, kind="workflow_mc", status="completed",
            params_json={"analysis_id": analysis_id, "scenario_id": scenario_id,
                         "des_job_id": des_job_id, "failure_threshold": 0.75,
                         "failure_rate_cap": 0.05, "num_trials": 2000,
                         "engine": "selected-plan-measured-mc"},
            result_json={"provenance": "SELECTED", "scenario_id": scenario_id,
                         "des_job_id": des_job_id, "results": rows},
            tenant_id=user.tenant_id,
            finished_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        return job.id


def _mc_result_row(time, qid, rate=0.0, adequate=True):
    return {"time": time, "queue_id": qid, "lambda": 2.0, "mu": 11.0, "c": 1,
            "rho_mean": 0.2, "Wq_mean": 0.01, "failure_rate": rate,
            "failure_count": 0, "status": "PASS", "error": None,
            "selected_model": "Parallel M/G/1", "simulation_supported": True,
            "failure_rate_ci_lower": 0.0, "failure_rate_ci_upper": 0.01,
            "failure_rate_adequate": adequate}


def test_cross_scenario_mc_evidence_is_rejected(db_engine, client):
    analysis_id, _, scenario_id = _api_workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    headers = csrf_header(client)
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": scenario_id}).status_code == 200
    des = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/selected",
        headers=headers, json={"seed": 7})
    assert des.status_code == 200
    _craft_mc_job(db_engine, "u@example.com", analysis_id, scenario_id,
                  des_job_id=999999,
                  rows=[_mc_result_row("08:00", "east-07")])
    response = _post(client, analysis_id, "simulation/validation/selected")
    assert response.status_code == 409
    assert "Monte Carlo" in response.json()["detail"]


def test_null_failure_rate_stays_null_and_inadequate(db_engine, client):
    analysis_id, _, scenario_id = _api_workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    headers = csrf_header(client)
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": scenario_id}).status_code == 200
    des = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/selected",
        headers=headers, json={"seed": 7})
    des_id = des.json()["evidence"]["id"]
    null_row = _mc_result_row("08:00", "east-07")
    null_row["mc_failure_rate"] = None
    null_row["failure_rate"] = None
    null_row["failure_rate_adequate"] = False
    _craft_mc_job(db_engine, "u@example.com", analysis_id, scenario_id,
                  des_job_id=des_id, rows=[null_row])
    validated = _post(client, analysis_id, "simulation/validation/selected")
    assert validated.status_code == 200, validated.text
    result = validated.json()["evidence"]["result"]
    assert result["verdict"]["status"] == "insufficient"
    queue = result["periods"][0]["queues"][0]
    assert queue["mc_failure_rate"] is None
    assert queue["validation_verdict"] == "inadequate"


def test_stale_evidence_blocks_and_selection_change_rescopes(db_engine, client):
    from backend.db.models import Dataset, Job, Scenario
    from tests.helpers import make_sessionmaker

    analysis_id, _, scenario_id = _api_workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    headers = csrf_header(client)
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": scenario_id}).status_code == 200
    assert client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/selected",
        headers=headers, json={"seed": 7}).status_code == 200
    assert client.post(
        f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
        headers=headers, json={}).status_code == 200
    assert _post(client, analysis_id, "simulation/validation/selected").status_code == 200
    with make_sessionmaker(db_engine)() as db:
        before = {row.id: dict(row.result_json) for row in db.query(Job).all()}
        scenario_before = dict(db.get(Scenario, scenario_id).results_json)
        user_id = db.get(Scenario, scenario_id).user_id
        newer = Dataset(
            user_id=user_id, analysis_id=analysis_id, name="Recut",
            source_filename="r.csv", source_format="csv", row_count=2,
            normalized_json=_dataset_rows(),
            validation_report_json={"ok": True, "message": "ok"})
        db.add(newer)
        db.commit()
    stale = _post(client, analysis_id, "simulation/validation/selected")
    assert stale.status_code == 422
    workflow = client.get(f"/analyses/{analysis_id}/workflow", headers=headers).json()
    assert workflow["validation"] is None
    assert workflow["scenario"] is None
    with make_sessionmaker(db_engine)() as db:
        for row in db.query(Job).all():
            assert dict(row.result_json) == before[row.id]
        assert db.get(Scenario, scenario_id).results_json == scenario_before


def test_validation_makes_no_engine_or_decision_calls():
    import inspect

    import backend.api.workflow as workflow_api

    source = inspect.getsource(workflow_api.run_selected_validation)
    assert "optimize_separate" not in source
    assert "_run_selected_plan_des" not in source
    assert "mc_simulate_segments" not in source
    assert "evaluate_candidate_with_des" not in source
    assert "create_decision" not in source
    assert "_derive_decision" not in source
    core = inspect.getsource(workflow_api.validate_selected_plan)
    assert "mc_simulate_segments" not in core
