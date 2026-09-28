"""G2 creation stamping (gate G-T1): every created dataset and scenario carries its own token, and a
scenario save records the token of the dataset row it verified.

Spec: docs/superpowers/specs/2026-09-26-generation-identity-contract.md §7 and §14 (G2). Decisions of
2026-09-28: ``generation`` is reported on scenario and dataset outputs, ``dataset_generation`` stays
internal, and a save that verified no calculation snapshot leaves ``dataset_generation`` NULL.

Runs on SQLite, and on PostgreSQL when NOVAQ_TEST_DATABASE_URL names a dedicated *_test database.
"""

from __future__ import annotations

import copy
import re

from backend.db.models import Dataset, Scenario
from tests.helpers import create_user, csrf_header, login, make_sessionmaker
from tests.test_optimize_separate_save import _run, _save, _snapshot, _workspace
from tests.test_scenario_integrity import snapshot_payload
from tests.test_setup_derivation import novamart_workbook

TOKEN = re.compile(r"^[0-9a-f]{32}$")
AGGREGATE = b"time,lambda,mu,c\nt,5,10,2\n"
SHARED_SETUP = {
    "queue_structure": "shared_queue", "fixed_server_count": 2, "staffing_varies_by_period": False,
    "capacity_mode": "unlimited", "total_system_capacity": None, "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None, "segments": [], "queue_ids": [],
}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SUPPLIED = {"generation": "f" * 32, "dataset_generation": "e" * 32}


def _stored(db_engine, model, row_id):
    with make_sessionmaker(db_engine)() as db:
        row = db.get(model, row_id)
        assert row is not None
        return row


def _upload(client, path="/datasets", data=AGGREGATE, filename="input.csv", params=None):
    media = XLSX if filename.endswith(".xlsx") else "text/csv"
    response = client.post(path, headers=csrf_header(client), params=params or {},
                           files={"file": (filename, data, media)})
    assert response.status_code == 201, response.text
    return response.json()["dataset"]


def _analysis(client, setup=None):
    body = {"name": "Branch"} if setup is None else {"name": "Branch", "queue_setup": setup}
    response = client.post("/analyses", headers=csrf_header(client), json=body)
    assert response.status_code == 201, response.text
    return response.json()["analysis"]


def _verified_payload(client, dataset_id):
    payload = snapshot_payload(client)
    payload["dataset_id"] = dataset_id
    return payload


def test_every_dataset_creation_path_stores_a_distinct_token_and_reports_it(db_engine, client):
    create_user(db_engine, "d@example.com", "pw")
    login(client, "d@example.com", "pw")
    shared = _analysis(client, SHARED_SETUP)
    setup_analysis = _analysis(client)
    created = {
        "datasets.py upload": _upload(client),
        "analyses.py upload": _upload(client, f"/analyses/{shared['id']}/datasets"),
        "analyses.py apply_setup upload": _upload(
            client, f"/analyses/{setup_analysis['id']}/datasets", novamart_workbook(),
            "novamart.xlsx", {"apply_setup": "true"},
        ),
    }
    tokens = {}
    for path, dataset in created.items():
        stored = _stored(db_engine, Dataset, dataset["id"]).generation
        assert TOKEN.match(stored), path
        assert dataset["generation"] == stored, path
        tokens[path] = stored
    assert len(set(tokens.values())) == 3
    by_id = {dataset["id"]: tokens[path] for path, dataset in created.items()}
    for dataset in client.get("/datasets").json()["datasets"]:
        assert dataset["generation"] == by_id[dataset["id"]]
    for dataset_id, token in by_id.items():
        assert client.get(f"/datasets/{dataset_id}").json()["dataset"]["generation"] == token
    for analysis in (shared, setup_analysis):
        for dataset in client.get(f"/analyses/{analysis['id']}/datasets").json()["datasets"]:
            assert dataset["generation"] == by_id[dataset["id"]]
    current = client.get(f"/analyses/{shared['id']}/current")
    assert current.status_code == 200, current.text
    shared_dataset = created["analyses.py upload"]
    assert current.json()["dataset"]["id"] == shared_dataset["id"]
    assert current.json()["dataset"]["generation"] == by_id[shared_dataset["id"]]


def test_verified_schema1_save_records_the_dataset_token_it_checked(db_engine, client):
    create_user(db_engine, "s@example.com", "pw")
    login(client, "s@example.com", "pw")
    dataset = _upload(client)
    dataset_token = _stored(db_engine, Dataset, dataset["id"]).generation
    created = client.post("/scenarios", headers=csrf_header(client),
                          json={**_verified_payload(client, dataset["id"]), **SUPPLIED})
    assert created.status_code == 201, created.text
    scenario = created.json()["scenario"]
    assert scenario["provenance"] == "verified_snapshot"
    stored = _stored(db_engine, Scenario, scenario["id"])
    assert stored.dataset_generation == dataset_token
    assert TOKEN.match(stored.generation) and stored.generation != SUPPLIED["generation"]
    assert scenario["generation"] == stored.generation
    assert "dataset_generation" not in scenario
    # Every scenario read reports the same token and never the dataset binding.
    analysis_id = scenario["analysis_id"]
    for read in (
        client.get(f"/scenarios/{scenario['id']}").json()["scenario"],
        client.get("/scenarios").json()["scenarios"][0],
        client.get(f"/analyses/{analysis_id}/scenarios").json()["scenarios"][0],
    ):
        assert read["id"] == scenario["id"]
        assert read["generation"] == stored.generation
        assert "dataset_generation" not in read
    # The dataset row the save read is unchanged.
    assert _stored(db_engine, Dataset, dataset["id"]).generation == dataset_token


def test_verified_separate_plan_save_records_the_dataset_token_it_checked(db_engine, client):
    analysis_id, dataset_id, row_count = _workspace(db_engine, "p@example.com")
    login(client, "p@example.com", "pw")
    dataset_token = _stored(db_engine, Dataset, dataset_id).generation
    run = _run(client, analysis_id, 0.70)
    assert run.status_code == 200, run.text
    settings, results = _snapshot(analysis_id, dataset_id, row_count, 0.70, run.json()["schedule"])
    saved = _save(client, "Optimal @ 70%", analysis_id, dataset_id, settings, results)
    assert saved.status_code == 201, saved.text
    scenario = saved.json()["scenario"]
    assert scenario["provenance"] == "verified_snapshot"
    stored = _stored(db_engine, Scenario, scenario["id"])
    assert stored.dataset_generation == dataset_token
    assert scenario["generation"] == stored.generation and TOKEN.match(stored.generation)


def test_a_save_without_a_snapshot_leaves_the_dataset_binding_unrecorded(db_engine, client):
    create_user(db_engine, "l@example.com", "pw")
    login(client, "l@example.com", "pw")
    dataset = _upload(client)
    created = client.post("/scenarios", headers=csrf_header(client),
                          json={"name": "Imported", "dataset_id": dataset["id"], **SUPPLIED})
    assert created.status_code == 201, created.text
    scenario = created.json()["scenario"]
    assert scenario["provenance"] == "legacy_unverified"
    stored = _stored(db_engine, Scenario, scenario["id"])
    assert stored.dataset_id == dataset["id"]
    assert stored.dataset_generation is None
    assert scenario["generation"] == stored.generation and TOKEN.match(stored.generation)


def test_a_verified_save_without_a_dataset_leaves_the_dataset_binding_unrecorded(db_engine, client):
    create_user(db_engine, "n@example.com", "pw")
    login(client, "n@example.com", "pw")
    created = client.post("/scenarios", headers=csrf_header(client), json=snapshot_payload(client))
    assert created.status_code == 201, created.text
    scenario = created.json()["scenario"]
    assert scenario["provenance"] == "verified_snapshot"
    stored = _stored(db_engine, Scenario, scenario["id"])
    assert stored.dataset_id is None
    assert stored.dataset_generation is None
    assert scenario["generation"] == stored.generation and TOKEN.match(stored.generation)


def test_a_rejected_save_stores_no_scenario(db_engine, client):
    create_user(db_engine, "r@example.com", "pw")
    login(client, "r@example.com", "pw")
    dataset = _upload(client)
    forged = copy.deepcopy(_verified_payload(client, dataset["id"]))
    forged["results"]["results"][0]["cost_optimal"] = 0
    assert client.post("/scenarios", headers=csrf_header(client), json=forged).status_code == 422
    assert client.get("/scenarios").json()["scenarios"] == []
    with make_sessionmaker(db_engine)() as db:
        assert db.query(Scenario).count() == 0


def test_a_legacy_dataset_reparent_keeps_its_token_and_the_save_records_it(db_engine, client):
    user = create_user(db_engine, "g@example.com", "pw")
    login(client, "g@example.com", "pw")
    source = _upload(client)
    with make_sessionmaker(db_engine)() as db:
        rows = db.get(Dataset, source["id"]).normalized_json
        orphan = Dataset(user_id=user.id, analysis_id=None, name="Orphan", source_filename="o.csv",
                         source_format="csv", row_count=len(rows), normalized_json=rows,
                         validation_report_json={"ok": True, "message": "Input data is valid."})
        db.add(orphan)
        db.commit()
        orphan_id, orphan_token = orphan.id, orphan.generation
    created = client.post("/scenarios", headers=csrf_header(client), json=_verified_payload(client, orphan_id))
    assert created.status_code == 201, created.text
    reparented = _stored(db_engine, Dataset, orphan_id)
    assert reparented.analysis_id is not None
    assert reparented.analysis_id == created.json()["scenario"]["analysis_id"]
    assert reparented.generation == orphan_token
    assert _stored(db_engine, Scenario, created.json()["scenario"]["id"]).dataset_generation == orphan_token


def test_a_replacement_with_the_same_id_and_time_is_recorded_by_its_own_token(db_engine, client):
    user = create_user(db_engine, "x@example.com", "pw")
    login(client, "x@example.com", "pw")
    original = _upload(client)
    before = _stored(db_engine, Dataset, original["id"])
    assert client.delete(f"/datasets/{original['id']}", headers=csrf_header(client)).status_code == 200
    with make_sessionmaker(db_engine)() as db:
        db.add(Dataset(
            id=before.id, user_id=user.id, analysis_id=before.analysis_id, name=before.name,
            source_filename=before.source_filename, source_format=before.source_format,
            row_count=before.row_count, normalized_json=before.normalized_json,
            validation_report_json=before.validation_report_json, created_at=before.created_at,
        ))
        db.commit()
    replacement = _stored(db_engine, Dataset, before.id)
    assert replacement.created_at == before.created_at
    assert TOKEN.match(replacement.generation) and replacement.generation != before.generation
    assert client.get(f"/datasets/{before.id}").json()["dataset"]["generation"] == replacement.generation
    created = client.post("/scenarios", headers=csrf_header(client), json=_verified_payload(client, before.id))
    assert created.status_code == 201, created.text
    assert _stored(db_engine, Scenario, created.json()["scenario"]["id"]).dataset_generation == replacement.generation
