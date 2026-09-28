"""Continuous shared-queue DES (Phase 3 of the shared-queue enhancement).

One event-driven simulation of one operating horizon for a shared M/M/c queue with
piecewise-constant arrival and service rates and a staffing schedule that may change
between segments. There is no restart, warm-up, or reset at any boundary: customers keep
their identity, arrival time, and waiting history for the whole run.

Specs: docs/superpowers/specs/2026-09-24-shared-queue-continuous-des.md and, for closing,
docs/superpowers/specs/2026-09-25-shared-queue-closing-policy.md (Phase 3A).

The engine reports hours and counts only; it holds no monetary assumption. Costs come from
``services/shared_day_cost.py`` with rates the caller supplies.

Nothing legacy imports this module, and it imports nothing from the legacy simulation.
The legacy shared DES in ``simulation.py`` and all separate-queue code are unchanged.
"""

from __future__ import annotations

import bisect
import heapq
import itertools
import math
from collections import deque
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from numbers import Integral, Real
from typing import Any

import numpy as np

from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    validate_timeline,
)

ENGINE_VERSION = "novaq-shared-continuous-des-v2"

# Same-time order: a completion frees its server before a capacity change is applied, and an
# arrival at a boundary sees the new capacity. Ties among arrivals follow customer id.
_COMPLETION, _CAPACITY, _ARRIVAL = 0, 1, 2

CLOSED, IDLE, BUSY, DRAINING = "CLOSED", "IDLE", "BUSY", "DRAINING"

# Closing policies approved by the product owner on 2026-09-25 (Phase 3A). There is no default.
DRAIN, HARD_CUTOFF = "DRAIN", "HARD_CUTOFF"
CLOSING_POLICIES = (DRAIN, HARD_CUTOFF)
CLOSING_RULES = {
    DRAIN: (
        "DRAIN: arrivals stop at closing, and completions at the closing time are processed first. "
        "The accepting servers on duty at closing keep serving the line first come, first served, with "
        "no overrun cap; a server draining at closing only finishes its own customer. Each server closes "
        "once it is idle and nobody is waiting. Services that start after closing use the final demand "
        "period's service rate. If no accepting server is on duty at closing, customers still waiting "
        "are recorded as unserved_at_close (reason no_eligible_server)."
    ),
    HARD_CUTOFF: (
        "HARD_CUTOFF: arrivals stop at closing, and completions at the closing time are processed first. "
        "Customers still waiting are recorded as unserved_at_close (reason hard_cutoff). Services already "
        "under way finish; no service starts at or after closing. Each server closes when it is idle."
    ),
}
SERVER_HOURS_MEANING = (
    "Server-hours are modeled service-capacity hours: the time a modeled server position is open. "
    "They are not necessarily paid employee-hours; shift minimums, breaks, handovers, and paid time "
    "outside open positions are not modeled."
)

EVENT_ORDER = (
    "At equal times: service completions, then capacity changes, then arrivals (by customer id). "
    "After each event, free accepting servers take waiting customers first come, first served; "
    "the lowest free server number serves first."
)
TRANSITION_POLICY = (
    "Non-preemptive. A capacity decrease closes idle servers first (highest number first), then "
    "designates busy servers to drain (highest number first): a draining server takes no new "
    "customer, finishes its current service, and closes at that completion. A capacity increase "
    "reactivates draining servers first (lowest number first), then reopens closed servers "
    "(lowest number first), creating new server numbers only when needed. Accepting servers always "
    "equal the schedule; draining servers are recorded as time above schedule."
)
ASSUMPTIONS = [
    "Arrivals form a Poisson process with the demand period's rate: exponential gaps restarted at "
    "each period start (exact by memorylessness). A period with arrival rate 0 has no arrivals.",
    "Each customer carries a unit work amount drawn once from Exp(1); service lasts work / mu, "
    "with mu the service rate of the demand period in which service starts. A started service is "
    "never redrawn, rescaled, or interrupted.",
    "The system is empty at the horizon start (initial condition).",
    "The horizon end is the closing time. Services that start after closing (DRAIN only) use the "
    "final demand period's service rate, because no demand data exists after closing.",
    "Waiting-time means are over customers who started service, including starts after closing "
    "under DRAIN. Unserved customers are counted separately; their elapsed waits at closing are "
    "censored, not completed waits.",
    "Simulated values are one stochastic realization of the configured model, not observations "
    "and not steady-state expectations.",
]


@dataclass
class _Server:
    server_id: int
    state: str = CLOSED
    customer_id: int | None = None


@dataclass
class _Clock:
    last: float = 0.0  # time up to which areas have been accumulated
    segment: int = 0  # index of the staffing segment in force
    closed: bool = False  # True from the closing time (the horizon end) onward


@dataclass
class _Customer:
    customer_id: int
    arrival: float
    work: float
    arrival_segment: int
    service_start: float | None = None
    service_end: float | None = None
    server_id: int | None = None
    departed: bool = False
    unserved_reason: str | None = None


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _hours(minute: int, horizon: OperatingHorizon) -> float:
    return (minute - horizon.start_minute) / 60.0


def simulate_prescribed(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    arrivals: Sequence[tuple[float, float]],
    *,
    closing_policy: str,
    max_trace_events: int | None = None,
) -> dict[str, Any]:
    """Run the continuous engine on prescribed (arrival hour, unit work) pairs.

    Arrival hours are measured from the horizon start. ``closing_policy`` (``DRAIN`` or
    ``HARD_CUTOFF``) has no default. This entry point is deterministic;
    ``simulate_shared_day`` draws the pairs from seeded random streams.
    """
    validate_timeline(horizon, demand_periods, staffing_segments)
    end = _hours(horizon.end_minute, horizon)
    period_starts = [_hours(period.start_minute, horizon) for period in demand_periods]
    segment_starts = [_hours(segment.start_minute, horizon) for segment in staffing_segments]
    segment_hours = [(segment.end_minute - segment.start_minute) / 60.0 for segment in staffing_segments]

    problems = []
    if closing_policy not in CLOSING_POLICIES:
        problems.append("closing_policy must be DRAIN or HARD_CUTOFF; there is no default.")
    if max_trace_events is not None and (
        not isinstance(max_trace_events, Integral) or isinstance(max_trace_events, bool) or max_trace_events < 0
    ):
        problems.append("max_trace_events must be a whole number, 0 or more, or omitted.")
    previous = -math.inf
    for position, pair in enumerate(arrivals, start=1):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            problems.append(f"Arrival {position} must be an (hour, work) pair.")
            continue
        at, work = pair
        if not _is_finite_real(at) or not 0 <= float(at) < end:
            problems.append(f"Arrival {position} time must lie in the horizon [0, {end:g}) hours.")
            continue
        if float(at) < previous:
            problems.append(f"Arrival {position} is earlier than the arrival before it.")
        previous = float(at)
        if not _is_finite_real(work) or float(work) <= 0:
            problems.append(f"Arrival {position} work must be a finite number above 0.")
        period = demand_periods[bisect.bisect_right(period_starts, float(at)) - 1]
        if float(period.arrival_rate_per_hour) == 0:
            problems.append(
                f"Arrival {position} falls in demand period {period.period_id}, whose arrival rate is 0."
            )
    if problems:
        raise SharedSegmentError(problems)

    def segment_at(hour: float) -> int:
        return bisect.bisect_right(segment_starts, hour) - 1

    def mu_at(hour: float) -> float:
        # At or after closing this is the final demand period's rate (approved Phase 3A rule).
        return float(demand_periods[bisect.bisect_right(period_starts, hour) - 1].service_rate_per_hour)

    servers: list[_Server] = []
    customers = [
        _Customer(customer_id, float(at), float(work), segment_at(float(at)))
        for customer_id, (at, work) in enumerate(arrivals, start=1)
    ]
    queue: deque[int] = deque()
    heap: list[tuple[float, int, int, int]] = []  # (time, order, sequence, payload)
    sequence = itertools.count()
    for index, start in enumerate(segment_starts):
        heapq.heappush(heap, (start, _CAPACITY, next(sequence), index))
    for customer in customers:
        heapq.heappush(heap, (customer.arrival, _ARRIVAL, next(sequence), customer.customer_id))

    trace: list[dict[str, Any]] = []
    truncated = False
    transitions: list[dict[str, Any]] = []
    drains: dict[int, dict[str, Any]] = {}
    drain_records: list[dict[str, Any]] = []
    areas = [{"queue": 0.0, "busy": 0.0, "present": 0.0} for _ in staffing_segments]
    after_close = {"queue": 0.0, "busy": 0.0, "present": 0.0}
    max_queue = [0 for _ in staffing_segments]
    clock = _Clock()

    def segment_id_now() -> str | None:
        # Events at or after closing belong to no staffing segment.
        return None if clock.closed else staffing_segments[clock.segment].segment_id

    def record(at: float, kind: str, customer_id: int | None, server_id: int | None) -> None:
        nonlocal truncated
        if max_trace_events is not None and len(trace) >= max_trace_events:
            truncated = True
            return
        trace.append({
            "t": at, "type": kind, "segment_id": segment_id_now(),
            "customer_id": customer_id, "server_id": server_id, "queue_len_after": len(queue),
        })

    def advance(now: float) -> None:
        elapsed = now - clock.last
        if elapsed > 0:
            area = after_close if clock.closed else areas[clock.segment]
            area["queue"] += len(queue) * elapsed
            area["busy"] += sum(1 for server in servers if server.state in (BUSY, DRAINING)) * elapsed
            area["present"] += sum(1 for server in servers if server.state != CLOSED) * elapsed
        clock.last = now

    def transition(at: float, kind: str, server: _Server) -> None:
        transitions.append({
            "t": at, "kind": kind, "server_id": server.server_id,
            "segment_id": segment_id_now(),
            "customer_id": server.customer_id,
        })
        record(at, f"server_{kind}", server.customer_id, server.server_id)

    def assign(now: float) -> None:
        while queue:
            free = [server for server in servers if server.state == IDLE]
            if not free:
                break
            server = min(free, key=lambda item: item.server_id)
            customer = customers[queue.popleft() - 1]
            duration = customer.work / mu_at(now)
            customer.service_start, customer.service_end = now, now + duration
            customer.server_id = server.server_id
            server.state, server.customer_id = BUSY, customer.customer_id
            heapq.heappush(heap, (customer.service_end, _COMPLETION, next(sequence), customer.customer_id))
            record(now, "service_start", customer.customer_id, server.server_id)
        if not clock.closed:
            segment = clock.segment
            max_queue[segment] = max(max_queue[segment], len(queue))

    def apply_capacity(now: float, index: int) -> None:
        clock.segment = index
        target = int(staffing_segments[index].servers)
        accepting = [server for server in servers if server.state in (IDLE, BUSY)]
        if target < len(accepting):
            excess = len(accepting) - target
            idle = sorted((s for s in accepting if s.state == IDLE), key=lambda s: -s.server_id)
            busy = sorted((s for s in accepting if s.state == BUSY), key=lambda s: -s.server_id)
            for server in idle[:excess]:
                server.state = CLOSED
                transition(now, "close", server)
            for server in busy[:max(0, excess - len(idle))]:
                server.state = DRAINING
                transition(now, "drain_start", server)
                drains[server.server_id] = {
                    "server_id": server.server_id, "customer_id": server.customer_id,
                    "designated_at": now, "released_at": None, "segment_id": staffing_segments[index].segment_id,
                }
                drain_records.append(drains[server.server_id])
        elif target > len(accepting):
            needed = target - len(accepting)
            for server in sorted((s for s in servers if s.state == DRAINING), key=lambda s: s.server_id):
                if not needed:
                    break
                server.state = BUSY
                drain = drains.pop(server.server_id)
                drain["released_at"], drain["reactivated_at"] = None, now
                transition(now, "reactivate", server)
                needed -= 1
            for server in sorted((s for s in servers if s.state == CLOSED), key=lambda s: s.server_id):
                if not needed:
                    break
                server.state = IDLE
                transition(now, "open", server)
                needed -= 1
            while needed:
                server = _Server(len(servers) + 1, IDLE)
                servers.append(server)
                transition(now, "open", server)
                needed -= 1
        record(now, "capacity_change", None, None)

    def complete(now: float, customer_id: int) -> None:
        customer = customers[customer_id - 1]
        customer.departed = True
        server = servers[int(customer.server_id) - 1]  # type: ignore[arg-type]
        record(now, "service_end", customer_id, server.server_id)
        if server.state == DRAINING:
            drain = drains.pop(server.server_id)
            drain["released_at"] = now
            server.state = CLOSED
            transition(now, "drain_complete", server)
            server.customer_id = None
        else:
            server.state, server.customer_id = IDLE, None

    while heap and heap[0][0] < end:
        now, order, _, payload = heapq.heappop(heap)
        advance(now)
        if order == _COMPLETION:
            complete(now, payload)
        elif order == _CAPACITY:
            apply_capacity(now, payload)
        else:
            queue.append(payload)
            record(now, "arrival", payload, None)
        assign(now)
    advance(end)

    # Closing (Phase 3A). Every arrival and capacity change lies before closing, so only service
    # completions remain in the heap. Completions at exactly the closing time are processed first,
    # without assigning anyone, so those customers depart at closing without overtime.
    clock.closed = True
    while heap and heap[0][0] == end:
        now, _, _, payload = heapq.heappop(heap)
        complete(now, payload)
    at_close = {
        "waiting_customer_ids": list(queue),
        "in_service_customer_ids": sorted(
            int(server.customer_id) for server in servers  # type: ignore[arg-type]
            if server.state in (BUSY, DRAINING)
        ),
        "accepting_server_ids": [server.server_id for server in servers if server.state in (IDLE, BUSY)],
        "draining_server_ids": [server.server_id for server in servers if server.state == DRAINING],
    }
    record(end, "closing", None, None)

    def release_idle(now: float) -> None:
        # After closing a server closes once it is idle and nobody is waiting.
        if queue:
            return
        for server in servers:
            if server.state == IDLE:
                server.state = CLOSED
                transition(now, "close", server)

    if closing_policy == HARD_CUTOFF or not at_close["accepting_server_ids"]:
        # HARD_CUTOFF, or DRAIN with nobody on duty: waiting customers cannot be served, so they
        # are recorded now instead of waiting forever.
        reason = "hard_cutoff" if closing_policy == HARD_CUTOFF else "no_eligible_server"
        while queue:
            customer = customers[queue.popleft() - 1]
            customer.unserved_reason = reason
            record(end, "unserved_at_close", customer.customer_id, None)
    else:
        assign(end)
    release_idle(end)
    while heap:
        now, _, _, payload = heapq.heappop(heap)
        advance(now)
        complete(now, payload)
        if closing_policy == DRAIN:
            assign(now)
        release_idle(now)
    # The run ends with every customer resolved and every server closed.
    assert not queue and all(server.state == CLOSED for server in servers)
    assert all(customer.departed or customer.unserved_reason for customer in customers)

    return _summarize(
        horizon, demand_periods, staffing_segments, arrivals, customers, servers,
        segment_hours, areas, max_queue, transitions, drain_records, trace, truncated, end,
        max_trace_events, closing_policy, at_close, after_close,
    )


def _mean(values: Sequence[float]) -> float | None:
    return math.fsum(values) / len(values) if values else None


def _unserved_possible(closing_policy: str, staffing_segments) -> tuple[bool, str]:
    """Whether the configured closing can leave customers unserved, with the reason."""
    if closing_policy == HARD_CUTOFF:
        return True, "HARD_CUTOFF records every customer still waiting at closing as unserved."
    final = staffing_segments[-1]
    if int(final.servers) == 0:
        return True, (
            f"DRAIN with 0 servers scheduled in the final staffing segment ({final.segment_id}): nobody "
            "is on duty at closing to serve customers still waiting."
        )
    return False, (
        f"DRAIN with {int(final.servers)} accepting server(s) on duty at closing serves every admitted "
        "customer, so no customer can be left unserved."
    )


def _summarize(
    horizon, demand_periods, staffing_segments, arrivals, customers, servers,
    segment_hours, areas, max_queue, transitions, drain_records, trace, truncated, end,
    max_trace_events, closing_policy, at_close, after_close,
) -> dict[str, Any]:
    customer_rows = []
    for customer in customers:
        status = "departed" if customer.departed else "unserved_at_close"
        wait = None if customer.service_start is None else customer.service_start - customer.arrival
        customer_rows.append({
            "customer_id": customer.customer_id,
            "arrival_hours": customer.arrival,
            "unit_work": customer.work,
            "arrival_segment_id": staffing_segments[customer.arrival_segment].segment_id,
            "service_start_hours": customer.service_start,
            "service_end_hours": customer.service_end,
            "server_id": customer.server_id,
            "wait_hours": wait,
            "elapsed_wait_at_close_hours": end - customer.arrival if status == "unserved_at_close" else None,
            "status": status,
            "unserved_reason": customer.unserved_reason,
        })
    # Unserved customers never started service, and everyone who started service departed.
    assert all((row["status"] == "unserved_at_close") == (row["service_start_hours"] is None) for row in customer_rows)

    segments = []
    for index, segment in enumerate(staffing_segments):
        rows = [row for row in customer_rows if customers[row["customer_id"] - 1].arrival_segment == index]
        started = [row["wait_hours"] for row in rows if row["wait_hours"] is not None]
        hours = segment_hours[index]
        area = areas[index]
        scheduled = int(segment.servers) * hours
        segments.append({
            "segment_id": segment.segment_id,
            "scheduled_servers": int(segment.servers),
            "duration_hours": hours,
            "arrivals": len(rows),
            "service_starts": len(started),
            "mean_wait_hours": _mean(started),
            "waited_count": sum(1 for wait in started if wait > 0),
            "unserved_at_close": sum(1 for row in rows if row["status"] == "unserved_at_close"),
            "time_average_queue": area["queue"] / hours,
            "max_queue": max_queue[index],
            "busy_server_hours": area["busy"],
            "present_server_hours": area["present"],
            "scheduled_server_hours": scheduled,
            "server_hours_above_schedule": area["present"] - scheduled,
            "utilization_of_present": area["busy"] / area["present"] if area["present"] > 0 else None,
        })

    started_waits = [row["wait_hours"] for row in customer_rows if row["wait_hours"] is not None]
    counts = {status: sum(1 for row in customer_rows if row["status"] == status)
              for status in ("departed", "unserved_at_close")}
    total_hours = end
    unserved_ids = [row["customer_id"] for row in customer_rows if row["status"] == "unserved_at_close"]
    unserved_possible, unserved_possible_reason = _unserved_possible(closing_policy, staffing_segments)
    assert unserved_possible or not unserved_ids
    closing_releases = [item["t"] for item in transitions if item["segment_id"] is None]
    last_release = max(closing_releases, default=end)
    in_horizon_present = math.fsum(area["present"] for area in areas)
    in_horizon_queue = math.fsum(area["queue"] for area in areas)
    return {
        "customers": customer_rows,
        "segments": segments,
        "totals": {
            "arrivals": len(customer_rows),
            **counts,
            "customer_conservation": len(customer_rows) == sum(counts.values()),
            "service_starts": len(started_waits),
            "mean_wait_hours": _mean(started_waits),
            "waited_count": sum(1 for wait in started_waits if wait > 0),
            "time_average_queue": in_horizon_queue / total_hours,
            "queue_customer_hours": in_horizon_queue,
            "max_queue": max(max_queue),
            "busy_server_hours": math.fsum(area["busy"] for area in areas),
            "present_server_hours": in_horizon_present,
            "scheduled_server_hours": math.fsum(row["scheduled_server_hours"] for row in segments),
            "server_hours_above_schedule": math.fsum(row["server_hours_above_schedule"] for row in segments),
            "servers_used": len(servers),
            "scope": (
                "Queue, server-hour, and max-queue values cover the horizon [start, closing) only; "
                "after-closing values are under closing. Customer counts and waits cover the whole run."
            ),
        },
        "capacity_transitions": transitions,
        "drains": drain_records,
        "closing": {
            "policy": closing_policy,
            "rule": CLOSING_RULES[closing_policy],
            "closing_hours": end,
            "at_close": at_close,
            "unserved_customer_ids": unserved_ids,
            "unserved_possible": unserved_possible,
            "unserved_possible_reason": unserved_possible_reason,
            "service_starts_after_close": sum(
                1 for row in customer_rows
                if row["service_start_hours"] is not None and row["service_start_hours"] >= end
            ),
            "completions_after_close": sum(
                1 for row in customer_rows if row["service_end_hours"] is not None and row["service_end_hours"] > end
            ),
            "after_close_server_hours": after_close["present"],
            "after_close_busy_server_hours": after_close["busy"],
            "after_close_waiting_customer_hours": after_close["queue"],
            "last_server_release_hours": last_release,
            "overrun_hours": last_release - end,
        },
        "cost_quantities": {
            "closing_policy": closing_policy,
            "regular_server_hours": in_horizon_present,
            "overtime_server_hours": after_close["present"],
            "total_waiting_customer_hours": math.fsum([in_horizon_queue, after_close["queue"]]),
            "unserved_customer_count": len(unserved_ids),
            "unserved_possible": unserved_possible,
            "definitions": {
                "regular_server_hours": (
                    "Present server-hours inside the horizon: scheduled hours plus above-schedule drain "
                    "time during the day."
                ),
                "overtime_server_hours": "Present server-hours after closing.",
                "total_waiting_customer_hours": "Customer-hours spent waiting, before and after closing.",
                "unserved_customer_count": "Customers recorded as unserved_at_close.",
            },
            "server_hours_meaning": SERVER_HOURS_MEANING,
        },
        "trace": trace,
        "trace_truncated": truncated,
        "provenance": {
            "engine_version": ENGINE_VERSION,
            "metric_provenance": "des_continuous_horizon",
            "time_unit": "hours from the horizon start",
            "trace_fields": (
                "queue_len_after is the number of waiting customers right after the event; an arriving "
                "customer counts as waiting until its service_start event, which may share the arrival time. "
                "Events and capacity transitions at or after closing carry segment_id None."
            ),
            "event_order": EVENT_ORDER,
            "transition_policy": TRANSITION_POLICY,
            "closing_policy": closing_policy,
            "closing_rule": CLOSING_RULES[closing_policy],
            "server_hours_meaning": SERVER_HOURS_MEANING,
            "assumptions": list(ASSUMPTIONS),
            "max_trace_events": max_trace_events,
            "inputs": {
                "horizon": asdict(horizon),
                "demand_periods": [asdict(period) for period in demand_periods],
                "staffing_segments": [asdict(segment) for segment in staffing_segments],
                "arrival_count": len(arrivals),
            },
        },
    }


def simulate_shared_day(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    *,
    seed: int | None,
    closing_policy: str,
    max_trace_events: int | None = None,
) -> dict[str, Any]:
    """Draw arrivals and unit work from seeded streams, then run the continuous engine.

    ``seed=None`` draws fresh entropy; it is recorded in the provenance so the run can be
    repeated exactly by passing it back as ``seed``. ``closing_policy`` has no default.
    """
    validate_timeline(horizon, demand_periods, staffing_segments)
    if seed is not None and (not isinstance(seed, Integral) or isinstance(seed, bool) or seed < 0):
        raise SharedSegmentError(["seed must be a whole number, 0 or more, or omitted."])
    seed_sequence = np.random.SeedSequence(seed)
    result = simulate_prescribed(
        horizon, demand_periods, staffing_segments, _draw_arrivals(horizon, demand_periods, seed_sequence),
        closing_policy=closing_policy, max_trace_events=max_trace_events,
    )
    result["provenance"].update({
        "seed": seed,
        "seed_entropy": seed_sequence.entropy,
        "random_streams": "numpy SeedSequence(seed).spawn(2): arrival gaps, then unit work (PCG64)",
    })
    return result


def _draw_arrivals(
    horizon: OperatingHorizon, demand_periods: Sequence[DemandPeriod], seed_sequence: np.random.SeedSequence
) -> list[tuple[float, float]]:
    """(arrival hour, unit work) pairs from the two streams ``seed_sequence.spawn(2)``."""
    arrival_stream, work_stream = (np.random.default_rng(child) for child in seed_sequence.spawn(2))
    times: list[float] = []
    for period in demand_periods:
        rate = float(period.arrival_rate_per_hour)
        start, stop = _hours(period.start_minute, horizon), _hours(period.end_minute, horizon)
        at = start
        while rate > 0:
            at += float(arrival_stream.exponential(1.0 / rate))
            if at >= stop:
                break
            times.append(at)
    works = [float(work) for work in work_stream.exponential(1.0, size=len(times))]
    return list(zip(times, works))


def draw_arrivals(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    *,
    seed_sequence: np.random.SeedSequence,
) -> list[tuple[float, float]]:
    """Public interface to this engine's arrival generation (X5, Phase 5B-4.4 named replications).

    Returns the (arrival hour, unit work) pairs that ``simulate_shared_replication`` simulates for
    the same inputs and ``seed_sequence``: the same checks, then the same ``_draw_arrivals``, with
    no logic of its own. The pairs depend only on the horizon, the demand periods, and the
    sequence; ``staffing_segments`` serve the timeline validation only. The sequence must be
    unused, because the draw spawns its two streams from it.
    """
    validate_timeline(horizon, demand_periods, staffing_segments)
    if not isinstance(seed_sequence, np.random.SeedSequence) or seed_sequence.n_children_spawned != 0:
        raise SharedSegmentError(["seed_sequence must be an unused numpy SeedSequence."])
    return _draw_arrivals(horizon, demand_periods, seed_sequence)


def simulate_shared_replication(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    *,
    seed_sequence: np.random.SeedSequence,
    closing_policy: str,
    max_trace_events: int | None = None,
) -> dict[str, Any]:
    """Run one replication from a numpy ``SeedSequence`` (Phase 4 replications and playback).

    Replication *i* of a run uses ``SeedSequence(entropy=root_entropy, spawn_key=(i,))``, the
    same child that ``SeedSequence(root_entropy).spawn(n)[i]`` returns, so any replication can
    be regenerated alone. The sequence must be unused: a sequence that has already spawned
    children would draw different streams.
    """
    validate_timeline(horizon, demand_periods, staffing_segments)
    if not isinstance(seed_sequence, np.random.SeedSequence) or seed_sequence.n_children_spawned != 0:
        raise SharedSegmentError(["seed_sequence must be an unused numpy SeedSequence."])
    result = simulate_prescribed(
        horizon, demand_periods, staffing_segments, _draw_arrivals(horizon, demand_periods, seed_sequence),
        closing_policy=closing_policy, max_trace_events=max_trace_events,
    )
    result["provenance"].update({
        "seed": None,
        "seed_entropy": seed_sequence.entropy,
        "spawn_key": list(seed_sequence.spawn_key),
        "random_streams": (
            "numpy SeedSequence(entropy, spawn_key).spawn(2): arrival gaps, then unit work (PCG64)"
        ),
    })
    return result


def staffing_from_capacity_result(capacity_result: dict[str, Any]) -> list[StaffingSegment]:
    """Staffing segments carrying the server counts selected by a complete Phase 2 plan."""
    rows = capacity_result["segments"]
    missing = [row["segment_id"] for row in rows if row["selected"] is None]
    if missing:
        raise SharedSegmentError([f"The capacity plan has no feasible server count in: {', '.join(missing)}."])
    inputs = capacity_result["provenance"]["inputs"]["staffing_segments"]
    return [
        StaffingSegment(source["segment_id"], source["start_minute"], source["end_minute"], row["selected"]["servers"])
        for source, row in zip(inputs, rows)
    ]
