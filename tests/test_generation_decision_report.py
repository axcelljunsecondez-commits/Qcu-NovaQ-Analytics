"""G6: Decisions and reports under ``GENERATION_ENFORCEMENT_ENABLED`` (gates G-T7 and G-T8, with G-T10,
G-T11, G-T12 and G-T13 at these consumers).

Spec: docs/superpowers/specs/2026-09-26-generation-identity-contract.md §6.2, §8, §10, §13 and §14 (G6).
Decisions of 2026-09-29:

- D1: a scenario whose own dataset generation is missing or different keeps the approved 422 ("Selected
  plan is not runnable: Scenario provenance is incomplete; …") on the selected report and the selected
  Decision. G-T8's 409 applies to Decision and job-chain generation mismatches.
- D2: under enforcement both Decision endpoints refuse with 409, and store nothing, when the selection's
  recorded dataset generation is unrecorded (missing, blank or not text) or is not the verified dataset
  row's. The check runs last, so every existing refusal keeps its status and message.
- D3: no new response fields.

Most of what is pinned here is inherited from the G5 wiring: the classifier policy, the scenario
provenance check, the selection binding and ``require_dependencies_current``. D2 is the one new check.
Enforcement stays off for the application; these tests switch it on with monkeypatch, which shows what
the code does, not how any deployment behaves.

Data labels: SYNTHETIC rows come from the real endpoints unless marked "direct row edit/insert". A
replacement is built as spec §13 describes: delete through the API, then insert directly under the
deleted row's id and stored ``created_at``.

Runs on SQLite, and on PostgreSQL when NOVAQ_TEST_DATABASE_URL names a dedicated *_test database.
"""

from __future__ import annotations

import io
from typing import Any

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm.attributes import flag_modified

import backend.api.workflow as workflow_api
from backend.db.models import Dataset, Job, Scenario
from tests.helpers import make_sessionmaker
from tests.test_generation_enforcement_wiring import (
    _DROP,
    OTHER,
    SELECTED_STEPS,
    _assess,
    _bind,
    _columns,
    _enforce,
    _latest,
    _plan,
    _post,
    _replace,
    _set_token,
    _stored,
    _workflow,
)
from tests.test_generation_job_stamping import TOKENS, _edit_job
from tests.test_step5_missing_dependency import MISSING_DEPENDENCY_DETAIL, Shop

UNRECORDED = workflow_api.GENERATION_UNRECORDED_DETAIL
UNAVAILABLE = ("Management recommendation unavailable: complete Decision for the "
               "currently selected and simulated Scenario.")
NOT_RUNNABLE_PROVENANCE = f"Selected plan is not runnable: {workflow_api.SCENARIO_PROVENANCE_DETAIL}"
SELECTION_DATASET_UNRECORDED = workflow_api.SELECTION_DATASET_GENERATION_UNRECORDED_DETAIL
SELECTION_DATASET_MISMATCH = workflow_api.SELECTION_DATASET_GENERATION_MISMATCH_DETAIL

# A Decision's own recorded tokens (SYNTHETIC direct row edits) and the refusal the selected report gives.
DECISION_TOKEN_CASES = [
    pytest.param({"params": {"dataset_generation": OTHER}}, MISSING_DEPENDENCY_DETAIL, id="dataset-mismatch"),
    pytest.param({"params": {"scenario_generation": OTHER}}, MISSING_DEPENDENCY_DETAIL, id="scenario-mismatch"),
    pytest.param({"drop": ("dataset_generation",)}, UNRECORDED, id="dataset-missing"),
    pytest.param({"params": {"dataset_generation": None}}, UNRECORDED, id="dataset-null"),
    pytest.param({"params": {"scenario_generation": "   "}}, UNRECORDED, id="scenario-blank"),
    pytest.param({"drop": TOKENS}, UNRECORDED, id="unstamped"),
]
UPSTREAM_CASES = [
    pytest.param({"params": {"dataset_generation": OTHER}}, MISSING_DEPENDENCY_DETAIL, id="mismatch"),
    pytest.param({"drop": TOKENS}, UNRECORDED, id="unstamped"),
]
# D2: the selection's recorded dataset generation, the Decision refusal, and what the selected report
# later says of a Decision stored under it with the flag off. The classifier (G4, unchanged) keeps a
# value that is not text tagged, so it reports that value as a mismatch (spec §8.2 caveat).
SELECTION_DATASET_CASES = [
    pytest.param(_DROP, SELECTION_DATASET_UNRECORDED, UNRECORDED, id="missing"),
    pytest.param(None, SELECTION_DATASET_UNRECORDED, UNRECORDED, id="null"),
    pytest.param("", SELECTION_DATASET_UNRECORDED, UNRECORDED, id="empty"),
    pytest.param("   ", SELECTION_DATASET_UNRECORDED, UNRECORDED, id="blank"),
    pytest.param(0, SELECTION_DATASET_UNRECORDED, MISSING_DEPENDENCY_DETAIL, id="zero"),
    pytest.param(True, SELECTION_DATASET_UNRECORDED, MISSING_DEPENDENCY_DETAIL, id="boolean"),
    pytest.param(OTHER, SELECTION_DATASET_MISMATCH, MISSING_DEPENDENCY_DETAIL, id="mismatch"),
]


def _decisions(db_engine) -> list[int]:
    with make_sessionmaker(db_engine)() as db:
        return [job.id for job in db.query(Job).filter(Job.kind == "workflow_decision").order_by(Job.id)]


def _headline(db_engine, job_id: int) -> str:
    with make_sessionmaker(db_engine)() as db:
        return db.get(Job, job_id).result_json["headline"]


def _view(workflow: dict[str, Any]) -> dict[str, Any]:
    return {"scenario": (workflow["scenario"] or {}).get("id"),
            "decision": (workflow["decision"] or {}).get("id"),
            "decision_stale": workflow["decision_stale"]}


def _set_result(db_engine, job_id: int, key: str, value: Any) -> None:
    """SYNTHETIC (direct row edit): a stored result field no endpoint would write."""
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, job_id)
        job.result_json = {**(job.result_json or {}), key: value}
        flag_modified(job, "result_json")
        db.commit()


def _id_report(client, monkeypatch, scenario_id: int, analysis_id: int) -> list[str]:
    """The recommendations of the ID-scoped export, read from both formats, which must agree."""
    captured: dict[str, list[str]] = {}

    def pdf(current, recommended, frame, recommendations):
        captured["pdf"] = list(recommendations)
        return io.BytesIO(b"%PDF g6")

    monkeypatch.setattr("backend.api.reports.generate_pdf_report", pdf)
    route = f"/reports/scenarios/{scenario_id}/{{}}?analysis_id={analysis_id}"
    assert client.get(route.format("pdf")).status_code == 200
    excel = client.get(route.format("excel"))
    assert excel.status_code == 200
    column = [cell.value for cell in openpyxl.load_workbook(io.BytesIO(excel.content))["Recommendations"]["A"]]
    assert column[0] == "Recommendation Evidence"
    assert column[1:] == captured["pdf"]
    return captured["pdf"]


def _selected_report(client, analysis_id: int, headers: dict[str, str]) -> tuple[int, str | None]:
    """The selected report's preview, PDF and Excel, which must agree: (status, detail)."""
    outcomes = set()
    for suffix in ("preview", "pdf", "excel"):
        response = client.get(f"/reports/analyses/{analysis_id}/selected/{suffix}", headers=headers)
        outcomes.add((response.status_code, None if response.status_code == 200 else response.json()["detail"]))
    assert len(outcomes) == 1, outcomes
    return outcomes.pop()


def _reported_decision(client, analysis_id: int, headers: dict[str, str]) -> int:
    preview = client.get(f"/reports/analyses/{analysis_id}/selected/preview", headers=headers)
    assert preview.status_code == 200, preview.text
    return preview.json()["model"]["provenance"]["decision_job_id"]


def _refused(response) -> tuple[int, Any]:
    """A refusal is exactly {"detail": text}: no new field (D3)."""
    body = response.json()
    assert set(body) == {"detail"}, body
    return response.status_code, body["detail"]


def _shared(client, db_engine, monkeypatch, email: str, *, decide: bool = True):
    """A shared-queue analysis with a bound schema-1 plan, its chain and (optionally) its Decision, all
    made with enforcement on. The plan is a SYNTHETIC direct row insert, bound as a verified save would."""
    shop = Shop(client, db_engine, email=email)
    dataset_id = shop.upload(4, "a.csv")
    scenario_id = shop.seed_scenario(dataset_id, 4)
    _bind(db_engine, scenario_id)
    _enforce(monkeypatch)
    assert shop.select(scenario_id).status_code == 200
    jobs = {"selection": _latest(db_engine, "workflow_selection"), **shop.run_chain()}
    if decide:
        decided = shop.decide().json()
        assert decided["persisted"] is True
        jobs["decision"] = decided["evidence"]["id"]
    return shop, dataset_id, scenario_id, jobs


def _selected(client, db_engine, monkeypatch, email: str, *, decide: bool = True):
    """A separate-queue analysis with a bound schema-2 plan, its selected chain and (optionally) its
    Decision, all made with enforcement on."""
    analysis_id, dataset_id, scenario_id, headers = _plan(client, db_engine, email)
    _enforce(monkeypatch)
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    jobs = {"selection": _latest(db_engine, "workflow_selection")}
    for name, (path, body) in zip(("des", "mc", "validation"), SELECTED_STEPS):
        response = _post(client, headers, analysis_id, path, body)
        assert response.status_code == 200, (path, response.text)
        jobs[name] = response.json()["evidence"]["id"]
    if decide:
        response = _post(client, headers, analysis_id, "decision/selected")
        assert response.status_code == 200, response.text
        jobs["decision"] = response.json()["evidence"]["id"]
    return analysis_id, dataset_id, scenario_id, headers, jobs


def _replace_dataset_and_its_scenario(client, headers: dict[str, str], db_engine, dataset_id: int,
                                      scenario_id: int) -> None:
    """Spec §13 for a dataset: deleting it through the API deletes its scenarios too (ORM cascade), so
    both are inserted again directly (SYNTHETIC) under their ids and stored created_at, byte-identical
    except for the tokens. The scenario keeps the binding it stored: the deleted dataset's token."""
    with make_sessionmaker(db_engine)() as db:
        dataset, scenario = db.get(Dataset, dataset_id), db.get(Scenario, scenario_id)
        dataset_columns, scenario_columns = _columns(dataset), _columns(scenario)
        old = (dataset.generation, scenario.generation)
    assert client.delete(f"/datasets/{dataset_id}", headers=headers).status_code == 200
    with make_sessionmaker(db_engine)() as db:
        assert db.get(Scenario, scenario_id) is None
        db.add(Dataset(**dataset_columns))
        db.flush()
        db.add(Scenario(**scenario_columns))
        db.commit()
    with make_sessionmaker(db_engine)() as db:
        dataset, scenario = db.get(Dataset, dataset_id), db.get(Scenario, scenario_id)
        assert (dataset.created_at, scenario.created_at) == (dataset_columns["created_at"],
                                                             scenario_columns["created_at"])
        assert dataset.generation != old[0] and scenario.generation != old[1]
        assert scenario.dataset_generation == old[0]


# -- A matching chain -----------------------------------------------------------------------------------


def test_a_matching_shared_chain_serves_and_reports_its_decision(client, db_engine, monkeypatch):
    shop, _, scenario_id, jobs = _shared(client, db_engine, monkeypatch, "g6-shared-ok@example.com")
    served = {"scenario": scenario_id, "decision": jobs["decision"], "decision_stale": False}
    for on in (True, False):                                   # G-T13: the same with the flag off
        _enforce(monkeypatch, on)
        assert _view(shop.workflow()) == served
        assert _id_report(client, monkeypatch, scenario_id, shop.analysis_id)[0] == _headline(
            db_engine, jobs["decision"])


def test_a_matching_selected_chain_serves_and_reports_its_decision(client, db_engine, monkeypatch):
    analysis_id, _, scenario_id, headers, jobs = _selected(client, db_engine, monkeypatch, "g6-sel-ok@example.com")
    served = {"scenario": scenario_id, "decision": jobs["decision"], "decision_stale": False}
    for on in (True, False):
        _enforce(monkeypatch, on)
        assert _view(_workflow(client, analysis_id)) == served
        assert _selected_report(client, analysis_id, headers) == (200, None)
        assert _reported_decision(client, analysis_id, headers) == jobs["decision"]
        # A verified schema-2 plan stores only its schedule, so the ID-scoped export has no comparison
        # rows and never reaches a Decision section, whatever the flag.
        refused = client.get(f"/reports/scenarios/{scenario_id}/pdf?analysis_id={analysis_id}")
        assert _refused(refused) == (422, "Scenario has no comparison results to report on.")


# -- G-T7, G-T8, G-T12: the Decision's own recorded tokens ----------------------------------------------


@pytest.mark.parametrize(("change", "_detail"), DECISION_TOKEN_CASES)
def test_a_shared_decision_with_a_broken_token_is_withheld_until_generated_again(client, db_engine,
                                                                                 monkeypatch, change, _detail):
    shop, _, scenario_id, jobs = _shared(client, db_engine, monkeypatch, "g6-shared-token@example.com")
    _edit_job(db_engine, jobs["decision"], **change)            # SYNTHETIC (direct row edit)
    stored = _stored(db_engine)
    _enforce(monkeypatch, False)                                # G-T13: Steps 1-5 cannot tell
    assert _view(shop.workflow())["decision"] == jobs["decision"]
    assert _id_report(client, monkeypatch, scenario_id, shop.analysis_id)[0] == _headline(db_engine, jobs["decision"])
    _enforce(monkeypatch)
    # An eligible plan whose Decision is broken: withheld and stale (Option A), and the export says so.
    assert _view(shop.workflow()) == {"scenario": scenario_id, "decision": None, "decision_stale": True}
    assert _id_report(client, monkeypatch, scenario_id, shop.analysis_id) == [UNAVAILABLE]
    assert _stored(db_engine) == stored
    generated = shop.decide().json()                            # regeneration from the valid chain clears it
    assert generated["persisted"] is True
    assert _view(shop.workflow()) == {"scenario": scenario_id, "decision": generated["evidence"]["id"],
                                      "decision_stale": False}


@pytest.mark.parametrize(("change", "detail"), DECISION_TOKEN_CASES)
def test_a_selected_decision_with_a_broken_token_blocks_the_selected_report(client, db_engine, monkeypatch,
                                                                            change, detail):
    analysis_id, _, scenario_id, headers, jobs = _selected(client, db_engine, monkeypatch,
                                                           "g6-sel-token@example.com")
    _edit_job(db_engine, jobs["decision"], **change)            # SYNTHETIC (direct row edit)
    stored = _stored(db_engine)
    _enforce(monkeypatch, False)
    assert _selected_report(client, analysis_id, headers) == (200, None)
    _enforce(monkeypatch)
    assert _selected_report(client, analysis_id, headers) == (409, detail)
    assert _view(_workflow(client, analysis_id)) == {"scenario": scenario_id, "decision": None,
                                                     "decision_stale": True}
    assert _stored(db_engine) == stored
    regenerated = _post(client, headers, analysis_id, "decision/selected")
    assert regenerated.status_code == 200, regenerated.text
    assert _selected_report(client, analysis_id, headers) == (200, None)
    assert _reported_decision(client, analysis_id, headers) == regenerated.json()["evidence"]["id"]


# -- G-T7, G-T8: each upstream job -------------------------------------------------------------------------


@pytest.mark.parametrize("broken", ["des", "mc", "validation"])
@pytest.mark.parametrize(("change", "_detail"), UPSTREAM_CASES)
def test_a_shared_decision_on_a_broken_upstream_job_is_withheld_and_never_regenerated_from_it(
        client, db_engine, monkeypatch, broken, change, _detail):
    shop, _, scenario_id, jobs = _shared(client, db_engine, monkeypatch, "g6-shared-up@example.com")
    _edit_job(db_engine, jobs[broken], **change)                # SYNTHETIC (direct row edit)
    _enforce(monkeypatch, False)
    assert _view(shop.workflow())["decision"] == jobs["decision"]
    _enforce(monkeypatch)
    assert _view(shop.workflow()) == {"scenario": scenario_id, "decision": None, "decision_stale": True}
    assert _id_report(client, monkeypatch, scenario_id, shop.analysis_id) == [UNAVAILABLE]
    generated = shop.decide().json()
    assert generated["persisted"] is True
    # The regenerated Decision is built without the broken run: it never names it.
    assert generated["decision"]["evidence_ids"][broken] is None
    assert jobs[broken] not in generated["decision"]["evidence_ids"].values()
    assert _view(shop.workflow())["decision"] == generated["evidence"]["id"]


@pytest.mark.parametrize("broken", ["des", "mc", "validation"])
@pytest.mark.parametrize(("change", "detail"), UPSTREAM_CASES)
def test_a_selected_decision_on_a_broken_upstream_job_is_refused_and_not_stored(client, db_engine, monkeypatch,
                                                                                 broken, change, detail):
    analysis_id, _, scenario_id, headers, jobs = _selected(client, db_engine, monkeypatch,
                                                           "g6-sel-up@example.com")
    _edit_job(db_engine, jobs[broken], **change)                # SYNTHETIC (direct row edit)
    stored = _stored(db_engine)
    _enforce(monkeypatch, False)
    assert _selected_report(client, analysis_id, headers) == (200, None)
    _enforce(monkeypatch)
    assert _selected_report(client, analysis_id, headers) == (409, detail)
    assert _refused(_post(client, headers, analysis_id, "decision/selected")) == (409, detail)
    assert _view(_workflow(client, analysis_id)) == {"scenario": scenario_id, "decision": None,
                                                     "decision_stale": True}
    assert _stored(db_engine) == stored


# -- G-T7: the selection's scenario token (G5 binding) at the Decision consumers ----------------------------


@pytest.mark.parametrize(("recorded", "detail"), [
    pytest.param(OTHER, workflow_api.SELECTED_PLAN_REPLACED_DETAIL, id="mismatch"),
    pytest.param(_DROP, workflow_api.SELECTION_GENERATION_UNRECORDED_DETAIL, id="missing"),
])
def test_a_selection_bound_to_another_scenario_generation_serves_and_produces_no_decision(
        client, db_engine, monkeypatch, recorded, detail):
    analysis_id, _, _, headers, jobs = _selected(client, db_engine, monkeypatch, "g6-sel-bind@example.com")
    _set_token(db_engine, jobs["selection"], "scenario_generation", recorded)   # SYNTHETIC (direct row edit)
    stored = _stored(db_engine)
    assert _selected_report(client, analysis_id, headers) == (409, detail)
    assert _refused(_post(client, headers, analysis_id, "decision/selected")) == (409, detail)
    # No eligible selection: Option A, and nothing was stored.
    assert _view(_workflow(client, analysis_id)) == {"scenario": None, "decision": None, "decision_stale": False}
    assert _stored(db_engine) == stored


# -- D2: the selection's dataset token (the gap G6 closes) ---------------------------------------------------


@pytest.mark.parametrize(("value", "detail", "_report_detail"), SELECTION_DATASET_CASES)
def test_a_shared_decision_is_never_produced_under_a_selection_without_its_dataset_generation(
        client, db_engine, monkeypatch, value, detail, _report_detail):
    shop, _, scenario_id, jobs = _shared(client, db_engine, monkeypatch, "g6-shared-d2@example.com", decide=False)
    _set_token(db_engine, jobs["selection"], "dataset_generation", value)       # SYNTHETIC (direct row edit)
    stored = _stored(db_engine)
    # The scenario token still binds, so the plan stays eligible; only the Decision is refused.
    assert _refused(shop.decide()) == (409, detail)
    assert _decisions(db_engine) == [] and _stored(db_engine) == stored
    assert _view(shop.workflow()) == {"scenario": scenario_id, "decision": None, "decision_stale": False}
    # G-T13: with the flag off the pre-G6 rule stores a Decision, which is the gap: under enforcement
    # that Decision is never served, and regenerating it stored another one without clearing the flag.
    _enforce(monkeypatch, False)
    produced = shop.decide().json()
    assert produced["persisted"] is True
    _enforce(monkeypatch)
    assert _view(shop.workflow()) == {"scenario": scenario_id, "decision": None, "decision_stale": True}
    assert _id_report(client, monkeypatch, scenario_id, shop.analysis_id) == [UNAVAILABLE]
    assert _refused(shop.decide()) == (409, detail)
    assert _decisions(db_engine) == [produced["evidence"]["id"]]
    # Selecting the plan again records both tokens, and the Decision is produced and served.
    assert shop.select(scenario_id).status_code == 200
    regenerated = shop.decide().json()
    assert regenerated["persisted"] is True
    assert _view(shop.workflow()) == {"scenario": scenario_id, "decision": regenerated["evidence"]["id"],
                                      "decision_stale": False}


@pytest.mark.parametrize(("value", "detail", "report_detail"), SELECTION_DATASET_CASES)
def test_a_selected_decision_is_never_produced_under_a_selection_without_its_dataset_generation(
        client, db_engine, monkeypatch, value, detail, report_detail):
    analysis_id, _, scenario_id, headers, jobs = _selected(client, db_engine, monkeypatch,
                                                           "g6-sel-d2@example.com", decide=False)
    _set_token(db_engine, jobs["selection"], "dataset_generation", value)       # SYNTHETIC (direct row edit)
    stored = _stored(db_engine)
    assert _refused(_post(client, headers, analysis_id, "decision/selected")) == (409, detail)
    assert _decisions(db_engine) == [] and _stored(db_engine) == stored
    assert _selected_report(client, analysis_id, headers) == (
        404, "Run selected-plan Decision before generating the final report.")
    # G-T13: the flag-off rule stores the Decision; under enforcement the report refuses it (its
    # recorded selection is part of its chain), and producing another one is refused again.
    _enforce(monkeypatch, False)
    produced = _post(client, headers, analysis_id, "decision/selected")
    assert produced.status_code == 200, produced.text
    assert _selected_report(client, analysis_id, headers) == (200, None)
    _enforce(monkeypatch)
    assert _selected_report(client, analysis_id, headers) == (409, report_detail)
    assert _view(_workflow(client, analysis_id)) == {"scenario": scenario_id, "decision": None,
                                                     "decision_stale": True}
    assert _refused(_post(client, headers, analysis_id, "decision/selected")) == (409, detail)
    assert _decisions(db_engine) == [produced.json()["evidence"]["id"]]
    assert _post(client, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    regenerated = _post(client, headers, analysis_id, "decision/selected")
    assert regenerated.status_code == 200, regenerated.text
    assert _reported_decision(client, analysis_id, headers) == regenerated.json()["evidence"]["id"]


def test_the_selected_decision_checks_the_selection_dataset_generation_after_every_existing_refusal(
        client, db_engine, monkeypatch):
    analysis_id, _, _, headers, jobs = _selected(client, db_engine, monkeypatch, "g6-sel-d2-order@example.com",
                                                 decide=False)
    _set_token(db_engine, jobs["selection"], "dataset_generation", _DROP)       # SYNTHETIC (direct row edit)
    def decide() -> tuple[int, Any]:
        return _refused(_post(client, headers, analysis_id, "decision/selected"))

    with make_sessionmaker(db_engine)() as db:
        scenario_token = db.get(Job, jobs["selection"]).params_json["scenario_generation"]
        des_token = db.get(Job, jobs["des"]).params_json["dataset_generation"]
        scenario_id = db.get(Job, jobs["validation"]).result_json["scenario_id"]
    _set_token(db_engine, jobs["selection"], "scenario_generation", _DROP)      # the G5 binding (D5)
    assert decide() == (409, workflow_api.SELECTION_GENERATION_UNRECORDED_DETAIL)
    _set_token(db_engine, jobs["selection"], "scenario_generation", scenario_token)
    _set_token(db_engine, jobs["des"], "dataset_generation", _DROP)             # the chain gate
    assert decide() == (409, UNRECORDED)
    _set_token(db_engine, jobs["des"], "dataset_generation", des_token)
    _set_result(db_engine, jobs["validation"], "scenario_id", None)             # the last existing check
    assert decide() == (409, "Validation evidence belongs to a different scenario.")
    _set_result(db_engine, jobs["validation"], "scenario_id", scenario_id)
    assert decide() == (409, SELECTION_DATASET_UNRECORDED)
    assert _decisions(db_engine) == []


def test_the_shared_decision_checks_the_selection_dataset_generation_after_every_existing_outcome(
        app, client, db_engine, monkeypatch):
    shop, _, _, jobs = _shared(client, db_engine, monkeypatch, "g6-shared-d2-order@example.com", decide=False)
    _set_token(db_engine, jobs["selection"], "dataset_generation", _DROP)       # SYNTHETIC (direct row edit)
    _set_token(db_engine, jobs["selection"], "scenario_generation", _DROP)
    # No eligible selection keeps its answer (Option A): nothing persisted, no 409.
    body = shop.decide().json()
    assert (body["persisted"], body["decision"]["status"]) == (False, "insufficient_evidence")
    # Shared rules on a separate-queue analysis never persist, whatever the selection records. The second
    # owner signs in on a client of their own.
    other = TestClient(app)
    other.headers["X-NovaQ-Client-Protocol"] = "2"
    analysis_id, _, scenario_id, headers = _plan(other, db_engine, "g6-sep-d2-order@example.com")
    assert _post(other, headers, analysis_id, "selection", {"scenario_id": scenario_id}).status_code == 200
    _set_token(db_engine, _latest(db_engine, "workflow_selection"), "dataset_generation", _DROP)
    body = _post(other, headers, analysis_id, "decision").json()
    assert body["persisted"] is False
    assert _decisions(db_engine) == []


# -- G-T10, G-T11: replacement at the Decision and report consumers -------------------------------------------


@pytest.mark.parametrize("renamed", [False, True], ids=["byte-identical", "same-id-and-time"])
def test_a_replaced_shared_scenario_serves_and_produces_no_decision_under_enforcement(client, db_engine,
                                                                                      monkeypatch, renamed):
    shop, _, scenario_id, jobs = _shared(client, db_engine, monkeypatch, "g6-shared-replace@example.com")
    _replace(client, shop.headers, db_engine, Scenario, scenario_id, "scenarios", renamed=renamed)
    stored = _stored(db_engine)
    _enforce(monkeypatch, False)       # flag off: the replacement inherits the old Decision (the known defect)
    assert _view(shop.workflow())["decision"] == jobs["decision"]
    assert _id_report(client, monkeypatch, scenario_id, shop.analysis_id)[0] == _headline(db_engine, jobs["decision"])
    _enforce(monkeypatch)
    assert _view(shop.workflow()) == {"scenario": None, "decision": None, "decision_stale": False}
    assert _id_report(client, monkeypatch, scenario_id, shop.analysis_id) == [UNAVAILABLE]
    body = shop.decide().json()
    assert (body["persisted"], body["decision"]["status"]) == (False, "insufficient_evidence")
    assert _stored(db_engine) == stored
    # Selecting the replacement binds to its own generation; the old chain is never reused.
    assert shop.select(scenario_id).status_code == 200
    generated = shop.decide().json()
    assert generated["persisted"] is True
    assert {key: generated["decision"]["evidence_ids"][key] for key in ("des", "mc", "validation")} == {
        "des": None, "mc": None, "validation": None}
    assert _view(shop.workflow())["decision"] == generated["evidence"]["id"]


@pytest.mark.parametrize("renamed", [False, True], ids=["byte-identical", "same-id-and-time"])
def test_a_replaced_selected_plan_blocks_the_decision_and_the_report_under_enforcement(client, db_engine,
                                                                                       monkeypatch, renamed):
    analysis_id, _, scenario_id, headers, jobs = _selected(client, db_engine, monkeypatch,
                                                           "g6-sel-replace@example.com")
    _replace(client, headers, db_engine, Scenario, scenario_id, "scenarios", renamed=renamed)
    stored = _stored(db_engine)
    _enforce(monkeypatch, False)
    assert _selected_report(client, analysis_id, headers) == (200, None)
    assert _reported_decision(client, analysis_id, headers) == jobs["decision"]
    _enforce(monkeypatch)
    replaced = (409, workflow_api.SELECTED_PLAN_REPLACED_DETAIL)
    assert _selected_report(client, analysis_id, headers) == replaced
    assert _refused(_post(client, headers, analysis_id, "decision/selected")) == replaced
    assert _view(_workflow(client, analysis_id)) == {"scenario": None, "decision": None, "decision_stale": False}
    assert _stored(db_engine) == stored


def test_a_replaced_dataset_and_its_cascaded_shared_scenario_serve_no_decision_under_enforcement(
        client, db_engine, monkeypatch):
    shop, dataset_id, scenario_id, jobs = _shared(client, db_engine, monkeypatch, "g6-shared-dataset@example.com")
    _replace_dataset_and_its_scenario(client, shop.headers, db_engine, dataset_id, scenario_id)
    stored = _stored(db_engine)
    _enforce(monkeypatch, False)
    assert _view(shop.workflow())["decision"] == jobs["decision"]
    _enforce(monkeypatch)
    assert _view(shop.workflow()) == {"scenario": None, "decision": None, "decision_stale": False}
    assert _id_report(client, monkeypatch, scenario_id, shop.analysis_id) == [UNAVAILABLE]
    assert shop.decide().json()["persisted"] is False
    assert _stored(db_engine) == stored


def test_a_replaced_dataset_and_its_cascaded_selected_plan_keep_the_provenance_422(client, db_engine,
                                                                                    monkeypatch):
    analysis_id, dataset_id, scenario_id, headers, jobs = _selected(client, db_engine, monkeypatch,
                                                                    "g6-sel-dataset@example.com")
    _replace_dataset_and_its_scenario(client, headers, db_engine, dataset_id, scenario_id)
    stored = _stored(db_engine)
    _enforce(monkeypatch, False)
    assert _reported_decision(client, analysis_id, headers) == jobs["decision"]
    _enforce(monkeypatch)
    assert _selected_report(client, analysis_id, headers) == (422, NOT_RUNNABLE_PROVENANCE)      # D1
    assert _refused(_post(client, headers, analysis_id, "decision/selected")) == (422, NOT_RUNNABLE_PROVENANCE)
    assert _view(_workflow(client, analysis_id)) == {"scenario": None, "decision": None, "decision_stale": False}
    assert _stored(db_engine) == stored


# -- D1: the scenario's own dataset binding keeps the approved 422 --------------------------------------------


@pytest.mark.parametrize("binding", [None, "", OTHER], ids=["null", "empty", "other-row"])
def test_the_selected_report_keeps_the_scenario_provenance_422(client, db_engine, monkeypatch, binding):
    analysis_id, _, scenario_id, headers, _ = _selected(client, db_engine, monkeypatch, "g6-sel-d1@example.com")
    _bind(db_engine, scenario_id, binding)                     # SYNTHETIC (direct row edit)
    stored = _stored(db_engine)
    _enforce(monkeypatch, False)
    assert _selected_report(client, analysis_id, headers) == (200, None)
    _enforce(monkeypatch)
    assert _selected_report(client, analysis_id, headers) == (422, NOT_RUNNABLE_PROVENANCE)
    assert _refused(_post(client, headers, analysis_id, "decision/selected")) == (422, NOT_RUNNABLE_PROVENANCE)
    assert _stored(db_engine) == stored


# -- Latest Decision only: never a fallback to an older, valid one --------------------------------------------


def test_a_broken_latest_shared_decision_never_falls_back_to_an_older_one(client, db_engine, monkeypatch):
    shop, _, scenario_id, jobs = _shared(client, db_engine, monkeypatch, "g6-shared-latest@example.com")
    latest = shop.decide().json()["evidence"]["id"]
    assert jobs["decision"] < latest
    _set_token(db_engine, latest, "dataset_generation", OTHER)  # SYNTHETIC (direct row edit)
    assert _assess(db_engine, jobs["decision"], enforced=True, monkeypatch=monkeypatch).is_current
    assert _view(shop.workflow()) == {"scenario": scenario_id, "decision": None, "decision_stale": True}
    assert _id_report(client, monkeypatch, scenario_id, shop.analysis_id) == [UNAVAILABLE]


def test_a_broken_latest_selected_decision_never_falls_back_to_an_older_one(client, db_engine, monkeypatch):
    analysis_id, _, _, headers, jobs = _selected(client, db_engine, monkeypatch, "g6-sel-latest@example.com")
    latest = _post(client, headers, analysis_id, "decision/selected").json()["evidence"]["id"]
    assert jobs["decision"] < latest
    _set_token(db_engine, latest, "dataset_generation", _DROP)  # SYNTHETIC (direct row edit)
    assert _assess(db_engine, jobs["decision"], enforced=True, monkeypatch=monkeypatch).is_current
    assert _selected_report(client, analysis_id, headers) == (409, UNRECORDED)
    assert _view(_workflow(client, analysis_id))["decision"] is None


# -- The dataset report reads no jobs ---------------------------------------------------------------------


def test_the_dataset_report_is_unchanged_by_enforcement(client, db_engine, monkeypatch):
    shop, dataset_id, _, jobs = _shared(client, db_engine, monkeypatch, "g6-dataset-report@example.com")
    _edit_job(db_engine, jobs["decision"], drop=TOKENS)         # SYNTHETIC (direct row edit)
    route = f"/reports/datasets/{dataset_id}/excel?analysis_id={shop.analysis_id}"
    responses = []
    for on in (False, True):
        _enforce(monkeypatch, on)
        response = client.get(route)
        assert response.status_code == 200
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        responses.append({name: [[cell.value for cell in row] for row in workbook[name].iter_rows()]
                          for name in workbook.sheetnames})
    assert responses[0] == responses[1]
