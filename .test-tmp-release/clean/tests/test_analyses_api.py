"""Analysis workspace ownership, ingestion, and explanation coverage."""

from __future__ import annotations

import math

import pytest

from backend.queueing_engine.services.model_explanations import analyze_segments
from tests.helpers import clear_cookies, create_user, csrf_header, login

AGGREGATE = b"time,lambda,mu,c\n08:00-09:00,4,6,2\n"
EVENTS = (
    b"customer_id,arrival_time,service_start,service_end\n"
    b"1,2026-09-08T08:05:00Z,2026-09-08T08:10:00Z,2026-09-08T08:40:00Z\n"
    b"2,2026-09-08T08:35:00Z,2026-09-08T08:40:00Z,2026-09-08T08:55:00Z\n"
    b"3,2026-09-08T09:05:00Z,2026-09-08T09:10:00Z,2026-09-08T09:30:00Z\n"
)


def queue_setup(*, structure="shared_queue", theta=None, capacity=None):
    return {
        "queue_structure": structure,
        "fixed_server_count": 2,
        "staffing_varies_by_period": False,
        "capacity_mode": "finite" if capacity else "unlimited",
        "total_system_capacity": capacity,
        "abandonment_mode": "modeled" if theta else "not_modeled",
        "patience_rate_per_hour": theta,
    }


def create_analysis(client, name="Branch A", configured_setup=None):
    response = client.post(
        "/analyses",
        headers=csrf_header(client),
        json={"name": name, "service_type": "checkout", "queue_setup": configured_setup or queue_setup()},
    )
    assert response.status_code == 201, response.text
    return response.json()["analysis"]


def upload(client, analysis_id, payload=AGGREGATE):
    return client.post(
        f"/analyses/{analysis_id}/datasets",
        headers=csrf_header(client),
        files={"file": ("input.csv", payload, "text/csv")},
    )


def test_analysis_crud_archive_and_csrf(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    assert client.post("/analyses", json={"name": "Blocked"}).status_code == 403
    analysis = create_analysis(client)
    assert analysis["setup_status"] == "ready"
    response = client.patch(
        f"/analyses/{analysis['id']}",
        headers=csrf_header(client),
        json={"name": "Renamed", "location_label": "North"},
    )
    assert response.status_code == 200
    assert response.json()["analysis"]["name"] == "Renamed"
    assert client.post(f"/analyses/{analysis['id']}/archive").status_code == 403
    assert client.post(f"/analyses/{analysis['id']}/archive", headers=csrf_header(client)).status_code == 200
    assert client.get("/analyses").json()["analyses"] == []


def test_analysis_names_reject_whitespace_only_values(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    response = client.post("/analyses", headers=csrf_header(client), json={"name": "   "})
    assert response.status_code == 422


def test_cross_user_analysis_is_404(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis_id = create_analysis(client)["id"]
    clear_cookies(client)
    create_user(db_engine, "b@example.com", "pw")
    login(client, "b@example.com", "pw")
    assert client.get(f"/analyses/{analysis_id}").status_code == 404
    assert upload(client, analysis_id).status_code == 404


def test_queue_setup_validation_and_separate_queue_state(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    invalid = queue_setup()
    invalid["queue_structure"] = "single_server"
    invalid["fixed_server_count"] = 3
    assert (
        client.post("/analyses", headers=csrf_header(client), json={"name": "Bad", "queue_setup": invalid}).status_code
        == 422
    )
    separate = create_analysis(client, "Separate", queue_setup(structure="separate_queues"))
    assert separate["setup_status"] == "unsupported"
    response = upload(client, separate["id"])
    assert response.status_code == 422
    assert "Separate queues" in response.json()["detail"]


def test_aggregate_upload_current_and_explanation(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis = create_analysis(client)
    response = upload(client, analysis["id"])
    assert response.status_code == 201, response.text
    dataset = response.json()["dataset"]
    assert dataset["analysis_id"] == analysis["id"]
    current = client.get(f"/analyses/{analysis['id']}/current")
    assert current.status_code == 200
    body = current.json()
    assert body["selected_model"] == "M/M/c"
    assert body["rows"][0]["model"] == "M/M/c"
    assert body["explanations"][0]["selection_reason"]


def test_event_upload_derives_hourly_segments_and_provenance(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis = create_analysis(client)
    response = upload(client, analysis["id"], EVENTS)
    assert response.status_code == 201, response.text
    dataset = response.json()["dataset"]
    assert dataset["row_count"] == 2
    first = dataset["normalized"][0]
    assert first["lambda"] == 2.0
    assert math.isclose(first["mu"], 1 / 0.375)
    assert math.isclose(first["variance"], 0.015625)
    assert dataset["validation"]["schema"] == "customer_events"
    assert dataset["validation"]["field_provenance"]["variance"] == "data_derived"
    assert math.isclose(
        dataset["validation"]["derived_statistics"][0]["mean_waiting_time_hours"],
        5 / 60,
    )
    current = client.get(f"/analyses/{analysis['id']}/current").json()
    assert current["selected_model"] == "M/G/c"
    assert "variance" in " ".join(current["explanations"][0]["measured_characteristics"])


def test_event_timestamp_order_is_rejected(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis_id = create_analysis(client)["id"]
    bad = b"arrival_time,service_start,service_end\n2026-09-08T08:10:00Z,2026-09-08T08:05:00Z,2026-09-08T08:20:00Z\n"
    response = upload(client, analysis_id, bad)
    assert response.status_code == 422
    assert "service_start cannot be before" in response.json()["detail"]


def test_aggregate_must_match_fixed_queue_setup(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis = create_analysis(client)
    mismatch = b"time,lambda,mu,c\n08:00-09:00,4,6,3\n"
    response = upload(client, analysis["id"], mismatch)
    assert response.status_code == 422
    assert "fixed server count" in response.json()["detail"]


def test_explicit_theta_has_provenance_and_selector_precedence(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis = create_analysis(client, configured_setup=queue_setup(theta=2.5, capacity=10))
    dataset = upload(client, analysis["id"], EVENTS).json()["dataset"]
    assert dataset["normalized"][0]["K"] == 10
    assert dataset["normalized"][0]["theta"] == 2.5
    assert dataset["validation"]["field_provenance"]["theta"] == "user_provided"
    current = client.get(f"/analyses/{analysis['id']}/current").json()
    assert current["selected_model"] == "M/M/c+M (Erlang-A)"


def test_cross_analysis_scenario_dataset_is_rejected(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    first = create_analysis(client, "First")
    second = create_analysis(client, "Second")
    dataset_id = upload(client, first["id"]).json()["dataset"]["id"]
    response = client.post(
        "/scenarios",
        headers=csrf_header(client),
        json={
            "name": "Wrong workspace",
            "analysis_id": second["id"],
            "dataset_id": dataset_id,
            "settings": {},
            "results": {},
        },
    )
    assert response.status_code == 404
    assert client.get(f"/analyses/{second['id']}/datasets").json()["datasets"] == []


@pytest.mark.parametrize(
    ("segment", "expected"),
    [
        ({"time": "a", "lambda": 1, "mu": 3, "c": 1}, "M/M/1"),
        ({"time": "a", "lambda": 1, "mu": 3, "c": 2}, "M/M/c"),
        ({"time": "a", "lambda": 1, "mu": 3, "c": 2, "variance": 0.1}, "M/G/c"),
        ({"time": "a", "lambda": 1, "mu": 3, "c": 2, "K": 5}, "M/M/c/K"),
        ({"time": "a", "lambda": 1, "mu": 3, "c": 2, "K": 5, "variance": 0.1}, "M/G/c/K"),
        ({"time": "a", "lambda": 1, "mu": 3, "c": 2, "theta": 1}, "M/M/c+M (Erlang-A)"),
    ],
)
def test_every_selected_model_has_structured_explanation(segment, expected):
    _, explanations, selected = analyze_segments([segment], {}, {})
    assert selected == expected
    assert explanations[0]["model_assumptions"]
    assert explanations[0]["selection_reason"]


def test_multiple_models_are_not_collapsed_to_dominant_model():
    segments = [
        {"time": "a", "lambda": 1, "mu": 3, "c": 1},
        {"time": "b", "lambda": 1, "mu": 3, "c": 2, "variance": 0.1},
    ]
    _, explanations, selected = analyze_segments(segments, {}, {})
    assert selected == "Multiple models by time period"
    assert [row["selected_model"] for row in explanations] == ["M/M/1", "M/G/c"]
