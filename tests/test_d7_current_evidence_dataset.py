"""D7: Current-mode evidence must belong to the current valid dataset and its real dependencies.

Before this step `_current_evidence` gated `des_current`, `mc_current` and `validation_current`
on the recorded setup hash alone, so a job produced from a replaced dataset stayed visible as
current evidence (probe: tests/test_dataset_staleness_probe.py). A matching Setup is not proof of
a matching dataset.

Every test asserts a literal expectation fixed when the test data was built (for example "the
dataset-A DES job id"); no expectation is recomputed from the rule under test.

Data labels:

- SYNTHETIC: users, analyses, datasets and runs made here through the real endpoints. Distinct
  arrival counts fingerprint which dataset produced a result (dataset A: 2 north arrivals/hour,
  dataset B: 6).
- SYNTHETIC (direct row edit): a stored job or dataset row edited in place to reach a state no
  endpoint produces - an unrecorded `dataset_id`, a stale dependency, an invalid report. Each such
  edit is marked at its call site.

Historical rows are never deleted by these tests; several assert the row is still stored.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm.attributes import flag_modified

from backend.db.models import Dataset, Job
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

MC_PAYLOAD = {"num_trials": 50, "failure_threshold": 0.8, "failure_rate_cap": 0.5, "seed": 7}
DES_PAYLOAD = {"sim_hours": 1, "max_events": 100}


def _setup(queue_ids: list[str], server_count: int = 1) -> dict[str, Any]:
    return {
        "queue_structure": "separate_queues",
        "fixed_server_count": server_count,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [
            {"id": "s1", "start_time": "07:00:00", "end_time": "08:00:00", "active_queue_ids": None}
        ],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": queue_ids,
    }


def _events(north_count: int, south_count: int = 1) -> bytes:
    lines = ["arrival_time,service_start,service_end,queue_id"]
    for index in range(north_count):
        minute = 5 + index
        lines.append(
            f"2026-09-08T07:{minute:02d}:00Z,2026-09-08T07:{minute:02d}:30Z,"
            f"2026-09-08T07:{minute + 5:02d}:00Z,north"
        )
    for index in range(south_count):
        minute = 10 + index
        lines.append(
            f"2026-09-08T07:{minute:02d}:00Z,2026-09-08T07:{minute:02d}:30Z,"
            f"2026-09-08T07:{minute + 5:02d}:00Z,south"
        )
    return ("\n".join(lines) + "\n").encode()


class Workspace:
    """One signed-in owner with one separate-queue analysis."""

    def __init__(self, client, db_engine, email: str = "d7@example.com"):
        self.client = client
        self.session_factory = make_sessionmaker(db_engine)
        self.user_id = create_user(db_engine, email, "pw").id
        assert login(client, email, "pw") == 200
        self.analysis_id = client.post(
            "/analyses", headers=self.headers, json={"name": "Lanes", "queue_setup": _setup(["north", "south"])}
        ).json()["analysis"]["id"]

    @property
    def headers(self) -> dict[str, str]:
        return csrf_header(self.client)

    def upload(self, north_count: int, name: str) -> int:
        response = self.client.post(
            f"/analyses/{self.analysis_id}/datasets", headers=self.headers,
            files={"file": (name, _events(north_count), "text/csv")},
        )
        assert response.status_code == 201, response.text
        return response.json()["dataset"]["id"]

    def run(self, kind: str, payload: dict[str, Any] | None = None) -> int:
        """Run one Current-mode job through its real endpoint and return its job id."""
        response = self.client.post(
            f"/analyses/{self.analysis_id}/workflow/simulation/{kind}/current",
            headers=self.headers, json=payload if payload is not None else {},
        )
        assert response.status_code == 200, response.text
        return response.json()["evidence"]["id"]

    def run_all(self) -> dict[str, int]:
        return {
            "des": self.run("des", DES_PAYLOAD),
            "mc": self.run("mc", MC_PAYLOAD),
            "validation": self.run("validation"),
        }

    def workflow(self) -> dict[str, Any]:
        response = self.client.get(f"/analyses/{self.analysis_id}/workflow")
        assert response.status_code == 200, response.text
        return response.json()

    def slots(self) -> dict[str, int | None]:
        """The job id in each Current slot of the workflow payload, or None when absent."""
        workflow = self.workflow()
        return {
            name: (workflow[f"{name}_current"] or {}).get("id")
            for name in ("des", "mc", "validation")
        }

    def recorded_dataset_ids(self) -> dict[str, int | None]:
        workflow = self.workflow()
        return {
            name: ((workflow[f"{name}_current"] or {}).get("params") or {}).get("dataset_id")
            for name in ("des", "mc", "validation")
        }

    def stored_job(self, job_id: int) -> Job | None:
        with self.session_factory() as db:
            return db.get(Job, job_id)

    def edit_job_params(self, job_id: int, **changes: Any) -> None:
        """SYNTHETIC (direct row edit): reach a params state no endpoint writes."""
        with self.session_factory() as db:
            job = db.get(Job, job_id)
            assert job is not None
            params = dict(job.params_json or {})
            for key, value in changes.items():
                if value is _REMOVE:
                    params.pop(key, None)
                else:
                    params[key] = value
            job.params_json = params
            # True == 1 in Python, so a dict differing only there compares equal and the flush
            # would skip the UPDATE. Mark the column modified so the edit always reaches the row.
            flag_modified(job, "params_json")
            db.add(job)
            db.commit()

    def delete_dataset(self, dataset_id: int) -> None:
        response = self.client.delete(f"/datasets/{dataset_id}", headers=self.headers)
        assert response.status_code == 200, response.text

    def invalidate_dataset(self, dataset_id: int) -> None:
        """SYNTHETIC (direct row edit): no upload path stores a not-ok report."""
        with self.session_factory() as db:
            dataset = db.get(Dataset, dataset_id)
            assert dataset is not None
            dataset.validation_report_json = {"ok": False, "message": "synthetic"}
            db.add(dataset)
            db.commit()


_REMOVE = object()


@pytest.fixture
def workspace(client, db_engine) -> Workspace:
    return Workspace(client, db_engine)


# ── 1. Dataset A evidence while A is current ────────────────────────────────


def test_1_evidence_is_current_while_its_dataset_is_current(workspace):
    dataset_a = workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    assert workspace.slots() == {"des": jobs["des"], "mc": jobs["mc"], "validation": jobs["validation"]}
    assert workspace.recorded_dataset_ids() == {
        "des": dataset_a, "mc": dataset_a, "validation": dataset_a,
    }
    # Numerical fingerprint: dataset A is 2 north arrivals/hour.
    lambdas = {row["lambda"] for row in workspace.workflow()["des_current"]["result"]["results"]}
    assert lambdas == {2.0, 1.0}


# ── 2./3. Dataset B replaces A with no Setup change ─────────────────────────


def test_2_replacing_the_dataset_without_a_setup_change_drops_current_evidence(workspace):
    dataset_a = workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    setup_hash_before = workspace.workflow()["des_current"]["params"]["setup_hash"]

    dataset_b = workspace.upload(6, "b.csv")
    assert dataset_b != dataset_a

    # The Setup is untouched: only the dataset changed.
    assert workspace.stored_job(jobs["des"]).params_json["setup_hash"] == setup_hash_before
    assert workspace.slots() == {"des": None, "mc": None, "validation": None}
    # The current dataset pointer moved to B (6 north arrivals/hour).
    current = workspace.client.get(f"/analyses/{workspace.analysis_id}/current").json()
    assert current["dataset"]["id"] == dataset_b
    assert {row["lambda"] for row in current["rows"]} == {6.0, 1.0}


def test_3_dataset_a_rows_are_no_longer_served_as_current_after_b(workspace):
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    workspace.upload(6, "b.csv")
    workflow = workspace.workflow()
    # The dataset-A lambda fingerprint is not reachable through any Current slot.
    assert workflow["des_current"] is None
    assert workflow["mc_current"] is None
    assert workflow["validation_current"] is None
    # The rows are still stored, with their dataset-A fingerprint intact.
    stored = workspace.stored_job(jobs["des"])
    assert stored is not None
    assert {row["lambda"] for row in stored.result_json["results"]} == {2.0, 1.0}


# ── 4. Dataset B evidence after recalculation ──────────────────────────────


def test_4_rerunning_on_the_new_dataset_restores_every_slot(workspace):
    workspace.upload(2, "a.csv")
    old = workspace.run_all()
    dataset_b = workspace.upload(6, "b.csv")
    new = workspace.run_all()
    assert new["des"] != old["des"] and new["mc"] != old["mc"] and new["validation"] != old["validation"]
    assert workspace.slots() == {"des": new["des"], "mc": new["mc"], "validation": new["validation"]}
    assert workspace.recorded_dataset_ids() == {
        "des": dataset_b, "mc": dataset_b, "validation": dataset_b,
    }
    # Numerical fingerprint: dataset B is 6 north arrivals/hour.
    lambdas = {row["lambda"] for row in workspace.workflow()["des_current"]["result"]["results"]}
    assert lambdas == {6.0, 1.0}


# ── 5. Missing recorded dataset identity ───────────────────────────────────


@pytest.mark.parametrize("slot", ["des", "mc", "validation"])
def test_5_a_job_without_a_recorded_dataset_is_not_current(workspace, slot):
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    # SYNTHETIC (direct row edit): drop the recorded dataset identity.
    workspace.edit_job_params(jobs[slot], dataset_id=_REMOVE)
    assert workspace.slots()[slot] is None
    # An unrecorded identity is never filled in from the analysis's current dataset.
    assert "dataset_id" not in (workspace.stored_job(jobs[slot]).params_json or {})


@pytest.mark.parametrize("recorded", [None, "7", 7.0, True])
def test_5_a_non_integer_recorded_dataset_is_not_current(workspace, recorded):
    dataset_a = workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    assert workspace.slots()["des"] == jobs["des"]
    # SYNTHETIC (direct row edit): a value that is not the integer dataset id.
    workspace.edit_job_params(jobs["des"], dataset_id=recorded)
    assert workspace.slots()["des"] is None
    # The real dataset is still current; the job simply does not record it.
    current = workspace.client.get(f"/analyses/{workspace.analysis_id}/current").json()
    assert current["dataset"]["id"] == dataset_a


# ── 6. Deleted source dataset ──────────────────────────────────────────────


def test_6_evidence_of_a_deleted_dataset_is_not_current(workspace):
    dataset_a = workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    dataset_b = workspace.upload(6, "b.csv")
    later = workspace.run_all()
    assert workspace.slots()["des"] == later["des"]

    # Deleting B makes A the current dataset again (Step 2 rule: highest valid id).
    workspace.delete_dataset(dataset_b)
    current = workspace.client.get(f"/analyses/{workspace.analysis_id}/current").json()
    assert current["dataset"]["id"] == dataset_a

    # Jobs have no foreign key to datasets, so the dataset-B jobs survive the delete
    # with a dangling recorded dataset id. They must not be served as current.
    assert workspace.stored_job(later["des"]) is not None
    assert workspace.stored_job(later["des"]).params_json["dataset_id"] == dataset_b
    assert workspace.slots() == {"des": None, "mc": None, "validation": None}
    # The dataset-A jobs also survive and still record the dataset that is current again,
    # but they are not the latest of their kind, so no slot is filled from them.
    assert workspace.stored_job(jobs["des"]).params_json["dataset_id"] == dataset_a


def test_6_a_deleted_dataset_is_never_treated_as_current(workspace):
    dataset_a = workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    assert workspace.slots()["des"] == jobs["des"]
    workspace.delete_dataset(dataset_a)
    # The analysis now has no dataset at all; nothing may be current.
    assert workspace.client.get(f"/analyses/{workspace.analysis_id}/current").status_code == 404
    assert workspace.slots() == {"des": None, "mc": None, "validation": None}
    assert workspace.stored_job(jobs["des"]) is not None


def test_6_deleting_a_non_current_dataset_changes_neither_current_nor_evidence(workspace):
    dataset_a = workspace.upload(2, "a.csv")
    workspace.run_all()
    dataset_b = workspace.upload(6, "b.csv")
    later = workspace.run_all()
    before = workspace.workflow()
    assert workspace.slots() == later

    # B has the higher id, so A was never current: deleting it moves nothing.
    workspace.delete_dataset(dataset_a)
    current = workspace.client.get(f"/analyses/{workspace.analysis_id}/current").json()
    assert current["dataset"]["id"] == dataset_b
    assert workspace.workflow() == before


# ── 7. No valid current dataset ────────────────────────────────────────────


def test_7_no_valid_current_dataset_leaves_nothing_current(workspace):
    dataset_a = workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    assert workspace.slots()["des"] == jobs["des"]
    # SYNTHETIC (direct row edit): the row still exists, its report is no longer ok.
    workspace.invalidate_dataset(dataset_a)
    assert workspace.client.get(f"/analyses/{workspace.analysis_id}/current").status_code == 404
    assert workspace.slots() == {"des": None, "mc": None, "validation": None}
    # The job still records the existing dataset; it is the dataset that stopped being valid.
    assert workspace.stored_job(jobs["des"]).params_json["dataset_id"] == dataset_a


# ── 8. Changed Setup with an unchanged dataset (existing behavior) ─────────


def test_8_setup_change_alone_still_drops_current_evidence(workspace):
    dataset_a = workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    assert workspace.slots()["des"] == jobs["des"]
    updated = workspace.client.patch(
        f"/analyses/{workspace.analysis_id}", headers=workspace.headers,
        json={"queue_setup": _setup(["north", "south"], server_count=3)},
    )
    assert updated.status_code == 200, updated.text
    # The dataset did not change; the Setup did.
    current = workspace.client.get(f"/analyses/{workspace.analysis_id}/current").json()
    assert current["dataset"]["id"] == dataset_a
    assert workspace.slots() == {"des": None, "mc": None, "validation": None}


# ── 9./10. Current DES and Current MC dependency handling ─────────────────


@pytest.mark.parametrize("slot", ["des", "mc"])
def test_9_and_10_des_and_mc_depend_only_on_their_recorded_dataset(workspace, slot):
    dataset_a = workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    stored = workspace.stored_job(jobs[slot]).params_json
    # These kinds record no job link: the dataset is their only dependency.
    assert stored["dataset_id"] == dataset_a
    assert "mc_job_id" not in stored
    assert stored["analysis_id"] == workspace.analysis_id
    assert workspace.slots()[slot] == jobs[slot]
    # SYNTHETIC (direct row edit): point the job at a dataset id that does not exist.
    workspace.edit_job_params(jobs[slot], dataset_id=dataset_a + 9000)
    assert workspace.slots()[slot] is None


# ── 11. Current validation dependency handling ────────────────────────────


def test_11_validation_records_and_requires_its_mc_job(workspace):
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    params = workspace.stored_job(jobs["validation"]).params_json
    assert params["mc_job_id"] == jobs["mc"]
    assert workspace.slots()["validation"] == jobs["validation"]


def test_11_validation_is_not_current_when_its_recorded_mc_is_stale(workspace):
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    # SYNTHETIC (direct row edit): the referenced MC job alone records a different Setup.
    # The validation job's own dataset and Setup stay current, so only the chain can fail it.
    workspace.edit_job_params(jobs["mc"], setup_hash="synthetic-other-setup")
    slots = workspace.slots()
    assert slots["mc"] is None
    assert slots["validation"] is None
    # Its own recorded identity was never altered.
    validation_params = workspace.stored_job(jobs["validation"]).params_json
    assert validation_params["mc_job_id"] == jobs["mc"]


def test_11_validation_is_not_current_when_its_recorded_mc_is_gone(workspace):
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    # SYNTHETIC (direct row edit): a dangling job link, as a deleted MC row would leave.
    workspace.edit_job_params(jobs["validation"], mc_job_id=jobs["mc"] + 9000)
    assert workspace.slots()["validation"] is None
    assert workspace.slots()["mc"] == jobs["mc"]


def test_11_validation_without_a_recorded_mc_link_is_not_current(workspace):
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    # SYNTHETIC (direct row edit): the link is absent, not merely unresolvable.
    workspace.edit_job_params(jobs["validation"], mc_job_id=_REMOVE)
    assert workspace.slots()["validation"] is None


# ── 12. Owner and analysis isolation ─────────────────────────────────────


def test_12_another_analysis_evidence_is_never_served_here(client, db_engine):
    first = Workspace(client, db_engine, "owner@example.com")
    dataset_a = first.upload(2, "a.csv")
    first_jobs = first.run_all()

    second_id = client.post(
        "/analyses", headers=first.headers,
        json={"name": "Other", "queue_setup": _setup(["north", "south"])},
    ).json()["analysis"]["id"]
    second = Workspace.__new__(Workspace)
    second.client, second.session_factory, second.user_id = first.client, first.session_factory, first.user_id
    second.analysis_id = second_id
    dataset_c = second.upload(4, "c.csv")
    assert dataset_c != dataset_a

    # Each analysis serves only its own evidence; the second has no runs yet.
    assert first.slots() == {"des": first_jobs["des"], "mc": first_jobs["mc"], "validation": first_jobs["validation"]}
    assert second.slots() == {"des": None, "mc": None, "validation": None}

    # SYNTHETIC (direct row edit): re-point a stored job at the other analysis.
    first.edit_job_params(first_jobs["des"], analysis_id=second_id)
    assert first.slots()["des"] is None
    # It is not adopted by the other analysis either: its dataset is the first analysis's.
    assert second.slots()["des"] is None


def test_12_another_owners_evidence_is_never_served(client, db_engine):
    owner = Workspace(client, db_engine, "owner@example.com")
    owner.upload(2, "a.csv")
    owner_jobs = owner.run_all()
    assert owner.slots()["des"] == owner_jobs["des"]

    stranger_id = create_user(db_engine, "stranger@example.com", "pw").id
    assert stranger_id != owner.user_id
    # SYNTHETIC (direct row edit): transfer the row to another user.
    with owner.session_factory() as db:
        job = db.get(Job, owner_jobs["des"])
        job.user_id = stranger_id
        db.add(job)
        db.commit()
    assert owner.slots()["des"] is None


# ── 13. Historical jobs remain stored ────────────────────────────────────


def test_13_superseded_jobs_stay_stored_with_their_values(workspace):
    workspace.upload(2, "a.csv")
    old = workspace.run_all()
    workspace.upload(6, "b.csv")
    new = workspace.run_all()
    for name in ("des", "mc", "validation"):
        stored = workspace.stored_job(old[name])
        assert stored is not None, name
        assert stored.status == "completed"
        assert stored.result_json is not None
    # The old DES keeps its dataset-A numbers; nothing was recomputed in place.
    assert {row["lambda"] for row in workspace.stored_job(old["des"]).result_json["results"]} == {2.0, 1.0}
    # And the new ones carry dataset B's.
    assert {row["lambda"] for row in workspace.stored_job(new["des"]).result_json["results"]} == {6.0, 1.0}


def test_13_every_job_of_a_replaced_dataset_is_still_in_the_database(workspace):
    workspace.upload(2, "a.csv")
    old = workspace.run_all()
    workspace.upload(6, "b.csv")
    assert workspace.slots() == {"des": None, "mc": None, "validation": None}
    with workspace.session_factory() as db:
        kinds = {
            db.get(Job, job_id).kind
            for job_id in old.values()
        }
    assert kinds == {"workflow_des_current", "workflow_mc_current", "workflow_validation_current"}


# ── 14. No fallback that promotes incompatible evidence ──────────────────


def test_14_an_older_matching_job_is_not_promoted_when_the_latest_is_stale(workspace):
    dataset_a = workspace.upload(2, "a.csv")
    on_a = workspace.run_all()
    dataset_b = workspace.upload(6, "b.csv")
    on_b = workspace.run_all()
    # Deleting B makes A current again. The latest job of each kind is the dataset-B one.
    workspace.delete_dataset(dataset_b)
    assert workspace.client.get(f"/analyses/{workspace.analysis_id}/current").json()["dataset"]["id"] == dataset_a
    # The dataset-A jobs match the current dataset, but they are not the latest of their kind
    # and are not resurrected: the slot stays empty until the user reruns.
    assert workspace.slots() == {"des": None, "mc": None, "validation": None}
    for job_id in (*on_a.values(), *on_b.values()):
        assert workspace.stored_job(job_id) is not None


def test_14_a_stale_job_is_never_promoted_by_a_matching_setup_alone(workspace):
    workspace.upload(2, "a.csv")
    jobs = workspace.run_all()
    setup_hash = workspace.stored_job(jobs["des"]).params_json["setup_hash"]
    workspace.upload(6, "b.csv")
    # The Setup still matches exactly; only the dataset moved on.
    for name in ("des", "mc", "validation"):
        assert workspace.stored_job(jobs[name]).params_json["setup_hash"] == setup_hash
    assert workspace.slots() == {"des": None, "mc": None, "validation": None}
