"""Separate-queue representative day: setup option and customer-event pooling.

Spec: docs/superpowers/specs/2026-09-18-separate-representative-day.md.
"""
from __future__ import annotations

import pandas as pd
import pytest
from pydantic import ValidationError

from backend.api.analysis_schemas import QueueSetup
from backend.data.analysis_ingestion import AnalysisIngestionError, normalize_analysis_input


def _setup(**over):
    base = {
        "queue_structure": "separate_queues",
        "fixed_server_count": 2,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "abandonment_mode": "not_modeled",
        "segments": [
            {"id": "s1", "start_time": "05:00:00", "end_time": "06:00:00", "active_queue_ids": None},
            {"id": "s2", "start_time": "06:00:00", "end_time": "07:00:00", "active_queue_ids": None},
        ],
        "queue_ids": ["a", "b"],
    }
    base.update(over)
    return QueueSetup.model_validate(base)


def _events(rows):
    """rows: (date, arrival HH:MM, service minutes, queue)."""
    out = []
    for date, arrive, minutes, queue in rows:
        start = pd.Timestamp(f"{date}T{arrive}:00Z")
        out.append({"arrival_time": start.isoformat(), "service_start": start.isoformat(),
                    "service_end": (start + pd.Timedelta(minutes=minutes)).isoformat(),
                    "queue_id": queue})
    return pd.DataFrame(out)


EVENTS = [
    ("2026-08-03", "05:10", 6, "a"), ("2026-08-03", "05:20", 12, "a"), ("2026-08-03", "05:30", 9, "b"),
    ("2026-08-04", "05:15", 3, "a"), ("2026-08-04", "06:05", 10, "a"), ("2026-08-04", "06:40", 5, "b"),
]


def test_period_basis_defaults_to_per_date_and_is_separate_only():
    assert _setup().event_period_basis == "per_date"
    assert _setup(event_period_basis="representative_day").event_period_basis == "representative_day"
    with pytest.raises(ValidationError, match="representative day"):
        QueueSetup.model_validate({"queue_structure": "shared_queue", "fixed_server_count": 2,
                                   "event_period_basis": "representative_day"})


def test_per_date_records_are_unchanged():
    records, provenance = normalize_analysis_input(_events(EVENTS), _setup())
    assert provenance.get("period_basis", "per_date") == "per_date"
    assert sorted({r["time"] for r in records}) == [
        "2026-08-03 s1 UTC", "2026-08-04 s1 UTC", "2026-08-04 s2 UTC"]
    assert all("observation_days" not in r for r in records)


def test_representative_day_pools_all_dates_per_segment_and_queue():
    records, provenance = normalize_analysis_input(
        _events(EVENTS), _setup(event_period_basis="representative_day"))
    by_key = {(r["time"], r["queue_id"]): r for r in records}
    assert set(by_key) == {("s1", "a"), ("s1", "b"), ("s2", "a"), ("s2", "b")}
    # 3 arrivals at lane a in s1 over 2 observed days of 1 hour each.
    a1 = by_key[("s1", "a")]
    assert a1["lambda"] == pytest.approx(3 / (1.0 * 2))
    assert a1["observation_days"] == 2
    assert a1["segment_id"] == "s1"
    assert sorted(a1["service_samples_hours"]) == pytest.approx(sorted([6 / 60, 12 / 60, 3 / 60]))
    assert a1["mu"] == pytest.approx(1 / ((6 + 12 + 3) / 3 / 60))
    assert provenance["period_basis"] == "representative_day"
    assert provenance["observation_days"] == 2


def test_separate_events_accept_varying_staffing_but_shared_does_not():
    varying = _setup(staffing_varies_by_period=True, fixed_server_count=None,
                     segments=[{"id": "s1", "start_time": "05:00:00", "end_time": "06:00:00",
                                "active_queue_ids": ["a", "b"]},
                               {"id": "s2", "start_time": "06:00:00", "end_time": "07:00:00",
                                "active_queue_ids": ["a", "b"]}],
                     event_period_basis="representative_day")
    records, _ = normalize_analysis_input(_events(EVENTS), varying)
    assert {r["c"] for r in records} == {1}
    shared = QueueSetup.model_validate({"queue_structure": "shared_queue",
                                        "staffing_varies_by_period": True})
    frame = _events(EVENTS).drop(columns=["queue_id"])
    with pytest.raises(AnalysisIngestionError, match="fixed server count"):
        normalize_analysis_input(frame, shared)


# --- full coverage follows the lane schedule -------------------------------------

from backend.queueing_engine.services import separate_optimization as sep  # noqa: E402

DES = {"replications": 2, "base_seed": 7, "duration_hours": 4.0, "max_events": 2000}


def _shift_setup():
    return {"queue_structure": "separate_queues", "staffing_varies_by_period": True,
            "queue_ids": ["a", "b", "c"],
            "segments": [
                {"id": "s1", "start_time": "05:00:00", "end_time": "06:00:00", "active_queue_ids": ["a", "b"]},
                {"id": "s2", "start_time": "06:00:00", "end_time": "07:00:00", "active_queue_ids": ["a", "b", "c"]}]}


def _lane(time, queue_id, lam=2.0):
    return {"time": time, "segment_id": time, "queue_id": queue_id, "lambda": lam, "mu": 8.0, "c": 1,
            "service_samples_hours": [0.08, 0.1, 0.12, 0.15]}


def test_full_coverage_keeps_every_scheduled_lane_per_period():
    records = [_lane("s1", "a"), _lane("s1", "b"), _lane("s2", "a"), _lane("s2", "b"), _lane("s2", "c")]
    schedule = sep.optimize_separate_schedule(_shift_setup(), records, target=0.70,
                                              des_settings=DES, full_coverage=True)
    assert schedule["overall"] == "COMPLETE", schedule.get("reason")
    lanes = {p["time"]: [c["active_queue_ids"] for c in p["candidates"]] for p in schedule["periods"]}
    assert lanes == {"s1": [["a", "b"]], "s2": [["a", "b", "c"]]}


def test_full_coverage_rejects_records_that_disagree_with_the_schedule():
    missing = [_lane("s1", "a"), _lane("s2", "a"), _lane("s2", "b"), _lane("s2", "c")]
    with pytest.raises(ValueError, match="scheduled"):
        sep.optimize_separate_schedule(_shift_setup(), missing, target=0.70,
                                       des_settings=DES, full_coverage=True)
