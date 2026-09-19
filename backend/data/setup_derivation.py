"""Derive a separate-queue Setup from a three-sheet upload, and export it back.

The ``events`` sheet holds customer events; the optional ``staff`` and
``breaks`` sheets state the facts events cannot show (shifts and breaks).
Every other Setup field is derived. Validation collects exact reasons and
never drops a row. Spec:
docs/superpowers/specs/2026-09-18-upload-template-setup-derivation.md.
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from datetime import time as datetime_time
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font
from pydantic import ValidationError

from backend.api.analysis_schemas import (
    STORED_SETUP,
    AbandonmentMode,
    CapacityMode,
    EventPeriodBasis,
    QueueSetup,
    QueueStructure,
)
from backend.data.analysis_ingestion import AnalysisIngestionError, normalize_analysis_input
from backend.data.ingestion import normalize_header_aliases

EVENT_COLUMNS = ["arrival_time", "service_start", "service_end", "queue_id"]
STAFF_COLUMNS = ["queue_id", "shift_start", "shift_end"]
BREAK_COLUMNS = ["queue_id", "break_name", "start", "minutes"]
_REQUIRED_BREAK_COLUMNS = ["queue_id", "start", "minutes"]
BREAK_NAME_MAX = 50
LATEST_ARRIVAL_MINUTES = 23 * 60
DIFF_FIELDS = [
    "queue_structure", "queue_ids", "segments", "staffing_varies_by_period", "fixed_server_count",
    "event_period_basis", "breaks", "capacity_mode", "total_system_capacity", "abandonment_mode",
    "patience_rate_per_hour", "separate_queue_closure_policy",
]
_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


class SetupExportError(ValueError):
    """The Setup cannot be written as a staff/breaks workbook."""


@dataclass
class Derivation:
    setup: dict | None
    staff_rows: list[dict] = field(default_factory=list)
    break_rows: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    records: list[dict] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)


def _wall_minutes(value: Any) -> float | None:
    """Wall-clock minutes from an Excel time cell or an ``HH:MM[:SS]`` string."""
    if isinstance(value, (datetime, pd.Timestamp)):
        value = value.time()
    if isinstance(value, datetime_time):
        return value.hour * 60 + value.minute + value.second / 60
    if isinstance(value, str):
        match = _CLOCK.match(value.strip())
        if match:
            hour, minute, second = int(match[1]), int(match[2]), int(match[3] or 0)
            if hour < 24 and minute < 60 and second < 60:
                return hour * 60 + minute + second / 60
    return None


def _whole_minutes(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        return int(value) if value.isdigit() and int(value) > 0 else None
    if isinstance(value, (int, float)) and math.isfinite(value) and float(value).is_integer() and value > 0:
        return int(value)
    return None


def _clock(minutes: float) -> str:
    total = int(round(minutes * 60))
    text = f"{total // 3600:02d}:{total // 60 % 60:02d}"
    return text if total % 60 == 0 else f"{text}:{total % 60:02d}"


def _iso(minutes: float) -> str:
    total = int(round(minutes * 60))
    return f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _missing(frame: pd.DataFrame, required: list[str]) -> list[str]:
    present = {str(column).strip() for column in frame.columns}
    return [column for column in required if column not in present]


def _stripped(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [str(column).strip() for column in out.columns]
    return out


def _labels(rows: list[dict]) -> None:
    """``break_name`` or "Break n" in time order per queue (rows with a valid start)."""
    by_queue: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("_start") is not None:
            by_queue.setdefault(row["queue_id"], []).append(row)
    for entries in by_queue.values():
        for number, row in enumerate(sorted(entries, key=lambda r: (r["_start"], r["row"])), start=1):
            row["label"] = row["break_name"] or f"Break {number}"


def _public(rows: list[dict]) -> list[dict]:
    return [{key: value for key, value in row.items() if not key.startswith("_")} for row in rows]


def derive_setup(sheets: dict[str, pd.DataFrame | None], saved_setup: dict | None) -> Derivation:
    """Derive the Setup from the sheets; errors carry the spec's exact messages."""
    events = sheets.get("events")
    staff = sheets.get("staff")
    breaks = sheets.get("breaks")
    staff = None if staff is None or staff.empty else _stripped(staff)
    breaks = None if breaks is None or breaks.empty else _stripped(breaks)
    result = Derivation(setup=None)
    errors = result.errors

    if events is None:
        errors.append("The events sheet has no rows.")
        return result
    aliased = events.copy()
    aliased.columns, _ = normalize_header_aliases([str(column).strip() for column in aliased.columns])
    for name, frame, required in (("events", aliased, EVENT_COLUMNS), ("staff", staff, STAFF_COLUMNS),
                                  ("breaks", breaks, _REQUIRED_BREAK_COLUMNS)):
        if frame is not None:
            missing = _missing(frame, required)
            if missing:
                errors.append(f"The {name} sheet is missing columns: {', '.join(missing)}.")
    if errors:
        return result
    if aliased.empty:
        errors.append("The events sheet has no rows.")
        return result

    arrivals = pd.to_datetime(aliased["arrival_time"], errors="coerce", utc=True)
    if arrivals.isna().any():
        row = int(arrivals.isna().to_numpy().nonzero()[0][0]) + 1
        errors.append(f"Row {row}: arrival_time must be a valid timestamp.")
        return result
    event_queues = aliased["queue_id"].map(_text)
    if (event_queues == "").any():
        errors.append("queue_id values must be non-empty for separate-queue analysis.")
        return result
    event_order = list(dict.fromkeys(event_queues))
    known = set(event_order)

    shifts: dict[str, tuple[float, float]] = {}
    staff_order: list[str] = []
    if staff is not None:
        first_row: dict[str, int] = {}
        for index, (queue_raw, start_raw, end_raw) in enumerate(
                staff[STAFF_COLUMNS].itertuples(index=False, name=None)):
            row = index + 2
            queue_id = _text(queue_raw)
            start, end = _wall_minutes(start_raw), _wall_minutes(end_raw)
            result.staff_rows.append({
                "row": row, "queue_id": queue_id,
                "shift_start": _clock(start) if start is not None else _text(start_raw),
                "shift_end": _clock(end) if end is not None else _text(end_raw)})
            if not queue_id:
                errors.append(f"Staff sheet row {row}: queue_id is empty.")
                continue
            if queue_id in first_row:
                errors.append(f"The staff sheet lists {queue_id} more than once "
                              f"(rows {first_row[queue_id]} and {row}).")
                continue
            first_row[queue_id] = row
            staff_order.append(queue_id)
            if start is None:
                errors.append(f"Staff sheet row {row}: shift_start must be a time in HH:MM.")
            if end is None:
                errors.append(f"Staff sheet row {row}: shift_end must be a time in HH:MM.")
            if start is not None and end is not None:
                if start >= end:
                    errors.append(f"Staff sheet row {row}: shift_start must be before shift_end.")
                else:
                    shifts[queue_id] = (start, end)
        missing_rows = [queue_id for queue_id in event_order if queue_id not in first_row]
        if missing_rows:
            errors.append(f"The staff sheet has no row for: {', '.join(missing_rows)}.")
        extra = [queue_id for queue_id in staff_order if queue_id not in known]
        if extra:
            errors.append(f"The staff sheet lists queues with no events: {', '.join(extra)}.")

    break_rows = result.break_rows
    if breaks is not None:
        names = breaks["break_name"] if "break_name" in breaks.columns else pd.Series([None] * len(breaks))
        for index, (queue_raw, start_raw, minutes_raw, name_raw) in enumerate(
                zip(breaks["queue_id"], breaks["start"], breaks["minutes"], names)):
            row = index + 2
            queue_id = _text(queue_raw)
            break_name = _text(name_raw) or None
            start = _wall_minutes(start_raw)
            minutes = _whole_minutes(minutes_raw)
            entry = {"row": row, "queue_id": queue_id, "break_name": break_name,
                     "start": _clock(start) if start is not None else _text(start_raw),
                     "minutes": minutes if minutes is not None else minutes_raw,
                     "label": None, "_start": None}
            break_rows.append(entry)
            if queue_id not in known:
                errors.append(f"Breaks sheet row {row}: queue_id {queue_id} is not in the events sheet.")
                continue
            if start is None:
                errors.append(f"Breaks sheet row {row}: start must be a time in HH:MM.")
            if minutes is None:
                errors.append(f"Breaks sheet row {row}: minutes must be a positive whole number.")
            if break_name is not None and len(break_name) > BREAK_NAME_MAX:
                errors.append(f"Breaks sheet row {row}: break_name must be at most {BREAK_NAME_MAX} characters.")
            if start is not None and minutes is not None:
                entry["_start"], entry["_minutes"] = start, minutes
        _labels(break_rows)
    if errors:
        result.break_rows = _public(break_rows)
        return result

    queue_ids = staff_order if staff is not None else event_order
    arrival_minutes = arrivals.dt.hour * 60 + arrivals.dt.minute + arrivals.dt.second / 60
    if staff is not None:
        for queue_id in queue_ids:
            low, high = shifts[queue_id]
            mine = arrival_minutes[event_queues == queue_id]
            outside = int(((mine < low) | (mine >= high)).sum())
            if outside:
                errors.append(f"{outside} events for {queue_id} arrive outside its shift "
                              f"{_clock(low)}–{_clock(high)}.")
        day_start = min(low for low, _ in shifts.values())
        day_end = max(high for _, high in shifts.values())
        points = {value for pair in shifts.values() for value in pair}
        points.update(hour * 60 for hour in range(24) if day_start < hour * 60 < day_end)
    else:
        if float(arrival_minutes.max()) >= LATEST_ARRIVAL_MINUTES:
            errors.append("Events that arrive at or after 23:00 cannot be placed in an hourly segment.")
            result.break_rows = _public(break_rows)
            return result
        day_start = math.floor(float(arrival_minutes.min()) / 60) * 60
        day_end = (math.floor(float(arrival_minutes.max()) / 60) + 1) * 60
        points = set(range(int(day_start), int(day_end) + 1, 60))
    boundaries = sorted(points)
    segments = []
    for low, high in zip(boundaries, boundaries[1:]):
        segment_id = f"{_clock(low)}-{_clock(high)}"
        active = None
        if staff is not None:
            active = [queue_id for queue_id in queue_ids if shifts[queue_id][0] <= low and high <= shifts[queue_id][1]]
            if not active:
                errors.append(f"Segment {segment_id} has no queue on shift.")
        segments.append({"id": segment_id, "start_time": _iso(low), "end_time": _iso(high),
                         "active_queue_ids": active})

    placed = [row for row in break_rows if row["_start"] is not None]
    for placed_row in placed:
        start, end = placed_row["_start"], placed_row["_start"] + placed_row["_minutes"]
        low, high = shifts[placed_row["queue_id"]] if staff is not None else (day_start, day_end)
        if start < low or end > high:
            where = "its shift" if staff is not None else "the operating day"
            errors.append(f"Breaks sheet row {placed_row['row']}: the {placed_row['queue_id']} break at "
                          f"{_clock(start)} for {placed_row['_minutes']} minutes is outside {where} "
                          f"{_clock(low)}–{_clock(high)}.")
    for queue_id in queue_ids:
        mine = sorted((row for row in placed if row["queue_id"] == queue_id), key=lambda r: (r["_start"], r["row"]))
        for previous, current in zip(mine, mine[1:]):
            if current["_start"] < previous["_start"] + previous["_minutes"]:
                first, second = sorted((previous["row"], current["row"]))
                errors.append(f"Breaks sheet rows {first} and {second} overlap for {queue_id}.")
    result.break_rows = _public(break_rows)
    if errors:
        return result

    saved = QueueSetup.model_validate(saved_setup or {}, context=STORED_SETUP)
    varies = staff is not None and any(set(seg["active_queue_ids"] or []) != set(queue_ids) for seg in segments)
    keep_capacity = saved.capacity_mode != CapacityMode.unknown
    keep_abandonment = saved.abandonment_mode != AbandonmentMode.unknown
    candidate = {
        "queue_structure": QueueStructure.separate_queues.value,
        "fixed_server_count": saved.fixed_server_count if varies else len(queue_ids),
        "staffing_varies_by_period": varies,
        "capacity_mode": saved.capacity_mode.value if keep_capacity else CapacityMode.unlimited.value,
        "total_system_capacity": saved.total_system_capacity if keep_capacity else None,
        "abandonment_mode": saved.abandonment_mode.value if keep_abandonment else AbandonmentMode.not_modeled.value,
        "patience_rate_per_hour": saved.patience_rate_per_hour if keep_abandonment else None,
        "segments": segments,
        "queue_ids": queue_ids,
        "breaks": [{"queue_id": row["queue_id"], "scheduled_start_time": _iso(row["_start"]),
                    "duration_minutes": row["_minutes"], "break_name": row["break_name"]} for row in placed],
        "event_period_basis": (EventPeriodBasis.representative_day.value
                               if arrivals.dt.date.nunique() > 1 else EventPeriodBasis.per_date.value),
    }
    try:
        setup = QueueSetup.model_validate(candidate)
    except ValidationError as exc:
        reason = str(exc.errors()[0]["msg"]).removeprefix("Value error, ").rstrip(".")
        errors.append(f"The derived Setup is invalid: {reason}.")
        return result
    result.setup = setup.model_dump(mode="json")
    try:
        result.records, result.provenance = normalize_analysis_input(events, setup)
    except AnalysisIngestionError as exc:
        errors.append(str(exc))
    return result


def setup_diff(saved_setup: dict | None, derived_setup: dict) -> list[dict]:
    """Fields whose saved and derived values differ, in display order."""
    saved = QueueSetup.model_validate(saved_setup or {}, context=STORED_SETUP).model_dump(mode="json")
    derived = QueueSetup.model_validate(derived_setup).model_dump(mode="json")
    return [{"field": name, "saved": saved[name], "derived": derived[name]}
            for name in DIFF_FIELDS if saved[name] != derived[name]]


def setup_workbook(setup_json: dict) -> bytes:
    """``staff`` and ``breaks`` sheets written from the Setup (re-upload derives it again)."""
    setup = QueueSetup.model_validate(setup_json or {}, context=STORED_SETUP)
    if setup.queue_structure != QueueStructure.separate_queues:
        raise SetupExportError("The setup workbook is available for separate queues.")
    staff_rows: list[list] = []
    if any(segment.active_queue_ids is not None for segment in setup.segments):
        ordered = sorted(setup.segments, key=lambda segment: segment.start_time)
        for queue_id in setup.queue_ids:
            spans = [(segment.start_time, segment.end_time) for segment in ordered
                     if queue_id in (segment.active_queue_ids if segment.active_queue_ids is not None
                                     else setup.queue_ids)]
            if not spans:
                raise SetupExportError(f"Cannot export {queue_id}: it is not active in any segment.")
            if any(previous[1] != current[0] for previous, current in zip(spans, spans[1:])):
                raise SetupExportError(f"Cannot export {queue_id}: it has more than one shift.")
            staff_rows.append([queue_id, _time_text(spans[0][0]), _time_text(spans[-1][1])])
    break_rows = [[entry.queue_id, entry.break_name or "", _time_text(entry.scheduled_start_time),
                   entry.duration_minutes] for entry in setup.breaks]
    workbook = Workbook()
    staff_sheet = workbook.active
    staff_sheet.title = "staff"
    breaks_sheet = workbook.create_sheet("breaks")
    for sheet, header, rows in ((staff_sheet, STAFF_COLUMNS, staff_rows), (breaks_sheet, BREAK_COLUMNS, break_rows)):
        sheet.append(header)
        for row in rows:
            sheet.append(row)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for letter in "ABCD":
            sheet.column_dimensions[letter].width = 18
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _time_text(value: datetime_time) -> str:
    return _clock(value.hour * 60 + value.minute + value.second / 60)


__all__ = [
    "BREAK_COLUMNS",
    "Derivation",
    "EVENT_COLUMNS",
    "STAFF_COLUMNS",
    "SetupExportError",
    "derive_setup",
    "setup_diff",
    "setup_workbook",
]
