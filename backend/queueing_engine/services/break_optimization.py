"""Separate-queue break schedule optimizer.

Moves each cashier's configured breaks (same cashier, same length) to start
times that lower the day's peak 15-minute utilization, then proves the result
with the existing continuous-day routing DES (simulation vs simulation only).

Spec: docs/superpowers/specs/2026-09-18-separate-break-optimizer.md.
The placement core (``place_breaks``) is pure: it takes per-slot lambda/mu so
the NovaMart 15-minute reference can be reproduced exactly.
"""

from __future__ import annotations

import math
from datetime import time as datetime_time
from typing import Any

from backend.queueing_engine.services.separate_optimization import (
    DES_DEFAULT_MAX_EVENTS,
    _segment_window,
    _summarize_metric,
    des_day_start_minutes,
    index_period_queues,
    replication_seeds,
    resolve_des_breaks,
    run_routing_day_des,
)

SLOT_MINUTES = 15
EDGE_MINUTES = 60
DEFAULT_TARGET_RHO = 0.85
DEFAULT_MAX_SHIFT_MINUTES = 120
_TOL = 1e-9

NOTES = [
    "Utilization per 15-minute slot uses each operating segment's pooled arrival and service "
    "rates, so every slot in an hourly segment shares the same demand.",
    "Simulated results compare the current and proposed break schedules under identical seeds. "
    "They are simulation versus simulation, never recorded waits.",
]


def _minutes(value: Any) -> float:
    parsed = datetime_time.fromisoformat(str(value))
    return parsed.hour * 60 + parsed.minute + parsed.second / 60


def _clock(minutes: float) -> str:
    total = int(round(minutes))
    return f"{total // 60:02d}:{total % 60:02d}"


def _clock_seconds(minutes: float) -> str:
    total = int(round(minutes * 60))
    return f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}"


def _peak(rows: list[dict]) -> float:
    return max((math.inf if row["rho"] is None else row["rho"] for row in rows), default=0.0)


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def _parse_breaks(breaks: list[dict], shifts: dict) -> list[dict]:
    parsed = []
    for index, entry in enumerate(breaks):
        queue_id = str(entry.get("queue_id"))
        if queue_id not in shifts:
            raise ValueError(f"Break for {queue_id} has no shift in the configured segments.")
        try:
            start = _minutes(entry.get("scheduled_start_time"))
        except (TypeError, ValueError):
            raise ValueError(
                f"Break for {queue_id} has an invalid scheduled_start_time: "
                f"{entry.get('scheduled_start_time')!r}.") from None
        duration = entry.get("duration_minutes")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
            raise ValueError(f"Break for {queue_id} needs a positive duration in minutes.")
        parsed.append({"index": index, "queue_id": queue_id, "start": start, "duration": float(duration),
                       "raw_duration": duration})
    return parsed


def slot_rho(slots: list[dict], shifts: dict, breaks: list[dict]) -> list[dict]:
    """Working cashiers and utilization per slot.

    ``working`` = cashiers on shift for the whole slot minus the fraction of the
    slot each of them spends on break. ``rho = lambda / (working * mu)``; it is
    0 without demand and None when demand meets nobody working.
    """
    parsed = breaks if breaks and "index" in breaks[0] else _parse_breaks(breaks, shifts)
    rows = []
    for slot in slots:
        start, end = float(slot["start"]), float(slot["end"])
        on_shift = [q for q, (low, high) in shifts.items() if low <= start and end <= high]
        away = sum(max(0.0, min(end, b["start"] + b["duration"]) - max(start, b["start"])) / (end - start)
                   for b in parsed if b["queue_id"] in on_shift)
        working = len(on_shift) - away
        lam, mu = float(slot["lambda"]), float(slot["mu"])
        if lam <= 0:
            rho: float | None = 0.0
        elif working <= _TOL or mu <= 0:
            rho = None
        else:
            rho = lam / (working * mu)
        rows.append({"start": start, "end": end, "lambda": lam, "mu": mu,
                     "on_shift": len(on_shift), "working": working, "rho": rho})
    return rows


def _better(score: float, tie: tuple, best: tuple[float, tuple] | None) -> bool:
    if best is None:
        return True
    best_score, best_tie = best
    if score == best_score or abs(score - best_score) <= _TOL:
        return tie < best_tie
    return score < best_score


def place_breaks(slots: list[dict], shifts: dict, breaks: list[dict], queue_order: list[str], *,
                 target: float = DEFAULT_TARGET_RHO,
                 max_shift_minutes: int = DEFAULT_MAX_SHIFT_MINUTES,
                 edge_minutes: int = EDGE_MINUTES,
                 step_minutes: int = SLOT_MINUTES) -> dict:
    """Greedy break placement (spec §Placement algorithm).

    Breaks are placed one at a time onto an empty schedule: longest first,
    then queue order, then current start. Each candidate start
    (current ± k·step, |k·step| ≤ max_shift_minutes) is scored by the day's
    peak slot rho with only already-placed breaks; ties go to the smallest
    move, then the earlier start. A candidate must lie inside the cashier's
    shift outside its first/last ``edge_minutes`` and keep order without
    overlap against the cashier's already-placed breaks.
    """
    if not (isinstance(target, (int, float)) and not isinstance(target, bool) and 0 < target <= 1):
        raise ValueError("Target utilization must be greater than 0 and at most 1.")
    if (isinstance(max_shift_minutes, bool) or not isinstance(max_shift_minutes, int)
            or max_shift_minutes < 0 or max_shift_minutes % step_minutes):
        raise ValueError(f"The maximum move must be a non-negative multiple of {step_minutes} minutes.")
    current = _parse_breaks(breaks, shifts)
    position = {queue_id: rank for rank, queue_id in enumerate(queue_order)}
    order = sorted(current, key=lambda b: (-b["duration"], position.get(b["queue_id"], len(position)),
                                           b["start"], b["index"]))
    steps = max_shift_minutes // step_minutes
    placed: list[dict] = []
    for item in order:
        low, high = shifts[item["queue_id"]]
        mine = [p for p in placed if p["queue_id"] == item["queue_id"]]
        best: tuple[float, tuple] | None = None
        best_start = None
        for k in range(-steps, steps + 1):
            start = item["start"] + k * step_minutes
            end = start + item["duration"]
            if start < low + edge_minutes - _TOL or end > high - edge_minutes + _TOL:
                continue
            feasible = True
            for other in mine:
                before = (other["start_current"], other["index"]) < (item["start"], item["index"])
                if before and other["start"] + other["duration"] > start + _TOL:
                    feasible = False
                if not before and end > other["start"] + _TOL:
                    feasible = False
            if not feasible:
                continue
            candidate = {**item, "start": start}
            score = _peak(slot_rho(slots, shifts, placed + [candidate]))
            tie = (abs(k), start)
            if _better(score, tie, best):
                best, best_start = (score, tie), start
        if best_start is None:
            raise ValueError(
                f"No allowed start for {item['queue_id']}'s break at {_clock(item['start'])}: it must stay "
                f"within ±{max_shift_minutes} minutes, inside the shift, and outside the first and last "
                f"{edge_minutes} minutes of the shift.")
        placed.append({**item, "start": best_start, "start_current": item["start"]})

    before_rows = slot_rho(slots, shifts, current)
    proposed = sorted(placed, key=lambda b: b["index"])
    after_rows = slot_rho(slots, shifts, proposed)
    peak_before, peak_after = _peak(before_rows), _peak(after_rows)
    improved = peak_after < peak_before - _TOL
    if not improved:
        proposed = [{**b, "start_current": b["start"]} for b in current]
        after_rows, peak_after = before_rows, peak_before

    labels: dict[int, str] = {}
    for queue_id in shifts:
        mine = sorted((b for b in current if b["queue_id"] == queue_id), key=lambda b: (b["start"], b["index"]))
        for number, entry in enumerate(mine, start=1):
            labels[entry["index"]] = f"Break {number}"

    proposed_out, moves = [], []
    for entry in proposed:
        shift = entry["start"] - entry["start_current"]
        proposed_out.append({
            "queue_id": entry["queue_id"], "label": labels[entry["index"]],
            "scheduled_start_time": _clock_seconds(entry["start"]),
            "duration_minutes": entry["raw_duration"],
            "current_start_time": _clock_seconds(entry["start_current"]),
            "shift_minutes": int(round(shift)),
        })
        if abs(shift) > _TOL:
            moves.append({"queue_id": entry["queue_id"], "label": labels[entry["index"]],
                          "from": _clock(entry["start_current"]), "to": _clock(entry["start"]),
                          "duration_minutes": entry["raw_duration"]})

    def above(rows: list[dict]) -> int:
        return sum(1 for row in rows if row["rho"] is None or row["rho"] > target)

    gaps = [{"start": _clock(row["start"]), "end": _clock(row["end"]), "on_shift": row["on_shift"],
             "rho_no_breaks": row["rho"]}
            for row in slot_rho(slots, shifts, [])
            if row["rho"] is None or row["rho"] >= target]
    return {
        "status": "improved" if improved else "no_improvement",
        "target_rho": float(target),
        "max_shift_minutes": max_shift_minutes,
        "all_below_target": all(row["rho"] is not None and row["rho"] < target for row in after_rows),
        "current_breaks": [{"queue_id": b["queue_id"], "label": labels[b["index"]],
                            "scheduled_start_time": _clock_seconds(b["start"]),
                            "duration_minutes": b["raw_duration"]} for b in current],
        "proposed_breaks": proposed_out,
        "moves": moves,
        "slots": [{"start": _clock(b["start"]), "end": _clock(b["end"]), "lambda": b["lambda"], "mu": b["mu"],
                   "working_before": b["working"], "working_after": a["working"],
                   "rho_before": b["rho"], "rho_after": a["rho"]}
                  for b, a in zip(before_rows, after_rows)],
        "peak_rho": {"before": _finite(peak_before), "after": _finite(peak_after)},
        "slots_above_target": {"before": above(before_rows), "after": above(after_rows)},
        "staffing_gaps": gaps,
    }


def _scheduled_lanes(setup: dict, segment: dict) -> list[str]:
    queue_ids = [str(q) for q in setup.get("queue_ids") or []]
    active = segment.get("active_queue_ids")
    if setup.get("staffing_varies_by_period") and active is not None:
        return [str(q) for q in active]
    return queue_ids


def slot_inputs_from_setup(setup: dict, records: list) -> tuple[list[dict], dict]:
    """Per-slot lambda/mu and per-cashier shifts from Setup and stored records.

    Requires a separate-queue, representative-day analysis with configured
    breaks. Slots are 15-minute steps from the earliest segment start; lambda
    is the segment's total arrival rate over its scheduled lanes (the rate the
    day DES uses) and mu the pooled rate ``samples / total service hours``.
    """
    setup = setup if isinstance(setup, dict) else {}
    if setup.get("queue_structure") != "separate_queues":
        raise ValueError("Break optimization is available for separate queues.")
    if setup.get("event_period_basis") != "representative_day":
        raise ValueError("Break optimization requires the representative day basis.")
    if not setup.get("breaks"):
        raise ValueError("This Analysis has no configured breaks to move.")
    segments = [seg for seg in setup.get("segments") or [] if isinstance(seg, dict)]
    origin = des_day_start_minutes(setup)
    if origin is None or not segments:
        raise ValueError("Break optimization requires configured operating segments.")
    windows = sorted(((_segment_window(seg), seg) for seg in segments), key=lambda item: item[0][1])
    active_spans: dict[str, list[tuple[float, float]]] = {}
    for (key, low, high), segment in windows:
        if (low - origin) % SLOT_MINUTES or (high - origin) % SLOT_MINUTES:
            raise ValueError(
                f"Segment {key} must start and end on the 15-minute grid from {_clock(origin)}.")
        for queue_id in _scheduled_lanes(setup, segment):
            active_spans.setdefault(queue_id, []).append((low, high))
    shifts: dict[str, tuple[float, float]] = {}
    for queue_id, spans in active_spans.items():
        spans.sort()
        if any(prev[1] != nxt[0] for prev, nxt in zip(spans, spans[1:])):
            raise ValueError(
                f"Cashier {queue_id} has more than one shift; break optimization needs one continuous "
                "shift per cashier.")
        shifts[queue_id] = (spans[0][0], spans[-1][1])
    slots: list[dict] = []
    for (key, low, high), segment in windows:
        rows = index_period_queues(records, key)
        lam = 0.0
        samples: list[float] = []
        for queue_id in _scheduled_lanes(setup, segment):
            row = rows.get(queue_id)
            if row is None:
                raise ValueError(f"Segment {key} has no stored record for scheduled cashier {queue_id}.")
            lam += float(row.get("lambda") or 0.0)
            samples.extend(float(value) for value in row.get("service_samples_hours") or [])
        if not samples or sum(samples) <= 0:
            raise ValueError(f"Segment {key} has no service times to estimate a service rate.")
        mu = len(samples) / sum(samples)
        start = low
        while start < high - _TOL:
            slots.append({"start": start, "end": start + SLOT_MINUTES, "lambda": lam, "mu": mu})
            start += SLOT_MINUTES
    return slots, shifts


def _run_summary(day: dict) -> dict:
    served = sum(lane["served"] for period in day["periods"] for lane in period["lanes"])
    wait = sum((lane["Wq"] or 0.0) * lane["served"] for period in day["periods"] for lane in period["lanes"])
    periods = {}
    for period in day["periods"]:
        count = sum(lane["served"] for lane in period["lanes"])
        total = sum((lane["Wq"] or 0.0) * lane["served"] for lane in period["lanes"])
        periods[period["time"]] = total / count * 60.0 if count else None
    return {
        "mean_wait_minutes": wait / served * 60.0 if served else None,
        "max_queue": max((lane["max_queue"] for period in day["periods"] for lane in period["lanes"]),
                         default=0),
        "admitted": day["admitted"], "served": day["served"],
        "customer_conservation": day["customer_conservation"] is True,
        "period_wait_minutes": periods,
    }


def _mean(values: list) -> float | None:
    present = [float(value) for value in values if value is not None]
    return math.fsum(present) / len(present) if present else None


def _schedule_des(windows: list[dict], tie_order: list[str], offsets: list[dict] | None,
                  seeds: list[int], max_events: int) -> dict:
    runs = []
    for seed in seeds:
        summary = _run_summary(run_routing_day_des(windows, tie_order=tie_order, seed=seed,
                                                   max_events=max_events, breaks=offsets))
        runs.append({"seed": seed, **summary})
    labels = [window["time"] for window in sorted(windows, key=lambda w: w["start_hours"])]
    return {
        "summary": {
            "mean_wait_minutes": _mean([run["mean_wait_minutes"] for run in runs]),
            "max_queue": _mean([run["max_queue"] for run in runs]),
            "admitted": _mean([run["admitted"] for run in runs]),
            "served": _mean([run["served"] for run in runs]),
            "customer_conservation": all(run["customer_conservation"] for run in runs),
        },
        "replications": [{key: value for key, value in run.items() if key != "period_wait_minutes"}
                         for run in runs],
        "periods": [{"time": label,
                     "mean_wait_minutes": _mean([run["period_wait_minutes"].get(label) for run in runs])}
                    for label in labels],
    }


def paired_wait_change(before_runs: list[dict], after_runs: list[dict]) -> dict:
    """95 % interval of the paired per-replication wait change (proposed - current).

    Replications share seeds (common random numbers), so each pair is one
    comparison. A pair with a missing wait is skipped, never zero-filled. The
    verdict comes from the interval only; with fewer than two pairs there is
    no interval and therefore no claim.
    """
    diffs = [after["mean_wait_minutes"] - before["mean_wait_minutes"]
             for before, after in zip(before_runs, after_runs)
             if before.get("mean_wait_minutes") is not None and after.get("mean_wait_minutes") is not None]
    summary = _summarize_metric(diffs) or {"mean": None, "sd": None, "se": None,
                                           "ci_lower": None, "ci_upper": None, "n": 0}
    lower, upper = summary["ci_lower"], summary["ci_upper"]
    if lower is not None and upper is not None and upper < 0:
        verdict = "shorter"
    elif lower is not None and upper is not None and lower > 0:
        verdict = "longer"
    else:
        verdict = "no_clear_difference"
    return {**summary, "verdict": verdict}


def compare_break_schedules_des(setup: dict, records: list, current: list[dict], proposed: list[dict], *,
                                replications: int, base_seed: int,
                                max_events: int = DES_DEFAULT_MAX_EVENTS) -> dict:
    """Run the existing continuous-day routing DES on both break schedules.

    One window per configured segment with its scheduled lanes, the stored
    record lambda, and the stored service samples; breaks resolve through
    ``resolve_des_breaks``. Both schedules use the same seeds.
    """
    origin = des_day_start_minutes(setup)
    if origin is None:
        raise ValueError("Break optimization requires configured operating segments.")
    windows = []
    for segment in setup.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        key, low, high = _segment_window(segment)
        windows.append({"time": key, "start_hours": (low - origin) / 60.0, "end_hours": (high - origin) / 60.0,
                        "active_queue_ids": _scheduled_lanes(setup, segment),
                        "queues_by_id": index_period_queues(records, key)})

    def clean(entries: list[dict]) -> list[dict]:
        return [{"queue_id": e["queue_id"], "scheduled_start_time": e["scheduled_start_time"],
                 "duration_minutes": e["duration_minutes"]} for e in entries]

    current_offsets = resolve_des_breaks({**setup, "breaks": clean(current)})
    proposed_offsets = resolve_des_breaks({**setup, "breaks": clean(proposed)})
    seeds = replication_seeds(base_seed, replications)
    tie_order = [str(q) for q in setup.get("queue_ids") or []]
    before = _schedule_des(windows, tie_order, current_offsets, seeds, max_events)
    after = _schedule_des(windows, tie_order, proposed_offsets, seeds, max_events)
    pairs = list(zip(before["replications"], after["replications"]))
    change = (None if before["summary"]["mean_wait_minutes"] is None
              or after["summary"]["mean_wait_minutes"] is None
              else after["summary"]["mean_wait_minutes"] - before["summary"]["mean_wait_minutes"])
    return {
        "seeds": seeds,
        "current": before,
        "proposed": after,
        "comparison": {
            "mean_wait_change_minutes": change,
            "proposed_better_runs": sum(
                1 for b, a in pairs
                if b["mean_wait_minutes"] is not None and a["mean_wait_minutes"] is not None
                and a["mean_wait_minutes"] < b["mean_wait_minutes"]),
            "runs": len(pairs),
            "paired_wait_change": paired_wait_change(before["replications"], after["replications"]),
        },
    }


def optimize_separate_breaks(setup: dict, records: list, *, target: float = DEFAULT_TARGET_RHO,
                             max_shift_minutes: int = DEFAULT_MAX_SHIFT_MINUTES,
                             replications: int, base_seed: int) -> dict:
    """Slot inputs -> greedy placement -> DES proof on both schedules."""
    slots, shifts = slot_inputs_from_setup(setup, records)
    result = place_breaks(slots, shifts, list(setup.get("breaks") or []),
                          [str(q) for q in setup.get("queue_ids") or []],
                          target=target, max_shift_minutes=max_shift_minutes)
    result["des"] = compare_break_schedules_des(setup, records, result["current_breaks"],
                                                result["proposed_breaks"],
                                                replications=replications, base_seed=base_seed)
    result["notes"] = list(NOTES)
    return result


__all__ = [
    "DEFAULT_MAX_SHIFT_MINUTES",
    "DEFAULT_TARGET_RHO",
    "compare_break_schedules_des",
    "optimize_separate_breaks",
    "place_breaks",
    "slot_inputs_from_setup",
    "slot_rho",
]
