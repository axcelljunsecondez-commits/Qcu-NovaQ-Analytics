"""B3: read-only results for any processed file of an analysis (spec D15, plan Phase 7).

``GET /analyses/{id}/current`` and ``GET /analyses/{id}/workflow/observed-wait`` take an optional
``dataset_id``: owner-checked, ``validation.ok`` required, and the response names the dataset.
Omitted, both keep reading the current planning file. Plans, selection and Decision are untouched.

Data: SYNTHETIC (users, analyses and uploads made for the test).
"""

from __future__ import annotations

from tests.helpers import create_user, csrf_header, login
from tests.test_current_dataset import NO_DATASET_DETAIL, SETUP, insert_dataset

PLANNING_EVENTS = (
    b"arrival_time,service_start,service_end\n"
    b"2026-09-08T08:05:00Z,2026-09-08T08:10:00Z,2026-09-08T08:40:00Z\n"
    b"2026-09-08T08:35:00Z,2026-09-08T08:40:00Z,2026-09-08T08:55:00Z\n"
)
REVIEW_EVENTS = (
    b"arrival_time,service_start,service_end\n"
    b"2026-03-02T08:05:00Z,2026-03-02T08:35:00Z,2026-03-02T08:50:00Z\n"
    b"2026-03-02T08:20:00Z,2026-03-02T08:50:00Z,2026-03-02T08:58:00Z\n"
    b"2026-03-02T08:30:00Z,2026-03-02T08:58:00Z,2026-03-02T09:05:00Z\n"
)


def sign_in(db_engine, client, email: str = "owner@example.com") -> int:
    user = create_user(db_engine, email, "pw")
    assert login(client, email, "pw") == 200
    return user.id


def create_analysis(client) -> int:
    response = client.post("/analyses", headers=csrf_header(client), json={"name": "Branch", "queue_setup": SETUP})
    assert response.status_code == 201, response.text
    return response.json()["analysis"]["id"]


def upload(client, analysis_id: int, content: bytes, purpose: str = "planning") -> int:
    response = client.post(f"/analyses/{analysis_id}/datasets", headers=csrf_header(client),
                           params={"purpose": purpose}, files={"file": ("events.csv", content, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()["dataset"]["id"]


def current(client, analysis_id: int, dataset_id: int | None = None):
    params = {} if dataset_id is None else {"dataset_id": dataset_id}
    return client.get(f"/analyses/{analysis_id}/current", params=params)


def observed(client, analysis_id: int, dataset_id: int | None = None):
    params = {} if dataset_id is None else {"dataset_id": dataset_id}
    return client.get(f"/analyses/{analysis_id}/workflow/observed-wait", params=params)


def test_omitted_dataset_id_keeps_reading_the_planning_file(db_engine, client):
    sign_in(db_engine, client)
    analysis = create_analysis(client)
    planning = upload(client, analysis, PLANNING_EVENTS)
    upload(client, analysis, REVIEW_EVENTS, "review")
    body = current(client, analysis).json()
    assert (body["dataset"]["id"], body["dataset"]["is_current"]) == (planning, True)
    assert observed(client, analysis).json()["dataset_id"] == planning


def test_a_review_file_is_readable_and_named_without_becoming_current(db_engine, client):
    sign_in(db_engine, client)
    analysis = create_analysis(client)
    planning = upload(client, analysis, PLANNING_EVENTS)
    review = upload(client, analysis, REVIEW_EVENTS, "review")
    planning_body = current(client, analysis, planning).json()
    review_body = current(client, analysis, review).json()
    assert (planning_body["dataset"]["id"], planning_body["dataset"]["is_current"]) == (planning, True)
    assert (review_body["dataset"]["id"], review_body["dataset"]["is_current"]) == (review, False)
    assert review_body["dataset"]["purpose"] == "review"
    assert review_body["dataset"]["data_dates"]["first"] == "2026-03-02"
    # Each file's numbers come from that file: three arrivals versus two in the same hour.
    assert [row["lambda"] for row in review_body["rows"]] == [3.0]
    assert [row["lambda"] for row in planning_body["rows"]] == [2.0]
    review_wait = observed(client, analysis, review).json()
    planning_wait = observed(client, analysis, planning).json()
    assert review_wait["dataset_id"] == review and planning_wait["dataset_id"] == planning
    assert review_wait["day_observed_wait"] != planning_wait["day_observed_wait"]
    # Reading the review file changed nothing: the default is still the planning file.
    assert current(client, analysis).json()["dataset"]["id"] == planning


def test_an_older_planning_file_is_readable_and_not_current(db_engine, client):
    sign_in(db_engine, client)
    analysis = create_analysis(client)
    older = upload(client, analysis, REVIEW_EVENTS)
    newer = upload(client, analysis, PLANNING_EVENTS)
    body = current(client, analysis, older).json()
    assert (body["dataset"]["id"], body["dataset"]["is_current"]) == (older, False)
    assert current(client, analysis).json()["dataset"]["id"] == newer


def test_another_users_file_is_not_found(db_engine, client):
    sign_in(db_engine, client, "other@example.com")
    foreign = upload(client, create_analysis(client), PLANNING_EVENTS)
    client.post("/auth/logout", headers=csrf_header(client))
    sign_in(db_engine, client)
    analysis = create_analysis(client)
    upload(client, analysis, PLANNING_EVENTS)
    for response in (current(client, analysis, foreign), observed(client, analysis, foreign)):
        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found in this Analysis."


def test_a_file_of_another_analysis_or_a_missing_file_is_not_found(db_engine, client):
    sign_in(db_engine, client)
    first = create_analysis(client)
    second = create_analysis(client)
    elsewhere = upload(client, second, PLANNING_EVENTS)
    upload(client, first, PLANNING_EVENTS)
    for dataset_id in (elsewhere, 999999):
        assert current(client, first, dataset_id).status_code == 404
        assert observed(client, first, dataset_id).status_code == 404


def test_an_unprocessed_file_is_refused(db_engine, client, session_factory):
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    invalid = insert_dataset(session_factory, owner_id=owner, analysis_id=analysis, report={"ok": False})
    for response in (current(client, analysis, invalid), observed(client, analysis, invalid)):
        assert response.status_code == 409
        assert response.json()["detail"] == {"code": "dataset_not_processed"}
    assert current(client, analysis).json()["detail"] == NO_DATASET_DETAIL


def test_signed_out_reads_are_refused(db_engine, client):
    sign_in(db_engine, client)
    analysis = create_analysis(client)
    planning = upload(client, analysis, PLANNING_EVENTS)
    client.post("/auth/logout", headers=csrf_header(client))
    assert current(client, analysis, planning).status_code == 401


# --- B12: totals the browser must not add up -----------------------------------------------------


def test_busiest_period_sums_separate_lines_on_the_server(db_engine, client):
    sign_in(db_engine, client)
    setup = {**SETUP, "queue_structure": "separate_queues", "fixed_server_count": None, "queue_ids": ["A", "B"]}
    created = client.post("/analyses", headers=csrf_header(client), json={"name": "Lanes", "queue_setup": setup})
    analysis = created.json()["analysis"]["id"]
    # 08:00 has the busiest single line (A, 9/h) but 09:00 has more customers in all (5 + 6 = 11/h).
    lanes = (b"time,queue_id,lambda,mu,c,variance\n"
             b"08:00-09:00,A,9,12,1,0.01\n08:00-09:00,B,1,12,1,0.01\n"
             b"09:00-10:00,A,5,12,1,0.01\n09:00-10:00,B,6,12,1,0.01\n")
    upload(client, analysis, lanes)
    body = current(client, analysis).json()
    assert body["arrivals_by_period"] == [{"time": "08:00-09:00", "arrivals_per_hour": 10.0},
                                          {"time": "09:00-10:00", "arrivals_per_hour": 11.0}]
    assert body["busiest_period"] == {"time": "09:00-10:00", "arrivals_per_hour": 11.0}


def test_busiest_period_keeps_the_first_on_a_tie_and_skips_unknown_rates():
    from backend.api.analyses import arrivals_by_period, busiest_period

    periods = arrivals_by_period([{"time": "a", "lambda": 4}, {"time": "b", "lambda": 4},
                                  {"time": "c", "lambda": 3}, {"time": "c", "lambda": None}, "junk"])
    assert periods == [{"time": "a", "arrivals_per_hour": 4.0}, {"time": "b", "arrivals_per_hour": 4.0},
                       {"time": "c", "arrivals_per_hour": None}]
    assert busiest_period(periods) == {"time": "a", "arrivals_per_hour": 4.0}
    assert busiest_period(arrivals_by_period([{"time": "a", "lambda": "x"}])) is None
    assert busiest_period(arrivals_by_period([])) is None
    assert arrivals_by_period([{"time": "a", "lambda": -1}]) == [{"time": "a", "arrivals_per_hour": None}]
