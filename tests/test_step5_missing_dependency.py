"""Step 5: a required dependency that is missing, out of scope or newer cannot support current
evidence.

Steps 3 (D7) and 4 bound Current-mode jobs and schema-1 scenarios to the *current dataset*. They
did not check that the records a stored job names are still there. A job carries its references
inside ``params_json`` and ``result_json``, which no foreign key protects: deleting a dataset
deletes its scenarios (``models.py``, ``cascade="all, delete-orphan"``) but leaves every job that
named them, and no endpoint deletes a job at all. A freed id can then be handed to a later record,
so an orphaned job silently re-binds to evidence it was never computed from.

Step 5 resolves each recorded reference (dataset, scenario, linked job) for existence, owner and
analysis scope, chronology, and the referenced evidence's own eligibility, and applies the same
rule at every consumer: the workflow slots, the Decision endpoints and the report chain.

Every expectation is a literal fixed when the data was built (for example "the dataset-A DES job
id"); none is recomputed from the rule under test.

Data labels:

- SYNTHETIC: users, analyses, datasets, scenarios and runs made here through the real endpoints.
  Distinct arrival rates fingerprint which generation produced a result (A: lambda 4, B: 99).
- SYNTHETIC (direct row insert/edit): a stored row written or edited in place to reach a state no
  endpoint produces -- a reference to a foreign owner or analysis, an unrecorded dataset id, a
  controlled creation time, a freed scenario id written back on an engine whose sequence never
  reissues one. Each such step is marked at its call site. No endpoint can produce a
  cross-owner reference, so those cases have no recorded counterpart.
- RECORDED (shape only): analysis 21 of the local development database holds selection job 90 and
  DES job 91 naming scenario 31 and dataset 36, both of which are deleted; the export method is
  documented in tests/fixtures/evidence_status_local_reference_2026-09-25.json. The *shape* of
  that state is reproduced here. No stored metric of those rows is used or needed, because the
  guard reads recorded identity only.

Historical rows are never deleted here; several tests assert the row is still stored and unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.orm.attributes import flag_modified

from backend.db.models import Dataset, Job, Scenario
from tests.helpers import create_user, csrf_header, login, make_sessionmaker
from tests.test_d7_current_evidence_dataset import Workspace
from tests.test_separate_report import _api_workspace, _full_chain

DES_PAYLOAD = {"sim_hours": 1, "max_events": 100}
MC_PAYLOAD = {"num_trials": 20, "failure_threshold": 0.8, "failure_rate_cap": 0.5, "seed": 7}
VALIDATION_PAYLOAD = {"des_sim_hours": 1, "mc_trials": 20, "mc_failure_threshold": 0.8,
                      "mc_failure_rate_cap": 0.5, "seed": 7}
MISSING_DEPENDENCY_DETAIL = (
    "Evidence references a record that no longer exists or is not this Analysis's. "
    "Rerun the affected step."
)
# 5d: a refusal whose missing record is known names it. MISSING_DEPENDENCY_DETAIL stays the text
# of generation refusals (G5, G6) and of a refusal that records no reason.
MISSING_DATASET_99999_DETAIL = (
    "Evidence references records that no longer exist: dataset #99999. Rerun the affected step."
)


def shared_setup() -> dict[str, Any]:
    return {"queue_structure": "shared_queue", "fixed_server_count": 2,
            "staffing_varies_by_period": False, "capacity_mode": "unlimited",
            "total_system_capacity": None, "abandonment_mode": "not_modeled",
            "patience_rate_per_hour": None, "segments": [], "queue_ids": []}


def schema1_snapshot(lam: float) -> dict[str, Any]:
    """A schema-1 calculation snapshot: no schema_version 2, and no setup fingerprint."""
    return {"engine_version": "novaq-2026-09-system-v2",
            "input_segments": [{"time": "08:00-09:00", "lambda": lam, "mu": 12, "c": 2}]}


def shared_results(lam: float) -> dict[str, Any]:
    return {"results": [{
        "time": "08:00-09:00", "lambda_": float(lam), "mu": 12.0,
        "c_current": 2, "c_optimal": 2, "rho_current": 0.1667, "rho_optimal": 0.1667,
        "Wq_current": 0.01, "Wq_optimal": 0.01, "Lq_current": 0.04, "Lq_optimal": 0.04,
        "cost_current": 200, "cost_optimal": 200,
        "current_stable": True, "optimized_stable": True,
    }]}


class Shop:
    """One signed-in owner with one shared-queue analysis."""

    def __init__(self, client, db_engine, email: str = "s5@example.com"):
        self.client = client
        self.db_engine = db_engine
        self.session_factory = make_sessionmaker(db_engine)
        self.user_id = create_user(db_engine, email, "pw").id
        assert login(client, email, "pw") == 200
        self.analysis_id = client.post(
            "/analyses", headers=self.headers,
            json={"name": "Shop", "queue_setup": shared_setup()},
        ).json()["analysis"]["id"]

    @property
    def headers(self) -> dict[str, str]:
        return csrf_header(self.client)

    def upload(self, lam: float, name: str) -> int:
        payload = f"time,lambda,mu,c\n08:00-09:00,{lam},12,2\n".encode()
        response = self.client.post(
            f"/analyses/{self.analysis_id}/datasets", headers=self.headers,
            files={"file": (name, payload, "text/csv")})
        assert response.status_code == 201, response.text
        return response.json()["dataset"]["id"]

    def seed_scenario(self, dataset_id: int, lam: float, *, name: str = "Plan",
                      scenario_id: int | None = None) -> int:
        """SYNTHETIC (direct row insert): a verified schema-1 snapshot pinned to a dataset.

        ``scenario_id`` writes the row under that id instead of the engine's next one.
        """
        with self.session_factory() as db:
            scenario = Scenario(
                user_id=self.user_id, analysis_id=self.analysis_id, dataset_id=dataset_id,
                name=name, settings_json={"calculation": schema1_snapshot(lam)},
                results_json=shared_results(lam))
            if scenario_id is not None:
                scenario.id = scenario_id
            db.add(scenario)
            db.commit()
            return scenario.id

    def seed_scenario_at_freed_id(self, freed_id: int, dataset_id: int, lam: float, *,
                                  name: str) -> int:
        """A new scenario under the id a deleted scenario held, on either test engine.

        SQLite gives the next insert one more than the highest id still stored, so once the
        newest scenario is deleted an ordinary insert reissues its id; that is asserted here, not
        assumed. A PostgreSQL sequence never hands out a value twice, so there the freed id is
        written explicitly -- SYNTHETIC (direct row insert under a chosen id). Either way the
        result is the state the guard exists for: a different scenario under an id that stored
        evidence already names.
        """
        if self.db_engine.dialect.name == "sqlite":
            reissued = self.seed_scenario(dataset_id, lam, name=name)
            assert reissued == freed_id, "SQLite reissues the highest freed id"
            return reissued
        return self.seed_scenario(dataset_id, lam, name=name, scenario_id=freed_id)

    def select(self, scenario_id: int):
        return self.client.post(f"/analyses/{self.analysis_id}/workflow/selection",
                                headers=self.headers, json={"scenario_id": scenario_id})

    def run(self, kind: str, payload: dict[str, Any]) -> int:
        response = self.client.post(
            f"/analyses/{self.analysis_id}/workflow/simulation/{kind}",
            headers=self.headers, json=payload)
        assert response.status_code == 200, response.text
        return response.json()["evidence"]["id"]

    def run_chain(self) -> dict[str, int]:
        return {"des": self.run("des", DES_PAYLOAD), "mc": self.run("mc", MC_PAYLOAD),
                "validation": self.run("validation", VALIDATION_PAYLOAD)}

    def decide(self):
        return self.client.post(f"/analyses/{self.analysis_id}/workflow/decision",
                                headers=self.headers)

    def workflow(self) -> dict[str, Any]:
        response = self.client.get(f"/analyses/{self.analysis_id}/workflow")
        assert response.status_code == 200, response.text
        return response.json()

    def slots(self) -> dict[str, int | None]:
        workflow = self.workflow()
        return {name: (workflow[name] or {}).get("id")
                for name in ("scenario", "des", "mc", "validation", "decision")}

    def edit_job(self, job_id: int, **params: Any) -> None:
        """SYNTHETIC (direct row edit): rewrite recorded params no endpoint would write."""
        with self.session_factory() as db:
            job = db.get(Job, job_id)
            job.params_json = {**(job.params_json or {}), **params}
            flag_modified(job, "params_json")
            db.commit()

    def forward_date_scenario(self, scenario_id: int, *, after: int) -> None:
        """SYNTHETIC (direct row edit): make a scenario newer than the job that cites it."""
        with self.session_factory() as db:
            scenario, job = db.get(Scenario, scenario_id), db.get(Job, after)
            scenario.created_at = job.created_at + timedelta(minutes=5)
            db.commit()

    def backdate_jobs(self, minutes: int = 5) -> None:
        """SYNTHETIC (direct row edit): age every stored job, without waiting for the clock."""
        with self.session_factory() as db:
            for job in db.query(Job).all():
                job.created_at = job.created_at - timedelta(minutes=minutes)
            db.commit()

    def stored_decisions(self) -> list[dict[str, Any]]:
        with self.session_factory() as db:
            return [deepcopy(job.result_json) for job in
                    db.query(Job).filter(Job.kind == "workflow_decision").order_by(Job.id)]


def _ready(shop: Shop) -> tuple[int, int, dict[str, int]]:
    """A complete, valid chain: dataset, scenario, selection, DES, MC, validation, Decision."""
    dataset_id = shop.upload(4, "a.csv")
    scenario_id = shop.seed_scenario(dataset_id, 4)
    assert shop.select(scenario_id).status_code == 200
    jobs = shop.run_chain()
    assert shop.decide().json()["persisted"] is True
    return dataset_id, scenario_id, jobs


# -- 1. A valid, complete dependency chain stays current ---------------------


def test_a_complete_chain_is_current_evidence(client, db_engine):
    shop = Shop(client, db_engine)
    _, scenario_id, jobs = _ready(shop)
    slots = shop.slots()
    assert slots["scenario"] == scenario_id
    assert slots["des"] == jobs["des"] and slots["mc"] == jobs["mc"]
    assert slots["validation"] == jobs["validation"]
    assert slots["decision"] is not None
    assert shop.workflow()["decision_stale"] is False


# -- 2-4. A deleted dependency stops supporting current evidence -------------


def test_a_deleted_scenario_ends_its_chain(client, db_engine):
    """Cases 3 and 4: the selection still names the scenario; the scenario row is gone."""
    shop = Shop(client, db_engine)
    _, scenario_id, jobs = _ready(shop)
    assert client.delete(f"/scenarios/{scenario_id}", headers=shop.headers).status_code == 200
    assert shop.slots() == {"scenario": None, "des": None, "mc": None,
                            "validation": None, "decision": None}
    # The selection job itself is still reported: it records that a selection was made, and the
    # page needs that to tell "nothing selected" apart from "the selected plan is gone".
    assert shop.workflow()["selection"] is not None
    # Case 13: every job row survives, unchanged.
    with shop.session_factory() as db:
        assert db.query(Job).count() == 5
        assert (db.get(Job, jobs["des"]).params_json or {}).get("scenario_id") == scenario_id


def test_a_deleted_dataset_ends_current_mode_evidence(client, db_engine):
    """Case 2: a Current-kind job names a dataset that no longer exists."""
    shop = Shop(client, db_engine)
    dataset_id = shop.upload(4, "a.csv")
    des = client.post(f"/analyses/{shop.analysis_id}/workflow/simulation/des/current",
                      headers=shop.headers, json=DES_PAYLOAD)
    assert des.status_code == 200
    job_id = des.json()["evidence"]["id"]
    assert shop.workflow()["des_current"]["id"] == job_id
    assert client.delete(f"/datasets/{dataset_id}", headers=shop.headers).status_code == 200
    assert shop.workflow()["des_current"] is None
    with shop.session_factory() as db:                       # case 13
        assert (db.get(Job, job_id).params_json or {}).get("dataset_id") == dataset_id


# -- 5. A required job reference that is unrecorded or unresolvable ----------


def _separate_current_chain(client, db_engine, email: str) -> tuple[Workspace, int]:
    """Current DES, MC and validation on a separate-queue analysis (the only kind Current
    validation supports). Returns the workspace and the Current-validation job id."""
    workspace = Workspace(client, db_engine, email=email)
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    return workspace, jobs["validation"]


def test_a_current_validation_without_its_mc_reference_is_not_current(client, db_engine):
    workspace, job_id = _separate_current_chain(client, db_engine, "s5-mc-missing@example.com")
    assert workspace.slots()["validation"] == job_id
    # SYNTHETIC (direct row edit): drop the recorded Current-MC link.
    workspace.edit_job_params(job_id, mc_job_id=None)
    assert workspace.slots()["validation"] is None
    assert workspace.stored_job(job_id) is not None          # case 13


def test_a_current_validation_pointing_at_a_missing_job_is_not_current(client, db_engine):
    workspace, job_id = _separate_current_chain(client, db_engine, "s5-mc-gone@example.com")
    # SYNTHETIC (direct row edit): point the link at an id no job row has.
    workspace.edit_job_params(job_id, mc_job_id=9999)
    assert workspace.slots()["validation"] is None


# -- 6-7. A reference outside the owner or the analysis ---------------------


def test_a_reference_to_another_owners_record_is_not_current(client, db_engine):
    """Case 6. No endpoint writes a cross-owner reference; the row is edited directly."""
    shop = Shop(client, db_engine)
    _, scenario_id, jobs = _ready(shop)
    stranger_id = create_user(db_engine, "stranger@example.com", "pw").id
    with shop.session_factory() as db:                       # SYNTHETIC (direct row insert)
        foreign = Scenario(user_id=stranger_id, analysis_id=shop.analysis_id,
                           dataset_id=None, name="Theirs",
                           settings_json={"calculation": schema1_snapshot(4)},
                           results_json=shared_results(4))
        db.add(foreign)
        db.commit()
        foreign_id = foreign.id
    # SYNTHETIC (direct row edit): the DES job now names a scenario owned by someone else.
    shop.edit_job(jobs["des"], scenario_id=foreign_id)
    with shop.session_factory() as db:
        assert db.get(Job, jobs["des"]).params_json["scenario_id"] == foreign_id
    assert shop.select(scenario_id).status_code == 200
    assert shop.slots()["des"] is None


def test_a_reference_to_another_analysis_is_not_current(client, db_engine):
    """Case 7."""
    shop = Shop(client, db_engine)
    _, scenario_id, jobs = _ready(shop)
    other = client.post("/analyses", headers=shop.headers,
                        json={"name": "Other", "queue_setup": shared_setup()}
                        ).json()["analysis"]["id"]
    with shop.session_factory() as db:                       # SYNTHETIC (direct row insert)
        elsewhere = Scenario(user_id=shop.user_id, analysis_id=other, dataset_id=None,
                             name="Elsewhere",
                             settings_json={"calculation": schema1_snapshot(4)},
                             results_json=shared_results(4))
        db.add(elsewhere)
        db.commit()
        elsewhere_id = elsewhere.id
    # SYNTHETIC (direct row edit): a validation job naming a scenario of another analysis.
    shop.edit_job(jobs["validation"], scenario_id=elsewhere_id)
    assert shop.select(scenario_id).status_code == 200
    assert shop.slots()["validation"] is None


# -- 8. A dependency created after the job that cites it --------------------


def test_a_scenario_newer_than_its_evidence_is_not_current(client, db_engine):
    """Case 8: an id freed by a deletion can be reissued, so evidence that predates the row it
    names was not computed from that row."""
    shop = Shop(client, db_engine)
    _, scenario_id, jobs = _ready(shop)
    # SYNTHETIC (direct row edit): the recorded chronology, without waiting for the clock.
    shop.forward_date_scenario(scenario_id, after=jobs["validation"])
    assert shop.slots() == {"scenario": scenario_id, "des": None, "mc": None,
                            "validation": None, "decision": None}
    assert shop.workflow()["decision_stale"] is True


def test_scenario_id_reuse_does_not_inherit_the_previous_generations_evidence(client, db_engine):
    """Case 8, end to end: delete the newest scenario, save another, and the freed id comes back
    (``Shop.seed_scenario_at_freed_id`` says how on each engine).

    The replacement is a different calculation (lambda 99 against lambda 4), so inheriting the
    old DES, MC and validation would present evidence about the deleted plan as evidence about
    this one.
    """
    shop = Shop(client, db_engine)
    dataset_id, first_id, jobs = _ready(shop)
    with shop.session_factory() as db:
        stored_des_result = deepcopy(db.get(Job, jobs["des"]).result_json)
    assert client.delete(f"/scenarios/{first_id}", headers=shop.headers).status_code == 200
    second_id = shop.seed_scenario_at_freed_id(first_id, dataset_id, 99, name="Replacement")
    assert second_id == first_id, "the replacement holds the freed id; the guard is what protects"
    # SYNTHETIC (direct row edit): the replacement is saved in the same clock second as the
    # original run, so its recorded creation time is advanced to what a real save would carry.
    shop.forward_date_scenario(second_id, after=jobs["validation"])
    assert shop.select(second_id).status_code == 200
    assert shop.slots() == {"scenario": second_id, "des": None, "mc": None,
                            "validation": None, "decision": None}
    decision = shop.decide().json()["decision"]
    assert decision["status"] == "insufficient_evidence"
    assert decision["evidence_ids"]["des"] is None
    assert decision["evidence_ids"]["validation"] is None
    with shop.session_factory() as db:                       # case 13
        assert db.get(Job, jobs["des"]).result_json == stored_des_result


# -- 9. Missing required provenance ----------------------------------------


def test_a_job_without_a_recorded_dataset_is_not_current(client, db_engine):
    shop = Shop(client, db_engine)
    _, _, jobs = _ready(shop)
    # SYNTHETIC (direct row edit): a job with no recorded dataset identity.
    shop.edit_job(jobs["des"], dataset_id=None)
    assert shop.slots()["des"] is None


# -- 10. A superseded but valid run stays stored and is not the current one --


def test_a_superseded_run_is_kept_and_the_latest_one_is_current(client, db_engine):
    shop = Shop(client, db_engine)
    _, _, first = _ready(shop)
    second_des = shop.run("des", DES_PAYLOAD)
    assert second_des != first["des"]
    assert shop.slots()["des"] == second_des
    with shop.session_factory() as db:                       # case 13
        assert db.get(Job, first["des"]) is not None


# -- 11-12. Decision and report eligibility ---------------------------------


def test_a_decision_is_refused_when_its_scenario_is_gone(client, db_engine):
    """Case 11."""
    shop = Shop(client, db_engine)
    _, scenario_id, _ = _ready(shop)
    assert client.delete(f"/scenarios/{scenario_id}", headers=shop.headers).status_code == 200
    body = shop.decide().json()
    assert body["persisted"] is False
    assert body["decision"]["status"] == "insufficient_evidence"


def test_a_scenario_report_serves_no_current_decision_for_a_broken_chain(client, db_engine):
    """Case 12, ID-scoped export.

    The stored comparison rows stay exportable -- that export is an ID-scoped historical read and
    Step 5 does not change what it serves -- but no current Decision backs it once the chain is
    broken, so the Decision section is empty.
    """
    shop = Shop(client, db_engine)
    _, scenario_id, jobs = _ready(shop)
    before = client.get(f"/reports/scenarios/{scenario_id}/excel?analysis_id={shop.analysis_id}")
    assert before.status_code == 200
    shop.forward_date_scenario(scenario_id, after=jobs["des"])
    after = client.get(f"/reports/scenarios/{scenario_id}/excel?analysis_id={shop.analysis_id}")
    assert after.status_code == 200
    assert shop.slots()["decision"] is None


# -- 14-15. Steps 3 and 4 behave as they did --------------------------------


def test_step3_current_mode_dataset_binding_is_unchanged(client, db_engine):
    """Case 14: replacing the dataset still ends Current-mode currentness."""
    shop = Shop(client, db_engine)
    shop.upload(4, "a.csv")
    job_id = client.post(f"/analyses/{shop.analysis_id}/workflow/simulation/des/current",
                         headers=shop.headers, json=DES_PAYLOAD).json()["evidence"]["id"]
    assert shop.workflow()["des_current"]["id"] == job_id
    shop.upload(9, "b.csv")
    assert shop.workflow()["des_current"] is None
    with shop.session_factory() as db:
        assert db.get(Job, job_id) is not None


def test_step4_schema1_dataset_currentness_is_unchanged(client, db_engine):
    """Case 15: a schema-1 scenario pinned to a replaced dataset is still not selectable."""
    shop = Shop(client, db_engine)
    dataset_a = shop.upload(4, "a.csv")
    scenario_id = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario_id).status_code == 200
    shop.upload(9, "b.csv")
    refused = shop.select(scenario_id)
    assert refused.status_code == 422
    assert refused.json()["detail"] == "Scenario is stale for the current dataset."
    with shop.session_factory() as db:
        assert db.get(Scenario, scenario_id).dataset_id == dataset_a


def test_a_dataset_newer_than_the_scenario_that_cites_it_is_not_current(client, db_engine):
    """The chronology rule reaches the scenario's own dataset reference too."""
    shop = Shop(client, db_engine)
    dataset_id, scenario_id, _ = _ready(shop)
    with shop.session_factory() as db:                       # SYNTHETIC (direct row edit)
        dataset, scenario = db.get(Dataset, dataset_id), db.get(Scenario, scenario_id)
        dataset.created_at = scenario.created_at + timedelta(minutes=5)
        db.commit()
    assert shop.slots()["des"] is None


# -- 11-12, 16. The selected-plan (schema-2) chain ---------------------------


def _selected_workspace(client, db_engine, email: str):
    """A separate-queue analysis with a saved schema-2 plan and its full evidence chain."""
    analysis_id, dataset_id, scenario_id = _api_workspace(db_engine, email)
    assert login(client, email, "pw") == 200
    headers = csrf_header(client)
    _full_chain(client, analysis_id, headers, scenario_id)
    return analysis_id, dataset_id, scenario_id, headers


def test_the_selected_plan_chain_is_complete_before_anything_is_broken(client, db_engine):
    """Case 16: the schema-2 protections and the selected report are unchanged by Step 5."""
    analysis_id, _, _, headers = _selected_workspace(client, db_engine, "s5-sel-ok@example.com")
    preview = client.get(f"/reports/analyses/{analysis_id}/selected/preview", headers=headers)
    assert preview.status_code == 200, preview.text
    report = client.get(f"/reports/analyses/{analysis_id}/selected/pdf", headers=headers)
    assert report.status_code == 200


def test_a_selected_chain_job_naming_a_missing_scenario_blocks_report_and_decision(
        client, db_engine):
    """Cases 11 and 12: one broken reference must block the report chain and the Decision, not
    just disappear from the workflow slots."""
    analysis_id, _, scenario_id, headers = _selected_workspace(
        client, db_engine, "s5-sel-broken@example.com")
    session_factory = make_sessionmaker(db_engine)
    with session_factory() as db:
        des_job = (db.query(Job)
                   .filter(Job.kind == "workflow_des")
                   .order_by(Job.id.desc()).first())
        des_id = des_job.id
        # SYNTHETIC (direct row edit): the scenario link, the DES/MC/validation link ids and the
        # setup hash all stay intact, so every check that existed before Step 5 still passes.
        # Only the dataset the DES job was computed from is repointed at a row that is not there
        # -- the state a dataset deletion leaves behind, which nothing else inspects.
        des_job.params_json = {**(des_job.params_json or {}), "dataset_id": 99999}
        flag_modified(des_job, "params_json")
        db.commit()
    decided = client.post(f"/analyses/{analysis_id}/workflow/decision/selected",
                          headers=headers, json={})
    assert decided.status_code == 409, decided.text
    assert decided.json()["detail"] == MISSING_DATASET_99999_DETAIL
    preview = client.get(f"/reports/analyses/{analysis_id}/selected/preview", headers=headers)
    assert preview.status_code == 409, preview.text
    assert preview.json()["detail"] == MISSING_DATASET_99999_DETAIL
    report = client.get(f"/reports/analyses/{analysis_id}/selected/pdf", headers=headers)
    assert report.status_code == 409
    with session_factory() as db:                            # case 13
        assert db.get(Job, des_id) is not None
        assert db.get(Scenario, scenario_id) is not None


# -- 17. `decision_stale` keeps its established meaning (Step 5 review, Option A) --------
#
# Step 5 must never serve an unresolvable Decision, and it does not: `decision` is null in every
# case below. What these tests pin is the separate flag. `decision_stale` tells the page "the
# Decision for the selected plan must be generated again". With no eligible selected scenario
# there is no plan to generate one for, so the flag keeps its pre-Step-5 value (false unless the
# Setup changed) and "Generate Decision" reports what is missing instead of being hidden behind a
# warning it cannot clear. Each literal below was recorded from the API before Step 5 (export of
# 2038845b) for the same actions.

NOT_RUNNABLE_DETAIL = "Selected plan is not runnable: Select a verified Scenario from this Analysis."


def _delete_selected_scenario(shop: Shop, dataset_id: int, scenario_id: int) -> None:
    assert shop.client.delete(f"/scenarios/{scenario_id}", headers=shop.headers).status_code == 200


def _upload_new_dataset(shop: Shop, dataset_id: int, scenario_id: int) -> None:
    shop.upload(9, "b.csv")


def _delete_source_dataset(shop: Shop, dataset_id: int, scenario_id: int) -> None:
    assert shop.client.delete(f"/datasets/{dataset_id}", headers=shop.headers).status_code == 200


@pytest.mark.parametrize("action", [_delete_selected_scenario, _upload_new_dataset,
                                    _delete_source_dataset],
                         ids=["scenario-deleted", "new-dataset", "dataset-deleted"])
def test_no_eligible_selection_does_not_flag_a_stale_decision(client, db_engine, action):
    shop = Shop(client, db_engine)
    dataset_id, scenario_id, _ = _ready(shop)
    stored = shop.stored_decisions()
    action(shop, dataset_id, scenario_id)
    workflow = shop.workflow()
    # The guard is intact: no scenario, no scenario-bound evidence and no Decision is served.
    assert {name: workflow[name] for name in ("scenario", "des", "mc", "validation", "decision")} \
        == {"scenario": None, "des": None, "mc": None, "validation": None, "decision": None}
    assert workflow["decision_stale"] is False
    # "Generate Decision" answers with what is missing, and nothing is persisted or promoted.
    generated = shop.decide().json()
    assert generated["persisted"] is False
    assert generated["decision"]["status"] == "insufficient_evidence"
    after = shop.workflow()
    assert after["decision"] is None and after["decision_stale"] is False
    assert shop.stored_decisions() == stored                # case 13: the stored Decision is kept


def test_separate_no_eligible_selection_does_not_flag_a_stale_decision(client, db_engine):
    analysis_id, _, scenario_id, headers = _selected_workspace(
        client, db_engine, "s5-sel-gone@example.com")
    assert client.delete(f"/scenarios/{scenario_id}", headers=headers).status_code == 200
    workflow = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert workflow["scenario"] is None and workflow["decision"] is None
    assert workflow["decision_stale"] is False
    refused = client.post(f"/analyses/{analysis_id}/workflow/decision/selected",
                          headers=headers, json={})
    assert refused.status_code == 422
    assert refused.json()["detail"] == NOT_RUNNABLE_DETAIL
    after = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert after["decision"] is None and after["decision_stale"] is False
    with make_sessionmaker(db_engine)() as db:              # case 13
        assert db.query(Job).filter(Job.kind == "workflow_decision").count() == 1


def test_a_broken_decision_for_the_selected_scenario_is_stale_until_generated_again(
        client, db_engine):
    """The flag still means what Step 5 made it mean while a scenario IS selected: a stored
    Decision whose chain no longer resolves is stale, and generating again clears it."""
    shop = Shop(client, db_engine)
    dataset_id, first_id, jobs = _ready(shop)
    assert client.delete(f"/scenarios/{first_id}", headers=shop.headers).status_code == 200
    second_id = shop.seed_scenario_at_freed_id(first_id, dataset_id, 99, name="Replacement")
    assert second_id == first_id, "the replacement holds the freed id"
    # SYNTHETIC (direct row edit): the old chain predates the replacement, as it would after a
    # real clock tick, so the chronology guard can tell the generations apart.
    shop.backdate_jobs()
    assert shop.select(second_id).status_code == 200
    workflow = shop.workflow()
    assert workflow["scenario"]["id"] == second_id
    assert {name: workflow[name] for name in ("des", "mc", "validation", "decision")} \
        == {"des": None, "mc": None, "validation": None, "decision": None}
    assert workflow["decision_stale"] is True
    generated = shop.decide().json()
    assert generated["persisted"] is True
    assert generated["decision"]["status"] == "insufficient_evidence"
    assert generated["decision"]["evidence_ids"]["des"] is None
    after = shop.workflow()
    assert after["decision_stale"] is False
    assert after["decision"]["id"] == generated["evidence"]["id"]
    assert after["decision"]["result"]["status"] == "insufficient_evidence"
    with shop.session_factory() as db:                       # case 13
        assert db.get(Job, jobs["des"]) is not None
