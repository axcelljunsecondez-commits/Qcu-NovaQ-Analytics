"""G5: generation identity wired through the workflow behind ``GENERATION_ENFORCEMENT_ENABLED``
(gates G-T2, G-T4, G-T5, G-T6 with enforcement on, G-T10, G-T11, G-T12 and G-T13).

Spec: docs/superpowers/specs/2026-09-26-generation-identity-contract.md §7, §8, §8.1 item 4, §9, §13
and §14 (G5). Decisions of 2026-09-29: one module flag, off, read at call time (D1); Decision and
report semantics are G6, so nothing here claims G-T7 or G-T8 (D2); the scenario's dataset binding is
built in workflow.py from the value exactly as stored (D3); refusal statuses and texts (D4); the
selected-plan binding is checked after every existing check (D5); the OD-G2 token part and the
``_save_job`` refusal belong to G5 (D6); ``run_validation_current`` checks the token only.

Enforcement stays off for the application. These tests switch it on with monkeypatch, which shows
what the wiring does, not how any deployment behaves.

Data labels: SYNTHETIC rows come from the real endpoints unless marked "direct row edit/insert". A
replacement is built as spec §13 describes: delete through the API, then insert directly under the
deleted row's id and stored ``created_at``.

Runs on SQLite, and on PostgreSQL when NOVAQ_TEST_DATABASE_URL names a dedicated *_test database.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm.attributes import flag_modified

import backend.api.workflow as workflow_api
from backend.api.evidence_status import (
    ArtifactRef,
    EvidenceRecord,
    EvidenceStatus,
    GenerationRequirement,
    ReasonCode,
    classify,
)
from backend.api.settings import Settings
from backend.db.models import AnalysisProject, Dataset, Job, Scenario, User
from tests.helpers import create_user, csrf_header, login, make_sessionmaker
from tests.test_d7_current_evidence_dataset import Workspace
from tests.test_generation_job_stamping import TOKENS, _direct_rows, _edit_job, _refuse_computation
from tests.test_separate_report import _api_workspace
from tests.test_step5_missing_dependency import DES_PAYLOAD, MC_PAYLOAD, MISSING_DEPENDENCY_DETAIL, Shop

R = ReasonCode
S = EvidenceStatus
OTHER = "0" * 32          # a well-formed token that no row holds (SYNTHETIC)
GENERATION_CODES = {R.GENERATION_MISMATCH, R.GENERATION_UNRECORDED}
EMPTY_CURRENT = {"des": None, "mc": None, "validation": None}
EMPTY_SHARED = {"scenario": None, "des": None, "mc": None, "validation": None, "decision": None}
SELECT_FIRST = "Select a Scenario in Compare first."
_DROP = object()          # remove the key rather than write a value
_LIVE = object()          # the dataset row's own generation


def _enforce(monkeypatch, on: bool = True) -> None:
    monkeypatch.setattr(workflow_api, "GENERATION_ENFORCEMENT_ENABLED", on)


def _generation(db_engine, model, row_id: int) -> str:
    with make_sessionmaker(db_engine)() as db:
        return db.get(model, row_id).generation


def _count(db_engine, kind: str) -> int:
    with make_sessionmaker(db_engine)() as db:
        return db.query(Job).filter(Job.kind == kind).count()


def _latest(db_engine, kind: str) -> int:
    with make_sessionmaker(db_engine)() as db:
        return db.query(Job).filter(Job.kind == kind).order_by(Job.id.desc()).first().id


def _stored(db_engine) -> dict[str, Any]:
    """Every stored job, scenario and dataset field that evidence or identity depends on."""
    with make_sessionmaker(db_engine)() as db:
        return {
            "jobs": {job.id: (job.kind, job.status, deepcopy(job.params_json), deepcopy(job.result_json),
                              job.created_at) for job in db.query(Job)},
            "scenarios": {row.id: (row.generation, row.dataset_generation, row.dataset_id,
                                   deepcopy(row.settings_json), deepcopy(row.results_json), row.created_at)
                          for row in db.query(Scenario)},
            "datasets": {row.id: (row.generation, row.created_at, deepcopy(row.normalized_json))
                         for row in db.query(Dataset)},
        }


def _set_token(db_engine, job_id: int, key: str, value: Any) -> None:
    """SYNTHETIC (direct row edit): a recorded token no endpoint would write. _DROP removes the key."""
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, job_id)
        params = dict(job.params_json or {})
        if value is _DROP:
            params.pop(key, None)
        else:
            params[key] = value
        job.params_json = params
        flag_modified(job, "params_json")
        db.commit()


def _bind(db_engine, scenario_id: int, value: Any = _LIVE) -> None:
    """SYNTHETIC (direct row edit): the dataset generation a verified save records (spec §13 fixture
    impact). Rows inserted directly, like every fixture scenario here, carry none."""
    with make_sessionmaker(db_engine)() as db:
        scenario = db.get(Scenario, scenario_id)
        scenario.dataset_generation = db.get(Dataset, scenario.dataset_id).generation if value is _LIVE else value
        db.commit()


def _columns(row: Any) -> dict[str, Any]:
    """Every mapped column of a row except its generation token."""
    return {attr.key: deepcopy(getattr(row, attr.key)) for attr in sa_inspect(type(row)).column_attrs
            if attr.key != "generation"}


def _replace(client, headers: dict[str, str], db_engine, model, row_id: int, route: str, *,
             renamed: bool) -> None:
    """Spec §13: delete through the API, then insert directly (SYNTHETIC) under the same id and stored
    created_at. ``renamed`` changes the name (G-T10); otherwise the replacement is byte-identical
    (G-T11). The token is never copied, and G1-H would refuse a reissued one."""
    with make_sessionmaker(db_engine)() as db:
        original = db.get(model, row_id)
        columns, old = _columns(original), original.generation
    assert client.delete(f"/{route}/{row_id}", headers=headers).status_code == 200
    if renamed:
        columns["name"] = "Replacement"
    with make_sessionmaker(db_engine)() as db:
        db.add(model(**columns))
        db.commit()
    with make_sessionmaker(db_engine)() as db:
        replacement = db.get(model, row_id)
        assert replacement.created_at == columns["created_at"]
        assert replacement.generation != old


def _plan(client, db_engine, email: str = "g5-plan@example.com", *, bind: bool = True):
    """A separate-queue analysis with one saved schema-2 plan (SYNTHETIC direct row insert)."""
    analysis_id, dataset_id, scenario_id = _api_workspace(db_engine, email)
    if bind:
        _bind(db_engine, scenario_id)
    assert login(client, email, "pw") == 200
    return analysis_id, dataset_id, scenario_id, csrf_header(client)


def _post(client, headers: dict[str, str], analysis_id: int, path: str, body: dict[str, Any] | None = None):
    return client.post(f"/analyses/{analysis_id}/workflow/{path}", headers=headers,
                       json=body if body is not None else {})


def _workflow(client, analysis_id: int) -> dict[str, Any]:
    response = client.get(f"/analyses/{analysis_id}/workflow")
    assert response.status_code == 200, response.text
    return response.json()


def _slot_ids(workflow: dict[str, Any], *names: str) -> dict[str, int | None]:
    return {name: (workflow[name] or {}).get("id") for name in names}


def _assess(db_engine, job_id: int, *, enforced: bool, monkeypatch):
    """The application's own assessment of one stored job (a new session reads the stored rows)."""
    _enforce(monkeypatch, enforced)
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, job_id)
        analysis = db.get(AnalysisProject, (job.params_json or {})["analysis_id"])
        user = db.get(User, job.user_id)
        context = workflow_api._evidence_context(db, user, analysis)
        return workflow_api._assess_evidence(db, job, context, workflow_api._current_evidence_policy())


def _unique_reasons(assessment) -> bool:
    pairs = [(reason.code, reason.subject) for reason in assessment.reasons]
    return len(pairs) == len(set(pairs)) and all(_unique_reasons(item) for item in assessment.dependencies)


# -- The flag (D1) -----------------------------------------------------------------------------------


def test_enforcement_is_off_by_default_and_read_at_call_time(monkeypatch):
    assert workflow_api.GENERATION_ENFORCEMENT_ENABLED is False
    assert workflow_api._current_evidence_policy().generation_kinds == frozenset()
    _enforce(monkeypatch)
    assert workflow_api._current_evidence_policy().generation_kinds == frozenset({"dataset", "scenario"})
    _enforce(monkeypatch, False)
    assert workflow_api._current_evidence_policy().generation_kinds == frozenset()


# -- G-T4, G-T10, G-T11: Current DES, MC and validation --------------------------------------------


def test_current_evidence_with_matching_generations_stays_current(client, db_engine, monkeypatch):
    workspace = Workspace(client, db_engine, email="g5-current@example.com")
    workspace.upload(2, "a.csv")
    _enforce(monkeypatch)
    jobs = workspace.run_all()              # Current validation passes its token check here
    assert workspace.slots() == jobs


@pytest.mark.parametrize("renamed", [False, True], ids=["byte-identical", "same-id-and-time"])
def test_a_replaced_dataset_rejects_current_evidence_only_under_enforcement(client, db_engine, monkeypatch,
                                                                            renamed):
    workspace = Workspace(client, db_engine, email="g5-dataset@example.com")
    dataset_id = workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    _replace(client, workspace.headers, db_engine, Dataset, dataset_id, "datasets", renamed=renamed)
    stored = _stored(db_engine)
    assert workspace.slots() == jobs        # flag off: exactly Steps 1-5, which cannot tell (G-T13)
    _enforce(monkeypatch)
    assert workspace.slots() == EMPTY_CURRENT
    run = f"/analyses/{workspace.analysis_id}/workflow/simulation/validation/current"
    refused = client.post(run, headers=workspace.headers, json={})
    assert refused.status_code == 409
    assert refused.json()["detail"] == workflow_api.CURRENT_MC_STALE_DETAIL
    assert _stored(db_engine) == stored
    _enforce(monkeypatch, False)
    assert client.post(run, headers=workspace.headers, json={}).status_code == 200
    _enforce(monkeypatch)
    renewed = workspace.run_all()           # evidence recalculated on the replacement is current
    assert workspace.slots() == renewed


@pytest.mark.parametrize("value", [_DROP, None, "", "   "], ids=["missing", "null", "empty", "blank"])
def test_legacy_current_evidence_is_never_current_under_enforcement(client, db_engine, monkeypatch, value):
    workspace = Workspace(client, db_engine, email="g5-legacy-current@example.com")
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    for job_id in jobs.values():
        _set_token(db_engine, job_id, "dataset_generation", value)
    stored = _stored(db_engine)
    assert workspace.slots() == jobs        # flag off: a token is never consulted
    _enforce(monkeypatch)
    assert workspace.slots() == EMPTY_CURRENT
    refused = client.post(f"/analyses/{workspace.analysis_id}/workflow/simulation/validation/current",
                          headers=workspace.headers, json={})
    assert refused.status_code == 409
    assert refused.json()["detail"] == workflow_api.CURRENT_MC_GENERATION_UNRECORDED_DETAIL
    assert _stored(db_engine) == stored


@pytest.mark.parametrize("value", [0, 1234, True], ids=["zero", "number", "boolean"])
def test_a_recorded_value_that_is_not_text_is_never_a_token(client, db_engine, monkeypatch, value):
    workspace = Workspace(client, db_engine, email="g5-not-text@example.com")
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    _set_token(db_engine, jobs["mc"], "dataset_generation", value)
    # The classifier (G4, unchanged) keeps such a value tagged, so it can never equal a live token.
    assessment = _assess(db_engine, jobs["mc"], enforced=True, monkeypatch=monkeypatch)
    assert R.GENERATION_MISMATCH in assessment.codes and not assessment.is_current
    assert workspace.slots()["mc"] is None
    # The refusal names it unrecorded, never stale or replaced: no token was recorded.
    refused = client.post(f"/analyses/{workspace.analysis_id}/workflow/simulation/validation/current",
                          headers=workspace.headers, json={})
    assert refused.status_code == 409
    assert refused.json()["detail"] == workflow_api.CURRENT_MC_GENERATION_UNRECORDED_DETAIL


def test_current_validation_checks_the_token_after_every_earlier_refusal(client, db_engine, monkeypatch):
    workspace = Workspace(client, db_engine, email="g5-order-current@example.com")
    workspace.upload(2, "a.csv")
    mc = workspace.run_all()["mc"]
    _set_token(db_engine, mc, "dataset_generation", _DROP)
    _enforce(monkeypatch)
    run = f"/analyses/{workspace.analysis_id}/workflow/simulation/validation/current"
    original = {"setup_hash": None, "failure_rate_cap": None}
    with make_sessionmaker(db_engine)() as db:
        params = db.get(Job, mc).params_json
        original = {key: params[key] for key in original}
    _edit_job(db_engine, mc, params={"setup_hash": "stale"})                 # SYNTHETIC (direct row edit)
    refused = client.post(run, headers=workspace.headers, json={})
    assert (refused.status_code, refused.json()["detail"]) == (409, workflow_api.SETUP_STALE_DETAIL)
    _edit_job(db_engine, mc, params={**original, "failure_rate_cap": None})  # SYNTHETIC (direct row edit)
    refused = client.post(run, headers=workspace.headers, json={})
    assert (refused.status_code, refused.json()["detail"]) == (
        422, "Current Monte Carlo evidence has no usable failure cap.")
    _edit_job(db_engine, mc, params=original)                                # SYNTHETIC (direct row edit)
    refused = client.post(run, headers=workspace.headers, json={})
    assert (refused.status_code, refused.json()["detail"]) == (
        409, workflow_api.CURRENT_MC_GENERATION_UNRECORDED_DETAIL)


# -- Spec §8 row 1: a scenario is eligible only with its verified dataset generation -----------------


@pytest.mark.parametrize("binding", [None, "", "   ", OTHER], ids=["null", "empty", "blank", "other-row"])
def test_a_shared_scenario_is_selectable_under_enforcement_only_with_its_dataset_generation(
        client, db_engine, monkeypatch, binding):
    shop = Shop(client, db_engine, email="g5-select@example.com")
    scenario_id = shop.seed_scenario(shop.upload(4, "a.csv"), 4)
    _bind(db_engine, scenario_id, binding)
    stored = _stored(db_engine)
    _enforce(monkeypatch)
    refused = shop.select(scenario_id)
    assert (refused.status_code, refused.json()["detail"]) == (422, workflow_api.SCENARIO_PROVENANCE_DETAIL)
    assert _stored(db_engine) == stored
    _enforce(monkeypatch, False)
    assert shop.select(scenario_id).status_code == 200      # flag off: the pre-G5 rule
    _enforce(monkeypatch)
    _bind(db_engine, scenario_id)
    assert shop.select(scenario_id).status_code == 200


def test_a_separate_plan_is_selectable_under_enforcement_only_with_its_dataset_generation(
        client, db_engine, monkeypatch):
    analysis_id, _, scenario_id, headers = _plan(client, db_engine, bind=False)
    _enforce(monkeypatch)
    refused = _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id})
    assert (refused.status_code, refused.json()["detail"]) == (422, workflow_api.SCENARIO_PROVENANCE_DETAIL)
    _bind(db_engine, scenario_id)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200


def test_the_provenance_check_runs_after_every_existing_refusal(client, db_engine, monkeypatch):
    shop = Shop(client, db_engine, email="g5-order-shared@example.com")
    scenario_id = shop.seed_scenario(shop.upload(4, "a.csv"), 4)     # unbound, and about to be stale
    shop.upload(5, "b.csv")
    _enforce(monkeypatch)
    refused = shop.select(scenario_id)
    assert (refused.status_code, refused.json()["detail"]) == (422, "Scenario is stale for the current dataset.")


def test_the_separate_provenance_check_runs_after_every_existing_refusal(client, db_engine, monkeypatch):
    analysis_id, dataset_id, scenario_id, headers = _plan(client, db_engine, bind=False)
    with make_sessionmaker(db_engine)() as db:                      # SYNTHETIC (direct row insert)
        columns = _columns(db.get(Dataset, dataset_id))
        columns.pop("id")
        columns.pop("created_at")
        db.add(Dataset(**columns))
        db.commit()
    _enforce(monkeypatch)
    refused = _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id})
    assert (refused.status_code, refused.json()["detail"]) == (422, "Separate plan is stale for the current dataset.")


# -- G-T2: selection binding and Option A -----------------------------------------------------------


@pytest.mark.parametrize("recorded", [_DROP, None, "", OTHER], ids=["missing", "null", "empty", "mismatched"])
def test_a_shared_selection_binds_only_to_its_own_generation(client, db_engine, monkeypatch, recorded):
    shop = Shop(client, db_engine, email="g5-bind-shared@example.com")
    scenario_id = shop.seed_scenario(shop.upload(4, "a.csv"), 4)
    _bind(db_engine, scenario_id)
    _enforce(monkeypatch)
    assert shop.select(scenario_id).status_code == 200
    chain = shop.run_chain()
    assert shop.slots() == {"scenario": scenario_id, **chain, "decision": None}
    _set_token(db_engine, _latest(db_engine, "workflow_selection"), "scenario_generation", recorded)
    stored = _stored(db_engine)
    assert shop.slots() == EMPTY_SHARED
    assert shop.workflow()["decision_stale"] is False               # Option A: no eligible selection
    refused = client.post(f"/analyses/{shop.analysis_id}/workflow/simulation/des", headers=shop.headers,
                          json=DES_PAYLOAD)
    assert (refused.status_code, refused.json()["detail"]) == (409, SELECT_FIRST)
    assert _stored(db_engine) == stored
    _enforce(monkeypatch, False)
    assert shop.slots() == {"scenario": scenario_id, **chain, "decision": None}   # G-T13


def test_decision_stale_keeps_option_a_under_enforcement(client, db_engine, monkeypatch):
    shop = Shop(client, db_engine, email="g5-option-a@example.com")
    scenario_id = shop.seed_scenario(shop.upload(4, "a.csv"), 4)
    _bind(db_engine, scenario_id)
    _enforce(monkeypatch)
    assert shop.select(scenario_id).status_code == 200
    chain = shop.run_chain()
    assert shop.decide().json()["persisted"] is True
    assert shop.workflow()["decision_stale"] is False
    _set_token(db_engine, chain["des"], "scenario_generation", OTHER)
    workflow = shop.workflow()
    assert _slot_ids(workflow, "scenario", "des", "decision") == {"scenario": scenario_id, "des": None,
                                                                  "decision": None}
    assert workflow["decision_stale"] is True        # an eligible plan whose Decision chain is broken
    _set_token(db_engine, _latest(db_engine, "workflow_selection"), "scenario_generation", _DROP)
    workflow = shop.workflow()
    assert _slot_ids(workflow, "scenario", "decision") == {"scenario": None, "decision": None}
    assert workflow["decision_stale"] is False       # no eligible selection: the Setup meaning (Option A)


# -- G-T5, G-T10, G-T11: selected-plan DES, MC and validation --------------------------------------


SELECTED_STEPS = [("simulation/des/selected", {"seed": 7}), ("simulation/mc/selected", {}),
                  ("simulation/validation/selected", {})]


def test_the_selected_plan_chain_runs_when_every_generation_matches(client, db_engine, monkeypatch):
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    _enforce(monkeypatch)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    for path, body in SELECTED_STEPS:
        response = _post(client, headers, analysis_id, path, body)
        assert response.status_code == 200, (path, response.text)
    workflow = _workflow(client, analysis_id)
    assert workflow["scenario"]["id"] == scenario_id
    assert all(workflow[name] is not None for name in ("des", "mc", "validation"))


@pytest.mark.parametrize("renamed", [False, True], ids=["byte-identical", "same-id-and-time"])
def test_a_replaced_scenario_is_refused_by_the_selected_plan_endpoints(client, db_engine, monkeypatch, renamed):
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    des_id = _post(client, headers, analysis_id, *SELECTED_STEPS[0]).json()["evidence"]["id"]
    _replace(client, headers, db_engine, Scenario, scenario_id, "scenarios", renamed=renamed)
    stored = _stored(db_engine)
    # Flag off: the replacement verifies and inherits the old evidence, the defect G5 wires the fix for.
    assert _slot_ids(_workflow(client, analysis_id), "scenario", "des") == {"scenario": scenario_id, "des": des_id}
    _enforce(monkeypatch)
    for path, body in SELECTED_STEPS:
        refused = _post(client, headers, analysis_id, path, body)
        assert (refused.status_code, refused.json()["detail"]) == (409, workflow_api.SELECTED_PLAN_REPLACED_DETAIL)
    assert _slot_ids(_workflow(client, analysis_id), "scenario", "des") == {"scenario": None, "des": None}
    assert _stored(db_engine) == stored
    # Selecting the replacement again binds to its own generation.
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    assert _post(client, headers, analysis_id, *SELECTED_STEPS[0]).status_code == 200


@pytest.mark.parametrize("recorded", [_DROP, None, "", "   ", 0], ids=["missing", "null", "empty", "blank",
                                                                     "not-text"])
def test_an_unrecorded_selection_gets_the_neutral_refusal(client, db_engine, monkeypatch, recorded):
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    _enforce(monkeypatch)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    _set_token(db_engine, _latest(db_engine, "workflow_selection"), "scenario_generation", recorded)
    refused = _post(client, headers, analysis_id, *SELECTED_STEPS[0])
    assert (refused.status_code, refused.json()["detail"]) == (
        409, workflow_api.SELECTION_GENERATION_UNRECORDED_DETAIL)


def test_the_selected_plan_binding_is_checked_after_every_existing_refusal(client, db_engine, monkeypatch):
    """D5: an unrecorded selection on a plan that also fails an earlier check keeps that refusal."""
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    _enforce(monkeypatch)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    _set_token(db_engine, _latest(db_engine, "workflow_selection"), "scenario_generation", _DROP)
    with make_sessionmaker(db_engine)() as db:                      # SYNTHETIC (direct row edit)
        scenario = db.get(Scenario, scenario_id)
        settings = deepcopy(scenario.settings_json)
        settings["calculation"]["options"]["lambda_multiplier"] = -1
        scenario.settings_json = settings
        flag_modified(scenario, "settings_json")
        db.commit()
    refused = _post(client, headers, analysis_id, *SELECTED_STEPS[0])
    assert (refused.status_code, refused.json()["detail"]) == (422, "Selected scenario demand multiplier is invalid.")
    _bind(db_engine, scenario_id, None)
    refused = _post(client, headers, analysis_id, *SELECTED_STEPS[0])
    assert (refused.status_code, refused.json()["detail"]) == (
        422, f"Selected plan is not runnable: {workflow_api.SCENARIO_PROVENANCE_DETAIL}")


# -- G-T6 with enforcement on: the token part of the OD-G2 gates ---------------------------------------


OD_G2_CASES = [
    pytest.param({"drop": TOKENS}, workflow_api.GENERATION_UNRECORDED_DETAIL, id="unstamped"),
    pytest.param({"drop": ("dataset_generation",)}, workflow_api.GENERATION_UNRECORDED_DETAIL,
                 id="dataset-unrecorded"),
    pytest.param({"params": {"scenario_generation": OTHER}}, MISSING_DEPENDENCY_DETAIL, id="scenario-mismatch"),
    pytest.param({"params": {"dataset_generation": OTHER}}, MISSING_DEPENDENCY_DETAIL, id="dataset-mismatch"),
    pytest.param({"params": {"scenario_generation": OTHER}, "drop": ("dataset_generation",)},
                 MISSING_DEPENDENCY_DETAIL, id="mismatch-and-unrecorded"),
    pytest.param({"params": {"dataset_id": 99999}, "drop": TOKENS}, MISSING_DEPENDENCY_DETAIL,
                 id="step5-failure-and-unrecorded"),
]


@pytest.mark.parametrize(("change", "detail"), OD_G2_CASES)
def test_selected_mc_refuses_a_des_input_by_its_tokens_under_enforcement(client, db_engine, monkeypatch,
                                                                         change, detail):
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    _enforce(monkeypatch)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    des_id = _post(client, headers, analysis_id, *SELECTED_STEPS[0]).json()["evidence"]["id"]
    _edit_job(db_engine, des_id, **change)                           # SYNTHETIC (direct row edit)
    stored, before = _stored(db_engine), _count(db_engine, "workflow_mc")
    _refuse_computation(monkeypatch, "mc_simulate_segments")
    refused = _post(client, headers, analysis_id, *SELECTED_STEPS[1])
    assert (refused.status_code, refused.json()["detail"]) == (409, detail)
    assert _count(db_engine, "workflow_mc") == before
    assert _stored(db_engine) == stored


@pytest.mark.parametrize("broken", ["des", "mc"])
@pytest.mark.parametrize(("change", "detail"), [
    pytest.param({"drop": TOKENS}, workflow_api.GENERATION_UNRECORDED_DETAIL, id="unstamped"),
    pytest.param({"params": {"dataset_generation": OTHER}}, MISSING_DEPENDENCY_DETAIL, id="mismatched"),
])
def test_selected_validation_refuses_an_input_by_its_tokens_under_enforcement(client, db_engine, monkeypatch,
                                                                              broken, change, detail):
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    _enforce(monkeypatch)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    jobs = {name: _post(client, headers, analysis_id, path, body).json()["evidence"]["id"]
            for name, (path, body) in zip(("des", "mc"), SELECTED_STEPS[:2])}
    _edit_job(db_engine, jobs[broken], **change)                     # SYNTHETIC (direct row edit)
    before = _count(db_engine, "workflow_validation")
    _refuse_computation(monkeypatch, "validate_selected_plan")
    refused = _post(client, headers, analysis_id, *SELECTED_STEPS[2])
    assert (refused.status_code, refused.json()["detail"]) == (409, detail)
    assert _count(db_engine, "workflow_validation") == before


def test_an_unrecorded_generation_upstream_gets_the_unrecorded_text(client, db_engine, monkeypatch):
    """The derived UPSTREAM_* reason is not a cause: an MC job whose only defect is its DES input's
    missing token is refused as unrecorded, not as a record that no longer exists."""
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    _enforce(monkeypatch)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    jobs = {name: _post(client, headers, analysis_id, path, body).json()["evidence"]["id"]
            for name, (path, body) in zip(("des", "mc"), SELECTED_STEPS[:2])}
    _edit_job(db_engine, jobs["des"], drop=TOKENS)                   # SYNTHETIC (direct row edit)
    assert R.UPSTREAM_MISSING_PROVENANCE in _assess(db_engine, jobs["mc"], enforced=True,
                                                    monkeypatch=monkeypatch).codes
    with make_sessionmaker(db_engine)() as db:
        mc = db.get(Job, jobs["mc"])
        with pytest.raises(HTTPException) as refused:
            workflow_api.require_dependencies_current(db, db.get(User, mc.user_id),
                                                      db.get(AnalysisProject, analysis_id), mc)
    assert (refused.value.status_code, refused.value.detail) == (409, workflow_api.GENERATION_UNRECORDED_DETAIL)


# -- D7: the latest evidence is never replaced by an older match ------------------------------------


def test_a_current_slot_never_falls_back_to_older_evidence(client, db_engine, monkeypatch):
    workspace = Workspace(client, db_engine, email="g5-fallback-current@example.com")
    workspace.upload(2, "a.csv")
    _enforce(monkeypatch)
    older = workspace.run("des", DES_PAYLOAD)
    latest = workspace.run("des", DES_PAYLOAD)
    assert older < latest and workspace.slots()["des"] == latest
    _set_token(db_engine, latest, "dataset_generation", _DROP)
    assert workspace.slots()["des"] is None


def test_selected_mc_never_falls_back_to_an_older_des_run(client, db_engine, monkeypatch):
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    _enforce(monkeypatch)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    older = _post(client, headers, analysis_id, *SELECTED_STEPS[0]).json()["evidence"]["id"]
    latest = _post(client, headers, analysis_id, *SELECTED_STEPS[0]).json()["evidence"]["id"]
    assert older < latest
    _set_token(db_engine, latest, "dataset_generation", _DROP)
    _refuse_computation(monkeypatch, "mc_simulate_segments")
    refused = _post(client, headers, analysis_id, *SELECTED_STEPS[1])
    assert (refused.status_code, refused.json()["detail"]) == (409, workflow_api.GENERATION_UNRECORDED_DETAIL)


# -- Spec §7: _save_job refuses a disagreeing scenario binding under enforcement ---------------------


def _direct_scenario(db, user: User, analysis: AnalysisProject, dataset: Dataset, binding: Any) -> Scenario:
    scenario = Scenario(user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id, name="s",
                        settings_json={}, results_json={}, dataset_generation=binding)
    db.add(scenario)
    db.commit()
    return scenario


@pytest.mark.parametrize("binding", [None, "", "   ", OTHER], ids=["null", "empty", "blank", "other-row"])
def test_save_job_refuses_a_scenario_whose_dataset_generation_disagrees(db_engine, monkeypatch, binding):
    create_user(db_engine, "g5-save@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:                      # SYNTHETIC (direct row insert)
        user, analysis, dataset = _direct_rows(db, "g5-save@example.com")
        scenario = _direct_scenario(db, user, analysis, dataset, binding)
        _enforce(monkeypatch)
        with pytest.raises(HTTPException) as refused:
            workflow_api._save_job(db, user, "workflow_des", analysis, scenario, {}, {}, Settings(), dataset)
        assert (refused.value.status_code, refused.value.detail) == (409, workflow_api.SCENARIO_PROVENANCE_DETAIL)
    assert _count(db_engine, "workflow_des") == 0


def test_save_job_stores_evidence_when_the_generations_agree_or_enforcement_is_off(db_engine, monkeypatch):
    create_user(db_engine, "g5-save-ok@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:                      # SYNTHETIC (direct row insert)
        user, analysis, dataset = _direct_rows(db, "g5-save-ok@example.com")
        unbound = _direct_scenario(db, user, analysis, dataset, None)
        workflow_api._save_job(db, user, "workflow_des", analysis, unbound, {}, {}, Settings(), dataset)
        bound = _direct_scenario(db, user, analysis, dataset, dataset.generation)
        _enforce(monkeypatch)
        workflow_api._save_job(db, user, "workflow_des", analysis, bound, {}, {}, Settings(), dataset)
        workflow_api._save_job(db, user, "workflow_des_current", analysis, None, {}, {}, Settings(), dataset)
    assert _count(db_engine, "workflow_des") == 2
    assert _count(db_engine, "workflow_des_current") == 1


# -- Records built from the database (spec §9, D3) --------------------------------------------------


def _without_live_tokens(record: EvidenceRecord) -> EvidenceRecord:
    return replace(record, dependencies=tuple(
        replace(dependency, generation=None,
                record=_without_live_tokens(dependency.record) if dependency.record is not None else None)
        for dependency in record.dependencies))


def test_database_records_carry_live_tokens_and_the_recorded_binding(client, db_engine, monkeypatch):
    analysis_id, dataset_id, scenario_id, headers = _plan(client, db_engine)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    des_id = _post(client, headers, analysis_id, *SELECTED_STEPS[0]).json()["evidence"]["id"]
    dataset_ref, scenario_ref = ArtifactRef("dataset", dataset_id), ArtifactRef("scenario", scenario_id)
    with make_sessionmaker(db_engine)() as db:
        job, analysis = db.get(Job, des_id), db.get(AnalysisProject, analysis_id)
        user, scenario, dataset = db.get(User, job.user_id), db.get(Scenario, scenario_id), db.get(Dataset, dataset_id)
        context = workflow_api._evidence_context(db, user, analysis)
        off = workflow_api._job_evidence_record(db, job, workflow_api._current_evidence_policy(), frozenset({des_id}))
        dependencies = {dependency.ref: dependency for dependency in off.dependencies}
        assert dependencies[dataset_ref].generation == dataset.generation
        assert dependencies[scenario_ref].generation == scenario.generation
        assert off.generations == () and dependencies[scenario_ref].record.generations == ()
        # G-T13: while no kind is enabled, the live tokens change nothing.
        assert classify(off, context) == classify(_without_live_tokens(off), context)
        assert classify(off, context).is_current
        _enforce(monkeypatch)
        on = workflow_api._job_evidence_record(db, job, workflow_api._current_evidence_policy(), frozenset({des_id}))
        assert set(on.generations) == {GenerationRequirement(dataset_ref, dataset.generation),
                                       GenerationRequirement(scenario_ref, scenario.generation)}
        plan_record = {dependency.ref: dependency for dependency in on.dependencies}[scenario_ref].record
        assert plan_record.generations == (GenerationRequirement(dataset_ref, scenario.dataset_generation),)
        assert classify(on, context).is_current


def test_a_legacy_scenario_makes_the_evidence_on_it_non_current_through_the_chain(client, db_engine, monkeypatch):
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    des_id = _post(client, headers, analysis_id, *SELECTED_STEPS[0]).json()["evidence"]["id"]
    _bind(db_engine, scenario_id, None)          # SYNTHETIC: a plan saved before G2 recorded a binding
    assert _assess(db_engine, des_id, enforced=False, monkeypatch=monkeypatch).is_current
    assessment = _assess(db_engine, des_id, enforced=True, monkeypatch=monkeypatch)
    assert assessment.status is S.MISSING_PROVENANCE
    assert R.UPSTREAM_MISSING_PROVENANCE in assessment.codes
    plan = {item.ref: item for item in assessment.dependencies}[ArtifactRef("scenario", scenario_id)]
    assert R.GENERATION_UNRECORDED in plan.codes
    with make_sessionmaker(db_engine)() as db:   # the NULL is carried exactly, never turned into text
        record = workflow_api._scenario_evidence_record(db, db.get(Scenario, scenario_id),
                                                        workflow_api._current_evidence_policy())
        assert [requirement.recorded for requirement in record.generations] == [None]


def test_a_matching_token_does_not_hide_a_dependency_created_after_the_job(client, db_engine, monkeypatch):
    workspace = Workspace(client, db_engine, email="g5-chronology@example.com")
    dataset_id = workspace.upload(2, "a.csv")
    _enforce(monkeypatch)
    des_id = workspace.run("des", DES_PAYLOAD)
    with make_sessionmaker(db_engine)() as db:                      # SYNTHETIC (direct row edit)
        db.get(Dataset, dataset_id).created_at = db.get(Job, des_id).created_at + timedelta(minutes=5)
        db.commit()
    assessment = _assess(db_engine, des_id, enforced=True, monkeypatch=monkeypatch)
    assert R.DEPENDENCY_CREATED_AFTER in assessment.codes
    assert not GENERATION_CODES & set(assessment.codes)
    assert workspace.slots()["des"] is None


def test_a_missing_dependency_gains_no_generation_reason(client, db_engine, monkeypatch):
    workspace = Workspace(client, db_engine, email="g5-missing@example.com")
    workspace.upload(2, "a.csv")
    des_id = workspace.run("des", DES_PAYLOAD)
    _edit_job(db_engine, des_id, params={"dataset_id": 99999})      # SYNTHETIC (direct row edit)
    assessment = _assess(db_engine, des_id, enforced=True, monkeypatch=monkeypatch)
    assert {reason.code for reason in assessment.reasons if reason.subject == "dataset 99999"} == {
        R.DEPENDENCY_MISSING}
    assert not GENERATION_CODES & set(assessment.codes)
    assert _unique_reasons(assessment)


def test_a_mismatch_outranks_an_unrecorded_token_and_both_are_kept(client, db_engine, monkeypatch):
    analysis_id, dataset_id, scenario_id, headers = _plan(client, db_engine)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    des_id = _post(client, headers, analysis_id, *SELECTED_STEPS[0]).json()["evidence"]["id"]
    _edit_job(db_engine, des_id, params={"scenario_generation": OTHER}, drop=("dataset_generation",))
    assessment = _assess(db_engine, des_id, enforced=True, monkeypatch=monkeypatch)
    assert assessment.status is S.MISSING_DEPENDENCY
    by_code = {reason.code: reason.subject for reason in assessment.reasons if reason.code in GENERATION_CODES}
    assert by_code == {R.GENERATION_MISMATCH: f"scenario {scenario_id}", R.GENERATION_UNRECORDED: f"dataset {dataset_id}"}
    assert _unique_reasons(assessment)


# -- G-T12: every legacy job kind is non-current under enforcement, and nothing is rewritten -----------


def test_every_legacy_job_kind_is_non_current_under_enforcement_and_left_unchanged(app, client, db_engine,
                                                                                   monkeypatch):
    # The selected-plan kinds on a saved plan; the Current kinds on an analysis whose rows the Current
    # simulation supports (the plan fixture's rows are M/G/c there, which Step 1-5 already refuse). The
    # second owner signs in on a client of their own.
    analysis_id, _, scenario_id, headers = _plan(client, db_engine)
    for path, body in [("selection", {"scenario_id": scenario_id}), *SELECTED_STEPS, ("decision/selected", {})]:
        response = _post(client, headers, analysis_id, path, body)
        assert response.status_code == 200, (path, response.text)
    other = TestClient(app)
    other.headers["X-NovaQ-Client-Protocol"] = "2"
    workspace = Workspace(other, db_engine, email="g5-legacy-kinds@example.com")
    workspace.upload(2, "a.csv")
    workspace.run_all()
    with make_sessionmaker(db_engine)() as db:
        jobs = {job.kind: job.id for job in db.query(Job).order_by(Job.id)}
    assert set(jobs) == workflow_api.WORKFLOW_KINDS
    for job_id in jobs.values():
        _edit_job(db_engine, job_id, drop=TOKENS)                    # SYNTHETIC: unstamped, as before G3
    stored = _stored(db_engine)
    for kind, job_id in jobs.items():                                # flag off: the Step 1-5 verdicts
        assert _assess(db_engine, job_id, enforced=False, monkeypatch=monkeypatch).is_current, kind
    for kind, job_id in jobs.items():
        assessment = _assess(db_engine, job_id, enforced=True, monkeypatch=monkeypatch)
        assert not assessment.is_current, kind
        assert R.GENERATION_UNRECORDED in workflow_api._root_causes(assessment), kind
    assert workspace.slots() == EMPTY_CURRENT
    workflow = _workflow(client, analysis_id)
    assert all(workflow[name] is None for name in ("scenario", "des", "mc", "validation", "decision"))
    assert _stored(db_engine) == stored
