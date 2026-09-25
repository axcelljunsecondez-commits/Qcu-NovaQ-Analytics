"""Event playback for one continuous shared-queue DES replication (Phase 4).

A playback is one identifiable replication, regenerated from its root entropy and replication
index with a full trace. Its events are the engine's own trace in engine order; nothing is
synthesized, and events from different replications are never combined. An independent replay
rebuilds the line and every server from the events alone and raises
``PlaybackConsistencyError`` if the events contradict the engine's results.

Spec: docs/superpowers/specs/2026-09-25-shared-queue-des-replications-playback.md.
Nothing legacy imports this module. No API or frontend uses it yet.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from numbers import Integral
from typing import Any, NoReturn

import numpy as np

from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    ENGINE_VERSION,
    HARD_CUTOFF,
    simulate_shared_replication,
)
from backend.queueing_engine.simulation.shared_replications import replication_row

PLAYBACK_VERSION = "novaq-shared-des-playback-v1"

EVENT_TYPES = {
    "arrival": (
        "The customer arrives and joins the line. The engine appends every arrival to the line and "
        "service may start at the same time, so there is no separate queue-entry event."
    ),
    "service_start": "A free accepting server takes the customer at the head of the line.",
    "service_end": "Service completion, which is also the departure (no post-service time is modeled).",
    "server_open": "A server opens and accepts customers.",
    "server_drain_start": "A busy server is designated to drain: it takes no new customer.",
    "server_drain_complete": "A draining server finishes its customer and closes.",
    "server_close": "An idle server closes (a staffing decrease, or at or after closing).",
    "server_reactivate": "A draining server accepts customers again (a staffing increase).",
    "capacity_change": "A staffing segment starts; accepting servers now equal its schedule.",
    "closing": "The closing policy is applied at the closing time.",
    "unserved_at_close": "A customer still waiting leaves unserved at closing.",
}

IDLE, BUSY, DRAINING, CLOSED = "IDLE", "BUSY", "DRAINING", "CLOSED"
_FINISHED_DRAIN = "DRAINING_FINISHED"  # a draining server between its service_end and drain_complete
_TOLERANCE = {"rel": 1e-9, "abs": 1e-12}


class PlaybackConsistencyError(Exception):
    """The events contradict the engine's results, so no playback is produced."""


def _close_enough(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=_TOLERANCE["rel"], abs_tol=_TOLERANCE["abs"])


def replay_events(result: dict[str, Any], staffing_segments: Sequence[StaffingSegment]) -> dict[str, Any]:
    """Rebuild the line and servers from the events alone; raise on any inconsistency.

    Returns the per-event states, customer and server timelines, and time integrals
    derived from the events only.
    """
    if result["trace_truncated"]:
        raise PlaybackConsistencyError("The trace is truncated; a playback needs every event.")
    end = result["closing"]["closing_hours"]
    policy = result["closing"]["policy"]
    scheduled = {segment.segment_id: int(segment.servers) for segment in staffing_segments}
    queue: deque[int] = deque()
    servers: dict[int, list[Any]] = {}  # server id -> [state, customer id, state since]
    intervals: dict[int, list[dict[str, Any]]] = {}
    customers: dict[int, dict[str, Any]] = {}
    integrals = {"queue_in": 0.0, "queue_after": 0.0, "busy_in": 0.0, "busy_after": 0.0,
                 "present_in": 0.0, "present_after": 0.0}
    closed_phase = False
    last = 0.0
    states = []

    def fail(seq: int, message: str) -> NoReturn:
        raise PlaybackConsistencyError(f"Event {seq}: {message}")

    def set_state(server_id: int, state: str, customer_id: int | None, at: float) -> None:
        previous = servers.get(server_id)
        if previous is not None and previous[0] in (IDLE, BUSY, DRAINING) and at > previous[2]:
            intervals[server_id].append(
                {"state": previous[0], "customer_id": previous[1], "start": previous[2], "end": at}
            )
        servers[server_id] = [state, customer_id, at]

    for seq, event in enumerate(result["trace"]):
        at, kind = event["t"], event["type"]
        customer_id, server_id = event["customer_id"], event["server_id"]
        if kind not in EVENT_TYPES:
            fail(seq, f"unknown event type {kind!r}")
        if at < last:
            fail(seq, "time goes backwards")
        elapsed = at - last
        if elapsed > 0:
            present = sum(1 for state in servers.values() if state[0] != CLOSED)
            busy = sum(1 for state in servers.values() if state[0] in (BUSY, DRAINING) and state[1] is not None)
            suffix = "after" if closed_phase else "in"
            integrals[f"queue_{suffix}"] += len(queue) * elapsed
            integrals[f"busy_{suffix}"] += busy * elapsed
            integrals[f"present_{suffix}"] += present * elapsed
        last = at
        if closed_phase and kind in ("arrival", "capacity_change", "server_open", "server_drain_start",
                                     "server_reactivate", "closing"):
            fail(seq, f"{kind} after closing")
        if closed_phase and event["segment_id"] is not None:
            fail(seq, "an event after closing names a staffing segment")
        if not closed_phase and at < end and event["segment_id"] is None:
            fail(seq, "an event before closing names no staffing segment")

        state = servers.get(server_id) if server_id is not None else None
        if kind == "arrival":
            if customer_id != len(customers) + 1:
                fail(seq, "customer ids must arrive in order 1, 2, ...")
            customers[customer_id] = {"customer_id": customer_id, "arrival_hours": at, "service_start_hours": None,
                                      "service_end_hours": None, "server_id": None, "status": None}
            queue.append(customer_id)
        elif kind == "service_start":
            if not queue or queue[0] != customer_id:
                fail(seq, "service must start with the customer at the head of the line")
            if state is None or state[0] != IDLE:
                fail(seq, "service must start on an idle accepting server")
            if closed_phase and policy == HARD_CUTOFF:
                fail(seq, "no service may start after a hard cutoff")
            queue.popleft()
            customers[customer_id].update(service_start_hours=at, server_id=server_id)
            set_state(server_id, BUSY, customer_id, at)
        elif kind == "service_end":
            if state is None or state[0] not in (BUSY, DRAINING) or state[1] != customer_id:
                fail(seq, "service must end on the server serving that customer")
            customers[customer_id].update(service_end_hours=at, status="departed")
            set_state(server_id, IDLE if state[0] == BUSY else _FINISHED_DRAIN, None, at)
        elif kind == "server_drain_complete":
            if state is None or state[0] != _FINISHED_DRAIN:
                fail(seq, "a drain completes only right after its server's service ends")
            set_state(server_id, CLOSED, None, at)
        elif kind == "server_open":
            if state is not None and state[0] != CLOSED:
                fail(seq, "only a closed or new server can open")
            intervals.setdefault(server_id, [])
            set_state(server_id, IDLE, None, at)
        elif kind == "server_close":
            if state is None or state[0] != IDLE:
                fail(seq, "only an idle server can close")
            set_state(server_id, CLOSED, None, at)
        elif kind == "server_drain_start":
            if state is None or state[0] != BUSY:
                fail(seq, "only a busy server can start draining")
            set_state(server_id, DRAINING, state[1], at)
        elif kind == "server_reactivate":
            if state is None or state[0] != DRAINING:
                fail(seq, "only a draining server can be reactivated")
            set_state(server_id, BUSY, state[1], at)
        elif kind == "capacity_change":
            accepting = sum(1 for item in servers.values() if item[0] in (IDLE, BUSY))
            if accepting != scheduled[event["segment_id"]]:
                fail(seq, "accepting servers differ from the segment's schedule")
        elif kind == "closing":
            if at != end:
                fail(seq, "closing must happen at the horizon end")
            closed_phase = True
        elif kind == "unserved_at_close":
            if not queue or queue[0] != customer_id:
                fail(seq, "unserved customers leave in line order")
            queue.popleft()
            customers[customer_id]["status"] = "unserved_at_close"

        if any(item[0] == _FINISHED_DRAIN for item in servers.values()) and kind != "service_end":
            fail(seq, "a finished draining server must close at its service end")
        if len(queue) != event["queue_len_after"]:
            fail(seq, "the rebuilt line length differs from the engine's queue_len_after")
        states.append({
            "queue_len_after": len(queue),
            "queue_head_after": queue[0] if queue else None,
            "servers_idle_after": sum(1 for item in servers.values() if item[0] == IDLE),
            "servers_busy_after": sum(1 for item in servers.values() if item[0] == BUSY),
            "servers_draining_after": sum(1 for item in servers.values() if item[0] == DRAINING),
            "server_state_after": servers[server_id][0] if server_id is not None else None,
        })

    if not closed_phase:
        raise PlaybackConsistencyError("The trace has no closing event.")
    if queue or any(item[0] != CLOSED for item in servers.values()):
        raise PlaybackConsistencyError("The run ends with a customer waiting or a server open.")
    if any(row["status"] is None for row in customers.values()):
        raise PlaybackConsistencyError("A customer has no final outcome.")
    closing_releases = [item["end"] for rows in intervals.values() for item in rows if item["end"] >= end]
    return {
        "states": states,
        "customers": [customers[key] for key in sorted(customers)],
        "servers": [{"server_id": key, "intervals": intervals[key]} for key in sorted(intervals)],
        "integrals": integrals,
        "last_release": max(closing_releases, default=end),
    }


def _check_against_engine(result: dict[str, Any], replay: dict[str, Any], row: dict[str, Any]) -> list[str]:
    """Compare replay-derived values with the engine's customer rows and summary row."""
    checks = []
    engine_customers = result["customers"]
    if len(engine_customers) != len(replay["customers"]):
        raise PlaybackConsistencyError("The events and the engine disagree on the number of customers.")
    for engine, derived in zip(engine_customers, replay["customers"]):
        for key in ("customer_id", "arrival_hours", "service_start_hours", "service_end_hours", "server_id", "status"):
            if engine[key] != derived[key]:
                raise PlaybackConsistencyError(f"Customer {engine['customer_id']}: {key} differs from the events.")
    checks.append("customer timelines equal the engine's customer rows")

    integrals = replay["integrals"]
    served = [item for item in replay["customers"] if item["status"] == "departed"]
    derived = {
        "served": len(served),
        "unserved": sum(1 for item in replay["customers"] if item["status"] == "unserved_at_close"),
        "wait_sum_hours": math.fsum(item["service_start_hours"] - item["arrival_hours"] for item in served),
        "waiting_hours_before_close": integrals["queue_in"],
        "waiting_hours_after_close": integrals["queue_after"],
        "busy_server_hours_in_horizon": integrals["busy_in"],
        "busy_server_hours_after_close": integrals["busy_after"],
        "available_server_hours_in_horizon": integrals["present_in"],
        "overtime_server_hours": integrals["present_after"],
        "overrun_hours": replay["last_release"] - result["closing"]["closing_hours"],
    }
    for key, value in derived.items():
        if not _close_enough(float(value), float(row[key])):
            raise PlaybackConsistencyError(f"{key} from the events ({value}) differs from the summary ({row[key]}).")
    checks.append("counts, waits, waiting-hours, busy and available server-hours, and overrun equal the summary")
    return checks


def build_playback(
    result: dict[str, Any],
    staffing_segments: Sequence[StaffingSegment],
    *,
    replication_index: int,
    root_entropy: int,
) -> dict[str, Any]:
    """A checked playback of one full-trace replication result."""
    replay = replay_events(result, staffing_segments)
    row = replication_row(result, replication_index)
    checks = [
        "time never goes backwards", "first come, first served at every service start",
        "every server transition is legal", "the rebuilt line length equals queue_len_after at every event",
        "accepting servers equal the schedule after every staffing change",
        "no arrival or staffing change after closing", "every customer ends departed or unserved",
        "every server ends closed",
    ] + _check_against_engine(result, replay, row)
    events = [
        {"seq": seq, **{key: event[key] for key in ("t", "type", "segment_id", "customer_id", "server_id")},
         **state}
        for seq, (event, state) in enumerate(zip(result["trace"], replay["states"]))
    ]
    reason = "hard_cutoff" if result["closing"]["policy"] == HARD_CUTOFF else "no_eligible_server"
    customers = [
        {**item, "wait_hours": None if item["service_start_hours"] is None
         else item["service_start_hours"] - item["arrival_hours"],
         "unserved_reason": reason if item["status"] == "unserved_at_close" else None}
        for item in replay["customers"]
    ]
    return {
        "replication": {
            "replication_index": replication_index,
            "root_entropy": root_entropy,
            "spawn_key": list(result["provenance"]["spawn_key"]),
            "closing_policy": result["closing"]["policy"],
            "engine_version": result["provenance"]["engine_version"],
        },
        "events": events,
        "customers": customers,
        "servers": replay["servers"],
        "closing": {key: result["closing"][key] for key in (
            "policy", "closing_hours", "at_close", "unserved_customer_ids", "overrun_hours")},
        "summary": row,
        "consistency_checks": checks,
        "event_types": dict(EVENT_TYPES),
        "provenance": {
            "playback_version": PLAYBACK_VERSION,
            "source": (
                "One replication regenerated from SeedSequence(entropy=root_entropy, spawn_key=(replication_index,)) "
                "with a full trace. Events are the engine's own trace in engine order; the per-event states "
                "come from an independent replay of those events. Nothing is synthesized or interpolated, "
                "and no events from other replications are included."
            ),
            "time_unit": "hours from the horizon start",
            "segment_id_after_closing": "Events at or after closing carry segment_id None.",
        },
    }


def _whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool) and int(value) >= 0


def prepare_shared_playback(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    *,
    root_entropy: int,
    replication_index: int,
    closing_policy: str,
) -> dict[str, Any]:
    """Regenerate replication ``replication_index`` of the run with ``root_entropy`` and prepare its playback."""
    problems = []
    if not _whole(root_entropy):
        problems.append("root_entropy must be a whole number, 0 or more.")
    if not _whole(replication_index):
        problems.append("replication_index must be a whole number, 0 or more.")
    if problems:
        raise SharedSegmentError(problems)
    child = np.random.SeedSequence(entropy=root_entropy, spawn_key=(replication_index,))
    result = simulate_shared_replication(
        horizon, demand_periods, staffing_segments,
        seed_sequence=child, closing_policy=closing_policy, max_trace_events=None,
    )
    return build_playback(result, staffing_segments, replication_index=replication_index, root_entropy=root_entropy)


def playback_from_replications(replication_result: dict[str, Any], replication_index: int) -> dict[str, Any]:
    """Playback of one replication of a ``run_shared_replications`` result, checked against its stored row."""
    provenance = replication_result["provenance"]
    if provenance["engine_version"] != ENGINE_VERSION:
        raise PlaybackConsistencyError(
            f"The run used engine {provenance['engine_version']}, not {ENGINE_VERSION}; it cannot be regenerated exactly."
        )
    if not _whole(replication_index) or replication_index >= provenance["replications"]:
        raise SharedSegmentError([f"replication_index must be from 0 to {provenance['replications'] - 1}."])
    inputs = provenance["inputs"]
    segments = [StaffingSegment(**item) for item in inputs["staffing_segments"]]
    playback = prepare_shared_playback(
        OperatingHorizon(**inputs["horizon"]),
        [DemandPeriod(**item) for item in inputs["demand_periods"]],
        segments,
        root_entropy=provenance["root_entropy"],
        replication_index=replication_index,
        closing_policy=provenance["closing_policy"],
    )
    stored = replication_result["replications"][replication_index]
    regenerated = playback["summary"]
    differing = [key for key in regenerated if stored.get(key) != regenerated[key]]
    if differing:
        raise PlaybackConsistencyError(
            f"Regenerated replication {replication_index} differs from the stored row in: {', '.join(differing)}."
        )
    playback["consistency_checks"].append("the regenerated summary equals the stored replication row exactly")
    return playback
