"""Representative-day staffing evidence comes from the continuous-day DES (finding K).

Full coverage leaves one candidate per period, so the optimizer only labels
each period FEASIBLE or INFEASIBLE and estimates its cost. Before this change
each period ran alone for 24 h, so a one-hour break was 1/24 of the run and
its load and waits were diluted. For a representative-day analysis each
replication now runs the whole schedule (breaks included) as one day, and a
period's lane utilization, waits and waiting cost come from its hour of that
day. The FEASIBLE rule, target, cost formula, seeds and ranking are unchanged.
Synthetic inputs only; no research data is modified.
"""
from __future__ import annotations

from statistics import mean

import pytest

from backend.data.setup_derivation import derive_setup
from backend.queueing_engine.services import separate_optimization as sep
from tests.test_setup_derivation import sheets

SAMPLES = [0.06, 0.08, 0.10, 0.12, 0.14]
LABELS = ("10:00", "11:00", "12:00")
DES = {"replications": 8, "base_seed": 42, "duration_hours": 24.0, "max_events": 200000}


def _setup(basis="representative_day"):
    return {
        "queue_structure": "separate_queues", "fixed_server_count": 2, "staffing_varies_by_period": False,
        "capacity_mode": "unlimited", "abandonment_mode": "not_modeled", "queue_ids": ["a", "b"],
        "segments": [{"id": label, "start_time": f"{label}:00", "end_time": f"{int(label[:2]) + 1}:00:00",
                      "active_queue_ids": None} for label in LABELS],
        "separate_queue_closure_policy": "drain_existing", "event_period_basis": basis,
        "breaks": [{"queue_id": "b", "scheduled_start_time": "11:00:00", "duration_minutes": 60}],
    }


def _records():
    return [{"time": label, "segment_id": label, "queue_id": queue_id, "lambda": 4.5, "mu": 10.0, "c": 1,
             "service_samples_hours": SAMPLES} for label in LABELS for queue_id in ("a", "b")]


DATES = ("2026-09-08", "2026-09-09")


def _per_date_records(dates=DATES[:1], lam=4.5):
    """Records as per-date ingestion writes them: one period per date and segment, labelled by date."""
    return [{"time": f"{date} {label} UTC", "segment_id": label, "queue_id": queue_id, "lambda": lam, "mu": 10.0,
             "c": 1, "service_samples_hours": SAMPLES} for date in dates for label in LABELS for queue_id in ("a", "b")]


def _date_day_lanes(setup, records, date, seeds, active=("a", "b")):
    """Per (period, lane) values of one date's continuous day run alone, from empty."""
    origin = sep.des_day_start_minutes(setup)
    windows = []
    for segment in setup["segments"]:
        key, low, high = sep._segment_window(segment)
        label = f"{date} {key} UTC"
        windows.append({"time": label, "start_hours": (low - origin) / 60, "end_hours": (high - origin) / 60,
                        "active_queue_ids": list(active), "queues_by_id": sep.index_period_queues(records, label)})
    out: dict[tuple[str, str], list[dict]] = {}
    for seed in seeds:
        day = sep.run_routing_day_des(windows, tie_order=list(setup["queue_ids"]), seed=seed,
                                      max_events=200000, breaks=sep.resolve_des_breaks(setup))
        for period in day["periods"]:
            for lane in period["lanes"]:
                out.setdefault((period["time"], lane["queue_id"]), []).append(lane)
    return out


def _day_lanes(setup, records, windows_active, seeds):
    """Per (period, lane) values from the continuous-day DES, the way Validation runs it."""
    origin = sep.des_day_start_minutes(setup)
    windows = []
    for segment in setup["segments"]:
        key, low, high = sep._segment_window(segment)
        windows.append({"time": key, "start_hours": (low - origin) / 60, "end_hours": (high - origin) / 60,
                        "active_queue_ids": windows_active[key],
                        "queues_by_id": sep.index_period_queues(records, key)})
    out: dict[tuple[str, str], list[dict]] = {}
    for seed in seeds:
        day = sep.run_routing_day_des(windows, tie_order=list(setup["queue_ids"]), seed=seed,
                                      max_events=200000, breaks=sep.resolve_des_breaks(setup))
        for period in day["periods"]:
            for lane in period["lanes"]:
                out.setdefault((period["time"], lane["queue_id"]), []).append(lane)
    return out


def _schedule(setup, records=None, target=0.70):
    return sep.optimize_separate_schedule(setup, records or _records(), target=target,
                                          des_settings=DES, full_coverage=True)


def test_break_hour_is_judged_on_the_continuous_day():
    schedule = _schedule(_setup())
    periods = {p["time"]: p for p in schedule["periods"]}
    assert periods["11:00"]["overall"] == "INFEASIBLE"
    assert schedule["overall"] == "INFEASIBLE"
    candidate = periods["11:00"]["candidates"][0]
    day = _day_lanes(_setup(), _records(), {label: ["a", "b"] for label in LABELS},
                     sep.replication_seeds(42, 8))
    expected = mean(min(1.0, lane["rho"]) for lane in day[("11:00", "a")])
    assert candidate["candidate_utilization"] == pytest.approx(expected)
    assert candidate["candidate_utilization"] > 0.70
    assert schedule["utilization_basis"] == "continuous-day DES"
    assert periods["11:00"]["utilization_basis"] == "continuous-day DES"


def test_period_cost_uses_the_period_hour_with_the_existing_formula():
    records = [{**row, "lambda": 2.0} for row in _records()]
    schedule = _schedule(_setup(), records, target=0.90)
    period = next(p for p in schedule["periods"] if p["time"] == "11:00")
    assert period["overall"] == "OPTIMAL"
    day = _day_lanes(_setup(), records, {label: ["a", "b"] for label in LABELS},
                     sep.replication_seeds(42, 8))
    lanes_11 = (day[("11:00", "a")], day[("11:00", "b")])
    assert all(lane["rho"] <= 0.90 for lanes in lanes_11 for lane in lanes)
    per_run = [sum(lanes[i]["served"] / 1.0 * lanes[i]["Wq"] * sep.DEFAULT_WAIT_COST_HR
                   for lanes in lanes_11 if lanes[i]["Wq"] is not None) for i in range(8)]
    assert period["optimum"]["waiting_cost"] == pytest.approx(mean(per_run))
    assert period["optimum"]["near_target_noise"] in (True, False)


def test_per_date_break_hour_is_judged_on_its_own_continuous_day():
    # B13 (replaces the K1 pin): the per-date break hour is judged inside its date's continuous day.
    setup, records = _setup("per_date"), _per_date_records()
    schedule = _schedule(setup, records)
    assert schedule["utilization_basis"] == "continuous-day DES"
    period = next(p for p in schedule["periods"] if p["time"] == "2026-09-08 11:00 UTC")
    day = _date_day_lanes(setup, records, "2026-09-08", sep.replication_seeds(42, 8))
    expected = mean(min(1.0, lane["rho"]) for lane in day[("2026-09-08 11:00 UTC", "a")])
    assert period["candidates"][0]["candidate_utilization"] == pytest.approx(expected)
    assert period["candidates"][0]["candidate_utilization"] > 0.70
    assert period["overall"] == "INFEASIBLE"


def test_each_date_is_its_own_day_from_empty():
    setup = _no_break_setup("per_date")
    records = _per_date_records(DATES[:1], lam=4.5) + _per_date_records(DATES[1:], lam=8.0)
    schedule = _schedule(setup, records, target=0.90)
    seeds = sep.replication_seeds(42, 8)
    lanes = {date: _date_day_lanes(setup, records, date, [sep.date_seed(seed, index) for seed in seeds])
             for index, date in enumerate(DATES)}
    assert [p["time"] for p in schedule["periods"]] == [f"{date} {label} UTC" for date in DATES for label in LABELS]
    for period in schedule["periods"]:
        date = period["time"][:10]
        expected = max(mean(min(1.0, lane["rho"]) for lane in lanes[date][(period["time"], queue_id)])
                       for queue_id in ("a", "b"))
        assert period["candidates"][0]["candidate_utilization"] == pytest.approx(expected), period["time"]


def test_novamart_optimizer_peaks_match_the_continuous_day():
    derived = derive_setup(sheets(), None)
    assert derived.errors == []
    setup, records = derived.setup, derived.records
    schedule = sep.optimize_separate_schedule(setup, records, target=0.85, full_coverage=True,
                                              des_settings={**DES, "replications": 3})
    active = {period["time"]: period["current_active_lanes"] for period in schedule["periods"]}
    day = _day_lanes(setup, records, active, sep.replication_seeds(42, 3))
    for period in schedule["periods"]:
        candidate = period["candidates"][0]
        lanes = period["current_active_lanes"]
        expected = max(mean(min(1.0, lane["rho"]) for lane in day[(period["time"], queue_id)])
                       for queue_id in lanes)
        assert candidate["candidate_utilization"] == pytest.approx(expected), period["time"]


# --- The day must be laid out or the schedule is rejected (finding K2) -----------------

def _no_break_setup(basis="representative_day"):
    return {**_setup(basis), "breaks": []}


def _assert_rejected(schedule, *reason_parts):
    assert schedule["overall"] == "INVALID_INPUT"
    assert schedule["periods"] == []
    assert "utilization_basis" not in schedule
    for part in reason_parts:
        assert part in schedule["reason"]


def test_period_labels_missing_from_the_segments_are_rejected_not_run_for_24_hours(monkeypatch):
    # Setup renamed the segment ids without re-uploading: records keep the old labels.
    setup = _no_break_setup()
    setup["segments"] = [{**segment, "id": f"renamed-{segment['id']}"} for segment in setup["segments"]]
    per_period_calls = []
    monkeypatch.setattr(sep, "evaluate_candidate_with_des",
                        lambda *args, **kwargs: per_period_calls.append(args))
    _assert_rejected(_schedule(setup), "10:00, 11:00, 12:00", "match no configured operating segment")
    assert per_period_calls == []


def test_one_unmatched_period_rejects_the_whole_day():
    records = [{**row, "time": "13:00", "segment_id": "13:00"} if row["time"] == "12:00" else row
               for row in _records()]
    _assert_rejected(_schedule(_no_break_setup(), records), "period(s) 13:00 match")


def test_representative_day_without_segments_is_rejected():
    setup = {**_no_break_setup(), "segments": []}
    _assert_rejected(_schedule(setup), "needs configured operating segments")


def test_representative_day_with_a_malformed_segment_end_is_rejected():
    setup = _no_break_setup()
    setup["segments"] = [*setup["segments"][:2], {**setup["segments"][2], "end_time": "noon"}]
    _assert_rejected(_schedule(setup), "invalid start or end time")


def test_per_date_segments_renamed_after_upload_are_rejected_not_run_for_24_hours(monkeypatch):
    # B13 rule 5 (replaces the K1 pin): a date that cannot be laid out is refused, never run as 24 h periods.
    setup = _no_break_setup("per_date")
    setup["segments"] = [{**segment, "id": f"renamed-{segment['id']}"} for segment in setup["segments"]]
    per_period_calls = []
    monkeypatch.setattr(sep, "evaluate_candidate_with_des", lambda *a, **k: per_period_calls.append(1))
    _assert_rejected(_schedule(setup, _per_date_records()), "2026-09-08", "renamed-10:00")
    assert per_period_calls == []


def test_dates_with_equal_inputs_are_independent_samples():
    setup = _no_break_setup("per_date")
    schedule = _schedule(setup, _per_date_records(DATES), target=0.90)
    by_date = {date: [p["candidates"][0]["candidate_utilization"] for p in schedule["periods"] if p["time"].startswith(date)]
               for date in DATES}
    assert by_date[DATES[0]] != by_date[DATES[1]]
    # The first date keeps the replication seeds, so one date alone is the same day as before.
    alone = _schedule(setup, _per_date_records(DATES[:1]), target=0.90)
    assert [p["candidates"][0]["candidate_utilization"] for p in alone["periods"]] == by_date[DATES[0]]


def test_a_date_without_records_for_a_segment_is_refused_naming_both():
    # OD-B13-2: NovaQ cannot tell whether the store was open and empty, so the date is not simulated.
    records = _per_date_records(DATES)
    records = [row for row in records if row["time"] != "2026-09-09 12:00 UTC"]
    _assert_rejected(_schedule(_no_break_setup("per_date"), records), "2026-09-09", "12:00")


def test_per_date_labels_without_a_date_are_refused():
    _assert_rejected(_schedule(_no_break_setup("per_date"), _records()), "cannot read the date")


def test_per_date_without_operating_segments_keeps_the_period_runs():
    # OD-B13-3: no segments, no day to lay out: today's method stays (with the run-bar notice).
    setup = {**_no_break_setup("per_date"), "segments": []}
    records = [{**row, "segment_id": row["time"].replace(" UTC", "")} for row in _per_date_records()]
    schedule = _schedule(setup, records, target=0.90)
    assert schedule["overall"] != "INVALID_INPUT"
    assert "utilization_basis" not in schedule
    assert sep.separate_engine_version(setup) == sep.SEPARATE_DES_ENGINE_VERSION


def test_engine_version_names_the_method():
    assert sep.separate_engine_version(_setup()) == sep.SEPARATE_DES_ENGINE_VERSION
    assert sep.separate_engine_version(_setup("per_date")) == sep.SEPARATE_DES_PER_DATE_DAY_ENGINE_VERSION
    # A Setup that records no period basis is never guessed to be per-date.
    unrecorded = {key: value for key, value in _setup().items() if key != "event_period_basis"}
    assert sep.separate_engine_version(unrecorded) == sep.SEPARATE_DES_ENGINE_VERSION



def test_rejection_survives_the_pruning_the_optimize_api_returns():
    setup = _no_break_setup()
    setup["segments"] = [{**segment, "id": f"renamed-{segment['id']}"} for segment in setup["segments"]]
    _assert_rejected(sep.prune_separate_schedule(_schedule(setup)), "match no configured operating segment")
