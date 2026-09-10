"""Scenarios API coverage: CRUD, size boundary, isolation."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.settings import Settings
from backend.db.models import Dataset
from tests.helpers import (
    clear_cookies,
    create_user,
    csrf_header,
    login,
    make_sessionmaker,
)

SCENARIO_BODY = {
    "name": "Morning rush",
    "settings": {"target_utilization": 0.7, "server_cost_per_hr": 87.0},
    "results": {"segments": 4, "total_cost": 1044.0},
}


@pytest.fixture
def small_result_client(db_engine, monkeypatch):
    monkeypatch.setenv("RESULT_JSONB_MAX_BYTES", "1024")
    return TestClient(create_app(engine=db_engine, settings=Settings()))


def test_create_scenario(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post("/scenarios", headers=csrf_header(client), json=SCENARIO_BODY)
    assert response.status_code == 201
    scenario = response.json()["scenario"]
    assert scenario["name"] == "Morning rush"
    assert scenario["settings"]["target_utilization"] == 0.7
    assert scenario["results"]["total_cost"] == 1044.0


def test_scenario_name_rejects_whitespace_only_value(db_engine, client):
    create_user(db_engine, "owner@example.com", "pw")
    login(client, "owner@example.com", "pw")
    response = client.post(
        "/scenarios",
        headers=csrf_header(client),
        json={"name": "   ", "settings": {}, "results": {}},
    )
    assert response.status_code == 422


def test_create_scenario_with_dataset(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        dataset = Dataset(
            user_id=1,
            name="d",
            source_filename="s.csv",
            source_format="csv",
            row_count=0,
            normalized_json=[],
            validation_report_json={},
        )
        db.add(dataset)
        db.commit()
        dataset_id = dataset.id
    body = {**SCENARIO_BODY, "dataset_id": dataset_id}
    response = client.post("/scenarios", headers=csrf_header(client), json=body)
    assert response.status_code == 201
    assert response.json()["scenario"]["dataset_id"] == dataset_id


def test_create_scenario_requires_auth(client):
    assert client.post("/scenarios", json=SCENARIO_BODY).status_code == 401


def test_create_scenario_requires_csrf(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    assert client.post("/scenarios", json=SCENARIO_BODY).status_code == 403


def test_create_scenario_rejects_oversize_results(db_engine, small_result_client):
    create_user(db_engine, "u@example.com", "pw")
    login(small_result_client, "u@example.com", "pw")
    response = small_result_client.post(
        "/scenarios",
        headers=csrf_header(small_result_client),
        json={"name": "big", "settings": {}, "results": {"blob": "x" * 2000}},
    )
    assert response.status_code == 413


def test_list_scenarios(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    client.post("/scenarios", headers=csrf_header(client), json=SCENARIO_BODY)
    client.post(
        "/scenarios",
        headers=csrf_header(client),
        json={**SCENARIO_BODY, "name": "Evening"},
    )
    listing = client.get("/scenarios")
    assert listing.status_code == 200
    names = [s["name"] for s in listing.json()["scenarios"]]
    assert names == ["Evening", "Morning rush"]


def test_get_scenario(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    scenario_id = client.post("/scenarios", headers=csrf_header(client), json=SCENARIO_BODY).json()["scenario"]["id"]
    detail = client.get(f"/scenarios/{scenario_id}")
    assert detail.status_code == 200
    assert detail.json()["scenario"]["name"] == "Morning rush"


def test_get_missing_scenario_404(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    assert client.get("/scenarios/99999").status_code == 404


def test_patch_scenario(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    scenario_id = client.post("/scenarios", headers=csrf_header(client), json=SCENARIO_BODY).json()["scenario"]["id"]
    response = client.patch(
        f"/scenarios/{scenario_id}",
        headers=csrf_header(client),
        json={"name": "Renamed"},
    )
    assert response.status_code == 200
    scenario = response.json()["scenario"]
    assert scenario["name"] == "Renamed"
    assert scenario["results"]["total_cost"] == 1044.0
    assert scenario["settings"]["target_utilization"] == 0.7


def test_patch_scenario_rejects_oversize_results(db_engine, small_result_client):
    create_user(db_engine, "u@example.com", "pw")
    login(small_result_client, "u@example.com", "pw")
    scenario_id = small_result_client.post(
        "/scenarios",
        headers=csrf_header(small_result_client),
        json={"name": "big", "settings": {}, "results": {"blob": "x"}},
    ).json()["scenario"]["id"]
    response = small_result_client.patch(
        f"/scenarios/{scenario_id}",
        headers=csrf_header(small_result_client),
        json={"results": {"blob": "x" * 2000}},
    )
    assert response.status_code == 413


def test_delete_scenario(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    scenario_id = client.post("/scenarios", headers=csrf_header(client), json=SCENARIO_BODY).json()["scenario"]["id"]
    response = client.delete(f"/scenarios/{scenario_id}", headers=csrf_header(client))
    assert response.status_code == 200
    assert client.get(f"/scenarios/{scenario_id}").status_code == 404


def test_cross_user_isolation(db_engine, client):
    create_user(db_engine, "alice@example.com", "pw")
    login(client, "alice@example.com", "pw")
    scenario_id = client.post("/scenarios", headers=csrf_header(client), json=SCENARIO_BODY).json()["scenario"]["id"]

    clear_cookies(client)
    create_user(db_engine, "bob@example.com", "pw")
    login(client, "bob@example.com", "pw")
    assert client.get(f"/scenarios/{scenario_id}").status_code == 404
    assert client.patch(f"/scenarios/{scenario_id}", headers=csrf_header(client), json={"name": "x"}).status_code == 404
    assert client.delete(f"/scenarios/{scenario_id}", headers=csrf_header(client)).status_code == 404


def test_scenario_json_roundtrip_utf8(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    body = {**SCENARIO_BODY, "name": "高峰时段"}
    response = client.post("/scenarios", headers=csrf_header(client), json=body)
    assert response.status_code == 201
    assert response.json()["scenario"]["name"] == "高峰时段"
    assert json.loads(client.get("/scenarios").content)["scenarios"][0]["name"] == "高峰时段"
