"""Shared-queue segment foundation (Phase 1 of the shared-queue enhancement).

Builds a gap-free, duration-aware timeline for one shared M/M/c queue and evaluates
each staffing segment analytically through the central ``select_model`` dispatcher.

Spec: docs/superpowers/specs/2026-09-24-shared-queue-segment-foundation.md.

Nothing existing imports this module. The legacy shared optimizer and DES, saved
scenarios, and all separate-queue code are unchanged by it.

Two resolutions are kept apart on purpose:

- demand periods: where an arrival rate and a service rate were supplied;
- staffing segments: where the server count may change.

A staffing segment may be shorter than its demand period. It then inherits that
period's rates (piecewise-constant rates). No finer demand is ever created.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Any

from backend.queueing_engine.services.model_selection import select_model
from backend.queueing_engine.utilization import is_saturated, utilization_band

MINUTES_PER_DAY = 1440

_CLOCK = re.compile(r"^(\d{2}):(\d{2})$")
_RANGE_LABEL = re.compile(r"^\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*$")

ASSUMPTIONS = [
    "Each staffing segment is evaluated as a stationary M/M/c queue (M/M/1 when c = 1): "
    "Poisson arrivals, exponential service, first come first served, unlimited waiting room. "
    "Results are steady-state estimates, not the transient behavior of a queue that starts "
    "or ends mid-day.",
    "A staffing segment shorter than its demand period inherits that period's arrival and "
    "service rates (piecewise-constant rates). No sub-period demand variation is observed "
    "or implied.",
    "Rates are per hour and the service rate is per server. Durations are whole minutes.",
    "Waiting is attributed to the segment in which a customer arrives: expected waiting "
    "customer-hours = arrival rate x Wq x duration. Segments are evaluated independently, so "
    "customers still waiting from an earlier segment (backlog) are not represented. A segment "
    "with zero demand or no servers can still hold such customers in a continuous day.",
]

# Rows carrying these inputs select a model other than M/M/c; Phase 1 does not cover them.
_OUT_OF_SCOPE_FIELDS = ("variance", "K", "theta")


class SharedSegmentError(ValueError):
    """Raised with every validation problem found, not only the first."""

    def __init__(self, problems: Sequence[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class OperatingHorizon:
    """The operating day being analysed, in minutes since midnight."""

    start_minute: int
    end_minute: int


@dataclass(frozen=True)
class DemandPeriod:
    """A period with a supplied arrival rate and per-server service rate (per hour)."""

    period_id: str
    start_minute: int
    end_minute: int
    arrival_rate_per_hour: float
    service_rate_per_hour: float


@dataclass(frozen=True)
class StaffingSegment:
    """A period with a fixed number of servers (0 means closed)."""

    segment_id: str
    start_minute: int
    end_minute: int
    servers: int


def parse_clock(value: object) -> int:
    """Minutes since midnight for ``HH:MM``; ``24:00`` is the end of the day."""
    match = _CLOCK.match(value.strip()) if isinstance(value, str) else None
    if match is None:
        raise SharedSegmentError([f"Time {value!r} must be written as HH:MM."])
    hours, minutes = int(match.group(1)), int(match.group(2))
    if minutes > 59 or hours > 24 or (hours == 24 and minutes != 0):
        raise SharedSegmentError([f"Time {value!r} is not a clock time between 00:00 and 24:00."])
    return hours * 60 + minutes


def format_clock(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _is_whole_number(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _minute_problems(label: str, start: object, end: object) -> list[str]:
    problems = []
    for name, value in (("start", start), ("end", end)):
        if not _is_whole_number(value) or not 0 <= int(value) <= MINUTES_PER_DAY:  # type: ignore[call-overload]
            problems.append(f"{label} {name} must be a whole minute between 0 and {MINUTES_PER_DAY}.")
    if not problems and int(end) <= int(start):  # type: ignore[call-overload]
        problems.append(f"{label} must end after it starts.")
    return problems


def _horizon_problems(horizon: OperatingHorizon) -> list[str]:
    return _minute_problems("The operating horizon", horizon.start_minute, horizon.end_minute)


def _sequence_problems(kind: str, items: Sequence[tuple[str, int, int]], horizon: OperatingHorizon) -> list[str]:
    """Order, gap, overlap, and horizon-coverage checks on already well-formed items."""
    if not items:
        return [f"At least one {kind} is required."]
    starts = [start for _, start, _ in items]
    if any(later <= earlier for earlier, later in zip(starts, starts[1:])):
        return [f"{kind.capitalize()}s must be listed in chronological order with distinct start times."]
    problems = []
    first_id, first_start, _ = items[0]
    if first_start != horizon.start_minute:
        problems.append(
            f"The first {kind} ({first_id}) starts at {format_clock(first_start)}, "
            f"not at the horizon start {format_clock(horizon.start_minute)}."
        )
    for (previous_id, _, previous_end), (current_id, current_start, _) in zip(items, items[1:]):
        if current_start > previous_end:
            problems.append(
                f"Gap between {kind}s {previous_id} and {current_id}: "
                f"{format_clock(previous_end)} to {format_clock(current_start)} is not covered."
            )
        elif current_start < previous_end:
            problems.append(
                f"{kind.capitalize()}s {previous_id} and {current_id} overlap: "
                f"{current_id} starts at {format_clock(current_start)} before "
                f"{previous_id} ends at {format_clock(previous_end)}."
            )
    last_id, _, last_end = items[-1]
    if last_end != horizon.end_minute:
        problems.append(
            f"The last {kind} ({last_id}) ends at {format_clock(last_end)}, "
            f"not at the horizon end {format_clock(horizon.end_minute)}."
        )
    return problems


def _id_problems(kind: str, identifiers: Sequence[object]) -> list[str]:
    problems = []
    if any(not isinstance(item, str) or not item.strip() for item in identifiers):
        problems.append(f"Every {kind} needs a non-empty text id.")
    texts = [item for item in identifiers if isinstance(item, str)]
    duplicates = sorted({item for item in texts if texts.count(item) > 1})
    if duplicates:
        problems.append(f"Duplicate {kind} ids: {', '.join(duplicates)}.")
    return problems


def validate_timeline(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
) -> None:
    """Raise ``SharedSegmentError`` listing every problem, or return when valid."""
    problems = _horizon_problems(horizon)
    problems += _id_problems("demand period", [period.period_id for period in demand_periods])
    problems += _id_problems("staffing segment", [segment.segment_id for segment in staffing_segments])

    item_problems: list[str] = []
    for period in demand_periods:
        label = f"Demand period {period.period_id}"
        item_problems += _minute_problems(label, period.start_minute, period.end_minute)
        rate = period.arrival_rate_per_hour
        if not _is_finite_real(rate) or float(rate) < 0:
            item_problems.append(f"{label} arrival rate must be a finite number of customers per hour, 0 or more.")
        rate = period.service_rate_per_hour
        if not _is_finite_real(rate) or float(rate) <= 0:
            item_problems.append(f"{label} service rate must be a finite number of customers per hour per server, above 0.")
    for segment in staffing_segments:
        label = f"Staffing segment {segment.segment_id}"
        item_problems += _minute_problems(label, segment.start_minute, segment.end_minute)
        if not _is_whole_number(segment.servers) or int(segment.servers) < 0:
            item_problems.append(f"{label} servers must be a whole number, 0 or more.")
    problems += item_problems

    # Order, coverage, and nesting are only meaningful once every item and the horizon are well formed.
    if not problems:
        problems += _sequence_problems(
            "demand period",
            [(period.period_id, period.start_minute, period.end_minute) for period in demand_periods],
            horizon,
        )
        problems += _sequence_problems(
            "staffing segment",
            [(segment.segment_id, segment.start_minute, segment.end_minute) for segment in staffing_segments],
            horizon,
        )
    if not problems:
        for segment in staffing_segments:
            if containing_period(segment, demand_periods) is None:
                problems.append(
                    f"Staffing segment {segment.segment_id} ({format_clock(segment.start_minute)}-"
                    f"{format_clock(segment.end_minute)}) crosses a demand-period boundary. Split it at the "
                    "boundary; rates are never averaged across demand periods."
                )
    if problems:
        raise SharedSegmentError(problems)


def containing_period(segment: StaffingSegment, demand_periods: Sequence[DemandPeriod]) -> DemandPeriod | None:
    """The one demand period that holds the staffing segment, or None when it crosses a boundary."""
    return next(
        (
            period for period in demand_periods
            if period.start_minute <= segment.start_minute and segment.end_minute <= period.end_minute
        ),
        None,
    )


def evaluate_segment(segment: StaffingSegment, period: DemandPeriod) -> dict[str, Any]:
    """Stationary evaluation of one staffing segment inside its (already validated) demand period."""
    duration_minutes = segment.end_minute - segment.start_minute
    duration_hours = duration_minutes / 60.0
    lambda_ = float(period.arrival_rate_per_hour)
    mu = float(period.service_rate_per_hour)
    servers = int(segment.servers)
    row: dict[str, Any] = {
        "segment_id": segment.segment_id,
        "start": format_clock(segment.start_minute),
        "end": format_clock(segment.end_minute),
        "start_minute": segment.start_minute,
        "end_minute": segment.end_minute,
        "duration_minutes": duration_minutes,
        "duration_hours": duration_hours,
        "servers": servers,
        "arrival_rate_per_hour": lambda_,
        "service_rate_per_hour": mu,
        "demand_period_id": period.period_id,
        "demand_resolution_minutes": period.end_minute - period.start_minute,
        "demand_source": (
            "same_as_demand_period"
            if (segment.start_minute, segment.end_minute) == (period.start_minute, period.end_minute)
            else "inherited_from_demand_period"
        ),
        "metric_provenance": "analytical_steady_state",
        "selected_model": None,
        "model_id": None,
        "rho": None,
        "utilization_band": None,
        "L": None,
        "Lq": None,
        "W_hours": None,
        "Wq_hours": None,
        "expected_arrivals": lambda_ * duration_hours,
        "server_hours": servers * duration_hours,
        "offered_work_hours": lambda_ / mu * duration_hours,
        "expected_waiting_customer_hours": None,
        "waiting_attribution": "customers_arriving_in_segment",
        "backlog_represented": False,
        "note": None,
    }

    if servers == 0:
        if lambda_ == 0:
            # Every state is absorbing, so there is no unique steady state: rho and the
            # queue metrics stay None. Only the arrival-attributed waiting is known.
            row.update(
                status="CLOSED",
                expected_waiting_customer_hours=0.0,
                note=(
                    "No servers and no arrivals. No customer arrives in this segment, so its "
                    "arrival-attributed waiting is 0, but queue metrics have no unique steady state. "
                    "Customers still waiting from an earlier segment would stay unserved; that backlog "
                    "is not represented."
                ),
            )
        else:
            row.update(status="NO_CAPACITY",
                       note="Customers arrive but no server is scheduled, so no steady state exists.")
        return row

    selected = select_model(lambda_, mu, servers)
    metrics = selected["metrics"]
    row.update(selected_model=selected["name"], model_id=selected["model_id"])
    rho = metrics.get("rho")
    if _is_finite_real(rho):
        row.update(rho=float(rho), utilization_band=utilization_band(float(rho)))

    if not metrics.get("stable"):
        saturated = _is_finite_real(rho) and is_saturated(float(rho))
        row.update(
            status="UNSTABLE" if saturated else "CALCULATION_FAILED",
            note=metrics.get("error") or "No finite steady state.",
        )
        return row

    wq = float(metrics["Wq"])
    row.update(
        status="ZERO_DEMAND" if lambda_ == 0 else "STABLE",
        L=float(metrics["L"]),
        Lq=float(metrics["Lq"]),
        W_hours=float(metrics["W"]),
        Wq_hours=wq,
        expected_waiting_customer_hours=lambda_ * wq * duration_hours,
    )
    if lambda_ == 0:
        row["note"] = (
            "No arrivals, so the stationary queue is empty and its waits are 0. Customers still "
            "waiting from an earlier segment would carry into this one in a continuous day; that "
            "backlog is not represented."
        )
    return row


def evaluate_shared_segments(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
) -> dict[str, Any]:
    """Validate the timeline, then evaluate every staffing segment and the horizon totals."""
    validate_timeline(horizon, demand_periods, staffing_segments)
    rows = []
    for segment in staffing_segments:
        period = containing_period(segment, demand_periods)
        assert period is not None  # guaranteed by validate_timeline
        rows.append(evaluate_segment(segment, period))

    undefined_waiting = [row["segment_id"] for row in rows if row["expected_waiting_customer_hours"] is None]
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    return {
        "horizon": {
            "start": format_clock(horizon.start_minute),
            "end": format_clock(horizon.end_minute),
            "duration_hours": (horizon.end_minute - horizon.start_minute) / 60.0,
        },
        "segments": rows,
        "totals": {
            "duration_hours": math.fsum(row["duration_hours"] for row in rows),
            "expected_arrivals": math.fsum(row["expected_arrivals"] for row in rows),
            "server_hours": math.fsum(row["server_hours"] for row in rows),
            "offered_work_hours": math.fsum(row["offered_work_hours"] for row in rows),
            "expected_waiting_customer_hours": (
                None if undefined_waiting
                else math.fsum(row["expected_waiting_customer_hours"] for row in rows)
            ),
            "undefined_waiting_segments": undefined_waiting,
            "status_counts": status_counts,
        },
        "assumptions": list(ASSUMPTIONS),
    }


def timeline_from_aggregate_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[list[DemandPeriod], list[StaffingSegment]]:
    """Read aggregate ``time, lambda, mu, c`` rows whose label is ``HH:MM-HH:MM``.

    Each row becomes one demand period and one staffing segment with the same bounds.
    Rows that select another model (variance, K, or theta supplied) or a separate queue
    are rejected, never silently reduced to M/M/c. Coverage of the horizon is checked
    later by ``validate_timeline``.
    """
    problems: list[str] = []
    periods: list[DemandPeriod] = []
    segments: list[StaffingSegment] = []
    for position, row in enumerate(rows, start=1):
        where = f"Row {position}"
        label = row.get("time")
        match = _RANGE_LABEL.match(label) if isinstance(label, str) else None
        if match is None:
            problems.append(f"{where}: time {label!r} must be a clock range such as 11:00-12:00.")
            continue
        try:
            start, end = parse_clock(match.group(1)), parse_clock(match.group(2))
        except SharedSegmentError as error:
            problems += [f"{where}: {problem}" for problem in error.problems]
            continue
        if row.get("queue_structure") == "separate_queues" or row.get("model_id") == "parallel_mg1":
            problems.append(f"{where}: separate-queue rows are outside the shared-queue timeline.")
            continue
        supplied = [field for field in _OUT_OF_SCOPE_FIELDS if row.get(field) is not None]
        if supplied:
            problems.append(
                f"{where}: {', '.join(supplied)} supplied; Phase 1 covers M/M/c only, and the model scope "
                "for other models is an open decision."
            )
            continue
        servers = row.get("c")
        if isinstance(servers, float) and servers.is_integer():
            servers = int(servers)
        period_id = f"{format_clock(start)}-{format_clock(end)}"
        periods.append(DemandPeriod(period_id, start, end, row.get("lambda"), row.get("mu")))  # type: ignore[arg-type]
        segments.append(StaffingSegment(period_id, start, end, servers))  # type: ignore[arg-type]
    if problems:
        raise SharedSegmentError(problems)
    return periods, segments
