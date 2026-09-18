"""R8: selected-plan Monte Carlo loads are mean routed arrivals, not one day's count.

The selected-plan DES stores one replication (its trace drives playback) plus
the mean routed arrivals per lane over ``load_replications`` paired
replications (seeds from ``replication_seeds``). Monte Carlo evaluates each
active lane at that mean, so its verdict and failing-lane list reflect the
plan rather than one simulated day's integer arrival counts.

Stability criterion (NovaMart, base seeds 7-11), set by the user: (a) the
decision is identical across seeds; (b) the lanes failing in every seed form
the stable core, and any other lane's verdict may differ across seeds only
when (c) in at least one seed its failure-rate 95% CI
(failure_rate_ci_lower..upper) contains MC_FAILURE_RATE_CAP, i.e. the MC run
itself cannot tell that lane from the cap. The one-day estimator violates
this (e.g. a lane failing 85% of trials in one run and passing in another).
"""
from __future__ import annotations

import math

import pytest

from backend.api.workflow import _require_selected_separate_plan, _run_selected_plan_des
from backend.db.models import AnalysisProject, User
from backend.queueing_engine.config import (
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
    MC_FAILURE_RATE_CAP,
)
from backend.queueing_engine.services.separate_optimization import (
    SEPARATE_DES_ENGINE_VERSION,
    replication_seeds,
)
from tests.helpers import create_user, csrf_header, login, make_sessionmaker
from tests.test_setup_derivation import novamart_workbook
from tests.test_upload_setup_api import _analysis, _upload

STABILITY_SEEDS = (7, 8, 9, 10, 11)
TARGET = 0.85
MIN_LANES = 5


def _novamart_selected(db_engine, client, email):
    """Upload NovaMart, optimize at 0.85 with full coverage, save and select (as the Optimize page does)."""
    create_user(db_engine, email, "pw")
    login(client, email, "pw")
    headers = csrf_header(client)
    analysis_id = _analysis(client)["id"]
    uploaded = _upload(client, analysis_id, novamart_workbook(), apply=True)
    assert uploaded.status_code == 201, uploaded.text
    dataset = uploaded.json()["dataset"]
    request = {"target_utilization": TARGET, "server_cost_per_hr": DEFAULT_SERVER_COST_HR,
               "customer_waiting_cost": DEFAULT_WAIT_COST_HR, "lambda_multiplier": 1.0,
               "min_active_lanes": MIN_LANES}
    optimized = client.post(f"/analyses/{analysis_id}/workflow/optimize/separate",
                            headers=headers, json={**request, "dataset_id": dataset["id"]})
    assert optimized.status_code == 200, optimized.text
    schedule = optimized.json()["schedule"]
    options = {**request, "target_utilization": schedule["target_utilization"],
               "max_active_lanes": None, "des": dict(schedule["des"])}
    saved = client.post("/scenarios", headers=headers, json={
        "name": "Optimal @ 85%", "analysis_id": analysis_id, "dataset_id": dataset["id"],
        "settings": {**options, "calculation": {
            "schema_version": 2, "engine_version": SEPARATE_DES_ENGINE_VERSION,
            "analysis_id": analysis_id, "dataset_id": dataset["id"],
            "dataset_row_count": dataset["row_count"], "options": options,
            "calculated_at": "2026-09-19T00:00:00+00:00"}},
        "results": {"schedule": schedule}})
    assert saved.status_code == 201, saved.text
    scenario_id = saved.json()["scenario"]["id"]
    assert client.post(f"/analyses/{analysis_id}/workflow/selection", headers=headers,
                       json={"scenario_id": scenario_id}).status_code == 200
    return analysis_id, headers


def _chain(client, analysis_id, headers, seed, load_replications=None):
    des_body: dict = {"seed": seed}
    if load_replications is not None:
        des_body["load_replications"] = load_replications
    des = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/selected",
                      headers=headers, json=des_body)
    assert des.status_code == 200, des.text
    mc = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
                     headers=headers, json={})
    assert mc.status_code == 200, mc.text
    validation = client.post(f"/analyses/{analysis_id}/workflow/simulation/validation/selected",
                             headers=headers, json={})
    assert validation.status_code == 200, validation.text
    decision = client.post(f"/analyses/{analysis_id}/workflow/decision/selected",
                           headers=headers, json={})
    assert decision.status_code == 200, decision.text
    return des.json()["evidence"], mc.json()["evidence"], decision.json()["decision"]


def test_selected_mc_lambda_is_mean_routed_arrivals_over_replications(db_engine, client):
    analysis_id, headers = _novamart_selected(db_engine, client, "load@example.com")
    des, mc, _ = _chain(client, analysis_id, headers, seed=7, load_replications=4)
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="load@example.com").one()
        plan = _require_selected_separate_plan(db, user, db.get(AnalysisProject, analysis_id))
        runs = [_run_selected_plan_des(plan, seed) for seed in replication_seeds(7, 4)]
    # Replication 0 is the stored run: playback evidence is unchanged.
    assert runs[0]["periods"] == des["result"]["periods"] or all(
        {k: v for k, v in lane.items() if k not in ("arrivals_mean", "lambda_routed_mean")}
        == other for period, stored in zip(runs[0]["periods"], des["result"]["periods"])
        for other, lane in zip(period["results"], stored["results"]))
    expected: dict[tuple[str, str], float] = {}
    for period in runs[0]["periods"]:
        for lane in period["results"]:
            if not lane["active"]:
                continue
            key = (period["time"], lane["queue_id"])
            counts = []
            for run in runs:
                match = next(p for p in run["periods"] if p["time"] == period["time"])
                row = next((r for r in match["results"] if r["queue_id"] == lane["queue_id"]), None)
                counts.append((row or {}).get("arrivals") or 0)
            expected[key] = math.fsum(counts) / len(counts) / period["duration_hours"]
    rows = {(row["time"], row["queue_id"]): row for row in mc["result"]["results"]}
    assert set(rows) == set(expected)
    for key, value in expected.items():
        assert rows[key]["lambda"] == pytest.approx(value), key
    assert any(not float(v).is_integer() for v in expected.values())
    load = des["result"]["load_replications"]
    assert load["count"] == 4 and load["seeds"] == replication_seeds(7, 4)
    assert mc["params"]["lambda_basis"] == "mean routed arrivals over 4 paired DES replications"


def test_load_replications_are_bounded_like_des_replications(db_engine, client):
    analysis_id, headers = _novamart_selected(db_engine, client, "bound@example.com")
    for bad in (0, 21):
        response = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/selected",
                               headers=headers, json={"seed": 7, "load_replications": bad})
        assert response.status_code == 422, bad


def test_novamart_failing_lanes_are_stable_across_base_seeds(db_engine, client):
    analysis_id, headers = _novamart_selected(db_engine, client, "stable@example.com")
    runs = []
    decisions = []
    for seed in STABILITY_SEEDS:
        _, mc, decision = _chain(client, analysis_id, headers, seed=seed)
        runs.append({(row["time"], row["queue_id"]): row for row in mc["result"]["results"]})
        decisions.append(decision["status"])
    failing = [{key for key, row in run.items() if row["status"] == "FAIL"} for run in runs]
    always = set.intersection(*failing)
    differing = set.union(*failing) - always
    print("FAILING_COUNTS", [len(f) for f in failing], "ALWAYS", sorted(always),
          "DIFFERING", sorted(differing), "DECISIONS", decisions)
    # (a) one decision for every seed.
    assert len(set(decisions)) == 1, decisions
    # (b)+(c) outside the always-failing core, a differing verdict must be one
    # the MC cannot separate from the cap in at least one seed.
    for key in differing:
        cis = [(run[key]["failure_rate_ci_lower"], run[key]["failure_rate_ci_upper"])
               for run in runs if key in run]
        assert any(low is not None and high is not None and low <= MC_FAILURE_RATE_CAP <= high
                   for low, high in cis), (key, cis)


# --- R9: selected MC failure threshold defaults to the plan's target -------------------

def _small_selected(db_engine, client, email):
    from tests.test_selected_plan_decision import _api_workspace

    analysis_id, _, scenario_id = _api_workspace(db_engine, email)  # plan target 0.70
    login(client, email, "pw")
    headers = csrf_header(client)
    assert client.post(f"/analyses/{analysis_id}/workflow/selection", headers=headers,
                       json={"scenario_id": scenario_id}).status_code == 200
    des = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/selected",
                      headers=headers, json={"seed": 7, "load_replications": 3})
    assert des.status_code == 200, des.text
    return analysis_id, headers


def test_selected_mc_threshold_defaults_to_plan_target(db_engine, client):
    analysis_id, headers = _small_selected(db_engine, client, "r9a@example.com")
    mc = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
                     headers=headers, json={})
    assert mc.status_code == 200, mc.text
    params = mc.json()["evidence"]["params"]
    assert params["failure_threshold"] == pytest.approx(0.70)
    assert params["failure_threshold_source"] == "plan_target"
    assert params["load_replications"] == 3
    assert params["load_seeds"] == replication_seeds(7, 3)
    assert params["lambda_basis"] == "mean routed arrivals over 3 paired DES replications"
    assert all(row["failure_threshold"] == pytest.approx(0.70)
               for row in mc.json()["evidence"]["result"]["results"])


def test_selected_mc_explicit_threshold_is_recorded_as_user(db_engine, client):
    analysis_id, headers = _small_selected(db_engine, client, "r9b@example.com")
    mc = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
                     headers=headers, json={"failure_threshold": 0.75})
    assert mc.status_code == 200, mc.text
    params = mc.json()["evidence"]["params"]
    assert params["failure_threshold"] == pytest.approx(0.75)
    assert params["failure_threshold_source"] == "user"


def test_current_and_shared_mc_defaults_stay_075():
    from backend.api.workflow import SelectedMcRequest, WorkflowMcRequest
    from backend.queueing_engine.config import MC_DEFAULT_FAILURE_THRESHOLD

    assert MC_DEFAULT_FAILURE_THRESHOLD == 0.75
    assert WorkflowMcRequest().failure_threshold == 0.75
    assert issubclass(SelectedMcRequest, WorkflowMcRequest)
    assert "failure_threshold" not in SelectedMcRequest().model_fields_set
    assert "load_days" not in WorkflowMcRequest.model_fields


def test_mc_rejects_des_evidence_without_mean_loads(db_engine, client):
    from backend.db.models import Job

    analysis_id, headers = _small_selected(db_engine, client, "r8old@example.com")
    with make_sessionmaker(db_engine)() as db:
        job = db.query(Job).filter_by(kind="workflow_des").one()
        result = dict(job.result_json)
        result.pop("load_replications", None)
        job.result_json = result
        db.commit()
    mc = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
                     headers=headers, json={})
    assert mc.status_code == 409, mc.text
    assert "Rerun selected-plan DES" in mc.json()["detail"]
