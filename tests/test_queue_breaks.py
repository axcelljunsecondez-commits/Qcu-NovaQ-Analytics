"""Separate-queue server break schedule authority (input only).

Breaks are explicit user configuration persisted on QueueSetup: each record
names an existing queue, a scheduled start time, and a positive duration in
minutes. Nothing is inferred, generated, or defaulted; an empty schedule is
valid and means "no configured breaks". No DES/optimizer behavior changes.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.analysis_schemas import QueueSetup


def _setup(**over):
    base = {
        "queue_structure": "separate_queues",
        "fixed_server_count": 1,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": ["cashier_3", "express"],
    }
    base.update(over)
    return base


def test_empty_break_schedule_is_valid():
    setup = QueueSetup(**_setup())
    assert setup.breaks == []
    assert QueueSetup(**_setup(breaks=[])).breaks == []


def test_unknown_queue_id_is_rejected():
    with pytest.raises(ValidationError):
        QueueSetup(**_setup(breaks=[
            {"queue_id": "ghost", "scheduled_start_time": "11:00", "duration_minutes": 60},
        ]))


def test_non_positive_duration_is_rejected():
    for bad in (0, -30):
        with pytest.raises(ValidationError):
            QueueSetup(**_setup(breaks=[
                {"queue_id": "cashier_3", "scheduled_start_time": "11:00",
                 "duration_minutes": bad},
            ]))


def test_malformed_time_is_rejected():
    for bad in ("11", "noon", "25:00", ""):
        with pytest.raises(ValidationError):
            QueueSetup(**_setup(breaks=[
                {"queue_id": "cashier_3", "scheduled_start_time": bad,
                 "duration_minutes": 60},
            ]))


def test_multiple_breaks_one_queue_and_across_queues_accepted():
    setup = QueueSetup(**_setup(breaks=[
        {"queue_id": "cashier_3", "scheduled_start_time": "11:00", "duration_minutes": 60},
        {"queue_id": "cashier_3", "scheduled_start_time": "15:30", "duration_minutes": 30},
        {"queue_id": "express", "scheduled_start_time": "12:00", "duration_minutes": 45},
    ]))
    assert [(b.queue_id, b.duration_minutes) for b in setup.breaks] == [
        ("cashier_3", 60), ("cashier_3", 30), ("express", 45)]
    assert setup.breaks[0].scheduled_start_time.isoformat() == "11:00:00"


def test_arbitrary_queue_ids_preserved_verbatim():
    setup = QueueSetup(**_setup(queue_ids=["east-07", "lane A"],
                                breaks=[{"queue_id": "lane A",
                                         "scheduled_start_time": "09:05",
                                         "duration_minutes": 15}]))
    assert setup.breaks[0].queue_id == "lane A"
    assert setup.model_dump(mode="json")["breaks"][0]["queue_id"] == "lane A"


def test_breaks_require_separate_queue_structure():
    with pytest.raises(ValidationError):
        QueueSetup(**_setup(queue_structure="shared_queue", queue_ids=[],
                            breaks=[{"queue_id": "cashier_3",
                                     "scheduled_start_time": "11:00",
                                     "duration_minutes": 60}]))


def _api_setup(**over):
    base = {
        "queue_structure": "separate_queues",
        "fixed_server_count": 1,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": ["cashier_3", "express"],
        "breaks": [{"queue_id": "cashier_3", "scheduled_start_time": "11:00",
                    "duration_minutes": 60}],
    }
    base.update(over)
    return base


def test_break_schedule_save_reload_round_trip(db_engine, client):
    from tests.helpers import create_user, csrf_header, login

    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    created = client.post(
        "/analyses", headers=csrf_header(client),
        json={"name": "Breaks", "queue_setup": _api_setup()},
    )
    assert created.status_code == 201, created.text
    analysis_id = created.json()["analysis"]["id"]
    reloaded = client.get(f"/analyses/{analysis_id}").json()["analysis"]["queue_setup"]
    assert reloaded["breaks"] == [{"queue_id": "cashier_3",
                                   "scheduled_start_time": "11:00:00",
                                   "duration_minutes": 60}]
    patched = client.patch(
        f"/analyses/{analysis_id}", headers=csrf_header(client),
        json={"queue_setup": _api_setup(breaks=[
            {"queue_id": "cashier_3", "scheduled_start_time": "11:00",
             "duration_minutes": 60},
            {"queue_id": "express", "scheduled_start_time": "12:30",
             "duration_minutes": 30},
        ])},
    )
    assert patched.status_code == 200, patched.text
    reloaded = client.get(f"/analyses/{analysis_id}").json()["analysis"]["queue_setup"]
    assert [(b["queue_id"], b["scheduled_start_time"], b["duration_minutes"])
            for b in reloaded["breaks"]] == [
        ("cashier_3", "11:00:00", 60), ("express", "12:30:00", 30)]


def test_break_with_unknown_queue_rejected_by_api(db_engine, client):
    from tests.helpers import create_user, csrf_header, login

    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/analyses", headers=csrf_header(client),
        json={"name": "Bad", "queue_setup": _api_setup(breaks=[
            {"queue_id": "ghost", "scheduled_start_time": "11:00",
             "duration_minutes": 60}])},
    )
    assert response.status_code == 422


def test_removing_break_queue_invalidates_setup(db_engine, client):
    from tests.helpers import create_user, csrf_header, login

    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    created = client.post(
        "/analyses", headers=csrf_header(client),
        json={"name": "Breaks", "queue_setup": _api_setup()},
    )
    analysis_id = created.json()["analysis"]["id"]
    response = client.patch(
        f"/analyses/{analysis_id}", headers=csrf_header(client),
        json={"queue_setup": _api_setup(queue_ids=["express"])},
    )
    assert response.status_code == 422
    reloaded = client.get(f"/analyses/{analysis_id}").json()["analysis"]["queue_setup"]
    assert reloaded["queue_ids"] == ["cashier_3", "express"]
    assert len(reloaded["breaks"]) == 1
