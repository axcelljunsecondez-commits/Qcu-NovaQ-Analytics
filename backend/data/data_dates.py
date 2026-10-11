"""B11: the dates an uploaded file's data covers ("Data covers" on Analysis results).

A customer-record upload stores the first and last arrival date at ingestion
(``validation_report_json["data_dates"]``). For customer-record datasets stored before B11
the dates are recovered from the per-date period labels NovaQ itself wrote at ingestion
("YYYY-MM-DD HH:00 UTC" or "YYYY-MM-DD <segment> UTC"). Anything else has no data dates:
aggregate files (their period labels are user text) and representative-day datasets stored
before B11 (their labels carry no date). Dates are never inferred from a filename.
"""

from __future__ import annotations

import re
from datetime import date

import pandas as pd

STORED = "stored_at_upload"
PERIOD_LABELS = "period_labels"
_LABEL_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}) \S.* UTC$")


def arrival_dates(arrival_times: pd.Series) -> dict:
    """First and last arrival date (UTC, the same clock as the period labels)."""
    return {"first": arrival_times.min().date().isoformat(), "last": arrival_times.max().date().isoformat()}


def _label_date(label) -> date | None:
    match = _LABEL_DATE.match(label) if isinstance(label, str) else None
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def data_dates(validation: dict | None, records: list | None) -> dict | None:
    """``{"first", "last", "source"}`` for the dataset, or None when the dates cannot be established."""
    validation = validation or {}
    stored = validation.get("data_dates")
    if isinstance(stored, dict) and stored.get("first") and stored.get("last"):
        return {"first": stored["first"], "last": stored["last"], "source": STORED}
    if validation.get("schema") != "customer_events" or validation.get("period_basis") == "representative_day":
        return None
    days = [_label_date(record.get("time")) if isinstance(record, dict) else None for record in records or []]
    if not days or any(day is None for day in days):
        return None
    known = [day for day in days if day is not None]
    return {"first": min(known).isoformat(), "last": max(known).isoformat(), "source": PERIOD_LABELS}
