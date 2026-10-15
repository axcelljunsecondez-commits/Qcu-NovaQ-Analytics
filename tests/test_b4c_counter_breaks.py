"""B4c: breaks taken by any counter on a shared line, in the continuous full-day run.

Specs: docs/superpowers/specs/2026-10-09-b4c-shared-line-breaks.md (approved 2026-10-09) and its addendum
docs/superpowers/specs/2026-10-12-b4c-addendum-anonymous-counter-breaks.md (owner answers OD-B4c-4/5/6 = A on
2026-10-12; addendum approved 2026-10-12, OD-B4c-A1). Tests are written before the engine code.

Data: SYNTHETIC (setups and customer records made for the test).
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    BREAKS_SUFFIX,
    DRAIN,
    ENGINE_VERSION,
    HARD_CUTOFF,
    RECORDED_ENGINE_VERSION,
    CounterBreak,
    simulate_prescribed,
    simulate_shared_replication,
)
from backend.queueing_engine.simulation.shared_playback import PlaybackConsistencyError, playback_from_replications
from backend.queueing_engine.simulation.shared_replications import run_shared_replications
from tests.helpers import create_user, csrf_header, login
from tests.test_b4b_recorded_service import EVENT_SETUP, _records_csv


def day(*spec: tuple[str, float, float, float, int]):
    """(id, start hour, end hour, arrival rate, counters) per period; service rate 1, so work = hours."""
    horizon = OperatingHorizon(int(spec[0][1] * 60), int(spec[-1][2] * 60))
    periods = [DemandPeriod(pid, int(a * 60), int(b * 60), lam, 1.0) for pid, a, b, lam, _ in spec]
    segments = [StaffingSegment(pid, int(a * 60), int(b * 60), c) for pid, a, b, _, c in spec]
    return horizon, periods, segments


def run(spec, arrivals, breaks, policy=DRAIN):
    horizon, periods, segments = day(*spec)
    return simulate_prescribed(horizon, periods, segments, arrivals, closing_policy=policy, counter_breaks=breaks)


def served(result: dict) -> list[tuple]:
    return [(row["service_start_hours"], row["service_end_hours"], row["server_id"]) for row in result["customers"]]


def only_break(result: dict) -> dict:
    (row,) = result["breaks"]
    return row


# ── Exact engine cases (addendum section 7, tests 1-6) ──────────────────────


def test_no_breaks_is_the_unchanged_engine():
    spec = [("d", 0, 2, 2.0, 1)]
    arrivals = [(0.0, 0.25), (0.625, 0.25)]
    horizon, periods, segments = day(*spec)
    plain = simulate_prescribed(horizon, periods, segments, arrivals, closing_policy=DRAIN)
    assert run(spec, arrivals, []) == plain
    assert run(spec, arrivals, None) == plain
    assert "breaks" not in plain and plain["provenance"]["engine_version"] == ENGINE_VERSION


def test_a_free_counter_starts_its_break_on_time_for_the_full_length():
    result = run([("d", 0, 2, 2.0, 1)], [(0.0, 0.25), (0.625, 0.25)], [CounterBreak("b1", 0.5, 0.25)])
    assert only_break(result) == {"break_id": "b1", "scheduled_start_hours": 0.5, "duration_hours": 0.25,
                                  "server_id": 1, "start_hours": 0.5, "end_hours": 0.75, "delay_hours": 0.0,
                                  "outcome": "completed"}
    # The second customer arrives during the break and is served when it ends.
    assert served(result) == [(0.0, 0.25, 1), (0.75, 1.0, 1)]
    assert result["totals"]["break_server_hours"] == 0.25
    assert result["totals"]["present_server_hours"] == 2.0  # a counter on break is still staffed
    assert result["provenance"]["engine_version"] == ENGINE_VERSION + BREAKS_SUFFIX


def test_a_busy_counter_finishes_its_customer_then_takes_the_break_before_the_next_customer():
    result = run([("d", 0, 2, 2.0, 1)], [(0.25, 0.5), (0.625, 0.125)], [CounterBreak("b1", 0.5, 0.25)])
    row = only_break(result)
    assert (row["start_hours"], row["end_hours"], row["delay_hours"]) == (0.75, 1.0, 0.25)
    assert served(result) == [(0.25, 0.75, 1), (1.0, 1.125, 1)]


def test_the_other_counter_keeps_serving_and_no_counter_replaces_the_one_on_break():
    result = run([("d", 0, 1, 2.0, 2)], [(0.125, 0.25), (0.25, 0.25)], [CounterBreak("b1", 0.0, 0.5)])
    assert only_break(result)["server_id"] == 1
    assert served(result) == [(0.125, 0.375, 2), (0.375, 0.625, 2)]
    totals = result["totals"]
    assert (totals["servers_used"], totals["present_server_hours"], totals["busy_server_hours"]) == (2, 2.0, 0.5)
    assert totals["break_server_hours"] == 0.5


def test_a_staffing_drop_closes_a_counter_on_break_before_a_busy_one():
    result = run([("s1", 0, 1, 2.0, 2), ("s2", 1, 2, 2.0, 1)], [(0.875, 0.5)], [CounterBreak("b1", 0.75, 0.5)])
    row = only_break(result)
    assert (row["server_id"], row["end_hours"], row["outcome"]) == (1, 1.0, "staffing_change")
    assert served(result) == [(0.875, 1.375, 2)]
    assert {"t": 1.0, "kind": "close_from_break", "server_id": 1, "segment_id": "s2",
            "customer_id": None} in result["capacity_transitions"]


def test_a_staffing_drop_closes_an_idle_counter_before_a_counter_on_break():
    result = run([("s1", 0, 1, 2.0, 2), ("s2", 1, 2, 2.0, 1)], [], [CounterBreak("b1", 0.75, 0.5)])
    row = only_break(result)
    assert (row["server_id"], row["end_hours"], row["outcome"]) == (1, 1.25, "completed")
    closes = [item for item in result["capacity_transitions"] if item["kind"] == "close" and item["t"] == 1.0]
    assert [item["server_id"] for item in closes] == [2]


@pytest.mark.parametrize(("policy", "reason"), [(DRAIN, "no_eligible_server"), (HARD_CUTOFF, "hard_cutoff")])
def test_a_break_in_progress_ends_at_closing_and_its_counter_does_not_join_the_crew(policy, reason):
    result = run([("d", 0, 1, 2.0, 1)], [(0.875, 0.25)], [CounterBreak("b1", 0.75, 0.5)], policy)
    row = only_break(result)
    assert (row["start_hours"], row["end_hours"], row["outcome"]) == (0.75, 1.0, "truncated_by_closing")
    customer = result["customers"][0]
    assert (customer["status"], customer["unserved_reason"]) == ("unserved_at_close", reason)
    assert result["closing"]["at_close"]["on_break_server_ids"] == [1]
    assert result["closing"]["unserved_possible"] is True


def test_a_due_break_not_started_by_closing_is_cancelled():
    result = run([("d", 0, 1, 2.0, 1)], [(0.5, 0.75)], [CounterBreak("b1", 0.75, 0.25)])
    row = only_break(result)
    assert (row["start_hours"], row["end_hours"], row["outcome"]) == (None, None, "cancelled_at_closing")
    assert served(result) == [(0.5, 1.25, 1)]  # DRAIN: the busy counter finishes after closing
    assert [event["type"] for event in result["trace"]].count("break_cancelled_at_closing") == 1


@pytest.mark.parametrize("breaks", [
    [CounterBreak("b1", 2.0, 0.25)], [CounterBreak("b1", -0.25, 0.25)], [CounterBreak("b1", 0.5, 0.0)],
    [CounterBreak("b1", 0.5, float("nan"))], [CounterBreak("b1", 0.5, 0.25), CounterBreak("b1", 1.0, 0.25)],
    [CounterBreak("", 0.5, 0.25)], [("b1", 0.5, 0.25)],
])
def test_unusable_breaks_are_refused(breaks):
    with pytest.raises(SharedSegmentError):
        run([("d", 0, 2, 2.0, 1)], [], breaks)


# ── Seeded runs, replay, and recorded service times together (test 8) ───────


def _seeded_day():
    return day(("s1", 0, 1, 6.0, 2), ("s2", 1, 2, 9.0, 3), ("s3", 2, 3, 4.0, 1))


BREAKS = [CounterBreak("b1", 0.5, 0.25), CounterBreak("b2", 1.25, 0.5), CounterBreak("b3", 2.75, 0.5)]
SAMPLES = {"s1": [0.25, 0.125, 0.375], "s2": [0.25, 0.5], "s3": [0.125]}


@pytest.mark.parametrize(("samples", "version"), [(None, ENGINE_VERSION), (SAMPLES, RECORDED_ENGINE_VERSION)])
def test_every_replication_with_breaks_replays_consistently(samples, version):
    horizon, periods, segments = _seeded_day()
    result = run_shared_replications(horizon, periods, segments, replications=4, seed=17, closing_policy=DRAIN,
                                     service_samples=samples, counter_breaks=BREAKS)
    assert result["provenance"]["engine_version"] == version + BREAKS_SUFFIX
    assert result["provenance"]["inputs"]["counter_breaks"] == [
        {"break_id": item.break_id, "start_hours": item.start_hours, "duration_hours": item.duration_hours}
        for item in BREAKS]
    assert result["summary"]["breaks"]["break_server_hours"]["n"] == 4
    for index in range(4):
        playback = playback_from_replications(result, index)
        kinds = [event["type"] for event in playback["events"]]
        assert kinds.count("break_due") == 3
        assert kinds.count("break_start") + kinds.count("break_cancelled_at_closing") == 3
        assert all("servers_on_break_after" in event for event in playback["events"])
    assert result == run_shared_replications(horizon, periods, segments, replications=4, seed=17,
                                             closing_policy=DRAIN, service_samples=samples, counter_breaks=BREAKS)


def test_a_replay_without_its_breaks_is_refused():
    horizon, periods, segments = _seeded_day()
    result = run_shared_replications(horizon, periods, segments, replications=1, seed=3, closing_policy=DRAIN,
                                     counter_breaks=BREAKS)
    inputs = {key: value for key, value in result["provenance"]["inputs"].items() if key != "counter_breaks"}
    with pytest.raises(PlaybackConsistencyError, match="counter breaks do not match"):
        playback_from_replications({**result, "provenance": {**result["provenance"], "inputs": inputs}}, 0)


def test_breaks_draw_no_random_numbers():
    horizon, periods, segments = _seeded_day()
    plain = simulate_shared_replication(horizon, periods, segments, seed_sequence=np.random.SeedSequence(5),
                                        closing_policy=DRAIN)
    with_breaks = simulate_shared_replication(horizon, periods, segments, seed_sequence=np.random.SeedSequence(5),
                                              closing_policy=DRAIN, counter_breaks=BREAKS)
    assert [(row["arrival_hours"], row["unit_work"]) for row in with_breaks["customers"]] == [
        (row["arrival_hours"], row["unit_work"]) for row in plain["customers"]]


def test_the_replay_refuses_a_customer_served_while_a_break_waits():
    from backend.queueing_engine.simulation.shared_playback import replay_events

    def event(t, kind, customer, server, waiting):
        return {"t": t, "type": kind, "segment_id": "d", "customer_id": customer, "server_id": server,
                "queue_len_after": waiting}

    trace = [event(0.0, "server_open", None, 1, 0), event(0.0, "capacity_change", None, None, 0),
             event(0.25, "break_due", None, None, 0), event(0.25, "arrival", 1, None, 1),
             event(0.25, "service_start", 1, 1, 0)]
    result = {"trace": trace, "trace_truncated": False, "closing": {"closing_hours": 1.0, "policy": DRAIN}}
    with pytest.raises(PlaybackConsistencyError, match="waiting break before a waiting customer"):
        replay_events(result, [StaffingSegment("d", 0, 60, 1)])


# ── The real path ───────────────────────────────────────────────────────────


def test_a_shared_counter_break_is_saved_run_and_replayed_through_the_public_routes(db_engine, client):
    create_user(db_engine, "owner@example.com", "pw")
    assert login(client, "owner@example.com", "pw") == 200
    setup = {**EVENT_SETUP,
             "segments": [{"id": "s1", "start_time": "08:00:00", "end_time": "09:00:00", "active_queue_ids": None},
                          {"id": "s2", "start_time": "09:00:00", "end_time": "10:00:00", "active_queue_ids": None}],
             "counter_breaks": [{"scheduled_start_time": "08:30:00", "duration_minutes": 15}]}
    created = client.post("/analyses", headers=csrf_header(client), json={"name": "Shared breaks", "queue_setup": setup})
    assert created.status_code == 201, created.text
    analysis_id = created.json()["analysis"]["id"]
    assert created.json()["analysis"]["queue_setup"]["counter_breaks"] == [
        {"scheduled_start_time": "08:30:00", "duration_minutes": 15}]
    upload = client.post(f"/analyses/{analysis_id}/datasets", headers=csrf_header(client),
                         files={"file": ("records.csv", _records_csv(), "text/csv")})
    assert upload.status_code == 201, upload.text
    assert client.put(f"/analyses/{analysis_id}/closing-policy", headers=csrf_header(client),
                      json={"closing_policy": "DRAIN"}).status_code == 200
    run = client.post(f"/analyses/{analysis_id}/continuous/runs", headers=csrf_header(client),
                      json={"plan": "current", "replications": 2, "seed": 7})
    assert run.status_code == 200, run.text
    evidence = run.json()["evidence"]
    assert evidence["result"]["provenance"]["engine_version"].endswith("+breaks-v1")
    replay = client.get(f"/analyses/{analysis_id}/continuous/runs/{evidence['id']}/replications/0/playback")
    assert replay.status_code == 200, replay.text
    kinds = [event["type"] for event in replay.json()["playback"]["events"]]
    assert "break_due" in kinds and "break_start" in kinds and "break_end" in kinds


# ── Refusals (addendum section 4) and the Setup (section 2) ─────────────────


def _two_breaks_at_nine(db_engine, client, breaks: list[dict]):
    """Current staffing has 2 counters per segment (the data); the plan has 1."""
    from tests.test_b4b_recorded_service import ALL_ROWS, _ready

    setup = {**EVENT_SETUP, "counter_breaks": breaks}
    ids = _ready(client, db_engine, ALL_ROWS, setup=setup, servers=[1, 1, 1])
    response = client.post(f"/analyses/{ids['analysis_id']}/continuous/compatibility", headers=csrf_header(client),
                           json={})
    assert response.status_code == 200, response.text
    return ids, response.json()["plans"]


def test_a_break_the_plan_cannot_staff_refuses_only_that_run_and_names_the_break(db_engine, client):
    two = [{"scheduled_start_time": "09:00:00", "duration_minutes": 30},
           {"scheduled_start_time": "09:00:00", "duration_minutes": 15}]
    ids, plans = _two_breaks_at_nine(db_engine, client, two)
    assert plans["current"]["compatible"] is True and plans["current"]["counter_breaks"] == 2
    reason = next(item for item in plans["suggested"]["reasons"] if item["code"] == "breaks_not_staffed")
    assert reason["problems"] == [
        "Break at 09:00 needs a counter, but this staffing has 1 counter(s) and 2 break(s) at 09:00.",
        "Break at 09:00 needs a counter, but this staffing has 1 counter(s) and 2 break(s) at 09:00."]
    suggested = client.post(f"/analyses/{ids['analysis_id']}/continuous/runs", headers=csrf_header(client),
                            json={"plan": "suggested", "replications": 1, "seed": 7})
    assert suggested.status_code == 422
    current = client.post(f"/analyses/{ids['analysis_id']}/continuous/runs", headers=csrf_header(client),
                          json={"plan": "current", "replications": 1, "seed": 7})
    assert current.status_code == 200, current.text
    stored = current.json()["evidence"]
    assert stored["params"]["counter_breaks"] == 2
    assert [item["start_hours"] for item in stored["result"]["provenance"]["inputs"]["counter_breaks"]] == [1.0, 1.0]


def test_a_break_outside_the_operating_hours_is_refused(db_engine, client):
    _, plans = _two_breaks_at_nine(db_engine, client, [{"scheduled_start_time": "07:30:00", "duration_minutes": 15}])
    for plan in ("current", "suggested"):
        reason = next(item for item in plans[plan]["reasons"] if item["code"] == "breaks_outside_hours")
        assert reason["problems"] == ["Break at 07:30 is outside the operating hours 08:00-11:00."]


def test_counter_breaks_are_for_shared_lines_and_an_empty_list_keeps_the_fingerprint(db_engine, client):
    from backend.api.scenarios import setup_fingerprint

    create_user(db_engine, "owner@example.com", "pw")
    assert login(client, "owner@example.com", "pw") == 200
    separate = {"queue_structure": "separate_queues", "queue_ids": ["a"], "fixed_server_count": 1,
                "counter_breaks": [{"scheduled_start_time": "09:00:00", "duration_minutes": 15}]}
    refused = client.post("/analyses", headers=csrf_header(client), json={"name": "Lanes", "queue_setup": separate})
    assert refused.status_code == 422
    assert "Counter breaks are only supported for one shared line" in refused.text
    created = client.post("/analyses", headers=csrf_header(client), json={"name": "Shared", "queue_setup": EVENT_SETUP})
    analysis = created.json()["analysis"]
    assert "counter_breaks" not in analysis["queue_setup"]
    before = setup_fingerprint(analysis["queue_setup"])
    saved = client.patch(f"/analyses/{analysis['id']}", headers=csrf_header(client),
                         json={"queue_setup": {**analysis["queue_setup"], "counter_breaks": []}})
    assert saved.status_code == 200, saved.text
    assert setup_fingerprint(saved.json()["analysis"]["queue_setup"]) == before
    with_break = client.patch(f"/analyses/{analysis['id']}", headers=csrf_header(client), json={"queue_setup": {
        **analysis["queue_setup"], "counter_breaks": [{"scheduled_start_time": "09:00", "duration_minutes": 15}]}})
    assert setup_fingerprint(with_break.json()["analysis"]["queue_setup"]) != before
