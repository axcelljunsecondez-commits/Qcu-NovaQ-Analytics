"""Continuous shared-queue DES (Phase 3 of the shared-queue enhancement).

One event-driven simulation of one operating horizon for a shared M/M/c queue with
piecewise-constant arrival and service rates and a staffing schedule that may change
between segments. There is no restart, warm-up, or reset at any boundary: customers keep
their identity, arrival time, and waiting history for the whole run.

Spec: docs/superpowers/specs/2026-09-24-shared-queue-continuous-des.md.

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

ENGINE_VERSION = "novaq-shared-continuous-des-v1"

# Same-time order: a completion frees its server before a capacity change is applied, and an
# arrival at a boundary sees the new capacity. Ties among arrivals follow customer id.
_COMPLETION, _CAPACITY, _ARRIVAL = 0, 1, 2

CLOSED, IDLE, BUSY, DRAINING = "CLOSED", "IDLE", "BUSY", "DRAINING"

CLOSING_POLICY_STATUS = (
    "UNRESOLVED: no approved shared-queue closing rule exists. The run observes the horizon only; "
    "customers still waiting or in service at the end are reported as unfinished. They are not "
    "served after closing and not removed."
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
    "Waiting-time means are over customers who started service; customers still waiting at the "
    "end are counted separately and their elapsed waits are lower bounds.",
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
    max_trace_events: int | None = None,
) -> dict[str, Any]:
    """Run the continuous engine on prescribed (arrival hour, unit work) pairs.

    Arrival hours are measured from the horizon start. This entry point is deterministic;
    ``simulate_shared_day`` draws the pairs from seeded random streams.
    """
    validate_timeline(horizon, demand_periods, staffing_segments)
    end = _hours(horizon.end_minute, horizon)
    period_starts = [_hours(period.start_minute, horizon) for period in demand_periods]
    segment_starts = [_hours(segment.start_minute, horizon) for segment in staffing_segments]
    segment_hours = [(segment.end_minute - segment.start_minute) / 60.0 for segment in staffing_segments]

    problems = []
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
    max_queue = [0 for _ in staffing_segments]
    clock = _Clock()

    def record(at: float, kind: str, customer_id: int | None, server_id: int | None) -> None:
        nonlocal truncated
        if max_trace_events is not None and len(trace) >= max_trace_events:
            truncated = True
            return
        trace.append({
            "t": at, "type": kind, "segment_id": staffing_segments[clock.segment].segment_id,
            "customer_id": customer_id, "server_id": server_id, "queue_len_after": len(queue),
        })

    def advance(now: float) -> None:
        elapsed = now - clock.last
        if elapsed > 0:
            area = areas[clock.segment]
            area["queue"] += len(queue) * elapsed
            area["busy"] += sum(1 for server in servers if server.state in (BUSY, DRAINING)) * elapsed
            area["present"] += sum(1 for server in servers if server.state != CLOSED) * elapsed
        clock.last = now

    def transition(at: float, kind: str, server: _Server) -> None:
        transitions.append({
            "t": at, "kind": kind, "server_id": server.server_id,
            "segment_id": staffing_segments[clock.segment].segment_id,
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

    return _summarize(
        horizon, demand_periods, staffing_segments, arrivals, customers, servers, queue,
        segment_hours, areas, max_queue, transitions, drain_records, trace, truncated, end,
        max_trace_events,
    )


def _mean(values: Sequence[float]) -> float | None:
    return math.fsum(values) / len(values) if values else None


def _summarize(
    horizon, demand_periods, staffing_segments, arrivals, customers, servers, queue,
    segment_hours, areas, max_queue, transitions, drain_records, trace, truncated, end,
    max_trace_events,
) -> dict[str, Any]:
    waiting_ids = set(queue)
    customer_rows = []
    for customer in customers:
        if customer.departed:
            status = "departed"
        elif customer.service_start is not None:
            status = "in_service_at_end"
        else:
            status = "waiting_at_end"
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
            "elapsed_wait_at_end_hours": end - customer.arrival if status == "waiting_at_end" else None,
            "status": status,
        })
    assert waiting_ids == {row["customer_id"] for row in customer_rows if row["status"] == "waiting_at_end"}

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
            "waiting_at_end": sum(1 for row in rows if row["status"] == "waiting_at_end"),
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
              for status in ("departed", "in_service_at_end", "waiting_at_end")}
    total_hours = end
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
            "time_average_queue": math.fsum(area["queue"] for area in areas) / total_hours,
            "queue_customer_hours": math.fsum(area["queue"] for area in areas),
            "max_queue": max(max_queue),
            "busy_server_hours": math.fsum(area["busy"] for area in areas),
            "present_server_hours": math.fsum(area["present"] for area in areas),
            "scheduled_server_hours": math.fsum(row["scheduled_server_hours"] for row in segments),
            "server_hours_above_schedule": math.fsum(row["server_hours_above_schedule"] for row in segments),
            "servers_used": len(servers),
        },
        "capacity_transitions": transitions,
        "drains": drain_records,
        "horizon_end": {
            "hours": end,
            "waiting_customer_ids": [row["customer_id"] for row in customer_rows if row["status"] == "waiting_at_end"],
            "in_service_customer_ids": [row["customer_id"] for row in customer_rows if row["status"] == "in_service_at_end"],
            "draining_server_ids": [server.server_id for server in servers if server.state == DRAINING],
            "closing_policy": CLOSING_POLICY_STATUS,
        },
        "trace": trace,
        "trace_truncated": truncated,
        "provenance": {
            "engine_version": ENGINE_VERSION,
            "metric_provenance": "des_continuous_horizon",
            "time_unit": "hours from the horizon start",
            "trace_fields": (
                "queue_len_after is the number of waiting customers right after the event; an arriving "
                "customer counts as waiting until its service_start event, which may share the arrival time."
            ),
            "event_order": EVENT_ORDER,
            "transition_policy": TRANSITION_POLICY,
            "closing_policy": CLOSING_POLICY_STATUS,
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
    max_trace_events: int | None = None,
) -> dict[str, Any]:
    """Draw arrivals and unit work from seeded streams, then run the continuous engine.

    ``seed=None`` draws fresh entropy; it is recorded in the provenance so the run can be
    repeated exactly by passing it back as ``seed``.
    """
    validate_timeline(horizon, demand_periods, staffing_segments)
    if seed is not None and (not isinstance(seed, Integral) or isinstance(seed, bool) or seed < 0):
        raise SharedSegmentError(["seed must be a whole number, 0 or more, or omitted."])
    seed_sequence = np.random.SeedSequence(seed)
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

    result = simulate_prescribed(
        horizon, demand_periods, staffing_segments, list(zip(times, works)), max_trace_events=max_trace_events
    )
    result["provenance"].update({
        "seed": seed,
        "seed_entropy": seed_sequence.entropy,
        "random_streams": "numpy SeedSequence(seed).spawn(2): arrival gaps, then unit work (PCG64)",
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
