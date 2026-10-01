"""4c, 4f, 5e and 5d: scenario eligibility as data, the selection's reason, and named dependencies.

The selection chokepoint ``_own_verified_scenario_and_dataset`` now raises the first failure of
``_scenario_evidence``, which also reports every failed check as an ``EvidenceStatus`` headline and
``ReasonCode`` reasons. These tests prove, for every fixture below and with generation enforcement
both off and on:

- the chokepoint accepts or refuses exactly as the committed pre-refactor chokepoint does (same
  HTTP status, same detail), using a verbatim copy of it as the reference;
- a scenario is CURRENT exactly when the chokepoint accepts it.

Data labels:

- SYNTHETIC: users, analyses, datasets, scenarios and runs made here, through the real endpoints
  or by direct row insert/edit (marked at each call site) to reach states no endpoint produces.
  No recorded operational data is used.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

import backend.api.workflow as workflow_api
from backend.api.evidence_status import ArtifactRef, EvidenceAssessment, EvidenceStatus, Reason, ReasonCode
from backend.api.workflow import (
    GENERATION_UNRECORDED_DETAIL,
    MISSING_DEPENDENCY_DETAIL,
    SCENARIO_PROVENANCE_DETAIL,
    _current_valid_dataset_id,
    _dependency_refusal_detail,
    _generation_enforced,
    _operationally_complete,
    _own_verified_scenario_and_dataset,
    _recorded_generation,
    _scenario_evidence,
    _scenario_rows,
    _scenario_setup_problem,
    _separate_schedule_problem,
)
from backend.db.models import AnalysisProject, Dataset, Job, Scenario, User
from tests.helpers import csrf_header, login, make_sessionmaker
from tests.test_separate_report import _api_workspace
from tests.test_step5_missing_dependency import Shop, schema1_snapshot, shared_results, shared_setup

S = EvidenceStatus
R = ReasonCode


# ── Reference: the chokepoint as committed at 822d5053 (backend/api/workflow.py:340-420) ──────
# Verbatim, except that the two function names carry a ``_reference`` prefix.


def _reference_own_verified_scenario_and_dataset(
    db: Session, user: User, analysis: AnalysisProject, scenario_id: int
) -> tuple[Scenario, Dataset]:
    """The verified scenario and the dataset row it was verified against.

    Evidence built on the scenario records that row's generation (G3), so it is returned rather
    than read again.
    """
    scenario = db.get(Scenario, scenario_id)
    if (
        scenario is None
        or scenario.user_id != user.id
        or scenario.analysis_id != analysis.id
        or scenario.dataset_id is None
        or not (scenario.settings_json or {}).get("calculation")
    ):
        raise HTTPException(
            status_code=422,
            detail="Select a verified Scenario from this Analysis.",
        )
    dataset = db.get(Dataset, scenario.dataset_id)
    if (
        dataset is None
        or dataset.user_id != user.id
        or dataset.analysis_id != analysis.id
        or not (dataset.validation_report_json or {}).get("ok")
    ):
        raise HTTPException(status_code=422, detail="Scenario source Dataset is unavailable.")
    snapshot = (scenario.settings_json or {}).get("calculation") or {}
    if snapshot.get("schema_version") == 2:
        problem = _separate_schedule_problem(scenario)
        if problem is not None:
            raise HTTPException(
                status_code=422,
                detail=f"Separate plan is not selectable: {problem}.",
            )
        if scenario.dataset_id != _current_valid_dataset_id(db, user, analysis):
            raise HTTPException(
                status_code=422,
                detail="Separate plan is stale for the current dataset.",
            )
        if _scenario_setup_problem(scenario, analysis) is not None:
            raise HTTPException(
                status_code=422,
                detail="Separate plan is stale for the current Setup.",
            )
        _reference_require_verified_dataset_generation(scenario, dataset)
        return scenario, dataset
    if _scenario_setup_problem(scenario, analysis) is not None:
        raise HTTPException(
            status_code=422,
            detail="Scenario is not verifiable for the current Setup queue structure.",
        )
    if not _operationally_complete(_scenario_rows(scenario)):
        raise HTTPException(status_code=422, detail="Scenario comparison evidence is incomplete.")
    # Step 4: a schema-1 snapshot is evidence of the dataset it was calculated on. It is checked
    # last so that a missing dataset, a changed Setup or incomplete evidence keeps reporting its
    # own reason instead of being reported as staleness. The current dataset comes from the one
    # resolver (backend.api.current_dataset, via _current_valid_dataset_id); nothing here infers
    # identity from queue types or from matching results.
    if scenario.dataset_id != _current_valid_dataset_id(db, user, analysis):
        raise HTTPException(
            status_code=422,
            detail="Scenario is stale for the current dataset.",
        )
    _reference_require_verified_dataset_generation(scenario, dataset)
    return scenario, dataset


def _reference_require_verified_dataset_generation(scenario: Scenario, dataset: Dataset) -> None:
    """G5 (spec 2026-09-26 §8): under enforcement a scenario is eligible only when the dataset
    generation its save verified is present and is the live row's.

    Called last on both schema branches, so every existing refusal keeps its own reason. A NULL
    binding (every scenario saved before G2) is never treated as a match.
    """
    if not _generation_enforced():
        return
    recorded = _recorded_generation(scenario.dataset_generation)
    if recorded is None or recorded != dataset.generation:
        raise HTTPException(status_code=422, detail=SCENARIO_PROVENANCE_DETAIL)

# ── End of reference ──────────────────────────────────────────────────────────────────────────


def _outcome(chokepoint, db: Session, user: User, analysis: AnalysisProject, scenario_id: int):
    try:
        scenario, dataset = chokepoint(db, user, analysis, scenario_id)
    except HTTPException as exc:
        return ("refused", exc.status_code, exc.detail)
    return ("verified", scenario.id, dataset.id)


# ── Fixtures ─────────────────────────────────────────────────────────────────────────────────


class Case:
    """One scenario to judge: its owner, its analysis and its id, plus the client signed in as them."""

    def __init__(self, client, db_engine, user_id: int, analysis_id: int, scenario_id: int,
                 dataset_id: int | None):
        self.client = client
        self.session_factory = make_sessionmaker(db_engine)
        self.user_id = user_id
        self.analysis_id = analysis_id
        self.scenario_id = scenario_id
        self.dataset_id = dataset_id

    def edit(self, model, row_id: int, **values: Any) -> None:
        """SYNTHETIC (direct row edit)."""
        with self.session_factory() as db:
            row = db.get(model, row_id)
            for key, value in values.items():
                setattr(row, key, value)
                if key.endswith("_json"):
                    flag_modified(row, key)
            db.commit()


def _insert_scenario(shop: Shop, *, dataset_id: int | None, settings: dict[str, Any],
                     results: dict[str, Any], analysis_id: int | None = None) -> int:
    """SYNTHETIC (direct row insert): a scenario in a state the save endpoints do not produce."""
    with shop.session_factory() as db:
        scenario = Scenario(user_id=shop.user_id, analysis_id=analysis_id or shop.analysis_id,
                            dataset_id=dataset_id, name="Plan", settings_json=settings, results_json=results)
        db.add(scenario)
        db.commit()
        return scenario.id


def _shared(client, db_engine, variant: str) -> Case:
    shop = Shop(client, db_engine, email=f"ev-{variant}@example.com")
    dataset_a = shop.upload(4, "a.csv")
    settings = {"calculation": schema1_snapshot(4)}
    results = shared_results(4)
    dataset_id: int | None = dataset_a
    if variant in ("setup-mismatch", "setup-mismatch-and-stale-dataset"):
        # The snapshot was calculated for separate queues; this analysis is a shared queue.
        snapshot = schema1_snapshot(4)
        snapshot["input_segments"] = [{**snapshot["input_segments"][0], "queue_structure": "separate_queues"}]
        settings = {"calculation": snapshot}
    if variant == "no-snapshot":
        settings = {}
    if variant == "no-dataset":
        dataset_id = None
    if variant == "no-results":
        results = {}
    if variant == "incomplete-rows":
        results = {"results": [{**shared_results(4)["results"][0], "optimized_stable": False}]}
    scenario_id = _insert_scenario(shop, dataset_id=dataset_id, settings=settings, results=results)
    if variant == "missing-scenario":
        scenario_id = 999_999
    if variant == "other-analysis":
        other = client.post("/analyses", headers=shop.headers,
                            json={"name": "Other", "queue_setup": shared_setup()})
        scenario_id = _insert_scenario(shop, dataset_id=None, settings=settings, results=results,
                                       analysis_id=other.json()["analysis"]["id"])
    case = Case(client, db_engine, shop.user_id, shop.analysis_id, scenario_id, dataset_a)
    if variant in ("stale-dataset", "setup-mismatch-and-stale-dataset"):
        shop.upload(14, "b.csv")
    if variant == "invalid-dataset":
        case.edit(Dataset, dataset_a, validation_report_json={"ok": False, "message": "synthetic"})
    return case


def _separate(client, db_engine, variant: str) -> Case:
    email = f"ev-sep-{variant}@example.com"
    analysis_id, dataset_id, scenario_id = _api_workspace(db_engine, email)
    assert login(client, email, "pw") == 200
    session_factory = make_sessionmaker(db_engine)
    with session_factory() as db:
        user_id = db.execute(select(User.id).where(User.email == email)).scalar_one()
        scenario = db.get(Scenario, scenario_id)
        settings, results = scenario.settings_json, scenario.results_json
        generation = db.get(Dataset, dataset_id).generation
    case = Case(client, db_engine, user_id, analysis_id, scenario_id, dataset_id)
    if variant == "engine":
        case.edit(Scenario, scenario_id, settings_json={
            **settings, "calculation": {**settings["calculation"], "engine_version": "separate-des-v0"}})
    if variant in ("schedule", "schedule-and-stale-dataset"):
        case.edit(Scenario, scenario_id, results_json={
            "schedule": {**results["schedule"], "overall": "INCOMPLETE"}})
    if variant in ("stale-dataset", "schedule-and-stale-dataset"):
        # SYNTHETIC (direct row insert): a newer processed dataset replaces the plan's.
        with session_factory() as db:
            db.add(Dataset(user_id=user_id, analysis_id=analysis_id, name="Newer", source_filename="b.csv",
                           source_format="csv", row_count=0, normalized_json=[],
                           validation_report_json={"ok": True, "message": "ok"}))
            db.commit()
    if variant == "setup-changed":
        with session_factory() as db:
            setup = dict(db.get(AnalysisProject, analysis_id).queue_setup_json)
        case.edit(AnalysisProject, analysis_id, queue_setup_json={**setup, "fixed_server_count": 2})
    if variant == "stamped":
        case.edit(Scenario, scenario_id, dataset_generation=generation)
    if variant == "generation-mismatch":
        case.edit(Scenario, scenario_id, dataset_generation="0" * 32)
    return case


# Headline status and reason codes with enforcement off, in the order the API reports them.
EXPECTED_OFF: dict[str, tuple[EvidenceStatus, tuple[ReasonCode, ...]]] = {
    "shared-current": (S.CURRENT, ()),
    "shared-stale-dataset": (S.STALE_DATASET, (R.DATASET_NOT_CURRENT,)),
    "shared-setup-mismatch": (S.STALE_SETUP, (R.SETUP_QUEUE_TYPE_MISMATCH,)),
    "shared-setup-mismatch-and-stale-dataset": (S.STALE_DATASET, (R.DATASET_NOT_CURRENT, R.SETUP_QUEUE_TYPE_MISMATCH)),
    "shared-no-snapshot": (S.MISSING_PROVENANCE, (R.VERSION_UNRECORDED,)),
    "shared-no-dataset": (S.MISSING_PROVENANCE, (R.DATASET_UNRECORDED,)),
    "shared-no-results": (S.MISSING_PROVENANCE, (R.RESULT_INCOMPLETE,)),
    "shared-incomplete-rows": (S.MISSING_PROVENANCE, (R.RESULT_INCOMPLETE,)),
    "shared-invalid-dataset": (S.STALE_DATASET, (R.DATASET_NOT_CURRENT,)),
    "shared-missing-scenario": (S.MISSING_DEPENDENCY, (R.DEPENDENCY_MISSING,)),
    "shared-other-analysis": (S.MISSING_DEPENDENCY, (R.OUT_OF_SCOPE,)),
    "separate-current": (S.CURRENT, ()),
    "separate-engine": (S.UNSUPPORTED, (R.VERSION_UNSUPPORTED,)),
    "separate-schedule": (S.UNSUPPORTED, (R.CALCULATION_UNSUPPORTED,)),
    "separate-stale-dataset": (S.STALE_DATASET, (R.DATASET_NOT_CURRENT,)),
    "separate-setup-changed": (S.STALE_SETUP, (R.SETUP_CHANGED,)),
    "separate-schedule-and-stale-dataset": (S.UNSUPPORTED, (R.CALCULATION_UNSUPPORTED, R.DATASET_NOT_CURRENT)),
    "separate-stamped": (S.CURRENT, ()),
    "separate-generation-mismatch": (S.CURRENT, ()),
}
# Enforcement on changes only the generation binding; every other case is as with it off.
EXPECTED_ON = {
    **EXPECTED_OFF,
    "shared-current": (S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED,)),
    "separate-current": (S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED,)),
    "separate-stale-dataset": (S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED, R.DATASET_NOT_CURRENT)),
    "separate-setup-changed": (S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED, R.SETUP_CHANGED)),
    "shared-stale-dataset": (S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED, R.DATASET_NOT_CURRENT)),
    "shared-setup-mismatch": (S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED, R.SETUP_QUEUE_TYPE_MISMATCH)),
    "shared-setup-mismatch-and-stale-dataset": (
        S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED, R.DATASET_NOT_CURRENT, R.SETUP_QUEUE_TYPE_MISMATCH)),
    "shared-incomplete-rows": (S.MISSING_PROVENANCE, (R.RESULT_INCOMPLETE, R.GENERATION_UNRECORDED)),
    "shared-no-results": (S.MISSING_PROVENANCE, (R.RESULT_INCOMPLETE, R.GENERATION_UNRECORDED)),
    "separate-engine": (S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED, R.VERSION_UNSUPPORTED)),
    "separate-schedule": (S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED, R.CALCULATION_UNSUPPORTED)),
    "separate-schedule-and-stale-dataset": (
        S.MISSING_PROVENANCE, (R.GENERATION_UNRECORDED, R.CALCULATION_UNSUPPORTED, R.DATASET_NOT_CURRENT)),
    "separate-generation-mismatch": (S.MISSING_DEPENDENCY, (R.GENERATION_MISMATCH,)),
}


def _build(client, db_engine, name: str) -> Case:
    family, variant = name.split("-", 1)
    return (_shared if family == "shared" else _separate)(client, db_engine, variant)


@pytest.mark.parametrize("enforced", [False, True], ids=["enforcement-off", "enforcement-on"])
@pytest.mark.parametrize("name", sorted(EXPECTED_OFF))
def test_evaluator_matches_the_committed_chokepoint_and_reports_every_failed_check(
        client, db_engine, monkeypatch, name, enforced):
    case = _build(client, db_engine, name)
    monkeypatch.setattr(workflow_api, "GENERATION_ENFORCEMENT_ENABLED", enforced)
    with case.session_factory() as db:
        user, analysis = db.get(User, case.user_id), db.get(AnalysisProject, case.analysis_id)
        reference = _outcome(_reference_own_verified_scenario_and_dataset, db, user, analysis, case.scenario_id)
        current = _outcome(_own_verified_scenario_and_dataset, db, user, analysis, case.scenario_id)
        evidence = _scenario_evidence(db, user, analysis, case.scenario_id)
    # Same acceptance, same refusal status and detail as the committed chokepoint.
    assert current == reference
    # CURRENT exactly when the chokepoint accepts; the refusal is the chokepoint's detail.
    assert (evidence.status is S.CURRENT) == (reference[0] == "verified")
    assert evidence.refusal == (None if reference[0] == "verified" else reference[2])
    status, codes = (EXPECTED_ON if enforced else EXPECTED_OFF)[name]
    assert (evidence.status, tuple(reason.code for reason in evidence.reasons)) == (status, codes)
    if not enforced:
        assert not {reason.code for reason in evidence.reasons} & {R.GENERATION_UNRECORDED, R.GENERATION_MISMATCH}


@pytest.mark.parametrize("name", sorted(EXPECTED_OFF))
def test_selection_is_accepted_exactly_when_the_scenario_is_current(client, db_engine, name):
    case = _build(client, db_engine, name)
    selected = client.post(f"/analyses/{case.analysis_id}/workflow/selection",
                           headers=csrf_header(client), json={"scenario_id": case.scenario_id})
    status, _ = EXPECTED_OFF[name]
    assert (selected.status_code == 200) == (status is S.CURRENT), selected.text
    if status is not S.CURRENT:
        assert selected.status_code == 422


def test_a_refused_selection_reports_the_chokepoints_first_failure_not_the_headline(client, db_engine):
    """Setup and dataset both fail: the headline follows §4.1 (dataset first), the 422 keeps the
    chokepoint's order (Setup first), and the scenario list reports both."""
    case = _build(client, db_engine, "shared-setup-mismatch-and-stale-dataset")
    refused = client.post(f"/analyses/{case.analysis_id}/workflow/selection",
                          headers=csrf_header(client), json={"scenario_id": case.scenario_id})
    assert (refused.status_code, refused.json()["detail"]) == (
        422, "Scenario is not verifiable for the current Setup queue structure.")
    listed = client.get("/scenarios", params={"analysis_id": case.analysis_id}).json()["scenarios"]
    assert [(item["evidence_status"], [reason["detail"] for reason in item["evidence_reasons"]])
            for item in listed] == [("STALE_DATASET", [
                "Scenario is stale for the current dataset.",
                "Scenario is not verifiable for the current Setup queue structure."])]


# ── 4c: every scenario response carries the fields ──────────────────────────────────────────


def _fields(item: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    return item["evidence_status"], item["evidence_reasons"]


@pytest.mark.parametrize("name", ["shared-current", "shared-stale-dataset", "separate-schedule"])
def test_every_read_endpoint_reports_the_same_evidence(client, db_engine, name):
    case = _build(client, db_engine, name)
    status, codes = EXPECTED_OFF[name]
    single = _fields(client.get(f"/scenarios/{case.scenario_id}").json()["scenario"])
    assert (single[0], [reason["code"] for reason in single[1]]) == (status.value, [code.value for code in codes])
    by_analysis = client.get("/scenarios", params={"analysis_id": case.analysis_id}).json()["scenarios"]
    scoped = client.get(f"/analyses/{case.analysis_id}/scenarios").json()["scenarios"]
    everything = client.get("/scenarios").json()["scenarios"]
    for listing in (by_analysis, scoped, everything):
        assert [_fields(item) for item in listing if item["id"] == case.scenario_id] == [single]


def test_a_stale_scenario_reason_names_the_chokepoint_check(client, db_engine):
    case = _build(client, db_engine, "shared-stale-dataset")
    scenario = client.get(f"/scenarios/{case.scenario_id}").json()["scenario"]
    assert scenario["evidence_reasons"] == [{
        "code": "DATASET_NOT_CURRENT", "subject": f"scenario {case.scenario_id}",
        "detail": "Scenario is stale for the current dataset."}]


def test_create_and_patch_responses_carry_the_fields(client, db_engine):
    shop = Shop(client, db_engine, email="ev-create@example.com")
    created = client.post("/scenarios", headers=shop.headers,
                          json={"name": "Imported", "analysis_id": shop.analysis_id})
    assert created.status_code == 201, created.text
    scenario = created.json()["scenario"]
    reasons = [{"code": "DATASET_UNRECORDED", "subject": f"scenario {scenario['id']}",
                "detail": "Select a verified Scenario from this Analysis."},
               {"code": "VERSION_UNRECORDED", "subject": f"scenario {scenario['id']}",
                "detail": "Select a verified Scenario from this Analysis."}]
    assert _fields(scenario) == ("MISSING_PROVENANCE", reasons)
    renamed = client.patch(f"/scenarios/{scenario['id']}", headers=shop.headers, json={"name": "Renamed"})
    assert renamed.status_code == 200, renamed.text
    assert _fields(renamed.json()["scenario"]) == ("MISSING_PROVENANCE", reasons)


def test_a_scenario_without_an_analysis_is_not_recorded(client, db_engine):
    shop = Shop(client, db_engine, email="ev-orphan@example.com")
    with shop.session_factory() as db:                    # SYNTHETIC (direct row insert)
        scenario = Scenario(user_id=shop.user_id, analysis_id=None, dataset_id=None, name="Legacy",
                            settings_json={}, results_json={})
        db.add(scenario)
        db.commit()
        scenario_id = scenario.id
    assert _fields(client.get(f"/scenarios/{scenario_id}").json()["scenario"]) == (
        "MISSING_PROVENANCE", [{"code": "ANALYSIS_UNRECORDED", "subject": f"scenario {scenario_id}",
                                "detail": "Select a verified Scenario from this Analysis."}])


# ── 4f / 5e: selection_evidence on GET /workflow ─────────────────────────────────────────────


def _workflow(case: Case) -> dict[str, Any]:
    response = case.client.get(f"/analyses/{case.analysis_id}/workflow")
    assert response.status_code == 200, response.text
    return response.json()


def _select(case: Case) -> int:
    selected = case.client.post(f"/analyses/{case.analysis_id}/workflow/selection",
                                headers=csrf_header(case.client), json={"scenario_id": case.scenario_id})
    assert selected.status_code == 200, selected.text
    return selected.json()["selection"]["id"]


def _consistent(workflow: dict[str, Any]) -> None:
    """A withheld scenario always has a reason, and a returned one is CURRENT."""
    evidence = workflow["selection_evidence"]
    assert (workflow["scenario"] is not None) == (evidence is not None and evidence["evidence_status"] == "CURRENT")


def test_no_selection_has_no_selection_evidence(client, db_engine):
    case = _build(client, db_engine, "shared-current")
    workflow = _workflow(case)
    assert workflow["selection"] is None and workflow["selection_evidence"] is None
    _consistent(workflow)


def test_a_current_selection_is_current(client, db_engine):
    case = _build(client, db_engine, "shared-current")
    _select(case)
    workflow = _workflow(case)
    assert workflow["scenario"]["id"] == case.scenario_id
    assert workflow["selection_evidence"] == {
        "scenario_id": case.scenario_id, "evidence_status": "CURRENT", "evidence_reasons": []}
    _consistent(workflow)


def test_a_deleted_selected_scenario_is_a_missing_source(client, db_engine):
    case = _build(client, db_engine, "shared-current")
    _select(case)
    assert client.delete(f"/scenarios/{case.scenario_id}", headers=csrf_header(client)).status_code == 200
    workflow = _workflow(case)
    assert workflow["scenario"] is None and workflow["selection"] is not None
    assert workflow["selection_evidence"] == {
        "scenario_id": case.scenario_id, "evidence_status": "MISSING_DEPENDENCY",
        "evidence_reasons": [{"code": "DEPENDENCY_MISSING", "subject": f"scenario {case.scenario_id}",
                              "detail": "Select a verified Scenario from this Analysis."}]}
    _consistent(workflow)


def test_a_selection_on_a_replaced_dataset_is_stale(client, db_engine):
    case = _build(client, db_engine, "shared-current")
    _select(case)
    uploaded = client.post(f"/analyses/{case.analysis_id}/datasets", headers=csrf_header(client),
                           files={"file": ("b.csv", b"time,lambda,mu,c\n08:00-09:00,14,12,2\n", "text/csv")})
    assert uploaded.status_code == 201, uploaded.text
    workflow = _workflow(case)
    assert workflow["scenario"] is None
    evidence = workflow["selection_evidence"]
    assert (evidence["scenario_id"], evidence["evidence_status"]) == (case.scenario_id, "STALE_DATASET")
    assert [reason["code"] for reason in evidence["evidence_reasons"]] == ["DATASET_NOT_CURRENT"]
    # Only identity, status and reasons: no scenario or result payload comes back with it.
    assert set(evidence) == {"scenario_id", "evidence_status", "evidence_reasons"}
    _consistent(workflow)


def test_a_selection_without_a_recorded_scenario_id_is_not_recorded(client, db_engine):
    case = _build(client, db_engine, "shared-current")
    selection_id = _select(case)
    with case.session_factory() as db:                    # SYNTHETIC (direct row edit)
        job = db.get(Job, selection_id)
        job.params_json = {**(job.params_json or {}), "scenario_id": "not-an-id"}
        flag_modified(job, "params_json")
        db.commit()
    workflow = _workflow(case)
    assert workflow["selection_evidence"] == {
        "scenario_id": None, "evidence_status": "MISSING_PROVENANCE",
        "evidence_reasons": [{"code": "REFERENCE_UNRECORDED", "subject": f"job:workflow_selection {selection_id}",
                              "detail": "The selection records no scenario id."}]}
    _consistent(workflow)


def test_under_enforcement_an_unbound_selection_names_the_generation(client, db_engine, monkeypatch):
    case = _build(client, db_engine, "separate-stamped")
    selection_id = _select(case)
    case.edit(Job, selection_id, params_json={
        key: value for key, value in _job_params(case, selection_id).items() if key != "scenario_generation"})
    monkeypatch.setattr(workflow_api, "GENERATION_ENFORCEMENT_ENABLED", True)
    workflow = _workflow(case)
    assert workflow["selection_evidence"] == {
        "scenario_id": case.scenario_id, "evidence_status": "MISSING_PROVENANCE",
        "evidence_reasons": [{"code": "GENERATION_UNRECORDED", "subject": f"job:workflow_selection {selection_id}",
                              "detail": workflow_api.SELECTION_GENERATION_UNRECORDED_DETAIL}]}
    _consistent(workflow)


def _job_params(case: Case, job_id: int) -> dict[str, Any]:
    with case.session_factory() as db:
        return dict(db.get(Job, job_id).params_json or {})


# ── 5d: the dependency refusal names what it depends on ──────────────────────────────────────


def _assessment(*reasons: Reason, upstream: tuple[EvidenceAssessment, ...] = ()) -> EvidenceAssessment:
    status = min((reason.status for reason in reasons), key=workflow_api.PRECEDENCE.index, default=S.MISSING_DEPENDENCY)
    return EvidenceAssessment(ArtifactRef("job:workflow_mc", 5), status, tuple(reasons), upstream)


MC = "job:workflow_mc 5"


@pytest.mark.parametrize(("reasons", "expected"), [
    pytest.param((Reason(R.DEPENDENCY_MISSING, "dataset 12", "The referenced record does not exist."),),
                 "Evidence references records that no longer exist: dataset #12. Rerun the affected step.",
                 id="missing-dataset"),
    pytest.param((Reason(R.DEPENDENCY_MISSING, "scenario 3", "The referenced record does not exist."),),
                 "Evidence references records that no longer exist: scenario #3. Rerun the affected step.",
                 id="missing-scenario"),
    pytest.param((Reason(R.DEPENDENCY_MISSING, "job:workflow_des 40", "The referenced record does not exist."),),
                 "Evidence references records that no longer exist: DES run #40. Rerun the affected step.",
                 id="missing-job"),
    pytest.param((Reason(R.DEPENDENCY_OUT_OF_SCOPE, "dataset 7", "The referenced record is not the analysis "
                         "owner's or belongs to another analysis."),),
                 "Evidence references records that are not this Analysis's: dataset #7. Rerun the affected step.",
                 id="out-of-scope"),
    pytest.param((Reason(R.DEPENDENCY_CREATED_AFTER, "scenario 3", "The referenced record was created after "
                         f"{MC}; the reference cannot be its own."),),
                 "Evidence references records created after the evidence that cites them: scenario #3. "
                 "Rerun the affected step.",
                 id="created-after"),
    pytest.param((Reason(R.DATASET_NOT_CURRENT, MC, "Recorded dataset 7; the current dataset is 9."),),
                 "Evidence is not current: Monte Carlo run #5: Recorded dataset 7; the current dataset is 9. "
                 "Rerun the affected step.",
                 id="not-current-is-not-deleted"),
    pytest.param((Reason(R.DEPENDENCY_MISSING, "dataset 12", "The referenced record does not exist."),
                   Reason(R.DATASET_NOT_CURRENT, MC, "Recorded dataset 12; the current dataset is 9.")),
                 "Evidence references records that no longer exist: dataset #12. Rerun the affected step.",
                 id="missing-names-only-the-missing-record"),
])
def test_the_detail_names_the_dependency_and_its_cause(reasons, expected):
    assert _dependency_refusal_detail(_assessment(*reasons)) == expected


def test_an_upstream_missing_record_is_named_through_the_chain():
    upstream = EvidenceAssessment(ArtifactRef("job:workflow_des", 40), S.MISSING_DEPENDENCY, (
        Reason(R.DEPENDENCY_MISSING, "dataset 12", "The referenced record does not exist."),), ())
    downstream = _assessment(Reason(R.UPSTREAM_MISSING_DEPENDENCY, "job:workflow_des 40",
                                    "Upstream evidence is MISSING_DEPENDENCY."), upstream=(upstream,))
    assert _dependency_refusal_detail(downstream) == (
        "Evidence references records that no longer exist: dataset #12. Rerun the affected step.")


@pytest.mark.parametrize(("reasons", "expected"), [
    pytest.param((Reason(R.GENERATION_UNRECORDED, "dataset 12", "No generation token is recorded."),),
                 GENERATION_UNRECORDED_DETAIL, id="generation-unrecorded"),
    pytest.param((Reason(R.GENERATION_MISMATCH, "dataset 12", "The recorded generation token differs."),),
                 MISSING_DEPENDENCY_DETAIL, id="generation-mismatch"),
    pytest.param((Reason(R.GENERATION_UNRECORDED, "dataset 12", "No generation token is recorded."),
                  Reason(R.DEPENDENCY_MISSING, "scenario 3", "The referenced record does not exist.")),
                 MISSING_DEPENDENCY_DETAIL, id="generation-with-another-cause"),
    pytest.param((), MISSING_DEPENDENCY_DETAIL, id="no-recorded-reason"),
])
def test_generation_refusals_keep_their_approved_texts(reasons, expected):
    assert _dependency_refusal_detail(_assessment(*reasons)) == expected


def _selected_des(client, db_engine, email: str) -> tuple[Case, int]:
    case = _build_named_separate(client, db_engine, email)
    _select(case)
    des = client.post(f"/analyses/{case.analysis_id}/workflow/simulation/des/selected",
                      headers=csrf_header(client), json={"seed": 7})
    assert des.status_code == 200, des.text
    return case, des.json()["evidence"]["id"]


def _build_named_separate(client, db_engine, email: str) -> Case:
    analysis_id, dataset_id, scenario_id = _api_workspace(db_engine, email)
    assert login(client, email, "pw") == 200
    with make_sessionmaker(db_engine)() as db:
        user_id = db.execute(select(User.id).where(User.email == email)).scalar_one()
    return Case(client, db_engine, user_id, analysis_id, scenario_id, dataset_id)


def _run_selected_mc(case: Case):
    return case.client.post(f"/analyses/{case.analysis_id}/workflow/simulation/mc/selected",
                            headers=csrf_header(case.client), json={})


def test_a_dataset_created_after_the_des_it_fed_is_named_at_the_gate(client, db_engine):
    case, des_id = _selected_des(client, db_engine, "ev-5d-later@example.com")
    with case.session_factory() as db:                    # SYNTHETIC (direct row edit)
        later = db.get(Job, des_id).created_at + timedelta(minutes=5)
    case.edit(Dataset, case.dataset_id, created_at=later)
    refused = _run_selected_mc(case)
    assert (refused.status_code, refused.json()["detail"]) == (409, (
        f"Evidence references records created after the evidence that cites them: dataset #{case.dataset_id}. "
        "Rerun the affected step."))


def test_a_non_missing_cause_is_not_called_deleted_at_the_gate(client, db_engine):
    case, des_id = _selected_des(client, db_engine, "ev-5d-other@example.com")
    case.edit(Job, des_id, params_json={               # SYNTHETIC (direct row edit)
        key: value for key, value in _job_params(case, des_id).items() if key != "dataset_id"})
    refused = _run_selected_mc(case)
    assert (refused.status_code, refused.json()["detail"]) == (409, (
        f"Evidence is not current: DES run #{des_id}: The dataset is not recorded. Rerun the affected step."))
    assert "no longer exist" not in refused.json()["detail"]
