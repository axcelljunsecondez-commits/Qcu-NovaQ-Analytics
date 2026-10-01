"""G3: every workflow job records the generation of the rows it was computed from, and selected-plan
Monte Carlo and validation refuse a broken input before computing (gates G-T3 and G-T6, flag off).

Spec: docs/superpowers/specs/2026-09-26-generation-identity-contract.md §7, §8.1 and §14 (G3).
Decisions of 2026-09-28: the OD-G2 gate runs last, immediately before the computation (D2), and a
Current-mode job records ``scenario_generation`` as null rather than omitting it (D3).

Generation enforcement is off in G3: a recorded token is written but never consulted, so a job
without tokens, or with tokens that no longer match, is still accepted when it meets the Step 5
rules. Enforcement is a later stage.

Data labels: SYNTHETIC rows come from the real endpoints unless marked "direct row edit/insert".

Runs on SQLite, and on PostgreSQL when NOVAQ_TEST_DATABASE_URL names a dedicated *_test database.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm.attributes import flag_modified

import backend.api.workflow as workflow_api
from backend.api.settings import Settings
from backend.db.models import AnalysisProject, Dataset, Job, Scenario, User
from tests.helpers import create_user, csrf_header, login, make_sessionmaker
from tests.test_d7_current_evidence_dataset import Workspace
from tests.test_separate_report import _api_workspace
from tests.test_step5_missing_dependency import (
    DES_PAYLOAD,
    MC_PAYLOAD,
    MISSING_DATASET_99999_DETAIL,
    VALIDATION_PAYLOAD,
    Shop,
)

TOKENS = ("scenario_generation", "dataset_generation")
FOREIGN = {"scenario_generation": "f" * 32, "dataset_generation": "e" * 32}


def _params(db_engine, job_id: int) -> dict[str, Any]:
    with make_sessionmaker(db_engine)() as db:
        return dict(db.get(Job, job_id).params_json or {})


def _generation(db_engine, model, row_id: int) -> str:
    with make_sessionmaker(db_engine)() as db:
        return db.get(model, row_id).generation


def _count(db_engine, kind: str) -> int:
    with make_sessionmaker(db_engine)() as db:
        return db.query(Job).filter(Job.kind == kind).count()


def _latest_id(db_engine, kind: str) -> int:
    with make_sessionmaker(db_engine)() as db:
        return db.query(Job).filter(Job.kind == kind).order_by(Job.id.desc()).first().id


def _edit_job(db_engine, job_id: int, *, params: dict[str, Any] | None = None,
              drop: tuple[str, ...] = (), drop_result: tuple[str, ...] = ()) -> None:
    """SYNTHETIC (direct row edit): recorded fields no endpoint would write."""
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, job_id)
        stored = {key: value for key, value in (job.params_json or {}).items() if key not in drop}
        job.params_json = {**stored, **(params or {})}
        job.result_json = {key: value for key, value in (job.result_json or {}).items() if key not in drop_result}
        flag_modified(job, "params_json")
        flag_modified(job, "result_json")
        db.commit()


def _assert_stamped(db_engine, job_id: int, *, scenario_id: int | None, dataset_id: int) -> None:
    params = _params(db_engine, job_id)
    assert set(TOKENS) <= set(params)
    expected_scenario = None if scenario_id is None else _generation(db_engine, Scenario, scenario_id)
    assert params["scenario_generation"] == expected_scenario
    assert params["dataset_generation"] == _generation(db_engine, Dataset, dataset_id)
    assert params["dataset_id"] == dataset_id
    assert params["scenario_id"] == scenario_id


# -- G-T3: each of the 12 _save_job call sites records the rows it read ---------------------------


def test_shared_flow_jobs_record_the_scenario_and_dataset_they_read(client, db_engine):
    """Selection, DES, MC, validation and the shared-queue Decision."""
    shop = Shop(client, db_engine, email="g3-shared@example.com")
    dataset_id = shop.upload(4, "a.csv")
    scenario_id = shop.seed_scenario(dataset_id, 4)
    selection = shop.select(scenario_id)
    assert selection.status_code == 200, selection.text
    jobs = {"selection": selection.json()["selection"]["id"], **shop.run_chain()}
    decided = shop.decide()
    assert decided.status_code == 200 and decided.json()["persisted"] is True
    jobs["decision"] = decided.json()["evidence"]["id"]
    for job_id in jobs.values():
        _assert_stamped(db_engine, job_id, scenario_id=scenario_id, dataset_id=dataset_id)
    # The page receives the recorded tokens with the evidence (additive params keys).
    assert decided.json()["evidence"]["params"]["dataset_generation"] == _generation(db_engine, Dataset, dataset_id)


def test_current_mode_jobs_record_the_current_dataset_and_a_null_scenario_generation(client, db_engine):
    """Current DES, MC and validation read no scenario: the key is present and null (D3)."""
    workspace = Workspace(client, db_engine, email="g3-current@example.com")
    first = workspace.upload(2, "a.csv")
    for job_id in workspace.run_all().values():
        _assert_stamped(db_engine, job_id, scenario_id=None, dataset_id=first)
    # A newer dataset becomes the Current one, and new evidence records its token instead.
    second = workspace.upload(3, "b.csv")
    job_id = workspace.run("des", DES_PAYLOAD)
    _assert_stamped(db_engine, job_id, scenario_id=None, dataset_id=second)
    assert _generation(db_engine, Dataset, first) != _generation(db_engine, Dataset, second)


def test_selected_plan_jobs_record_the_verified_plan_rows(client, db_engine):
    """Selection, selected DES, MC, validation and the selected Decision."""
    analysis_id, dataset_id, scenario_id = _api_workspace(db_engine, "g3-selected@example.com")
    assert login(client, "g3-selected@example.com", "pw") == 200
    headers = csrf_header(client)
    before = {kind: _count(db_engine, kind) for kind in
              ("workflow_selection", "workflow_des", "workflow_mc", "workflow_validation", "workflow_decision")}
    steps = [("selection", {"scenario_id": scenario_id}), ("simulation/des/selected", {"seed": 7}),
             ("simulation/mc/selected", {}), ("simulation/validation/selected", {}),
             ("decision/selected", {})]
    for path, body in steps:
        response = client.post(f"/analyses/{analysis_id}/workflow/{path}", headers=headers, json=body)
        assert response.status_code == 200, (path, response.text)
    for kind, count in before.items():
        assert _count(db_engine, kind) == count + 1
        _assert_stamped(db_engine, _latest_id(db_engine, kind), scenario_id=scenario_id, dataset_id=dataset_id)


def test_tokens_in_a_request_body_are_never_recorded(client, db_engine):
    shop = Shop(client, db_engine, email="g3-body@example.com")
    dataset_id = shop.upload(4, "a.csv")
    scenario_id = shop.seed_scenario(dataset_id, 4)
    selected = client.post(f"/analyses/{shop.analysis_id}/workflow/selection", headers=shop.headers,
                           json={"scenario_id": scenario_id, **FOREIGN})
    assert selected.status_code == 200
    des = shop.run("des", {**DES_PAYLOAD, **FOREIGN})
    current = client.post(f"/analyses/{shop.analysis_id}/workflow/simulation/des/current",
                          headers=shop.headers, json={**DES_PAYLOAD, **FOREIGN})
    assert current.status_code == 200
    _assert_stamped(db_engine, selected.json()["selection"]["id"], scenario_id=scenario_id, dataset_id=dataset_id)
    _assert_stamped(db_engine, des, scenario_id=scenario_id, dataset_id=dataset_id)
    _assert_stamped(db_engine, current.json()["evidence"]["id"], scenario_id=None, dataset_id=dataset_id)


def _direct_rows(db, email: str) -> tuple[User, AnalysisProject, Dataset]:
    user = db.query(User).filter_by(email=email).one()
    analysis = AnalysisProject(user_id=user.id, name="Direct", queue_setup_json={}, setup_status="legacy")
    db.add(analysis)
    db.flush()
    dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="d", source_filename="d.csv",
                      source_format="csv", row_count=0, normalized_json=[],
                      validation_report_json={"ok": True})
    db.add(dataset)
    db.flush()
    return user, analysis, dataset


def test_the_server_tokens_replace_any_caller_supplied_params(db_engine):
    create_user(db_engine, "g3-direct@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        user, analysis, dataset = _direct_rows(db, "g3-direct@example.com")
        job = workflow_api._save_job(db, user, "workflow_des_current", analysis, None, dict(FOREIGN),
                                     {}, Settings(), dataset)
        assert job.params_json["scenario_generation"] is None
        assert job.params_json["dataset_generation"] == dataset.generation != FOREIGN["dataset_generation"]


def test_a_job_is_refused_when_its_dataset_is_not_the_scenarios(db_engine):
    create_user(db_engine, "g3-guard@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        user, analysis, dataset = _direct_rows(db, "g3-guard@example.com")
        other = Dataset(user_id=user.id, analysis_id=analysis.id, name="o", source_filename="o.csv",
                        source_format="csv", row_count=0, normalized_json=[],
                        validation_report_json={"ok": True})
        db.add(other)
        db.flush()
        scenario = Scenario(user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id, name="s",
                            settings_json={}, results_json={})
        db.add(scenario)
        db.commit()
        with pytest.raises(ValueError, match="dataset its scenario was verified against"):
            workflow_api._save_job(db, user, "workflow_des", analysis, scenario, {}, {}, Settings(), other)
    assert _count(db_engine, "workflow_des") == 0


def test_a_replacement_dataset_with_the_same_id_and_time_is_recorded_by_its_own_token(client, db_engine):
    shop = Shop(client, db_engine, email="g3-replace@example.com")
    dataset_id = shop.upload(4, "a.csv")
    run = f"/analyses/{shop.analysis_id}/workflow/simulation/des/current"
    first = client.post(run, headers=shop.headers, json=DES_PAYLOAD)
    assert first.status_code == 200
    with shop.session_factory() as db:
        original = db.get(Dataset, dataset_id)
        columns = {column.name: getattr(original, column.key) for column in Dataset.__table__.columns
                   if column.name != "generation"}
    assert client.delete(f"/datasets/{dataset_id}", headers=shop.headers).status_code == 200
    with shop.session_factory() as db:                    # SYNTHETIC (direct row insert)
        db.add(Dataset(**columns))
        db.commit()
    second = client.post(run, headers=shop.headers, json=DES_PAYLOAD)
    assert second.status_code == 200
    old = _params(db_engine, first.json()["evidence"]["id"])
    new = _params(db_engine, second.json()["evidence"]["id"])
    assert old["dataset_id"] == new["dataset_id"] == dataset_id
    assert new["dataset_generation"] == _generation(db_engine, Dataset, dataset_id)
    assert new["dataset_generation"] != old["dataset_generation"]


# -- G-T6 (flag off): OD-G2 write-time gates -------------------------------------------------------


def _selected(client, db_engine, email: str, *, through: str) -> tuple[int, dict[str, str], dict[str, int]]:
    """A selected separate plan run through ``through`` ("des" or "mc")."""
    analysis_id, _, scenario_id = _api_workspace(db_engine, email)
    assert login(client, email, "pw") == 200
    headers = csrf_header(client)
    base = f"/analyses/{analysis_id}/workflow"
    assert client.post(f"{base}/selection", headers=headers, json={"scenario_id": scenario_id}).status_code == 200
    jobs = {"des": client.post(f"{base}/simulation/des/selected", headers=headers,
                               json={"seed": 7}).json()["evidence"]["id"]}
    if through == "mc":
        mc = client.post(f"{base}/simulation/mc/selected", headers=headers, json={})
        assert mc.status_code == 200, mc.text
        jobs["mc"] = mc.json()["evidence"]["id"]
    return analysis_id, headers, jobs


def _refuse_computation(monkeypatch, name: str) -> None:
    def computed(*args, **kwargs):
        raise AssertionError(f"{name} ran on a refused input")
    monkeypatch.setattr(workflow_api, name, computed)


def test_selected_mc_refuses_a_des_input_that_fails_step5_before_computing(client, db_engine, monkeypatch):
    analysis_id, headers, jobs = _selected(client, db_engine, "g3-mc-gate@example.com", through="des")
    # SYNTHETIC (direct row edit): the dataset the DES job was computed from no longer resolves; the
    # scenario link, engine, Setup hash and loads all still pass every pre-G3 check.
    _edit_job(db_engine, jobs["des"], params={"dataset_id": 99999})
    before = _count(db_engine, "workflow_mc")
    _refuse_computation(monkeypatch, "mc_simulate_segments")
    response = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc/selected", headers=headers, json={})
    assert response.status_code == 409
    assert response.json()["detail"] == MISSING_DATASET_99999_DETAIL
    assert _count(db_engine, "workflow_mc") == before


@pytest.mark.parametrize("broken", ["des", "mc"])
def test_selected_validation_refuses_a_broken_input_before_computing(client, db_engine, monkeypatch, broken):
    analysis_id, headers, jobs = _selected(client, db_engine, f"g3-val-{broken}@example.com", through="mc")
    _edit_job(db_engine, jobs[broken], params={"dataset_id": 99999})     # SYNTHETIC (direct row edit)
    before = _count(db_engine, "workflow_validation")
    _refuse_computation(monkeypatch, "validate_selected_plan")
    response = client.post(f"/analyses/{analysis_id}/workflow/simulation/validation/selected",
                           headers=headers, json={})
    assert response.status_code == 409
    assert response.json()["detail"] == MISSING_DATASET_99999_DETAIL
    assert _count(db_engine, "workflow_validation") == before


@pytest.mark.parametrize("tokens", ["unstamped", "mismatched"])
def test_inputs_are_not_judged_by_their_tokens_while_enforcement_is_off(client, db_engine, tokens):
    """An input that meets Step 5 is accepted whatever its tokens say (spec §8.1 item 3)."""
    analysis_id, headers, jobs = _selected(client, db_engine, f"g3-{tokens}@example.com", through="des")
    change = {"drop": TOKENS} if tokens == "unstamped" else {"params": {"scenario_generation": "0" * 32,
                                                                      "dataset_generation": "1" * 32}}
    _edit_job(db_engine, jobs["des"], **change)                          # SYNTHETIC (direct row edit)
    base = f"/analyses/{analysis_id}/workflow/simulation"
    mc = client.post(f"{base}/mc/selected", headers=headers, json={})
    assert mc.status_code == 200, mc.text
    _edit_job(db_engine, mc.json()["evidence"]["id"], **change)          # SYNTHETIC (direct row edit)
    validated = client.post(f"{base}/validation/selected", headers=headers, json={})
    assert validated.status_code == 200, validated.text


def test_the_gates_run_after_every_earlier_refusal(client, db_engine):
    """D2: an input that is also broken keeps reporting the refusal it reported before G3."""
    analysis_id, headers, jobs = _selected(client, db_engine, "g3-order@example.com", through="mc")
    base = f"/analyses/{analysis_id}/workflow/simulation"
    # SYNTHETIC (direct row edits): each input fails an earlier check and Step 5 at once.
    _edit_job(db_engine, jobs["mc"], params={"dataset_id": 99999, "failure_rate_cap": None})
    validated = client.post(f"{base}/validation/selected", headers=headers, json={})
    assert validated.status_code == 422
    assert validated.json()["detail"] == "Selected Monte Carlo evidence has no usable failure cap."
    _edit_job(db_engine, jobs["des"], params={"dataset_id": 99999}, drop_result=("load_replications",))
    mc = client.post(f"{base}/mc/selected", headers=headers, json={})
    assert mc.status_code == 409
    assert mc.json()["detail"] == "Selected-plan DES evidence has no mean routed loads. Rerun selected-plan DES."
