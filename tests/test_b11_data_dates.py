"""B11: the dates an uploaded file covers ("Data covers"; spec D17, plan Phase 7).

Customer-record uploads store their first and last arrival date at ingestion. Customer-record
datasets stored earlier recover the dates from NovaQ's own per-date period labels. Aggregate
files and earlier representative-day datasets have none ("Data period unavailable").

Data: SYNTHETIC (timestamps and rows made for the test).
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.data.analysis_ingestion import normalize_analysis_input
from backend.data.data_dates import PERIOD_LABELS, STORED, data_dates
from tests.helpers import create_user, csrf_header, login
from tests.test_current_dataset import SETUP
from tests.test_representative_day import EVENTS, _events, _setup

AGGREGATE = b"time,lambda,mu,c\n08:00-09:00,4,6,2\n"
SHARED_EVENTS = (
    b"customer_id,arrival_time,service_start,service_end\n"
    b"1,2026-09-08T08:05:00Z,2026-09-08T08:10:00Z,2026-09-08T08:40:00Z\n"
    b"2,2026-09-10T09:35:00Z,2026-09-10T09:40:00Z,2026-09-10T09:55:00Z\n"
    b"3,2026-09-09T09:05:00Z,2026-09-09T09:10:00Z,2026-09-09T09:30:00Z\n"
)


# --- stored at ingestion -------------------------------------------------------------------------


def test_per_date_events_store_first_and_last_arrival_date():
    _, provenance = normalize_analysis_input(_events(EVENTS), _setup())
    assert provenance["data_dates"] == {"first": "2026-08-03", "last": "2026-08-04"}


def test_representative_day_events_store_the_dates_too():
    _, provenance = normalize_analysis_input(_events(EVENTS), _setup(event_period_basis="representative_day"))
    assert provenance["data_dates"] == {"first": "2026-08-03", "last": "2026-08-04"}
    assert data_dates(provenance, []) == {"first": "2026-08-03", "last": "2026-08-04", "source": STORED}


def test_dates_use_the_utc_clock_of_the_period_labels():
    frame = pd.DataFrame([{"arrival_time": "2026-08-04T06:30:00+08:00", "service_start": "2026-08-04T06:30:00+08:00",
                           "service_end": "2026-08-04T06:40:00+08:00", "queue_id": "a"}])
    setup = _setup(segments=[{"id": "s0", "start_time": "22:00:00", "end_time": "23:00:00", "active_queue_ids": None}])
    records, provenance = normalize_analysis_input(frame, setup)
    assert records[0]["time"] == "2026-08-03 s0 UTC"
    assert provenance["data_dates"] == {"first": "2026-08-03", "last": "2026-08-03"}


def test_aggregate_files_store_no_dates():
    frame = pd.DataFrame([{"time": "2026-08-03 08:00-09:00", "lambda": 4, "mu": 6, "c": 2}])
    _, provenance = normalize_analysis_input(frame, _setup(queue_structure="shared_queue", queue_ids=[], segments=[]))
    assert "data_dates" not in provenance
    assert data_dates({"ok": True, **provenance}, [{"time": "2026-08-03 08:00-09:00"}]) is None


# --- recovered for datasets stored before B11 ----------------------------------------------------


def test_recovered_from_hourly_and_segment_labels():
    validation = {"ok": True, "schema": "customer_events"}
    records = [{"time": "2026-08-05 08:00 UTC"}, {"time": "2026-08-03 s1 UTC"}, {"time": "2026-08-04 09:00 UTC"}]
    assert data_dates(validation, records) == {"first": "2026-08-03", "last": "2026-08-05", "source": PERIOD_LABELS}


def test_stored_dates_win_over_labels():
    validation = {"schema": "customer_events", "data_dates": {"first": "2026-01-01", "last": "2026-01-02"}}
    assert data_dates(validation, [{"time": "2026-08-05 08:00 UTC"}])["first"] == "2026-01-01"


@pytest.mark.parametrize("validation, records", [
    ({"schema": "customer_events", "period_basis": "representative_day"}, [{"time": "s1"}]),
    ({"schema": "customer_events", "period_basis": "representative_day"}, [{"time": "2026-08-05 08:00 UTC"}]),
    ({"schema": "customer_events"}, [{"time": "2026-08-05 08:00 UTC"}, {"time": "08:00-09:00"}]),
    ({"schema": "customer_events"}, [{"time": "2026-02-30 08:00 UTC"}]),
    ({"schema": "customer_events"}, [{"time": "2026-08-05 08:00"}]),
    ({"schema": "customer_events"}, []),
    ({"schema": "aggregate"}, [{"time": "2026-08-05 08:00 UTC"}]),
    ({}, [{"time": "2026-08-05 08:00 UTC"}]),
    (None, None),
])
def test_unrecoverable_dates_are_none(validation, records):
    assert data_dates(validation, records) is None


# --- API ----------------------------------------------------------------------------------------


def _upload(client, analysis_id: int, content: bytes):
    response = client.post(f"/analyses/{analysis_id}/datasets", headers=csrf_header(client),
                           files={"file": ("input.csv", content, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()["dataset"]


def test_dataset_responses_carry_data_dates(db_engine, client):
    create_user(db_engine, "owner@example.com", "pw")
    assert login(client, "owner@example.com", "pw") == 200
    created = client.post("/analyses", headers=csrf_header(client), json={"name": "Branch", "queue_setup": SETUP})
    analysis = created.json()["analysis"]["id"]
    events = _upload(client, analysis, SHARED_EVENTS)
    assert events["data_dates"] == {"first": "2026-09-08", "last": "2026-09-10", "source": STORED}
    assert events["validation"]["data_dates"] == {"first": "2026-09-08", "last": "2026-09-10"}
    aggregate = _upload(client, analysis, AGGREGATE)
    assert aggregate["data_dates"] is None
    listed = {item["id"]: item["data_dates"] for item in client.get(f"/analyses/{analysis}/datasets").json()["datasets"]}
    assert listed == {events["id"]: events["data_dates"], aggregate["id"]: None}
    everywhere = {item["id"]: item["data_dates"] for item in client.get("/datasets").json()["datasets"]}
    assert everywhere == listed
    assert client.get(f"/datasets/{events['id']}").json()["dataset"]["data_dates"] == events["data_dates"]
