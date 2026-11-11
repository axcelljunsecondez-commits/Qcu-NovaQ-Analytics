"""Selected-only guard integration; all inputs/SQLite records here are synthetic."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.api import workflow
from backend.api.evidence_status import VersionFamily, job_references, selected_load_record
from backend.api.workflow import (
    _selected_load_summaries,
    _selected_mc_load_assessment,
    current_decision_for_report,
    validate_selected_plan,
)
from backend.db.models import Job, User
from backend.queueing_engine.services.separate_optimization import replication_seeds
from backend.queueing_engine.statistics.selected_load_uncertainty import SELECTED_LOAD_METHOD
from tests.helpers import csrf_header, login, make_sessionmaker
from tests.test_evidence_status import syn_policy
from tests.test_selected_load_uncertainty import decimal_settings, raw_mc
from tests.test_selected_plan_simulation import _select, _setup, _workspace


def plan_for(mode="static"):
    setup = _setup(("a", "b"))
    setup["segments"][0]["end_time"] = "08:30:00"
    labels = ["s1"]
    if mode != "static":
        setup["event_period_basis"] = mode
    if mode == "per_date":
        labels = ["2026-11-09 s1 UTC", "2026-11-10 s1 UTC"]
    records = [{"time": label, "segment_id": "s1", "queue_id": queue_id,
                "lambda": rate, "mu": 10., "c": 1, "variance": .0001,
                "service_samples_hours": [.05, .1, .15]}
               for label in labels for queue_id, rate in (("a", 2.), ("b", 3.))]
    schedule = {"periods": [{"time": label, "optimum": {"active_queue_ids": ["a"],
                                                         "inactive_queue_ids": ["b"]}}
                            for label in labels]}
    return {"setup": setup, "schedule": schedule, "dataset": SimpleNamespace(normalized_json=records),
            "scenario": SimpleNamespace(id=9, analysis_id=7, dataset_id=2), "multiplier": 1.,
            "duration_hours": 2., "target": .7, "server_cost": 87., "waiting_cost": 100., "max_events": 1000}


@pytest.mark.parametrize("mode,expected_hours,expected_envelope", [("static", 2., 10.),
    ("representative_day", .5, 1.), ("per_date", .5, 1.)])
def test_actual_execution_modes_use_their_own_input_envelopes(mode, expected_hours, expected_envelope):
    plan = plan_for(mode)
    runs = [workflow._run_selected_plan_des(plan, seed) for seed in replication_seeds(42, 3)]
    before = deepcopy(runs)
    measured = _selected_load_summaries(plan, 42, 3, runs)
    assert runs == before
    assert measured["family_size"] == len(plan["schedule"]["periods"])
    assert len(measured["results"]) == measured["family_size"]
    cutoff, _, _ = decimal_settings(Decimal(str(expected_envelope)), 3, measured["family_size"])
    for row in measured["results"]:
        assert row["status"] == "bounded", row
        assert row["duration_hours"] == expected_hours
        assert row["envelope_mean"] == expected_envelope
        assert row["cutoff"] == cutoff
        counts = [next(lane["arrivals"] for period in run["periods"] if period["time"] == row["time"]
                       for lane in period["results"] if lane["queue_id"] == "a") for run in runs]
        assert row["sum_truncated"] == sum(min(value, cutoff) for value in counts)


def synthetic_guard(raw_status="PASS", *, mu=1., threshold=.8, counts=1):
    """Complete synthetic count vectors; expected verdicts use analytic corners/overlap."""
    plan = plan_for()
    plan["duration_hours"] = 1.
    plan["dataset"].normalized_json[0]["lambda"] = 1.
    plan["dataset"].normalized_json[1]["lambda"] = 0.
    runs = [{"execution": workflow.SELECTED_DES_PER_PERIOD_EXECUTION, "duration_hours": 1.,
             "overall_conservation": True, "overall_status": "COMPLETED", "seed": 42 + index,
             "periods": [{"time": "s1", "conservation": True, "results": [
                 {"queue_id": "a", "active": True, "simulation_supported": True,
                  "customer_conservation": True, "arrivals": counts, "served": counts}]}]}
            for index in range(20)]
    des = {**deepcopy(runs[0]), "selected_load_method": SELECTED_LOAD_METHOD,
           "load_replications": {"count": 20}, "load_uncertainty": _selected_load_summaries(plan, 42, 20, runs)}
    raw = raw_mc(mu=mu, failure_threshold=threshold, status=raw_status,
                 failure_count=20 if raw_status == "PASS" else 2000,
                 failure_rate=.01 if raw_status == "PASS" else 1., time="s1", queue_id="a")
    mc = {"selected_load_method": SELECTED_LOAD_METHOD, "results": [raw],
          "load_uncertainty": _selected_mc_load_assessment(plan["schedule"], des, [raw])}
    return plan["schedule"], des, mc


@pytest.mark.parametrize("raw_status,mu,threshold,counts,guard", [
    ("PASS", 1., .8, 1, "fail"), ("FAIL", 2., 1., 3, "pass"), ("FAIL", 1., 1., 3, "insufficient")])
def test_supported_guard_is_separate_from_raw_point_status(raw_status, mu, threshold, counts, guard):
    schedule, des, mc = synthetic_guard(raw_status, mu=mu, threshold=threshold, counts=counts)
    before = deepcopy((des, mc))
    result = validate_selected_plan(schedule, des, mc["results"], .05, mc_result=mc)
    assert result["verdict"]["status"] == guard
    row = result["periods"][0]["queues"][0]
    assert row["raw_mc_verdict"] == raw_status.lower()
    assert row["load_assessment"]["status"] == guard
    assert row["validation_verdict"] == ("inadequate" if guard == "insufficient" else guard)
    assert (des, mc) == before


def test_missing_methods_assessments_or_empty_family_cannot_fall_back_to_raw_pass():
    schedule, des, mc = synthetic_guard(mu=2., threshold=1.)
    assert validate_selected_plan(schedule, des, mc["results"], .05)["verdict"]["status"] == "insufficient"
    for corrupted in ({**mc, "selected_load_method": None}, {**mc, "load_uncertainty": None}):
        assert validate_selected_plan(schedule, des, mc["results"], .05, mc_result=corrupted)["verdict"]["status"] == "insufficient"
    empty = validate_selected_plan({"periods": []}, des, [], .05, mc_result=mc)
    assert empty["verdict"]["status"] == "insufficient"


def test_missing_coordinate_keeps_family_and_failed_replication_invalidates_all():
    plan = plan_for("per_date")
    runs = [workflow._run_selected_plan_des(plan, seed) for seed in (42, 43)]
    assert all(row["status"] == "bounded" for row in _selected_load_summaries(plan, 42, 2, runs)["results"])
    missing = deepcopy(runs)
    missing[1]["periods"][0]["results"] = []
    measured = _selected_load_summaries(plan, 42, 2, missing)
    assert measured["family_size"] == 2 and measured["replications"] == 2
    assert measured["results"][0]["status"] == "insufficient"
    assert measured["results"][1]["status"] == "bounded"
    failed = deepcopy(runs)
    failed[1]["overall_conservation"] = False
    measured = _selected_load_summaries(plan, 42, 2, failed)
    assert all(row["status"] == "insufficient" and "failed_conservation" in row["reason_codes"]
               for row in measured["results"])


@pytest.mark.parametrize("field,bad", [("failure_count", None), ("failure_count", True),
    ("failure_count", -1), ("failure_count", 2001), ("trials_completed", 0),
    ("trials_completed", False), ("failure_rate", None), ("failure_rate", float("nan")),
    ("failure_rate_adequate", False), ("simulation_supported", False)])
def test_guard_raw_quality_mutations_start_from_current_pass(field, bad):
    schedule, des, mc = synthetic_guard(mu=2., threshold=1.)
    positive = validate_selected_plan(schedule, des, mc["results"], .05, mc_result=mc)
    assert positive["verdict"]["status"] == "pass"
    broken = deepcopy(mc)
    broken["results"][0][field] = bad
    outcome = validate_selected_plan(schedule, des, broken["results"], .05, mc_result=broken)
    assert outcome["verdict"]["status"] == "insufficient"
    assert "raw_mc_inadequate" in outcome["periods"][0]["queues"][0]["load_assessment"]["reason_codes"]


@pytest.mark.parametrize("mutation", ["missing_lane", "unsupported_lane", "failed_period", "bad_assessment"])
def test_guard_evidence_mutations_start_from_current_pass(mutation):
    schedule, des, mc = synthetic_guard(mu=2., threshold=1.)
    assert validate_selected_plan(schedule, des, mc["results"], .05, mc_result=mc)["verdict"]["status"] == "pass"
    des, mc = deepcopy(des), deepcopy(mc)
    if mutation == "missing_lane":
        des["periods"][0]["results"] = []
    elif mutation == "unsupported_lane":
        des["periods"][0]["results"][0]["simulation_supported"] = False
    elif mutation == "failed_period":
        des["periods"][0]["conservation"] = False
    else:
        mc["load_uncertainty"]["results"][0]["failure_probability_upper"] = .5
    assert validate_selected_plan(schedule, des, mc["results"], .05, mc_result=mc)["verdict"]["status"] == "insufficient"


def api_chain(db_engine, client, email, *, seed=42, count=20):
    analysis_id, _, scenario_id = _workspace(db_engine, email)
    login(client, email, "pw")
    headers = csrf_header(client)
    assert _select(client, analysis_id, scenario_id).status_code == 200
    evidence = {}
    for step, body in (("des", {"seed": seed, "load_replications": count}), ("mc", {}), ("validation", {})):
        response = client.post(f"/analyses/{analysis_id}/workflow/simulation/{step}/selected", json=body, headers=headers)
        assert response.status_code == 200, response.text
        evidence[step] = response.json()["evidence"]
    response = client.post(f"/analyses/{analysis_id}/workflow/decision/selected", headers=headers)
    assert response.status_code == 200, response.text
    evidence["decision"] = response.json()["evidence"]
    current = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert all(current[step] is not None and current[step]["id"] == job["id"]
               for step, job in evidence.items())
    return analysis_id, scenario_id, headers, evidence


@pytest.mark.parametrize("seed,count,reason", [(None, 20, "unsupported_seed_domain"),
                                             (-1, 20, "unsupported_seed_domain"), (42, 1, "insufficient_replications")])
def test_valid_raw_requests_with_unsupported_inference_are_current_but_insufficient(db_engine, client, seed, count, reason):
    analysis_id, _, _, evidence = api_chain(db_engine, client, "abstain@example.com", seed=seed, count=count)
    assert reason in evidence["des"]["result"]["load_uncertainty"]["results"][0]["reason_codes"]
    assert evidence["validation"]["result"]["verdict"]["status"] == "insufficient"
    assert evidence["decision"]["result"]["status"] == "insufficient_evidence"
    for job in evidence.values():
        assert job["params"]["selected_load_method"] == job["result"]["selected_load_method"] == SELECTED_LOAD_METHOD
    slots = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert all(slots[slot] is not None for slot in ("des", "mc", "validation", "decision"))


@pytest.mark.parametrize("step,next_step", [("des", "mc"), ("mc", "validation"),
                                           ("validation", "decision"), ("decision", None)])
@pytest.mark.parametrize("source", ["params_json", "result_json"])
@pytest.mark.parametrize("bad_method", [None, "unknown-load-method"])
def test_selected_method_is_required_through_slots_endpoints_and_report_reader(db_engine, client, step, next_step, source, bad_method):
    analysis_id, scenario_id, headers, evidence = api_chain(db_engine, client, "method@example.com")
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, evidence[step]["id"])
        changed = dict(getattr(job, source))
        if bad_method is None:
            changed.pop("selected_load_method")
        else:
            changed["selected_load_method"] = bad_method
        setattr(job, source, changed)
        db.commit()
        historical = deepcopy((job.params_json, job.result_json))
        before_count = db.query(Job).count()
    slots = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert slots[step] is None
    assert slots["decision"] is None
    if next_step:
        path = (f"/analyses/{analysis_id}/workflow/decision/selected" if next_step == "decision" else
                f"/analyses/{analysis_id}/workflow/simulation/{next_step}/selected")
        refused = client.post(path, json={}, headers=headers)
        assert refused.status_code == 409, refused.text
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="method@example.com").one()
        assert current_decision_for_report(db, user, analysis_id, scenario_id) is None
        job = db.get(Job, evidence[step]["id"])
        assert (job.params_json, job.result_json) == historical
        assert db.query(Job).count() == before_count


@pytest.mark.parametrize("step", ["des", "mc"])
def test_explicit_selected_provenance_cannot_shed_guard_by_losing_engine(db_engine, client, step):
    analysis_id, _, _, evidence = api_chain(db_engine, client, "lost-engine@example.com")
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, evidence[step]["id"])
        params, result = dict(job.params_json), dict(job.result_json)
        params.pop("engine")
        params.pop("selected_load_method")
        result.pop("selected_load_method")
        assert result["provenance"] == "SELECTED"
        job.params_json, job.result_json = params, result
        db.commit()
    slots = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert slots[step] is None
    assert slots["decision"] is None


@pytest.mark.parametrize("step", ["des", "mc", "validation", "decision"])
def test_surviving_selected_chain_identity_cannot_become_current_by_marker_erasure(db_engine, client, step):
    analysis_id, _, _, evidence = api_chain(db_engine, client, "erased-markers@example.com")
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, evidence[step]["id"])
        params, result = dict(job.params_json), dict(job.result_json)
        params.pop("engine", None)
        params.pop("selected_load_method")
        result.pop("selected_load_method")
        result.pop("provenance")
        assert params["scenario_id"] == evidence[step]["params"]["scenario_id"]
        job.params_json, job.result_json = params, result
        db.commit()
    slots = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert slots[step] is None
    assert slots["decision"] is None


@pytest.mark.parametrize("step", ["des", "mc", "validation", "decision"])
def test_verified_selected_consumer_refuses_completely_erased_identity(db_engine, client, step):
    analysis_id, scenario_id, headers, evidence = api_chain(db_engine, client, "erased-identity@example.com")
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, evidence[step]["id"])
        params, result = dict(job.params_json), dict(job.result_json)
        for key in ("engine", "selected_load_method", "des_job_id", "mc_job_id", "validation_job_id"):
            params.pop(key, None)
        for key in ("provenance", "selected_load_method", "execution", "evidence_ids", "load_uncertainty",
                    "des_job_id", "mc_job_id", "validation_job_id"):
            result.pop(key, None)
        # Only common server-stamped scope bindings survive; no invented Job FK.
        assert params["scenario_id"] == scenario_id
        job.params_json, job.result_json = params, result
        db.commit()
        before_count = db.query(Job).count()
    slots = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert slots[step] is None and slots["decision"] is None
    if step != "decision":
        refused = client.post(f"/analyses/{analysis_id}/workflow/decision/selected", headers=headers)
        assert refused.status_code in (404, 409), refused.text
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="erased-identity@example.com").one()
        assert current_decision_for_report(db, user, analysis_id, scenario_id) is None
        assert db.query(Job).count() == before_count


def test_optional_scope_recovery_preserves_generic_shared_current_and_disabled_policy():
    policy = syn_policy(selected_load_method=VersionFamily.of("load method", current={SELECTED_LOAD_METHOD}))
    recovered = [("workflow_des", {}, {"execution": "basis-day"}),
                 ("workflow_mc", {"des_job_id": 2}, {}),
                 ("workflow_validation", {"des_job_id": 2, "mc_job_id": 3}, {}),
                 ("workflow_decision", {"validation_job_id": 4, "des_job_id": 2, "mc_job_id": 3}, {})]
    for kind, params, result in recovered:
        params = {"scenario_id": 9, **params}
        assert selected_load_record(kind, params, result, policy)
        disabled = replace(policy, selected_load_method=None)
        assert not selected_load_record(kind, params, result, disabled)
        assert job_references(kind, params, result, policy=disabled) == job_references(kind, params, result)
    for kind in ("workflow_des", "workflow_mc", "workflow_validation", "workflow_decision"):
        # Ordinary shared records and a common scenario binding provide no selected identity.
        assert not selected_load_record(kind, {"scenario_id": 9}, {"results": [{"rho": .9}]}, policy)
        assert selected_load_record(kind, {}, {}, replace(policy, selected_load_context=True))
    for kind in ("workflow_des_current", "workflow_mc_current", "workflow_validation_current"):
        params = {"engine": workflow.SELECTED_DES_ENGINE, "mc_job_id": 3}
        result = {"provenance": "SELECTED"}
        assert not selected_load_record(kind, params, result, replace(policy, selected_load_context=True))
        assert job_references(kind, params, result, policy=policy) == job_references(kind, params, result)
    for invalid in (True, None, "2", 2.0):
        assert not selected_load_record("workflow_mc", {"scenario_id": 9, "des_job_id": invalid}, {}, policy)
