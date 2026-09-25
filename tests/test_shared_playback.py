"""Phase 4 playback of one continuous shared-queue DES replication.

The playback's events must be the engine's own trace. The independent replay must reproduce
the engine's customers and summary, must reject tampered event streams, and a playback taken
from a replication run must regenerate exactly the stored replication.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    DRAIN,
    HARD_CUTOFF,
    simulate_prescribed,
    simulate_shared_replication,
)
from backend.queueing_engine.simulation.shared_playback import (
    EVENT_TYPES,
    PlaybackConsistencyError,
    build_playback,
    playback_from_replications,
    prepare_shared_playback,
    replay_events,
)
from backend.queueing_engine.simulation.shared_replications import run_shared_replications
from tests.test_shared_replications import MULTI_CLOSED_AT_END, OVERLOAD

MULTI_OPEN_AT_END = (
    MULTI_CLOSED_AT_END[0], MULTI_CLOSED_AT_END[1],
    MULTI_CLOSED_AT_END[2][:-1] + [StaffingSegment("f", 660, 780, 3)],
)


def hourly(*servers: int) -> tuple[OperatingHorizon, list, list]:
    hours = len(servers)
    return (OperatingHorizon(0, 60 * hours), [DemandPeriod("d", 0, 60 * hours, 1.0, 1.0)],
            [StaffingSegment(f"h{i}", 60 * i, 60 * (i + 1), c) for i, c in enumerate(servers)])


def exact_playback(policy: str) -> dict:
    """Phase 3A exact case: server 2 drains from 1.0 and is busy at closing (2.0); customer 3 waits."""
    config = hourly(2, 1)
    result = simulate_prescribed(*config, [(0.125, 2.5), (0.25, 1.875), (1.5, 0.25)], closing_policy=policy)
    result["provenance"]["spawn_key"] = []  # prescribed runs have no seed; identity fields for the test only
    return build_playback(result, config[2], replication_index=0, root_entropy=0)


def test_exact_case_states_and_server_timelines():
    playback = exact_playback(DRAIN)
    closing = next(event for event in playback["events"] if event["type"] == "closing")
    assert (closing["t"], closing["queue_len_after"], closing["queue_head_after"]) == (2.0, 1, 3)
    assert (closing["servers_busy_after"], closing["servers_draining_after"], closing["servers_idle_after"]) == (1, 1, 0)
    after = [(event["t"], event["type"], event["customer_id"], event["server_id"])
             for event in playback["events"] if event["seq"] > closing["seq"]]
    assert after == [
        (2.125, "service_end", 2, 2), (2.125, "server_drain_complete", 2, 2),
        (2.625, "service_end", 1, 1), (2.625, "service_start", 3, 1),
        (2.875, "service_end", 3, 1), (2.875, "server_close", None, 1),
    ]
    servers = {item["server_id"]: [(i["state"], i["customer_id"], i["start"], i["end"]) for i in item["intervals"]]
               for item in playback["servers"]}
    assert servers[1] == [("IDLE", None, 0.0, 0.125), ("BUSY", 1, 0.125, 2.625), ("BUSY", 3, 2.625, 2.875)]
    assert servers[2] == [("IDLE", None, 0.0, 0.25), ("BUSY", 2, 0.25, 1.0), ("DRAINING", 2, 1.0, 2.125)]
    customers = {row["customer_id"]: row for row in playback["customers"]}
    assert (customers[3]["wait_hours"], customers[3]["status"]) == (1.125, "departed")
    assert playback["summary"]["overtime_server_hours"] == 1.0

    cutoff = exact_playback(HARD_CUTOFF)
    unserved = [event for event in cutoff["events"] if event["type"] == "unserved_at_close"]
    assert [(event["t"], event["customer_id"], event["queue_len_after"]) for event in unserved] == [(2.0, 3, 0)]
    assert {row["customer_id"]: row["unserved_reason"] for row in cutoff["customers"]}[3] == "hard_cutoff"
    assert not any(e["type"] == "service_start" and e["seq"] > unserved[0]["seq"] for e in cutoff["events"])


def test_playback_events_are_the_engine_trace():
    playback = prepare_shared_playback(*OVERLOAD, root_entropy=77, replication_index=4, closing_policy=DRAIN)
    child = np.random.SeedSequence(entropy=77, spawn_key=(4,))
    trace = simulate_shared_replication(*OVERLOAD, seed_sequence=child, closing_policy=DRAIN)["trace"]
    keys = ("t", "type", "segment_id", "customer_id", "server_id", "queue_len_after")
    assert [{key: event[key] for key in keys} for event in playback["events"]] == [
        {key: event[key] for key in keys} for event in trace
    ]
    assert [event["seq"] for event in playback["events"]] == list(range(len(trace)))
    assert {event["type"] for event in playback["events"]} <= set(EVENT_TYPES)
    assert playback["replication"] == {
        "replication_index": 4, "root_entropy": 77, "spawn_key": [4], "closing_policy": DRAIN,
        "engine_version": "novaq-shared-continuous-des-v2",
    }


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
@pytest.mark.parametrize("config", [OVERLOAD, MULTI_CLOSED_AT_END, MULTI_OPEN_AT_END],
                         ids=["overload", "multi_closed_at_end", "multi_open_at_end"])
def test_every_playback_regenerates_its_stored_replication(config, policy):
    run = run_shared_replications(*config, replications=12, seed=31, closing_policy=policy)
    kinds: set[str] = set()
    for index in range(12):
        playback = playback_from_replications(run, index)
        assert playback["summary"] == {key: run["replications"][index][key] for key in playback["summary"]}
        assert "the regenerated summary equals the stored replication row exactly" in playback["consistency_checks"]
        assert [event["type"] for event in playback["events"]].count("closing") == 1
        kinds |= {event["type"] for event in playback["events"]}
    # The runs exercise staffing changes, drains, closing, and (where possible) unserved outcomes.
    assert {"server_open", "server_close", "capacity_change", "closing", "service_start", "service_end"} <= kinds
    if config is not OVERLOAD:
        assert "server_drain_start" in kinds
    assert ("unserved_at_close" in kinds) == (policy == HARD_CUTOFF or config is MULTI_CLOSED_AT_END)


def test_playback_is_reproducible():
    first = prepare_shared_playback(*MULTI_OPEN_AT_END, root_entropy=5, replication_index=2, closing_policy=DRAIN)
    assert first == prepare_shared_playback(*MULTI_OPEN_AT_END, root_entropy=5, replication_index=2,
                                            closing_policy=DRAIN)
    other = prepare_shared_playback(*MULTI_OPEN_AT_END, root_entropy=5, replication_index=3, closing_policy=DRAIN)
    assert other["events"] != first["events"]


# ── Tampered events are rejected ─────────────────────────────────────────────


def full_result() -> tuple[dict, list]:
    child = np.random.SeedSequence(entropy=9, spawn_key=(0,))
    return simulate_shared_replication(*OVERLOAD, seed_sequence=child, closing_policy=DRAIN), OVERLOAD[2]


def tampered(edit) -> tuple[dict, list]:
    result, segments = full_result()
    result = copy.deepcopy(result)
    edit(result["trace"])
    return result, segments


def first_index(trace: list, kind: str, after: int = 0) -> int:
    return next(i for i, event in enumerate(trace) if event["type"] == kind and i >= after)


def swap_first_two_service_starts(trace: list) -> None:
    i = first_index(trace, "service_start")
    j = first_index(trace, "service_start", i + 1)
    trace[i]["customer_id"], trace[j]["customer_id"] = trace[j]["customer_id"], trace[i]["customer_id"]


@pytest.mark.parametrize(("edit", "message"), [
    (swap_first_two_service_starts, "service must start with the customer at the head of the line"),
    (lambda trace: trace[first_index(trace, "arrival")].update(queue_len_after=7),
     "rebuilt line length differs from the engine's queue_len_after"),
    (lambda trace: trace.pop(first_index(trace, "closing")), "no closing event"),
    (lambda trace: trace[first_index(trace, "service_end")].update(t=-1.0), "time goes backwards"),
    (lambda trace: trace.insert(len(trace) - 1, {**trace[first_index(trace, "arrival")], "t": trace[-1]["t"],
                                                 "segment_id": None}), "arrival after closing"),
    (lambda trace: trace.pop(first_index(trace, "server_close", first_index(trace, "closing"))),
     "ends with a customer waiting or a server open"),
], ids=["fcfs", "queue_length", "no_closing", "time_backwards", "arrival_after_closing", "server_left_open"])
def test_replay_rejects_inconsistent_events(edit, message):
    result, segments = tampered(edit)
    with pytest.raises(PlaybackConsistencyError, match=message):
        replay_events(result, segments)


def test_replay_rejects_a_truncated_trace_and_a_changed_engine_row():
    child = np.random.SeedSequence(entropy=9, spawn_key=(0,))
    capped = simulate_shared_replication(*OVERLOAD, seed_sequence=child, closing_policy=DRAIN, max_trace_events=10)
    with pytest.raises(PlaybackConsistencyError, match="truncated"):
        replay_events(capped, OVERLOAD[2])
    result, segments = full_result()
    result = copy.deepcopy(result)
    result["customers"][0]["service_end_hours"] += 0.5
    with pytest.raises(PlaybackConsistencyError, match="service_end_hours differs"):
        build_playback(result, segments, replication_index=0, root_entropy=9)


def test_playback_refuses_a_mismatched_or_foreign_replication_run():
    run = run_shared_replications(*OVERLOAD, replications=3, seed=12, closing_policy=HARD_CUTOFF)
    altered = copy.deepcopy(run)
    altered["replications"][1]["unserved"] += 1
    with pytest.raises(PlaybackConsistencyError, match="differs from the stored row in: unserved"):
        playback_from_replications(altered, 1)
    foreign = copy.deepcopy(run)
    foreign["provenance"]["engine_version"] = "novaq-shared-continuous-des-v1"
    with pytest.raises(PlaybackConsistencyError, match="cannot be regenerated exactly"):
        playback_from_replications(foreign, 0)
    for index in (3, -1, True):
        with pytest.raises(SharedSegmentError, match="replication_index must be from 0 to 2"):
            playback_from_replications(run, index)


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"root_entropy": -1}, "root_entropy"),
    ({"replication_index": True}, "replication_index"),
    ({"closing_policy": "OBSERVE"}, "closing_policy must be DRAIN or HARD_CUTOFF"),
])
def test_invalid_playback_requests_are_rejected(kwargs, message):
    arguments = {"root_entropy": 1, "replication_index": 0, "closing_policy": DRAIN, **kwargs}
    with pytest.raises(SharedSegmentError, match=message):
        prepare_shared_playback(*OVERLOAD, **arguments)


def test_used_seed_sequences_are_refused():
    child = np.random.SeedSequence(entropy=3, spawn_key=(0,))
    child.spawn(1)
    with pytest.raises(SharedSegmentError, match="unused numpy SeedSequence"):
        simulate_shared_replication(*OVERLOAD, seed_sequence=child, closing_policy=DRAIN)
