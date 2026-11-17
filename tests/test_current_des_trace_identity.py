"""D2 trace identity: the Current separate-lanes DES sample path is unchanged by the accounting fix.

All data here is SYNTHETIC. The fixture was written on unmodified origin/main c2316ed4, before any D2
engine edit (owner authorization 2026-11-17, handoff output/d2-fix-20261117 §4 "Trace identity"), by running

    NOVAQ_WRITE_D2_TRACE_IDENTITY=1 python -m pytest tests/test_current_des_trace_identity.py

Without the variable the test only compares, byte for byte. Per setup and seed it records the canonical
digest of the trace and every row field the fix must not change: all fields except the three accounting
fields ``busy_time``, ``rho_sim`` and ``Wq_sim`` and the fields D2 adds. Compact per-date days keep their
``trace_digest``; their ``rows_digest`` covers the accounting fields, so it is left out.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.queueing_engine.simulation.simulation import (
    canonical_digest,
    simulate_parallel_days_compact,
    simulate_parallel_days_with_trace,
    simulate_segments_with_trace,
)

FIXTURE = Path(__file__).parent / "fixtures" / "current_des_trace_identity_c2316ed4.json"
ACCOUNTING = frozenset({"busy_time", "rho_sim", "Wq_sim"})
D2_ADDED = frozenset({"started", "censored_customers", "censored_waiting_hours", "active"})
SEEDS = (1, 7, 42)


def _setup(lanes, periods, active=None, breaks=None, basis="representative_day") -> dict:
    segments = []
    for index, (period, start, end) in enumerate(periods):
        segment: dict[str, Any] = {"id": period, "start_time": start, "end_time": end}
        if active is not None:
            segment["active_queue_ids"] = active[index]
        segments.append(segment)
    setup: dict[str, Any] = {
        "queue_structure": "separate_queues", "queue_ids": list(lanes), "fixed_server_count": len(lanes),
        "staffing_varies_by_period": active is not None, "capacity_mode": "unlimited",
        "abandonment_mode": "not_modeled", "event_period_basis": basis,
        "separate_queue_closure_policy": "drain_existing", "segments": segments,
    }
    if breaks is not None:
        setup["breaks"] = breaks
    return setup


def _record(period, lane, lam, samples, label=None) -> dict:
    return {
        "segment_id": period, "time": label or period, "queue_id": lane, "queue_structure": "separate_queues",
        "model_id": "parallel_mg1", "lambda": lam, "mu": len(samples) / sum(samples), "c": 1,
        "service_time_source": "empirical", "service_samples_hours": list(samples),
    }


BREAK_PERIODS = [("p0", "08:00:00", "09:00:00"), ("p1", "09:00:00", "10:00:00"), ("p2", "10:00:00", "11:00:00")]
BREAK_SETUP = _setup(["a", "b"], BREAK_PERIODS, breaks=[
    {"queue_id": "a", "scheduled_start_time": "08:30", "duration_minutes": 30},
    {"queue_id": "b", "scheduled_start_time": "09:45", "duration_minutes": 30},
])
BREAK_RECORDS = [_record(p, "a", 5.0, [0.1, 0.15, 0.3]) for p, _, _ in BREAK_PERIODS] + [
    _record(p, "b", 3.0, [0.2, 0.4]) for p, _, _ in BREAK_PERIODS]

PLAIN_PERIODS = [("q1", "08:00:00", "08:30:00"), ("q2", "08:30:00", "10:00:00"),
                 ("q3", "10:00:00", "10:45:00"), ("q4", "10:45:00", "11:00:00")]
PLAIN_SETUP = _setup(["a", "b", "c"], PLAIN_PERIODS)
PLAIN_RECORDS = [
    _record(p, lane, lam, samples) for p, _, _ in PLAIN_PERIODS
    for lane, lam, samples in (("a", 6.0, [0.15, 0.25]), ("b", 2.0, [0.6, 0.9]), ("c", 4.0, [0.05, 0.5]))
]

DATE_PERIODS = [("s1", "05:00:00", "06:00:00"), ("s2", "06:00:00", "07:00:00")]
DATE_SETUP = _setup(["a", "b"], DATE_PERIODS, basis="per_date",
                    breaks=[{"queue_id": "a", "scheduled_start_time": "05:30", "duration_minutes": 15}])
DATES = ("2026-08-03", "2026-08-04")
DATE_DAYS = [
    (date, [_record(p, lane, lam, samples, f"{date} {p} UTC") for p, _, _ in DATE_PERIODS
            for lane, lam, samples in (("a", 4.0 + index, [0.2, 0.25]), ("b", 2.0, [0.1, 0.45]))])
    for index, date in enumerate(DATES)
]

DRAIN_SETUP = _setup(["a", "b"], BREAK_PERIODS, active=[["a", "b"], ["a"], ["a"]])
DRAIN_RECORDS = [_record(p, "a", 1.5, [0.1, 0.2]) for p, _, _ in BREAK_PERIODS] + [
    _record("p0", "b", 8.0, [0.2, 0.3])]


def _rows(rows: list[dict]) -> list[dict]:
    return [{key: value for key, value in row.items() if key not in ACCOUNTING | D2_ADDED} for row in rows]


def _identity(result: dict) -> dict:
    """The fields of one run the accounting fix must leave unchanged (trace by digest)."""
    out: dict[str, Any] = {key: value for key, value in result.items() if key not in {"results", "trace", "days"}}
    out["results"] = _rows(result["results"])
    out["trace_digest"] = canonical_digest(result["trace"])
    out["trace_events"] = len(result["trace"])
    if "days" in result:
        out["days"] = [{key: value for key, value in day.items() if key != "rows_digest"} for day in result["days"]]
    return out


def _actual() -> dict:
    out: dict[str, Any] = {}
    for seed in SEEDS:
        out[f"representative_breaks_seed{seed}"] = _identity(simulate_segments_with_trace(
            BREAK_RECORDS, sim_hours=1.0, max_events=100_000, seed=seed, queue_setup=BREAK_SETUP))
        out[f"representative_no_breaks_seed{seed}"] = _identity(simulate_segments_with_trace(
            PLAIN_RECORDS, sim_hours=1.0, max_events=100_000, seed=seed, queue_setup=PLAIN_SETUP))
        out[f"draining_lane_seed{seed}"] = _identity(simulate_segments_with_trace(
            DRAIN_RECORDS, sim_hours=1.0, max_events=100_000, seed=seed, queue_setup=DRAIN_SETUP))
        seeds = [seed, seed + 1000]
        out[f"per_date_two_dates_compact_seed{seed}"] = _identity(simulate_parallel_days_compact(
            DATE_DAYS, DATE_SETUP, 1.0, seeds, 100_000))
        out[f"per_date_two_dates_full_seed{seed}"] = _identity(simulate_parallel_days_with_trace(
            DATE_DAYS, DATE_SETUP, 1.0, seeds, 100_000))
    return out


def _encoded(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=1, allow_nan=False, ensure_ascii=False) + "\n"


def test_trace_and_non_accounting_fields_are_byte_identical_to_c2316ed4():
    actual = _actual()
    for name, run in actual.items():
        # Every setup is supported and actually exercises its scenario.
        assert run["results"] and all(row["simulation_supported"] is True for row in run["results"]), name
        assert run["truncated"] is False, name
        if "compact" in name:
            assert all(day["event_count"] > 0 and day["truncated"] is False for day in run["days"]), name
        else:
            assert run["trace_events"] > 0, name
        has_breaks = name.startswith(("representative_breaks", "per_date"))
        assert bool(run.get("break_policy")) is has_breaks, name
    payload = {"generated_at": "c2316ed4 (origin/main, before the D2 engine edit)", "data": "SYNTHETIC",
               "runs": actual}
    if os.environ.get("NOVAQ_WRITE_D2_TRACE_IDENTITY") == "1":
        FIXTURE.write_text(_encoded(payload), encoding="utf-8", newline="\n")
    assert _encoded(payload) == FIXTURE.read_text(encoding="utf-8")
