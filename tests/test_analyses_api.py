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


def queue_setup(*, structure="shared_queue", theta=None, capacity=None, segments=None, queue_ids=None, varies=False):
    return {
        "queue_structure": structure,
        "fixed_server_count": 2,
        "staffing_varies_by_period": varies,
        "capacity_mode": "finite" if capacity else "unlimited",
        "total_system_capacity": capacity,
        "abandonment_mode": "modeled" if theta else "not_modeled",
        "patience_rate_per_hour": theta,
        "segments": segments or [],
        "queue_ids": queue_ids if queue_ids is not None else (["queue_a"] if structure == "separate_queues" else []),
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
    assert separate["setup_status"] == "ready"
    response = upload(client, separate["id"], b"time,lambda,mu,c,variance,queue_id\n08:00-09:00,4,6,1,0.02,queue_a\n")
    assert response.status_code == 201, response.text
    current = client.get(f"/analyses/{separate['id']}/current")
    assert current.status_code == 200, current.text
    body = current.json()
    assert body["selected_model"] == "Parallel M/G/1"
    assert body["rows"][0]["model"] == "Parallel M/G/1"
    assert body["rows"][0]["model_id"] == "parallel_mg1"
    assert body["rows"][0]["queue_structure"] == "separate_queues"


def test_separate_queue_configuration_validates_authoritative_ids(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    for queue_ids in ([], ["queue_a", "queue_a"], [" "]):
        response = client.post(
            "/analyses",
            headers=csrf_header(client),
            json={"name": "Invalid queues", "queue_setup": queue_setup(structure="separate_queues", queue_ids=queue_ids)},
        )
        assert response.status_code == 422
    invalid_active = queue_setup(
        structure="separate_queues",
        queue_ids=["queue_a"],
        varies=True,
        segments=[{"id": "s", "start_time": "07:00", "end_time": "08:00", "active_queue_ids": ["queue_b"]}],
    )
    response = client.post("/analyses", headers=csrf_header(client), json={"name": "Unknown active", "queue_setup": invalid_active})
    assert response.status_code == 422


def test_separate_queue_upload_requires_service_variance(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    separate = create_analysis(client, "Separate", queue_setup(structure="separate_queues"))
    response = upload(client, separate["id"], b"time,lambda,mu,c,queue_id\n08:00-09:00,4,6,1,queue_a\n")
    assert response.status_code == 422
    assert "service-time variance" in response.json()["detail"]


def test_separate_queue_upload_rejects_unconfigured_queue_id(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    separate = create_analysis(client, "Separate", queue_setup(structure="separate_queues", queue_ids=["queue_a"]))
    response = upload(client, separate["id"], b"time,lambda,mu,c,variance,queue_id\n08:00-09:00,4,6,1,0.02,queue_b\n")
    assert response.status_code == 422
    assert "not configured" in response.json()["detail"]


def _separate_csv(rows):
    lines = ["time,queue_id,lambda,mu,c,variance"]
    lines += [f"{time},{queue},{lam},{mu},{c},{var}" for time, queue, lam, mu, c, var in rows]
    return ("\n".join(lines) + "\n").encode()


def test_separate_queue_single_arbitrary_id_round_trip(db_engine, client):
    """CASE A: one configured queue with an arbitrary name persists and validates."""
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    separate = create_analysis(client, "Solo", queue_setup(structure="separate_queues", queue_ids=["solo"]))
    assert separate["queue_setup"]["queue_ids"] == ["solo"]
    reloaded = client.get(f"/analyses/{separate['id']}").json()["analysis"]
    assert reloaded["queue_setup"]["queue_ids"] == ["solo"]
    response = upload(client, separate["id"], _separate_csv([("08:00-09:00", "solo", 4, 6, 1, 0.02)]))
    assert response.status_code == 201, response.text
    assert response.json()["dataset"]["row_count"] == 1


def test_separate_queue_two_arbitrary_ids(db_engine, client):
    """CASE B: two configured queues accept matching uploads without pooling."""
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    separate = create_analysis(client, "Pair", queue_setup(structure="separate_queues", queue_ids=["north", "south"]))
    response = upload(
        client,
        separate["id"],
        _separate_csv([
            ("08:00-09:00", "north", 4, 6, 1, 0.02),
            ("08:00-09:00", "south", 5, 6, 1, 0.03),
        ]),
    )
    assert response.status_code == 201, response.text
    current = client.get(f"/analyses/{separate['id']}/current").json()
    by_queue = {row["queue_id"]: row for row in current["rows"]}
    assert set(by_queue) == {"north", "south"}
    assert by_queue["north"]["lambda"] == 4
    assert by_queue["south"]["lambda"] == 5


def test_separate_queue_five_ids_cover_study_dataset(db_engine, client):
    """CASE C: five configured queues validate without defining a limit."""
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    ids = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    separate = create_analysis(client, "Five", queue_setup(structure="separate_queues", queue_ids=ids))
    assert separate["queue_setup"]["queue_ids"] == ids


def test_separate_queue_more_than_five_ids(db_engine, client):
    """CASE D: eight lanes persist and validate; no five-queue limit exists."""
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    ids = [f"lane_{index}" for index in range(1, 9)]
    separate = create_analysis(client, "Eight", queue_setup(structure="separate_queues", queue_ids=ids))
    assert separate["queue_setup"]["queue_ids"] == ids
    response = upload(
        client,
        separate["id"],
        _separate_csv([("08:00-09:00", queue, 4, 6, 1, 0.02) for queue in ids]),
    )
    assert response.status_code == 201, response.text
    current = client.get(f"/analyses/{separate['id']}/current").json()
    assert {row["queue_id"] for row in current["rows"]} == set(ids)


def test_separate_queue_partial_activity_is_valid(db_engine, client):
    """CASE E: configured queues may be absent from individual periods."""
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    ids = ["A", "B", "C", "D", "E"]
    separate = create_analysis(client, "Partial", queue_setup(structure="separate_queues", queue_ids=ids))
    response = upload(
        client,
        separate["id"],
        _separate_csv([
            ("05:00-06:00", "A", 4, 6, 1, 0.02),
            ("05:00-06:00", "B", 4, 6, 1, 0.02),
            ("06:00-07:00", "A", 4, 6, 1, 0.02),
            ("06:00-07:00", "B", 4, 6, 1, 0.02),
            ("06:00-07:00", "C", 4, 6, 1, 0.02),
            ("06:00-07:00", "D", 4, 6, 1, 0.02),
            ("06:00-07:00", "E", 4, 6, 1, 0.02),
        ]),
    )
    assert response.status_code == 201, response.text
    current = client.get(f"/analyses/{separate['id']}/current").json()
    early = {row["queue_id"] for row in current["rows"] if row["time"] == "05:00-06:00"}
    late = {row["queue_id"] for row in current["rows"] if row["time"] == "06:00-07:00"}
    assert early == {"A", "B"}
    assert late == {"A", "B", "C", "D", "E"}


def test_separate_queue_arbitrary_names_with_spaces_and_symbols(db_engine, client):
    """CASE F: names with spaces, hyphens, and underscores persist and validate."""
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    ids = ["regular-left", "regular-right", "express", "Cashier 1", "counter_03", "checkout-east"]
    separate = create_analysis(client, "Names", queue_setup(structure="separate_queues", queue_ids=ids))
    assert separate["queue_setup"]["queue_ids"] == ids
    response = upload(
        client,
        separate["id"],
        _separate_csv([("08:00-09:00", queue, 4, 6, 1, 0.02) for queue in ids]),
    )
    assert response.status_code == 201, response.text


def test_separate_queue_patch_reload_preserves_ids(db_engine, client):
    """Configured IDs survive save, refresh, and re-login scoping."""
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    separate = create_analysis(client, "Reload", queue_setup(structure="separate_queues", queue_ids=["cashier_a"]))
    updated = client.patch(
        f"/analyses/{separate['id']}",
        headers=csrf_header(client),
        json={"queue_setup": queue_setup(structure="separate_queues", queue_ids=["cashier_a", "cashier_b"])},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["analysis"]["queue_setup"]["queue_ids"] == ["cashier_a", "cashier_b"]
    reloaded = client.get(f"/analyses/{separate['id']}").json()["analysis"]
    assert reloaded["queue_setup"]["queue_ids"] == ["cashier_a", "cashier_b"]


def test_separate_queue_duplicate_pair_merges_into_one_observation(db_engine, client):
    """CASE J: a repeated (time, queue_id) pair combines; it never duplicates evidence."""
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    separate = create_analysis(client, "Dupes", queue_setup(structure="separate_queues", queue_ids=["north"]))
    response = upload(
        client,
        separate["id"],
        _separate_csv([
            ("08:00-09:00", "north", 2, 6, 1, 0.02),
            ("08:00-09:00", "north", 3, 6, 1, 0.02),
        ]),
    )
    assert response.status_code == 201, response.text
    current = client.get(f"/analyses/{separate['id']}/current").json()
    assert len(current["rows"]) == 1
    assert current["rows"][0]["lambda"] == 5


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


def test_separate_event_upload_derives_variance_per_queue(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis = create_analysis(client, "Separate events", queue_setup(structure="separate_queues", queue_ids=["queue_a", "queue_b"]))
    events = (
        b"queue_id,arrival_time,service_start,service_end\n"
        b"queue_a,2026-09-08T08:00:00Z,2026-09-08T08:00:00Z,2026-09-08T08:30:00Z\n"
        b"queue_a,2026-09-08T08:10:00Z,2026-09-08T08:10:00Z,2026-09-08T09:10:00Z\n"
        b"queue_b,2026-09-08T08:20:00Z,2026-09-08T08:20:00Z,2026-09-08T08:35:00Z\n"
    )
    response = upload(client, analysis["id"], events)
    assert response.status_code == 201, response.text
    records = {row["queue_id"]: row for row in response.json()["dataset"]["normalized"]}
    assert records["queue_a"]["lambda"] == 2.0
    assert records["queue_a"]["mu"] == 1 / 0.75
    assert records["queue_a"]["variance"] == 0.0625
    assert records["queue_a"]["service_time_source"] == "empirical"
    assert records["queue_a"]["service_samples_hours"] == [0.5, 1.0]
    assert records["queue_a"]["server_id"] == "server:queue_a"
    assert records["queue_b"]["lambda"] == 1.0
    assert records["queue_b"]["mu"] == 4.0
    assert records["queue_b"]["variance"] == 0.0
    assert records["queue_b"]["service_samples_hours"] == [0.25]
    reloaded = client.get(f"/datasets/{response.json()['dataset']['id']}")
    assert reloaded.status_code == 200
    assert reloaded.json()["dataset"]["normalized"] == response.json()["dataset"]["normalized"]
    for record in records.values():
        samples = record["service_samples_hours"]
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / len(samples)
        second_moment = sum(value**2 for value in samples) / len(samples)
        assert math.isclose(record["mu"], 1.0 / mean)
        assert math.isclose(record["variance"], variance)
        assert math.isclose(record["variance"] + mean**2, second_moment)


def test_aggregate_separate_input_remains_des_gated(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis = create_analysis(client, "Aggregate separate", queue_setup(structure="separate_queues"))
    response = upload(
        client,
        analysis["id"],
        b"time,lambda,mu,c,variance,queue_id\n08:00-09:00,4,6,1,0.02,queue_a\n",
    )
    assert response.status_code == 201, response.text
    record = response.json()["dataset"]["normalized"][0]
    assert record["service_time_source"] == "aggregate_statistics"
    assert "requires empirical service observations" in record["des_capability"]
    assert "service_samples_hours" not in record


def test_empirical_samples_do_not_cross_segments(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis = create_analysis(
        client,
        "Segment-scoped samples",
        queue_setup(
            structure="separate_queues",
            queue_ids=["queue_a", "queue_b"],
            segments=[
                {"id": "segment_a", "start_time": "07:00", "end_time": "08:00"},
                {"id": "segment_b", "start_time": "08:00", "end_time": "09:00"},
            ],
        ),
    )
    events = (
        b"queue_id,arrival_time,service_start,service_end\n"
        b"queue_a,2026-09-08T07:10:00Z,2026-09-08T07:10:00Z,2026-09-08T07:20:00Z\n"
        b"queue_a,2026-09-08T08:10:00Z,2026-09-08T08:10:00Z,2026-09-08T08:40:00Z\n"
    )
    response = upload(client, analysis["id"], events)
    assert response.status_code == 201, response.text
    records = response.json()["dataset"]["normalized"]
    assert [record["segment_id"] for record in records] == ["segment_a", "segment_b"]
    assert records[0]["service_samples_hours"] == [10 / 60]
    assert records[1]["service_samples_hours"] == [30 / 60]
    assert all(record["queue_id"] == "queue_a" for record in records)


def test_configured_segments_normalize_mixed_durations_and_boundary(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    segments = [
        {"id": "early", "start_time": "05:00", "end_time": "06:00"},
        {"id": "morning", "start_time": "06:00", "end_time": "07:00"},
        {"id": "short_a", "start_time": "07:00", "end_time": "07:15"},
        {"id": "short_b", "start_time": "07:15", "end_time": "07:30"},
        {"id": "half", "start_time": "07:30", "end_time": "08:00"},
        {"id": "hour", "start_time": "08:00", "end_time": "09:00"},
    ]
    analysis = create_analysis(client, "Mixed segments", queue_setup(segments=segments))
    events = ["arrival_time,service_start,service_end"]
    event_times = [
        *("05:05",),
        *("06:05",),
        "07:01",
        "07:02",
        "07:03",
        "07:15",
        "07:30",
        "07:35",
        "07:40",
        "07:45",
        "07:50",
        "08:00",
        "08:05",
        "08:10",
        "08:15",
        "08:20",
        "08:25",
        "08:30",
        "08:35",
        "08:40",
        "08:45",
    ]
    for clock_time in event_times:
        start = f"2026-09-08T{clock_time}:00Z"
        hour, minute = (int(value) for value in clock_time.split(":"))
        end_minute = minute + 5
        end_hour = hour + end_minute // 60
        end_minute %= 60
        events.append(f"{start},{start},2026-09-08T{end_hour:02d}:{end_minute:02d}:00Z")
    response = upload(client, analysis["id"], ("\n".join(events) + "\n").encode())
    assert response.status_code == 201, response.text
    records = response.json()["dataset"]["normalized"]
    by_id = {record["time"].split()[-2]: record for record in records}
    assert by_id["early"]["lambda"] == 1.0
    assert by_id["morning"]["lambda"] == 1.0
    assert by_id["short_a"]["lambda"] == 12.0
    assert by_id["short_b"]["lambda"] == 4.0
    assert by_id["half"]["lambda"] == 10.0
    assert by_id["hour"]["lambda"] == 10.0


def test_segment_schedule_persists_and_rejects_invalid_intervals(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    valid = queue_setup(
        segments=[
            {"id": "a", "start_time": "07:00", "end_time": "07:15"},
            {"id": "b", "start_time": "07:15", "end_time": "07:30"},
        ]
    )
    analysis = create_analysis(client, "Persisted schedule", valid)
    persisted = client.get(f"/analyses/{analysis['id']}").json()["analysis"]["queue_setup"]
    assert persisted["separate_queue_closure_policy"] == "drain_existing"
    assert persisted["segments"] == [
        {"id": "a", "start_time": "07:00:00", "end_time": "07:15:00", "active_queue_ids": None},
        {"id": "b", "start_time": "07:15:00", "end_time": "07:30:00", "active_queue_ids": None},
    ]
    for invalid_segments in (
        [{"id": "bad", "start_time": "07:30", "end_time": "07:30"}],
        [
            {"id": "a", "start_time": "07:00", "end_time": "07:20"},
            {"id": "b", "start_time": "07:15", "end_time": "07:30"},
        ],
    ):
        response = client.post(
            "/analyses",
            headers=csrf_header(client),
            json={"name": "Invalid schedule", "queue_setup": queue_setup(segments=invalid_segments)},
        )
        assert response.status_code == 422
    outside = upload(
        client,
        analysis["id"],
        b"arrival_time,service_start,service_end\n2026-09-08T08:00:00Z,2026-09-08T08:00:00Z,2026-09-08T08:05:00Z\n",
    )
    assert outside.status_code == 422
    assert "outside the configured analysis segments" in outside.json()["detail"]


def test_aggregate_lambda_is_not_duration_normalized(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis = create_analysis(
        client,
        "Aggregate rate",
        queue_setup(segments=[{"id": "short", "start_time": "07:00", "end_time": "07:15"}]),
    )
    response = upload(client, analysis["id"], b"time,lambda,mu,c\n07:00-07:15,12,6,2\n")
    assert response.status_code == 201, response.text
    assert response.json()["dataset"]["normalized"][0]["lambda"] == 12.0


def test_separate_queues_remain_independent_inside_short_segment(db_engine, client):
    create_user(db_engine, "a@example.com", "pw")
    login(client, "a@example.com", "pw")
    analysis = create_analysis(
        client,
        "Short separate queues",
        queue_setup(
            structure="separate_queues",
            queue_ids=["queue_a", "queue_b"],
            segments=[{"id": "short", "start_time": "07:00", "end_time": "07:15"}],
        ),
    )
    events = (
        b"queue_id,arrival_time,service_start,service_end\n"
        b"queue_a,2026-09-08T07:01:00Z,2026-09-08T07:01:00Z,2026-09-08T07:06:00Z\n"
        b"queue_a,2026-09-08T07:02:00Z,2026-09-08T07:02:00Z,2026-09-08T07:07:00Z\n"
        b"queue_a,2026-09-08T07:03:00Z,2026-09-08T07:03:00Z,2026-09-08T07:08:00Z\n"
        b"queue_b,2026-09-08T07:04:00Z,2026-09-08T07:04:00Z,2026-09-08T07:14:00Z\n"
        b"queue_b,2026-09-08T07:05:00Z,2026-09-08T07:05:00Z,2026-09-08T07:15:00Z\n"
    )
    response = upload(client, analysis["id"], events)
    assert response.status_code == 201, response.text
    records = {row["queue_id"]: row for row in response.json()["dataset"]["normalized"]}
    assert records["queue_a"]["lambda"] == 12.0
    assert records["queue_b"]["lambda"] == 8.0


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
