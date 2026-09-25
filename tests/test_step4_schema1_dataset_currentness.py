"""Step 4: a schema-1 saved scenario is current evidence only for the current dataset.

`_own_verified_scenario` checks that a scenario's dataset exists, is the owner's, belongs to the
analysis and has an ok validation report. For a schema-2 separate plan it also checks that the
dataset is the *current* one (`workflow.py:321-325`). The schema-1 path never did, so a scenario
calculated against dataset A kept qualifying as the selected current scenario after dataset B
replaced it, and every downstream consumer -- scenario-bound DES, Monte Carlo, validation,
Decision and the selected-plan report -- inherited that answer through the same helper.

A saved scenario remains evidence of the dataset it was calculated on. Uploading a replacement
must not silently change what it represents.

Data labels:

- SYNTHETIC: users, analyses, datasets and scenarios made here. Aggregate rows carry distinct
  arrival rates so a result can be traced to its dataset (A: lambda 4, B: lambda 14).
- SYNTHETIC (direct row insert/edit): schema-1 scenarios are inserted directly, as the repository's
  existing workflow fixtures do, because no endpoint stores a verified snapshot with an arbitrary
  engine string; and a dataset is invalidated in place because no upload path stores a not-ok
  report. Each such step is marked at its call site.
- RECORDED: scenario 12's id, owner, analysis, dataset link, creation time and calculation
  snapshot, and datasets 7 and 8 of analysis 2, copied from
  tests/fixtures/evidence_status_local_reference_2026-09-25.json. Its `results_json` is NOT
  recorded in that export and is supplied synthetically, which is stated where it is used.

Historical rows are never deleted here; several tests assert they are still stored.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm.attributes import flag_modified

from backend.db.models import AnalysisProject, Dataset, Job, Scenario, User
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

VERIFIED_SCENARIO_DETAIL = "Select a verified Scenario from this Analysis."
DATASET_UNAVAILABLE_DETAIL = "Scenario source Dataset is unavailable."
SETUP_QUEUE_DETAIL = "Scenario is not verifiable for the current Setup queue structure."
INCOMPLETE_DETAIL = "Scenario comparison evidence is incomplete."
NO_RESULTS_DETAIL = "Scenario has no optimization results."
STALE_DATASET_DETAIL = "Scenario is stale for the current dataset."
NO_SELECTION_DETAIL = "Select a Scenario in Compare first."


def shared_setup(server_count: int = 2) -> dict[str, Any]:
    return {
        "queue_structure": "shared_queue", "fixed_server_count": server_count,
        "staffing_varies_by_period": False, "capacity_mode": "unlimited",
        "total_system_capacity": None, "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None, "segments": [], "queue_ids": [],
    }


def separate_setup() -> dict[str, Any]:
    return {
        "queue_structure": "separate_queues", "fixed_server_count": 1,
        "staffing_varies_by_period": False, "capacity_mode": "unlimited",
        "total_system_capacity": None, "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [{"id": "s1", "start_time": "07:00:00", "end_time": "08:00:00",
                      "active_queue_ids": None}],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": ["north", "south"],
    }


def schema1_snapshot(lam: float, engine: str = "novaq-test") -> dict[str, Any]:
    """A schema-1 calculation snapshot: no schema_version 2, and no setup fingerprint."""
    return {"engine_version": engine,
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

    def __init__(self, client, db_engine, email: str = "s4@example.com"):
        self.client = client
        self.session_factory = make_sessionmaker(db_engine)
        self.user_id = create_user(db_engine, email, "pw").id
        assert login(client, email, "pw") == 200
        self.analysis_id = client.post(
            "/analyses", headers=self.headers, json={"name": "Shop", "queue_setup": shared_setup()},
        ).json()["analysis"]["id"]

    @property
    def headers(self) -> dict[str, str]:
        return csrf_header(self.client)

    def upload(self, lam: float, name: str) -> int:
        payload = f"time,lambda,mu,c\n08:00-09:00,{lam},12,2\n".encode()
        response = self.client.post(
            f"/analyses/{self.analysis_id}/datasets", headers=self.headers,
            files={"file": (name, payload, "text/csv")},
        )
        assert response.status_code == 201, response.text
        return response.json()["dataset"]["id"]

    def seed_scenario(self, dataset_id: int, lam: float, *, analysis_id: int | None = None,
                      owner_id: int | None = None, calculation: dict | None = None,
                      results: dict | None = None, name: str = "Plan A") -> int:
        """SYNTHETIC (direct row insert): a verified schema-1 snapshot pinned to a dataset."""
        with self.session_factory() as db:
            scenario = Scenario(
                user_id=owner_id if owner_id is not None else self.user_id,
                analysis_id=analysis_id if analysis_id is not None else self.analysis_id,
                dataset_id=dataset_id, name=name,
                settings_json={"calculation": calculation if calculation is not None
                               else schema1_snapshot(lam)},
                results_json=results if results is not None else shared_results(lam),
            )
            db.add(scenario)
            db.commit()
            return scenario.id

    def select(self, scenario_id: int):
        return self.client.post(
            f"/analyses/{self.analysis_id}/workflow/selection", headers=self.headers,
            json={"scenario_id": scenario_id},
        )

    def workflow(self) -> dict[str, Any]:
        response = self.client.get(f"/analyses/{self.analysis_id}/workflow")
        assert response.status_code == 200, response.text
        return response.json()

    def run(self, kind: str, payload: dict[str, Any] | None = None):
        return self.client.post(
            f"/analyses/{self.analysis_id}/workflow/simulation/{kind}", headers=self.headers,
            json=payload if payload is not None else {},
        )

    def decide(self):
        return self.client.post(f"/analyses/{self.analysis_id}/workflow/decision", headers=self.headers)

    def patch_setup(self, setup: dict[str, Any]):
        return self.client.patch(
            f"/analyses/{self.analysis_id}", headers=self.headers, json={"queue_setup": setup},
        )

    def stored_scenario(self, scenario_id: int) -> Scenario | None:
        with self.session_factory() as db:
            return db.get(Scenario, scenario_id)

    def invalidate_dataset(self, dataset_id: int) -> None:
        """SYNTHETIC (direct row edit): no upload path stores a not-ok report."""
        with self.session_factory() as db:
            dataset = db.get(Dataset, dataset_id)
            assert dataset is not None
            dataset.validation_report_json = {"ok": False, "message": "synthetic"}
            flag_modified(dataset, "validation_report_json")
            db.add(dataset)
            db.commit()


@pytest.fixture
def shop(client, db_engine) -> Shop:
    return Shop(client, db_engine)


# ── 1. Schema-1 scenario on the current dataset ────────────────────────────


def test_1_scenario_on_the_current_dataset_is_selectable(shop):
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario).status_code == 200
    workflow = shop.workflow()
    assert workflow["scenario"]["id"] == scenario
    assert workflow["scenario"]["dataset_id"] == dataset_a
    # Numerical fingerprint: dataset A is lambda 4.
    assert workflow["scenario"]["settings"]["calculation"]["input_segments"][0]["lambda"] == 4


# ── 2./3. Dataset replacement with an unchanged setup ─────────────────────


def test_2_replacement_with_unchanged_setup_ends_eligibility(shop):
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario).status_code == 200
    setup_before = shop.client.get(f"/analyses/{shop.analysis_id}").json()["analysis"]["queue_setup"]

    dataset_b = shop.upload(14, "b.csv")
    assert dataset_b != dataset_a
    # The Setup is untouched: only the dataset changed.
    assert shop.client.get(f"/analyses/{shop.analysis_id}").json()["analysis"]["queue_setup"] == setup_before
    # The already-recorded selection no longer yields a current scenario.
    assert shop.workflow()["scenario"] is None
    # And it cannot be selected again.
    refused = shop.select(scenario)
    assert refused.status_code == 422
    assert refused.json()["detail"] == STALE_DATASET_DETAIL


def test_3_scenario_on_a_superseded_dataset_is_never_current(shop):
    dataset_a = shop.upload(4, "a.csv")
    older = shop.seed_scenario(dataset_a, 4, name="On A")
    dataset_b = shop.upload(14, "b.csv")
    newer = shop.seed_scenario(dataset_b, 14, name="On B")
    # The dataset-B scenario is current; the dataset-A one is not.
    assert shop.select(newer).status_code == 200
    assert shop.workflow()["scenario"]["id"] == newer
    refused = shop.select(older)
    assert refused.status_code == 422
    assert refused.json()["detail"] == STALE_DATASET_DETAIL
    # The refused selection did not replace the recorded one.
    assert shop.workflow()["scenario"]["id"] == newer


# ── 4. No valid current dataset ──────────────────────────────────────────


def test_4_no_valid_current_dataset_reports_the_dependency_not_staleness(shop):
    """A missing dependency outranks dataset staleness and is not concealed by it."""
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario).status_code == 200
    # SYNTHETIC (direct row edit): the only dataset stops being valid.
    shop.invalidate_dataset(dataset_a)
    assert shop.client.get(f"/analyses/{shop.analysis_id}/current").status_code == 404
    refused = shop.select(scenario)
    assert refused.status_code == 422
    # The scenario's own source dataset is unusable; that is the reason reported.
    assert refused.json()["detail"] == DATASET_UNAVAILABLE_DETAIL
    assert shop.workflow()["scenario"] is None


# ── 5. Missing source dataset ────────────────────────────────────────────


def test_5_deleting_the_source_dataset_removes_the_scenario_with_it(shop):
    """Verified existing behavior: Dataset.scenarios cascades, so the scenario cannot outlive it."""
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario).status_code == 200
    assert shop.client.delete(f"/datasets/{dataset_a}", headers=shop.headers).status_code == 200
    assert shop.stored_scenario(scenario) is None
    refused = shop.select(scenario)
    assert refused.status_code == 422
    assert refused.json()["detail"] == VERIFIED_SCENARIO_DETAIL
    assert shop.workflow()["scenario"] is None


# ── 6. Another owner or analysis ─────────────────────────────────────────


def test_6_a_scenario_of_another_analysis_is_not_selectable(shop):
    dataset_a = shop.upload(4, "a.csv")
    other_id = shop.client.post(
        "/analyses", headers=shop.headers, json={"name": "Other", "queue_setup": shared_setup()},
    ).json()["analysis"]["id"]
    foreign = shop.seed_scenario(dataset_a, 4, analysis_id=other_id, name="Elsewhere")
    refused = shop.select(foreign)
    assert refused.status_code == 422
    assert refused.json()["detail"] == VERIFIED_SCENARIO_DETAIL


def test_6_a_scenario_of_another_owner_is_not_selectable(shop, db_engine):
    dataset_a = shop.upload(4, "a.csv")
    stranger = create_user(db_engine, "stranger@example.com", "pw").id
    assert stranger != shop.user_id
    foreign = shop.seed_scenario(dataset_a, 4, owner_id=stranger, name="Theirs")
    refused = shop.select(foreign)
    assert refused.status_code == 422
    assert refused.json()["detail"] == VERIFIED_SCENARIO_DETAIL


# ── 7. Existing setup checks still apply and are not concealed ───────────


def test_7_setup_change_alone_still_reports_the_setup_reason(shop):
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario).status_code == 200
    assert shop.patch_setup(separate_setup()).status_code == 200
    # The dataset did not change; the queue structure did.
    assert shop.client.get(f"/analyses/{shop.analysis_id}/current").json()["dataset"]["id"] == dataset_a
    refused = shop.select(scenario)
    assert refused.status_code == 422
    assert refused.json()["detail"] == SETUP_QUEUE_DETAIL


def test_7_a_stale_dataset_does_not_conceal_a_stale_setup(shop):
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    shop.upload(14, "b.csv")
    assert shop.patch_setup(separate_setup()).status_code == 200
    refused = shop.select(scenario)
    assert refused.status_code == 422
    # Both are wrong; the setup incompatibility is still the reported reason.
    assert refused.json()["detail"] == SETUP_QUEUE_DETAIL


def test_7_absent_results_are_still_reported(shop):
    dataset_a = shop.upload(4, "a.csv")
    # SYNTHETIC (direct row insert): a verified snapshot with no comparison rows at all.
    scenario = shop.seed_scenario(dataset_a, 4, results={"results": []})
    refused = shop.select(scenario)
    assert refused.status_code == 422
    assert refused.json()["detail"] == NO_RESULTS_DETAIL


def test_7_incomplete_rows_are_still_reported(shop):
    dataset_a = shop.upload(4, "a.csv")
    # SYNTHETIC (direct row insert): rows exist but are not operationally complete.
    incomplete = shared_results(4)
    incomplete["results"][0]["c_optimal"] = 0
    scenario = shop.seed_scenario(dataset_a, 4, results=incomplete)
    refused = shop.select(scenario)
    assert refused.status_code == 422
    assert refused.json()["detail"] == INCOMPLETE_DETAIL


def test_7_a_stale_dataset_does_not_conceal_incomplete_evidence(shop):
    dataset_a = shop.upload(4, "a.csv")
    incomplete = shared_results(4)
    incomplete["results"][0]["c_optimal"] = 0
    scenario = shop.seed_scenario(dataset_a, 4, results=incomplete)
    shop.upload(14, "b.csv")
    refused = shop.select(scenario)
    assert refused.status_code == 422
    # Both are wrong; the completeness defect is still the reported reason.
    assert refused.json()["detail"] == INCOMPLETE_DETAIL


# ── 8. Selected-scenario behavior ────────────────────────────────────────


def test_8_the_recorded_selection_row_is_kept_but_yields_no_scenario(shop):
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    selection_id = shop.select(scenario).json()["selection"]["id"]
    shop.upload(14, "b.csv")
    workflow = shop.workflow()
    # The selection job is still reported; the scenario it points at is not current.
    assert workflow["selection"]["id"] == selection_id
    assert workflow["selection"]["params"]["scenario_id"] == scenario
    assert workflow["scenario"] is None
    # No other scenario is silently selected in its place.
    with shop.session_factory() as db:
        assert db.get(Job, selection_id) is not None


# ── 9./10. Scenario-bound DES, Monte Carlo and validation ───────────────


@pytest.mark.parametrize("kind,payload", [
    ("des", {"sim_hours": 1, "max_events": 50}),
    ("mc", {"num_trials": 50, "failure_threshold": 0.8, "failure_rate_cap": 0.5, "seed": 7}),
    ("validation", {}),
])
def test_9_and_10_scenario_bound_runs_are_refused_after_replacement(shop, kind, payload):
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario).status_code == 200
    assert shop.run(kind, payload).status_code == 200, kind
    shop.upload(14, "b.csv")
    refused = shop.run(kind, payload)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == NO_SELECTION_DETAIL


def test_10_earlier_scenario_bound_evidence_is_no_longer_served(shop):
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario).status_code == 200
    des_id = shop.run("des", {"sim_hours": 1, "max_events": 50}).json()["evidence"]["id"]
    assert shop.workflow()["des"]["id"] == des_id
    shop.upload(14, "b.csv")
    workflow = shop.workflow()
    assert workflow["des"] is None
    assert workflow["mc"] is None
    assert workflow["validation"] is None
    # The job row survives untouched.
    with shop.session_factory() as db:
        stored = db.get(Job, des_id)
        assert stored is not None and stored.params_json["scenario_id"] == scenario


# ── 11. Decision eligibility ────────────────────────────────────────────


def test_11_decision_is_insufficient_after_replacement(shop):
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario).status_code == 200
    shop.run("des", {"sim_hours": 1, "max_events": 50})
    shop.run("validation", {})
    shop.upload(14, "b.csv")
    decision = shop.decide()
    assert decision.status_code == 200, decision.text
    assert decision.json()["decision"]["status"] == "insufficient_evidence"
    assert shop.workflow()["decision"] is None


# ── 12. Report eligibility ──────────────────────────────────────────────


def test_12_the_id_scoped_historical_report_still_works(shop):
    """An explicitly id-scoped export stays available: it never claims to be current evidence."""
    dataset_a = shop.upload(4, "a.csv")
    shop.seed_scenario(dataset_a, 4)
    shop.upload(14, "b.csv")
    report = shop.client.get(f"/reports/datasets/{dataset_a}/pdf")
    assert report.status_code == 200
    assert report.content[:4] == b"%PDF"


# ── 13. Historical records remain unchanged ─────────────────────────────


def test_13_the_scenario_row_is_unchanged_after_replacement(shop):
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    before = shop.stored_scenario(scenario)
    recorded = (before.dataset_id, before.name, json.dumps(before.results_json, sort_keys=True),
                json.dumps(before.settings_json, sort_keys=True))
    shop.upload(14, "b.csv")
    assert shop.workflow()["scenario"] is None
    after = shop.stored_scenario(scenario)
    assert after is not None
    assert (after.dataset_id, after.name, json.dumps(after.results_json, sort_keys=True),
            json.dumps(after.settings_json, sort_keys=True)) == recorded
    # Nothing was recomputed: the stored rows still carry dataset A's lambda.
    assert after.results_json["results"][0]["lambda_"] == 4.0


# ── 14. Existing schema-2 separate-plan behavior ────────────────────────


def test_14_schema_2_keeps_its_own_reason_and_branch(shop):
    """The schema-2 branch is reached first and reports its own message, unchanged."""
    dataset_a = shop.upload(4, "a.csv")
    # SYNTHETIC (direct row insert): a schema-2 snapshot whose schedule is absent.
    scenario = shop.seed_scenario(
        dataset_a, 4, calculation={"schema_version": 2, "engine_version": "novaq-test",
                                   "input_segments": []}, results={"results": []},
    )
    refused = shop.select(scenario)
    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert detail.startswith("Separate plan is not selectable:"), detail
    # It is not the schema-1 message.
    assert detail not in (STALE_DATASET_DETAIL, SETUP_QUEUE_DETAIL, INCOMPLETE_DETAIL)


# ── 15. Existing D7 Current-mode behavior ──────────────────────────────


def test_15_current_mode_evidence_is_unaffected_by_scenario_eligibility(shop):
    """Current-mode slots never depended on a scenario, and still do not."""
    dataset_a = shop.upload(4, "a.csv")
    scenario = shop.seed_scenario(dataset_a, 4)
    assert shop.select(scenario).status_code == 200
    des_current = shop.client.post(
        f"/analyses/{shop.analysis_id}/workflow/simulation/des/current", headers=shop.headers,
        json={"sim_hours": 1, "max_events": 50},
    )
    assert des_current.status_code == 200, des_current.text
    assert shop.workflow()["des_current"]["id"] == des_current.json()["evidence"]["id"]
    # Replacing the dataset ends both: D7 for the Current slot, Step 4 for the scenario.
    shop.upload(14, "b.csv")
    workflow = shop.workflow()
    assert workflow["des_current"] is None
    assert workflow["scenario"] is None


# ── RECORDED reference case: scenario 12 ───────────────────────────────

FIXTURE = Path(__file__).parent / "fixtures" / "evidence_status_local_reference_2026-09-25.json"


def test_recorded_scenario_12_records_a_superseded_dataset(shop):
    """RECORDED: scenario 12's dataset link versus analysis 2's datasets, from the local export.

    Pure read of the export, no database writes: it fixes the *input* to the rule.
    """
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenario_12 = next(item for item in data["scenarios"] if item["id"] == 12)
    assert scenario_12["analysis_id"] == 2 and scenario_12["dataset_id"] == 7
    calculation = (scenario_12["settings"] or {})["calculation"]
    # RECORDED: schema 1, and no setup fingerprint of any kind.
    assert calculation["schema_version"] == 1
    assert "setup_hash" not in calculation
    owner = next(item for item in data["analyses"] if item["id"] == 2)["user_id"]
    valid = [item["id"] for item in data["datasets"]
             if item["analysis_id"] == 2 and item["user_id"] == owner and item["validation_ok"]]
    assert sorted(valid) == [7, 8]
    # The Step 2 rule (highest valid id) makes 8 current, so scenario 12 records a superseded one.
    assert max(valid) == 8 != scenario_12["dataset_id"]


def test_recorded_scenario_12_is_refused_while_scenario_13_shape_is_accepted(client, db_engine):
    """RECORDED ids/owner/analysis/dataset links and scenario 12's snapshot, replayed locally.

    NOT RECORDED and supplied synthetically: user email and password, dataset names and normalized
    rows, and scenario 12's `results_json` (the export carries no results). A scenario shaped like
    the spec's "scenario 13" (same snapshot, dataset 8) is added synthetically to show that the
    dataset link is what separates the two.
    """
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenario_12 = next(item for item in data["scenarios"] if item["id"] == 12)
    owner_id = next(item for item in data["analyses"] if item["id"] == 2)["user_id"]
    recorded_analysis = next(item for item in data["analyses"] if item["id"] == 2)

    # Recreate the recorded owner, analysis 2 and datasets 7 and 8 at their recorded ids.
    for index in range(1, owner_id + 1):
        user = create_user(db_engine, f"recorded-{index}@example.com", "pw")
        if user.id == owner_id:
            email = f"recorded-{index}@example.com"
    assert login(client, email, "pw") == 200
    session_factory = make_sessionmaker(db_engine)
    with session_factory() as db:
        db.add(AnalysisProject(id=2, user_id=owner_id, name="recorded 2",
                               queue_setup_json=recorded_analysis["queue_setup_json"]))
        db.commit()
        for item in (entry for entry in data["datasets"] if entry["analysis_id"] == 2):
            assert item["validation_ok"] is True
            db.add(Dataset(id=item["id"], user_id=item["user_id"], analysis_id=2,
                           name=f"recorded {item['id']}", source_filename="recorded.csv",
                           source_format="csv", row_count=0, normalized_json=[],
                           validation_report_json={"ok": True}))
        db.commit()
        # RECORDED snapshot, SYNTHETIC results.
        db.add(Scenario(id=12, user_id=owner_id, analysis_id=2, dataset_id=7, name="recorded 12",
                        settings_json=scenario_12["settings"], results_json=shared_results(4)))
        db.add(Scenario(id=13, user_id=owner_id, analysis_id=2, dataset_id=8, name="synthetic 13",
                        settings_json=scenario_12["settings"], results_json=shared_results(4)))
        db.commit()
        assert db.get(User, owner_id) is not None
        recorded_created = db.get(Scenario, 12).created_at
        assert isinstance(recorded_created, datetime)

    def select(scenario_id: int):
        return client.post("/analyses/2/workflow/selection", headers=csrf_header(client),
                           json={"scenario_id": scenario_id})

    refused = select(12)
    assert refused.status_code == 422
    assert refused.json()["detail"] == STALE_DATASET_DETAIL
    # The same snapshot on the current dataset passes the dataset check.
    assert select(13).status_code == 200, select(13).text
    # Scenario 12's row is untouched by the refusal.
    with session_factory() as db:
        kept = db.get(Scenario, 12)
        assert kept is not None and kept.dataset_id == 7
        assert kept.settings_json == scenario_12["settings"]
