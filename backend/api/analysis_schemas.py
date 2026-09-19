"""Validated API schemas for Analysis queue setup."""

from __future__ import annotations

from datetime import time as datetime_time
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    ValidationInfo,
    model_serializer,
    model_validator,
)

# Validation context for a Setup read back from storage: the break-schedule
# checks apply to new input only, so an older saved Analysis still loads.
STORED_SETUP = {"stored_setup": True}


class QueueStructure(str, Enum):
    shared_queue = "shared_queue"
    single_server = "single_server"
    separate_queues = "separate_queues"
    unknown = "unknown"


class CapacityMode(str, Enum):
    unlimited = "unlimited"
    finite = "finite"
    unknown = "unknown"


class AbandonmentMode(str, Enum):
    not_modeled = "not_modeled"
    modeled = "modeled"
    unknown = "unknown"


class SeparateQueueClosurePolicy(str, Enum):
    drain_existing = "drain_existing"


class EventPeriodBasis(str, Enum):
    """How customer-event uploads form analysis periods.

    ``per_date`` keeps one period per calendar date and segment. The
    ``representative_day`` basis pools every observed date into one period per
    segment (arrival rate averaged over the observed days).
    """

    per_date = "per_date"
    representative_day = "representative_day"


class AnalysisSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, min_length=1, max_length=100)
    start_time: datetime_time
    end_time: datetime_time
    active_queue_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> AnalysisSegment:
        if self.end_time <= self.start_time:
            raise ValueError("Analysis segment end_time must be after start_time.")
        return self


class QueueBreak(BaseModel):
    """One explicitly user-configured server break (input authority only).

    The queue must already exist in ``QueueSetup.queue_ids``; the start is a
    wall-clock time and the duration is a positive whole number of minutes.
    Multiple breaks per queue are allowed. Nothing here executes breaks —
    downstream simulation phases consume these records.
    """

    model_config = ConfigDict(extra="forbid")

    queue_id: str = Field(min_length=1, max_length=100)
    scheduled_start_time: datetime_time
    duration_minutes: int = Field(gt=0)
    break_name: str | None = Field(default=None, max_length=50)
    # The store's baseline start, set once by the break optimizer's Apply; the
    # optimizer's move window is measured from it. Editing the start clears it.
    original_start_time: datetime_time | None = None

    @model_serializer(mode="wrap")
    def _omit_missing_name(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        # Unnamed/unanchored breaks serialize exactly as before these fields existed.
        data = handler(self)
        for key in ("break_name", "original_start_time"):
            if data.get(key) is None:
                data.pop(key, None)
        return data


class QueueSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_structure: QueueStructure = QueueStructure.unknown
    fixed_server_count: int | None = Field(default=None, ge=1, le=100000)
    staffing_varies_by_period: bool = False
    capacity_mode: CapacityMode = CapacityMode.unknown
    total_system_capacity: int | None = Field(default=None, ge=1, le=100000)
    abandonment_mode: AbandonmentMode = AbandonmentMode.unknown
    patience_rate_per_hour: float | None = Field(default=None, gt=0)
    segments: list[AnalysisSegment] = Field(default_factory=list)
    separate_queue_closure_policy: SeparateQueueClosurePolicy = SeparateQueueClosurePolicy.drain_existing
    queue_ids: list[str] = Field(default_factory=list)
    breaks: list[QueueBreak] = Field(default_factory=list)
    event_period_basis: EventPeriodBasis = EventPeriodBasis.per_date

    @model_validator(mode="after")
    def validate_dependencies(self, info: ValidationInfo) -> QueueSetup:
        if self.queue_structure == QueueStructure.single_server:
            if self.staffing_varies_by_period:
                raise ValueError("A single-server queue cannot vary staffing by period.")
            if self.fixed_server_count not in (None, 1):
                raise ValueError("A single-server queue must have exactly one server.")
            self.fixed_server_count = 1
        if self.capacity_mode != CapacityMode.finite and self.total_system_capacity is not None:
            raise ValueError("Total system capacity is only valid for finite capacity.")
        if (
            self.capacity_mode == CapacityMode.finite
            and self.total_system_capacity is not None
            and self.fixed_server_count is not None
            and self.total_system_capacity < self.fixed_server_count
        ):
            raise ValueError("Total system capacity must include and be at least the server count.")
        if self.abandonment_mode != AbandonmentMode.modeled and self.patience_rate_per_hour is not None:
            raise ValueError("Patience rate is only valid when abandonment is modeled.")
        cleaned_queue_ids = [queue_id.strip() for queue_id in self.queue_ids]
        if any(not queue_id for queue_id in cleaned_queue_ids):
            raise ValueError("Configured queue IDs must be non-empty.")
        if len(set(cleaned_queue_ids)) != len(cleaned_queue_ids):
            raise ValueError("Configured queue IDs must be unique.")
        self.queue_ids = cleaned_queue_ids
        if self.queue_structure == QueueStructure.separate_queues and not self.queue_ids:
            raise ValueError("Separate-queue analysis requires at least one configured queue ID.")
        configured = set(self.queue_ids)
        if (
            self.event_period_basis == EventPeriodBasis.representative_day
            and self.queue_structure != QueueStructure.separate_queues
        ):
            raise ValueError("The representative day basis is only supported for separate queues.")
        if self.breaks and self.queue_structure != QueueStructure.separate_queues:
            raise ValueError("Server break schedules are only supported for separate queues.")
        for entry in self.breaks:
            queue_id = entry.queue_id.strip()
            if not queue_id:
                raise ValueError("Break queue IDs must be non-empty.")
            if queue_id not in configured:
                raise ValueError(
                    f"Break references unknown queue ID: {entry.queue_id}."
                )
            entry.queue_id = queue_id
        ordered = sorted(self.segments, key=lambda segment: segment.start_time)
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_time < previous.end_time:
                raise ValueError("Analysis segments must not overlap.")
        for segment in self.segments:
            if segment.active_queue_ids is None:
                continue
            active_ids = [queue_id.strip() for queue_id in segment.active_queue_ids]
            if len(set(active_ids)) != len(active_ids):
                raise ValueError(f"Segment {segment.id or 'unnamed'} active_queue_ids must be unique.")
            unknown = sorted(set(active_ids) - configured)
            if unknown:
                raise ValueError(
                    f"Segment {segment.id or 'unnamed'} contains unknown active queue IDs: {', '.join(unknown)}."
                )
            if any(not queue_id for queue_id in active_ids):
                raise ValueError(f"Segment {segment.id or 'unnamed'} active_queue_ids must be non-empty values.")
            segment.active_queue_ids = active_ids
        if self.queue_structure == QueueStructure.separate_queues and self.staffing_varies_by_period:
            missing = [segment.id or "unnamed" for segment in self.segments if segment.active_queue_ids is None]
            if missing:
                raise ValueError(
                    "Variable separate-queue staffing requires active_queue_ids for every configured segment: "
                    + ", ".join(missing)
                )
            if any(not segment.active_queue_ids for segment in self.segments):
                raise ValueError("Variable separate-queue staffing requires at least one active queue per segment.")
        if self.queue_structure == QueueStructure.separate_queues and not self.staffing_varies_by_period:
            conflicting = [
                segment.id or "unnamed"
                for segment in self.segments
                if segment.active_queue_ids is not None and set(segment.active_queue_ids) != configured
            ]
            if conflicting:
                raise ValueError(
                    "Fixed separate-queue staffing keeps all configured queues active; "
                    "active_queue_ids must match queue_ids for: " + ", ".join(conflicting)
                )
        if self.breaks and not (info.context or {}).get("stored_setup"):
            _validate_break_schedule(self)
        return self


def _minutes(value: datetime_time) -> float:
    return value.hour * 60 + value.minute + value.second / 60


def _clock(minutes: float) -> str:
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def _shift_runs(setup: QueueSetup, queue_id: str) -> list[tuple[float, float]]:
    """Continuous runs of segments in which ``queue_id`` is scheduled active."""
    runs: list[tuple[float, float]] = []
    for segment in sorted(setup.segments, key=lambda item: item.start_time):
        active = segment.active_queue_ids if segment.active_queue_ids is not None else setup.queue_ids
        if queue_id not in active:
            continue
        low, high = _minutes(segment.start_time), _minutes(segment.end_time)
        if runs and runs[-1][1] == low:
            runs[-1] = (runs[-1][0], high)
        else:
            runs.append((low, high))
    return runs


def _validate_break_schedule(setup: QueueSetup) -> None:
    """The three-sheet upload's break rules (``setup_derivation.derive_setup``).

    A break must lie inside one continuous run of its cashier's active
    segments (the operating day when staffing is fixed), and one cashier's
    breaks must not overlap. Different cashiers may overlap. Without
    segments there is no shift to check, so only the overlap rule applies.
    """
    by_queue: dict[str, list[QueueBreak]] = {}
    for entry in setup.breaks:
        by_queue.setdefault(entry.queue_id, []).append(entry)
    where = "its shift" if setup.staffing_varies_by_period else "the operating day"
    for queue_id, entries in by_queue.items():
        ordered = sorted(entries, key=lambda item: item.scheduled_start_time)
        for previous, current in zip(ordered, ordered[1:]):
            if _minutes(current.scheduled_start_time) < (
                    _minutes(previous.scheduled_start_time) + previous.duration_minutes):
                raise ValueError(
                    f"Breaks for {queue_id} overlap: {_clock(_minutes(previous.scheduled_start_time))} "
                    f"({previous.duration_minutes} minutes) and {_clock(_minutes(current.scheduled_start_time))} "
                    f"({current.duration_minutes} minutes).")
        if not setup.segments:
            continue
        runs = _shift_runs(setup, queue_id)
        for entry in ordered:
            start = _minutes(entry.scheduled_start_time)
            end = start + entry.duration_minutes
            if not any(low <= start and end <= high for low, high in runs):
                spans = ", ".join(f"{_clock(low)}–{_clock(high)}" for low, high in runs) or "none"
                raise ValueError(
                    f"The {queue_id} break at {_clock(start)} for {entry.duration_minutes} minutes "
                    f"is outside {where} {spans}.")


def setup_status(setup: QueueSetup) -> str:
    if setup.queue_structure == QueueStructure.unknown:
        return "incomplete"
    if setup.capacity_mode == CapacityMode.finite and setup.total_system_capacity is None:
        return "incomplete"
    if setup.abandonment_mode == AbandonmentMode.modeled and setup.patience_rate_per_hour is None:
        return "incomplete"
    if setup.staffing_varies_by_period:
        return "ready_for_aggregate"
    if setup.fixed_server_count is None:
        return "incomplete"
    return "ready"


def unknown_queue_setup() -> QueueSetup:
    return QueueSetup()
