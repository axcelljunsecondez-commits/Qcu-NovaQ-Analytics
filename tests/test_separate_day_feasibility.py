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


def test_per_date_basis_keeps_the_24_hour_candidate_runs():
    schedule = _schedule(_setup("per_date"))
    assert "utilization_basis" not in schedule
    period = next(p for p in schedule["periods"] if p["time"] == "11:00")
    assert period["overall"] == "OPTIMAL"
    assert period["candidates"][0]["candidate_utilization"] < 0.55


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
