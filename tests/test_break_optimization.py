"""Separate-queue break optimizer: pure placement core and Setup slot inputs.

Spec: docs/superpowers/specs/2026-09-18-separate-break-optimizer.md.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.api.analysis_schemas import QueueSetup
from backend.data.analysis_ingestion import normalize_analysis_input
from backend.queueing_engine.services import break_optimization as bo

# NovaMart ``Avg 15Min`` sheet (novaq_data.xlsx): slot start, arrivals over
# 14 days, total service minutes. lambda/h = a * 4 / 14, mu/h = 60 * a / svc
# reproduce the sheet's ``Lambda / hr`` and ``Mu / hr`` columns exactly.
AVG_15MIN = [
    ("05:00", 24, 290), ("05:15", 27, 316), ("05:30", 23, 286), ("05:45", 20, 233),
    ("06:00", 23, 294), ("06:15", 25, 317), ("06:30", 23, 294), ("06:45", 30, 384),
    ("07:00", 20, 231), ("07:15", 33, 427), ("07:30", 29, 370), ("07:45", 33, 367),
    ("08:00", 35, 446), ("08:15", 31, 397), ("08:30", 28, 333), ("08:45", 29, 356),
    ("09:00", 34, 396), ("09:15", 34, 444), ("09:30", 30, 359), ("09:45", 31, 396),
    ("10:00", 49, 577), ("10:15", 54, 665), ("10:30", 41, 521), ("10:45", 39, 550),
    ("11:00", 31, 413), ("11:15", 32, 400), ("11:30", 42, 557), ("11:45", 25, 328),
    ("12:00", 35, 444), ("12:15", 42, 565), ("12:30", 35, 506), ("12:45", 24, 293),
    ("13:00", 52, 599), ("13:15", 48, 559), ("13:30", 53, 605), ("13:45", 28, 338),
    ("14:00", 27, 325), ("14:15", 42, 533), ("14:30", 46, 564), ("14:45", 25, 302),
    ("15:00", 23, 283), ("15:15", 21, 250), ("15:30", 31, 426), ("15:45", 22, 282),
    ("16:00", 26, 304), ("16:15", 24, 318), ("16:30", 29, 353), ("16:45", 14, 162),
    ("17:00", 18, 232), ("17:15", 23, 290), ("17:30", 14, 161), ("17:45", 23, 187),
]
QUEUES = ["cashier_1", "cashier_2", "cashier_3", "cashier_4", "cashier_5"]


def _m(clock: str) -> int:
    return int(clock[:2]) * 60 + int(clock[3:5])


def _reference_slots():
    return [{"start": _m(t), "end": _m(t) + 15, "lambda": a * 4 / 14, "mu": 60 * a / svc}
            for t, a, svc in AVG_15MIN]


SHIFTS = {**{q: (_m("05:00"), _m("17:00")) for q in QUEUES[:3]},
          **{q: (_m("06:00"), _m("18:00")) for q in QUEUES[3:]}}


def _brk(queue_id, start, minutes):
    return {"queue_id": queue_id, "scheduled_start_time": f"{start}:00", "duration_minutes": minutes}


CURRENT = ([b for q in QUEUES[:3] for b in (_brk(q, "07:00", 30), _brk(q, "11:00", 60), _brk(q, "15:00", 15))]
           + [b for q in QUEUES[3:] for b in (_brk(q, "07:30", 30), _brk(q, "12:00", 60), _brk(q, "15:15", 15))])


def _place(**kwargs):
    return bo.place_breaks(_reference_slots(), SHIFTS, CURRENT, QUEUES, **kwargs)


def _assert_rules(result, shifts, current, window=120, edge=60):
    proposed = result["proposed_breaks"]
    assert len(proposed) == len(current)
    for before, after in zip(current, proposed):
        assert after["queue_id"] == before["queue_id"]
        assert after["duration_minutes"] == before["duration_minutes"]
        start = _m(after["scheduled_start_time"])
        shift = start - _m(before["scheduled_start_time"])
        assert shift % 15 == 0 and abs(shift) <= window
        low, high = shifts[after["queue_id"]]
        assert start >= low + edge and start + after["duration_minutes"] <= high - edge
    for queue_id in shifts:
        mine_before = [b for b in current if b["queue_id"] == queue_id]
        mine_after = [p for p in proposed if p["queue_id"] == queue_id]
        order_before = sorted(range(len(mine_before)), key=lambda i: _m(mine_before[i]["scheduled_start_time"]))
        order_after = sorted(range(len(mine_after)), key=lambda i: _m(mine_after[i]["scheduled_start_time"]))
        assert order_before == order_after
        spans = sorted((_m(p["scheduled_start_time"]), _m(p["scheduled_start_time"]) + p["duration_minutes"])
                       for p in mine_after)
        assert all(prev[1] <= nxt[0] for prev, nxt in zip(spans, spans[1:]))


def test_reference_avg15min_reproduces_prototype():
    result = _place()
    moves = {(m["queue_id"], m["from"], m["to"]) for m in result["moves"]}
    assert moves == {
        ("cashier_2", "11:00", "10:30"),
        ("cashier_3", "07:00", "06:45"),
        ("cashier_3", "11:00", "11:45"),
        ("cashier_4", "12:00", "13:45"),
        ("cashier_5", "12:00", "12:45"),
    }
    assert result["status"] == "improved"
    assert round(result["peak_rho"]["before"], 4) == 1.3262
    assert round(result["peak_rho"]["after"], 4) == 0.7202
    assert result["slots_above_target"] == {"before": 5, "after": 0}
    assert result["all_below_target"] is True
    assert result["staffing_gaps"] == []


def test_proposed_breaks_respect_rules():
    _assert_rules(_place(), SHIFTS, CURRENT)
    slots = [{"start": s, "end": s + 15, "lambda": 20.0 if 600 <= s < 660 else 4.0, "mu": 5.0}
             for s in range(480, 1020, 15)]
    shifts = {"a": (480, 1020), "b": (480, 1020), "c": (540, 1020)}
    current = [_brk("a", "10:00", 30), _brk("a", "12:00", 60), _brk("b", "10:00", 60), _brk("c", "10:15", 15)]
    result = bo.place_breaks(slots, shifts, current, ["a", "b", "c"])
    _assert_rules(result, shifts, current)


def test_max_shift_window_is_configurable():
    result = _place(max_shift_minutes=0)
    assert result["moves"] == []
    assert result["status"] == "no_improvement"
    with pytest.raises(ValueError, match="multiple of 15"):
        _place(max_shift_minutes=20)


def test_tie_prefers_nearest_then_earlier():
    # Flat demand: every candidate gives the same peak, so the break stays put.
    slots = [{"start": s, "end": s + 15, "lambda": 2.0, "mu": 5.0} for s in range(480, 960, 15)]
    shifts = {"a": (480, 960), "b": (480, 960)}
    stay = bo.place_breaks(slots, shifts, [_brk("a", "12:00", 30)], ["a", "b"])
    assert stay["moves"] == [] and stay["status"] == "no_improvement"
    # Break sits on a hot slot; the two nearest escapes (11:30 and 12:30) tie,
    # so the earlier one wins.
    hot = [dict(s, **{"lambda": 8.0}) if s["start"] in (720, 735) else s for s in slots]
    moved = bo.place_breaks(hot, shifts, [_brk("a", "12:00", 30)], ["a", "b"], max_shift_minutes=30)
    assert [(m["from"], m["to"]) for m in moved["moves"]] == [("12:00", "11:30")]


def test_no_improvement_keeps_current_schedule():
    slots = [{"start": s, "end": s + 15, "lambda": 2.0, "mu": 5.0} for s in range(480, 960, 15)]
    shifts = {"a": (480, 960), "b": (480, 960)}
    current = [_brk("a", "10:00", 30), _brk("b", "13:00", 30)]
    result = bo.place_breaks(slots, shifts, current, ["a", "b"])
    assert result["status"] == "no_improvement"
    assert [(p["queue_id"], p["scheduled_start_time"]) for p in result["proposed_breaks"]] == [
        ("a", "10:00:00"), ("b", "13:00:00")]
    assert result["peak_rho"]["after"] == result["peak_rho"]["before"]


def test_unplaceable_break_raises_named_error():
    slots = [{"start": s, "end": s + 15, "lambda": 2.0, "mu": 5.0} for s in range(480, 660, 15)]
    shifts = {"a": (480, 660), "b": (480, 660)}
    # A 90-minute break cannot fit between 09:00 and 10:00 (shift minus 60-minute edges).
    with pytest.raises(ValueError, match="No allowed start for a's break at 08:30"):
        bo.place_breaks(slots, shifts, [_brk("a", "08:30", 90)], ["a", "b"])


def test_staffing_gaps_reported_when_no_move_can_fix():
    slots = [{"start": s, "end": s + 15, "lambda": 2.0, "mu": 5.0} for s in range(480, 720, 15)]
    slots[4] = dict(slots[4], **{"lambda": 12.0})           # 09:00: 12 / (2 x 5) = 1.2 >= target
    slots.append({"start": 720, "end": 735, "lambda": 3.0, "mu": 5.0})  # nobody on shift
    shifts = {"a": (480, 720), "b": (480, 720)}
    result = bo.place_breaks(slots, shifts, [_brk("a", "10:00", 15)], ["a", "b"])
    gaps = {(g["start"], g["on_shift"]): g["rho_no_breaks"] for g in result["staffing_gaps"]}
    assert gaps == {("09:00", 2): pytest.approx(1.2), ("12:00", 0): None}
    assert result["all_below_target"] is False


def test_partial_slot_break_counts_fractional_working():
    slots = [{"start": 480, "end": 495, "lambda": 3.0, "mu": 2.0}]
    rows = bo.slot_rho(slots, {"a": (480, 600), "b": (480, 600)}, [_brk("a", "07:50", 10)])
    # The 07:50-08:00 break ends before the slot starts, so both cashiers work.
    assert rows[0]["working"] == pytest.approx(2.0)
    rows = bo.slot_rho(slots, {"a": (480, 600), "b": (480, 600)},
                       [{"queue_id": "a", "scheduled_start_time": "08:05:00", "duration_minutes": 5}])
    assert rows[0]["working"] == pytest.approx(2 - 5 / 15)
    assert rows[0]["rho"] == pytest.approx(3.0 / ((2 - 5 / 15) * 2.0))


# --- Setup + stored records -> slot inputs -------------------------------------------------


def _setup(**over):
    base = {
        "queue_structure": "separate_queues",
        "staffing_varies_by_period": True,
        "capacity_mode": "unlimited",
        "abandonment_mode": "not_modeled",
        "event_period_basis": "representative_day",
        "segments": [
            {"id": None, "start_time": "08:00:00", "end_time": "09:00:00", "active_queue_ids": ["a", "b"]},
            {"id": None, "start_time": "09:00:00", "end_time": "10:00:00", "active_queue_ids": ["a", "b"]},
            {"id": None, "start_time": "10:00:00", "end_time": "11:00:00", "active_queue_ids": ["b"]},
        ],
        "queue_ids": ["a", "b"],
        "breaks": [{"queue_id": "b", "scheduled_start_time": "09:00:00", "duration_minutes": 15}],
    }
    base.update(over)
    return QueueSetup.model_validate(base).model_dump(mode="json")


def _events():
    rows = []
    for date in ("2026-08-03", "2026-08-04"):
        for clock, minutes, queue in (("08:10", 6, "a"), ("08:20", 12, "b"), ("09:05", 9, "a"),
                                      ("09:30", 3, "b"), ("10:10", 10, "b")):
            start = pd.Timestamp(f"{date}T{clock}:00Z")
            rows.append({"arrival_time": start.isoformat(), "service_start": start.isoformat(),
                         "service_end": (start + pd.Timedelta(minutes=minutes)).isoformat(),
                         "queue_id": queue})
    return pd.DataFrame(rows)


def _records(setup):
    records, _ = normalize_analysis_input(_events(), QueueSetup.model_validate(setup))
    return records


def test_slot_inputs_pool_hourly_records():
    setup = _setup()
    slots, shifts = bo.slot_inputs_from_setup(setup, _records(setup))
    assert [s["start"] for s in slots] == list(range(480, 660, 15))
    first_hour = slots[:4]
    # 08:00-09:00: lanes a and b each 2 arrivals over 2 days -> 1/h each.
    assert all(s["lambda"] == pytest.approx(2.0) for s in first_hour)
    # Pooled mu = samples / total service hours = 4 / ((6+12+6+12)/60).
    assert all(s["mu"] == pytest.approx(4 / (36 / 60)) for s in first_hour)
    assert slots[8]["lambda"] == pytest.approx(1.0)       # 10:00 hour: only b, 2 arrivals / 2 days
    assert shifts == {"a": (480, 600), "b": (480, 660)}


def test_slot_inputs_reject_per_date_off_grid_split_shift_no_breaks():
    setup = _setup()
    records = _records(setup)
    with pytest.raises(ValueError, match="^Break optimization is available for separate queues.$"):
        bo.slot_inputs_from_setup({**setup, "queue_structure": "shared_queue"}, records)
    with pytest.raises(ValueError, match="^Break optimization requires the representative day basis.$"):
        bo.slot_inputs_from_setup({**setup, "event_period_basis": "per_date"}, records)
    with pytest.raises(ValueError, match="^This Analysis has no configured breaks to move.$"):
        bo.slot_inputs_from_setup({**setup, "breaks": []}, records)
    off_grid = [dict(seg) for seg in setup["segments"]]
    off_grid[2]["end_time"] = "10:50:00"
    with pytest.raises(ValueError, match="15-minute grid"):
        bo.slot_inputs_from_setup({**setup, "segments": off_grid}, records)
    split = [dict(seg) for seg in setup["segments"]]
    split[1]["active_queue_ids"] = ["b"]
    split[2]["active_queue_ids"] = ["a", "b"]
    with pytest.raises(ValueError, match="more than one shift"):
        bo.slot_inputs_from_setup({**setup, "segments": split}, records)


# --- R12: anchored window + fixed-point passes ---------------------------------------------


def _clock_of(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def _anchored(proposed, current):
    """Proposed starts as the next Setup, anchored at the original starts (what Apply stores)."""
    return [{"queue_id": p["queue_id"], "scheduled_start_time": p["scheduled_start_time"],
             "duration_minutes": p["duration_minutes"], "original_start_time": c["scheduled_start_time"]}
            for p, c in zip(proposed, current)]


def test_one_run_reaches_a_fixed_point():
    result = _place()
    again = bo.place_breaks(_reference_slots(), SHIFTS, _anchored(result["proposed_breaks"], CURRENT), QUEUES)
    assert again["moves"] == []
    assert again["peak_rho"]["before"] == result["peak_rho"]["after"]
    assert result["pass_cap_reached"] is False
    assert result["passes"] >= 1


def test_every_proposed_start_stays_within_the_window_of_the_anchor():
    result = _place()
    for before, after in zip(CURRENT, result["proposed_breaks"]):
        assert abs(_m(after["scheduled_start_time"]) - _m(before["scheduled_start_time"])) <= 120
    # A Setup already moved late by an earlier apply can never drift further from its anchor.
    drifted = [dict(b, scheduled_start_time=_clock_of(_m(b["scheduled_start_time"]) + 60),
                    original_start_time=b["scheduled_start_time"]) for b in CURRENT]
    moved = bo.place_breaks(_reference_slots(), SHIFTS, drifted, QUEUES)
    for entry, after in zip(drifted, moved["proposed_breaks"]):
        assert abs(_m(after["scheduled_start_time"]) - _m(entry["original_start_time"])) <= 120


def test_window_is_measured_from_original_start_time():
    slots = [{"start": s, "end": s + 15, "lambda": 2.0, "mu": 5.0} for s in range(480, 960, 15)]
    slots = [dict(s, **{"lambda": 8.0}) if 720 <= s["start"] < 780 else s for s in slots]  # 12:00-13:00 hot
    shifts = {"a": (480, 960), "b": (480, 960)}
    entry = dict(_brk("a", "12:00", 30), original_start_time="10:00:00")
    result = bo.place_breaks(slots, shifts, [entry], ["a", "b"], max_shift_minutes=30)
    start = _m(result["proposed_breaks"][0]["scheduled_start_time"])
    assert 570 <= start <= 630                                   # 10:00 +/- 30, not 12:00 +/- 30
    assert result["proposed_breaks"][0]["current_start_time"] == "12:00:00"
    assert [m["from"] for m in result["moves"]] == ["12:00"]


def test_peak_never_increases_between_passes():
    result = _place()
    peaks = result["pass_peak_rho"]
    assert len(peaks) == result["passes"]
    assert all(later <= earlier for earlier, later in zip(peaks, peaks[1:]))
    assert peaks[-1] == result["peak_rho"]["after"]


def test_pass_cap_is_reported():
    capped = _place(max_passes=1)
    assert capped["passes"] == 1
    assert capped["pass_cap_reached"] is True
    assert bo.MAX_PLACEMENT_PASSES == 10
