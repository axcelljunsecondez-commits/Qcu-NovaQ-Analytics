"""D5: Separate-queue costs for a period are hourly rates times the period length.

Candidate costs are hourly rates (PHP per hour): lanes x server rate per
server-hour, and served / horizon x Wq x waiting rate per customer-hour. A
period of T hours therefore costs rate x T. Periods of different lengths are
only additive in PHP per period, never as summed hourly rates. Ranking inside
a period is unchanged: every candidate shares the same T.

Existing rules kept, not decided here: a scheduled lane is charged for its
whole scheduled period (including breaks inside it), a closing lane's drain
time after its period is not charged, and waiting is attributed to the
customer's arrival period. A period with no configured duration has no period
cost (None with the reason), never an assumed hour.
"""
from __future__ import annotations

import math
import random
import statistics

import pytest

from backend.queueing_engine.services import separate_optimization as sep
from backend.reports.separate_report import build_separate_report_model

SAMPLES = [0.05, 0.10, 0.15]
SEEDS = [42, 43, 44, 45, 46]
SERVER, WAIT = 90.0, 100.0
PERIODS = [("p60", "08:00:00", "09:00:00", 1.0), ("p30", "09:00:00", "09:30:00", 0.5),
           ("p15", "09:30:00", "09:45:00", 0.25)]


def _setup(periods=PERIODS, *, basis="representative_day", active=None, breaks=None):
    return {
        "queue_structure": "separate_queues", "fixed_server_count": 2,
        "staffing_varies_by_period": active is not None, "capacity_mode": "unlimited",
        "total_system_capacity": None, "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None, "separate_queue_closure_policy": "drain_existing",
        "queue_ids": ["a", "b"], "event_period_basis": basis, "breaks": breaks or [],
        "segments": [{"id": pid, "start_time": start, "end_time": end,
                      "active_queue_ids": (active or {}).get(pid)}
                     for pid, start, end, _ in periods],
    }


def _row(period, lane, lam, samples=SAMPLES, segment=True):
    row = {"time": period, "queue_id": lane, "lambda": lam, "mu": 1 / statistics.fmean(samples),
           "c": 1, "variance": statistics.pvariance(samples), "queue_structure": "separate_queues",
           "model_id": "parallel_mg1", "service_time_source": "empirical",
           "service_samples_hours": list(samples)}
    if segment:
        row["segment_id"] = period
    return row


def _records(lam=3.0, periods=PERIODS, lanes=("a", "b"), overrides=None):
    rows = []
    for pid, *_ in periods:
        for lane in lanes:
            rows.append(_row(pid, lane, (overrides or {}).get((pid, lane), lam)))
    return rows


def _schedule(setup, records, target=0.90, **des):
    return sep.optimize_separate_schedule(
        setup, records, target=target, server_cost=SERVER, waiting_cost=WAIT, full_coverage=True,
        des_settings={"replications": 5, "base_seed": 42, **des})


def _windows(setup, records, periods=PERIODS):
    out, origin = [], 8 * 60
    for pid, start, end, _ in periods:
        low = int(start[:2]) * 60 + int(start[3:5])
        high = int(end[:2]) * 60 + int(end[3:5])
        seg = next(s for s in setup["segments"] if s["id"] == pid)
        out.append({"time": pid, "start_hours": (low - origin) / 60, "end_hours": (high - origin) / 60,
                    "active_queue_ids": seg["active_queue_ids"] or ["a", "b"],
                    "queues_by_id": {r["queue_id"]: r for r in records if r["time"] == pid}})
    return out


# --- units: 60, 30 and 15 minute periods, two servers -------------------------------

def test_period_costs_are_hourly_rates_times_the_period_length():
    setup = _setup()
    schedule = _schedule(setup, _records())
    assert schedule["overall"] == "COMPLETE"
    for period, (pid, _, _, hours) in zip(schedule["periods"], PERIODS):
        assert period["time"] == pid
        assert period["duration_hours"] == pytest.approx(hours)
        (candidate,) = period["candidates"]
        rates = candidate["evidence"]["costs"]
        costs = candidate["period_costs"]
        assert costs["duration_hours"] == pytest.approx(hours)
        assert costs["staffing"]["mean"] == pytest.approx(2 * SERVER * hours)
        for key in ("staffing", "waiting", "total"):
            for stat in ("mean", "sd", "se", "ci_lower", "ci_upper"):
                assert costs[key][stat] == pytest.approx(rates[key][stat] * hours)
            assert costs[key]["n"] == 5
        assert period["optimum"]["period_costs"] == costs


def test_period_costs_match_a_hand_calculation_from_the_day_simulation():
    """Independent reference: run the unchanged DES primitive per seed and price it."""
    setup, records = _setup(), _records()
    schedule = _schedule(setup, records)
    hand = {pid: [] for pid, *_ in PERIODS}
    for seed in SEEDS:
        day = sep.run_routing_day_des(_windows(setup, records), tie_order=["a", "b"], seed=seed,
                                      max_events=100000)
        trace = day["trace_events"]
        arrived = {e["customer_id"]: e for e in trace if e["type"] == "arrival"}
        started = {e["customer_id"]: e["t"] for e in trace if e["type"] == "service_start"}
        for per, (pid, _, _, hours) in zip(day["periods"], PERIODS):
            exposure = math.fsum(lane["served"] * lane["Wq"] for lane in per["lanes"]
                                 if lane["active"] and lane["served"])
            # The same exposure from raw events: waits of customers arriving in the period.
            # Trace times are rounded to 1e-6 h, so each wait carries up to 1e-6 h of rounding.
            mine = [cid for cid, event in arrived.items() if event["segment_id"] == pid]
            from_trace = math.fsum(started[cid] - arrived[cid]["t"] for cid in mine)
            assert exposure == pytest.approx(from_trace, abs=1e-6 * max(1, len(mine)))
            hand[pid].append(2 * SERVER * hours + WAIT * exposure)
    for period in schedule["periods"]:
        costs = period["optimum"]["period_costs"]
        assert costs["total"]["mean"] == pytest.approx(statistics.fmean(hand[period["time"]]))


def test_waiting_crossing_period_boundaries_is_counted_once():
    """A backlog built in p60 is served in p30; every customer's wait counts once,
    in its arrival period, so the periods add up to the day's total wait."""
    setup = _setup()
    records = _records(overrides={("p60", "a"): 9.0, ("p60", "b"): 9.0})
    crossings = 0
    for seed in SEEDS:
        day = sep.run_routing_day_des(_windows(setup, records), tie_order=["a", "b"], seed=seed,
                                      max_events=100000)
        assert day["customer_conservation"] is True and not day["trace_truncated"]
        trace = day["trace_events"]
        arrivals = {e["customer_id"]: e["t"] for e in trace if e["type"] == "arrival"}
        starts = {e["customer_id"]: e["t"] for e in trace if e["type"] == "service_start"}
        crossings += sum(1 for cid in arrivals if arrivals[cid] < 1.0 <= starts[cid])
        per_period = math.fsum(lane["served"] * lane["Wq"] for per in day["periods"]
                               for lane in per["lanes"] if lane["served"])
        # Trace times are rounded to 1e-6 h (up to 1e-6 h per wait).
        assert per_period == pytest.approx(math.fsum(starts[c] - arrivals[c] for c in arrivals),
                                           abs=1e-6 * max(1, len(arrivals)))
    assert crossings > 0  # the boundary case under test actually occurs


def test_a_zero_arrival_period_has_zero_waiting_and_full_staffing_cost():
    setup = _setup()
    schedule = _schedule(setup, _records(overrides={("p15", "a"): 0.0, ("p15", "b"): 0.0}))
    period = next(p for p in schedule["periods"] if p["time"] == "p15")
    costs = period["optimum"]["period_costs"]
    assert costs["waiting"]["mean"] == 0.0
    assert costs["staffing"]["mean"] == pytest.approx(2 * SERVER * 0.25)
    assert costs["total"]["mean"] == pytest.approx(2 * SERVER * 0.25)


def test_arrivals_never_served_leave_the_period_cost_undefined():
    periods = [("p60", "08:00:00", "09:00:00", 1.0)]
    setup = _setup(periods, basis="per_date")
    records = [_row("p60", "a", 6.0, samples=[10.0]), _row("p60", "b", 6.0, samples=[10.0])]
    schedule = _schedule(setup, records, duration_hours=1.0)
    (period,) = schedule["periods"]
    (candidate,) = period["candidates"]
    # The first two arrivals (a1 < a2) start 10 h services on the two lanes that run
    # through the 1 h horizon, so the lanes are busy (1 - a1) + (1 - a2) hours in total
    # (D10: busy time is credited up to the horizon; the old accounting credited nothing
    # and read 0%). Arrival times regenerated independently from each replication seed.
    evidence = candidate["evidence"]
    hand = []
    for seed in evidence["replication_seeds"]:
        gaps = random.Random(random.Random(seed).getrandbits(64))
        a1 = gaps.expovariate(12.0)
        a2 = a1 + gaps.expovariate(12.0)
        hand.append(max(0.0, 1.0 - a1) + max(0.0, 1.0 - a2))
    lane_means = [lane["utilization"]["mean"] for lane in evidence["per_lane"]]
    assert math.fsum(lane_means) == pytest.approx(statistics.fmean(hand))
    assert candidate["candidate_utilization"] == pytest.approx(max(lane_means))
    assert candidate["candidate_utilization"] > 0.90
    assert period["overall"] == "INFEASIBLE"  # over the target, so no optimum either way
    costs = candidate["period_costs"]
    assert costs["staffing"]["mean"] == pytest.approx(2 * SERVER * 1.0)
    assert costs["waiting"] is None and costs["total"] is None
    assert "undefined" in costs["unavailable_reason"]


def test_over_target_replications_stay_priced_after_scaling():
    schedule = _schedule(_setup(), _records(lam=5.0), target=0.40)
    period = schedule["periods"][1]  # p30
    (candidate,) = period["candidates"]
    assert candidate["replications_over_target"] >= 1
    assert candidate["period_costs"]["total"]["n"] == 5
    assert candidate["period_costs"]["total"]["mean"] == pytest.approx(
        candidate["evidence"]["costs"]["total"]["mean"] * 0.5)


# --- existing staffing rules, kept (policy decisions are reported, not made) ---------

def test_scheduled_breaks_keep_the_existing_full_period_staffing_charge():
    periods = [("p60", "08:00:00", "09:00:00", 1.0)]
    breaks = [{"queue_id": "a", "scheduled_start_time": "08:20:00", "duration_minutes": 15}]
    setup = _setup(periods, breaks=breaks)
    schedule = _schedule(setup, _records(periods=periods))
    costs = schedule["periods"][0]["optimum"]["period_costs"]
    assert costs["staffing"]["mean"] == pytest.approx(2 * SERVER * 1.0)


def test_a_closing_lane_is_charged_only_for_its_scheduled_periods():
    periods = [("p60", "08:00:00", "09:00:00", 1.0), ("p30", "09:00:00", "09:30:00", 0.5)]
    setup = _setup(periods, active={"p60": ["a", "b"], "p30": ["a"]})
    records = _records(periods=periods[:1], overrides={("p60", "a"): 9.0, ("p60", "b"): 9.0}) \
        + [_row("p30", "a", 2.0)]
    schedule = _schedule(setup, records)
    by_time = {p["time"]: p["optimum"]["period_costs"] for p in schedule["periods"]}
    assert by_time["p60"]["staffing"]["mean"] == pytest.approx(2 * SERVER * 1.0)
    assert by_time["p30"]["staffing"]["mean"] == pytest.approx(1 * SERVER * 0.5)


# --- totals across unequal periods ---------------------------------------------------

def test_report_totals_add_period_costs_not_hourly_rates():
    schedule = _schedule(_setup(), _records())
    model = build_separate_report_model({"schedule": schedule})
    optima = [p["optimum"] for p in schedule["periods"]]
    period_totals = [o["period_costs"]["total"]["mean"] for o in optima]
    assert model["cost"]["selected_total"] == pytest.approx(math.fsum(period_totals))
    assert model["cost"]["selected_staffing"] == pytest.approx(2 * SERVER * (1.0 + 0.5 + 0.25))
    assert model["cost"]["selected_total"] != pytest.approx(math.fsum(o["total_cost"] for o in optima))
    for row, total in zip(model["schedule"]["periods"], period_totals):
        assert row["total_cost"] == pytest.approx(total)


def test_unknown_period_duration_gives_no_period_cost_and_keeps_the_ranking():
    periods = [("p60", "08:00:00", "09:00:00", 1.0)]
    setup = _setup(periods, basis="per_date")
    setup["segments"] = []
    records = [_row("08:00", "a", 3.0, segment=False), _row("08:00", "b", 3.0, segment=False)]
    schedule = _schedule(setup, records, duration_hours=8.0)
    (period,) = schedule["periods"]
    assert period["overall"] == "OPTIMAL"
    assert period["duration_hours"] is None
    costs = period["optimum"]["period_costs"]
    assert costs["total"] is None and "duration unknown" in costs["unavailable_reason"]
    assert period["optimum"]["total_cost"] is not None  # the hourly rate is still reported
    assert build_separate_report_model({"schedule": schedule})["cost"]["selected_total"] is None


def test_a_plan_saved_without_period_costs_reports_no_total():
    """A pre-D5 plan holds only hourly rates; summing them is what D5 removes."""
    schedule = _schedule(_setup(), _records())
    for period in schedule["periods"]:
        del period["optimum"]["period_costs"]
    model = build_separate_report_model({"schedule": schedule})
    assert model["cost"]["selected_total"] is None
    assert all(row["total_cost"] is None for row in model["schedule"]["periods"])


def test_ranking_inside_a_period_is_unchanged():
    periods = [("p30", "08:00:00", "08:30:00", 0.5)]
    setup = _setup(periods, basis="per_date")
    schedule = sep.optimize_separate_schedule(
        setup, _records(lam=1.0, periods=periods), target=0.90, server_cost=SERVER, waiting_cost=WAIT,
        full_coverage=False, des_settings={"replications": 2, "base_seed": 42, "duration_hours": 8.0})
    (period,) = schedule["periods"]
    feasible = [c for c in period["candidates"] if c["status"] == "FEASIBLE"]
    by_rate = min(feasible, key=lambda c: (c["mean_total_cost"], c["active_lane_count"]))
    by_period = min(feasible, key=lambda c: (c["period_costs"]["total"]["mean"], c["active_lane_count"]))
    assert period["optimum"]["active_lane_count"] == by_rate["active_lane_count"] \
        == by_period["active_lane_count"]


# --- Compare endpoint totals ---------------------------------------------------------

def test_compare_totals_add_period_costs(db_engine, client):
    from backend.api.scenarios import setup_fingerprint
    from backend.db.models import AnalysisProject, Dataset, Scenario
    from tests.helpers import create_user, login, make_sessionmaker

    setup, records = _setup(), _records()
    schedule = sep.prune_separate_schedule(_schedule(setup, records))
    user = create_user(db_engine, "d5@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="D5", queue_setup_json=setup,
                                   setup_status="ready")
        db.add(analysis)
        db.flush()
        dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="D5",
                          source_filename="d5.csv", source_format="csv", row_count=len(records),
                          normalized_json=records, validation_report_json={"ok": True})
        db.add(dataset)
        db.flush()
        options = {"target_utilization": 0.90, "server_cost_per_hr": SERVER,
                   "customer_waiting_cost": WAIT, "min_active_lanes": None, "max_active_lanes": None,
                   "lambda_multiplier": 1.0, "des": {"replications": 5, "base_seed": 42}}
        db.add(Scenario(user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id, name="Plan",
                        settings_json={**options, "calculation": {
                            "schema_version": 2, "engine_version": sep.SEPARATE_DES_ENGINE_VERSION,
                            "dataset_id": dataset.id, "dataset_row_count": len(records),
                            "options": options, "calculated_at": "2026-09-25T00:00:00+00:00",
                            "setup_hash": setup_fingerprint(setup)}},
                        results_json={"schedule": schedule}))
        db.commit()
        analysis_id = analysis.id
    login(client, "d5@example.com", "pw")
    body = client.get(f"/analyses/{analysis_id}/workflow/comparison/separate").json()
    (plan,) = body["plans"]
    expected = [p["optimum"]["period_costs"]["total"]["mean"] for p in schedule["periods"]]
    assert [d["total_cost_mean"] for d in plan["periods"]] == pytest.approx(expected)
    assert [d["duration_hours"] for d in plan["periods"]] == pytest.approx([1.0, 0.5, 0.25])
    assert plan["totals"]["total_cost_mean"] == pytest.approx(math.fsum(expected))
    waiting = [p["optimum"]["period_costs"]["waiting"]["mean"] for p in schedule["periods"]]
    assert plan["totals"]["waiting_cost_mean"] == pytest.approx(math.fsum(waiting))
