"""Create Analysis queue-structure persistence (Phase 2 final architecture)."""

from __future__ import annotations

from tests.helpers import create_user, csrf_header, login


def base_setup(structure="unknown", queue_ids=None):
    return {
        "queue_structure": structure,
        "fixed_server_count": None,
        "staffing_varies_by_period": False,
        "capacity_mode": "unknown",
        "total_system_capacity": None,
        "abandonment_mode": "unknown",
        "patience_rate_per_hour": None,
        "segments": [],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": queue_ids if queue_ids is not None else [],
    }


def create(client, name, setup=None):
    payload = {"name": name}
    if setup is not None:
        payload["queue_setup"] = setup
    return client.post("/analyses", headers=csrf_header(client), json=payload)


def test_create_defaults_to_unknown_structure(db_engine, client):
    create_user(db_engine, "s@example.com", "pw")
    login(client, "s@example.com", "pw")
    r = create(client, "No choice yet")
    assert r.status_code == 201, r.text
    body = r.json()["analysis"]
    assert body["queue_setup"]["queue_structure"] == "unknown"


def test_create_shared_structure_persists_without_server_count(db_engine, client):
    create_user(db_engine, "s@example.com", "pw")
    login(client, "s@example.com", "pw")
    r = create(client, "Shared shop", base_setup("shared_queue"))
    assert r.status_code == 201, r.text
    body = r.json()["analysis"]
    assert body["queue_setup"]["queue_structure"] == "shared_queue"
    assert body["setup_status"] == "incomplete"


def test_create_separate_structure_persists_queue_ids(db_engine, client):
    create_user(db_engine, "s@example.com", "pw")
    login(client, "s@example.com", "pw")
    r = create(client, "Lanes", base_setup("separate_queues", ["queue_1", "queue_2"]))
    assert r.status_code == 201, r.text
    body = r.json()["analysis"]
    assert body["queue_setup"]["queue_structure"] == "separate_queues"
    assert body["queue_setup"]["queue_ids"] == ["queue_1", "queue_2"]


def test_create_separate_without_queue_ids_rejected(db_engine, client):
    create_user(db_engine, "s@example.com", "pw")
    login(client, "s@example.com", "pw")
    r = create(client, "No lanes", base_setup("separate_queues", []))
    assert r.status_code == 422, r.text


def test_guided_confirm_patches_structure_without_rewriting_evidence(db_engine, client):
    create_user(db_engine, "s@example.com", "pw")
    login(client, "s@example.com", "pw")
    created = create(client, "Guided shop").json()["analysis"]
    analysis_id = created["id"]
    setup = dict(created["queue_setup"])
    setup.update({"queue_structure": "separate_queues", "queue_ids": ["queue_1"]})
    r = client.patch(
        f"/analyses/{analysis_id}", headers=csrf_header(client), json={"queue_setup": setup}
    )
    assert r.status_code == 200, r.text
    assert r.json()["analysis"]["queue_setup"]["queue_structure"] == "separate_queues"
