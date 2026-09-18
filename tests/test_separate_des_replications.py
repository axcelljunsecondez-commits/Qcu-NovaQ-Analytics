"""Replication/aggregation layer over the single-run routing DES evaluator.

The single-run evaluator stays the simulation primitive; this layer adds
controlled replications with matched seed schedules and aggregates candidate
evidence for future optimization ranking. Tied to repository conventions:
per-segment seed increments, Student-t intervals via the already-declared
scipy dependency, no Wilson intervals on continuous metrics, no downstream
Monte Carlo semantics, no feasibility verdicts (policy unfrozen).
"""
from __future__ import annotations

import pytest

from backend.queueing_engine.services import separate_optimization as sep


def _sampled(queue_id, lam, mu, samples):
    return {"queue_id": queue_id, "lambda": lam, "mu": mu, "c": 1,
            "service_samples_hours": list(samples)}


def _candidate(active, available):
    active = list(active)
    return {
        "time": "08:00",
        "available_queue_ids": list(available),
        "active_queue_ids": active,
        "inactive_queue_ids": [qid for qid in available if qid not in active],
    }


# --- replication configuration ------------------------------------------------

def test_replication_config_defaults_and_validation():
    assert hasattr(sep, "validate_des_replication_config")
    config = sep.validate_des_replication_config(None)
    assert config["replications"] == sep.DES_REPLICATIONS_DEFAULT_COUNT
    assert config["base_seed"] == 42
    assert config["duration_hours"] == 24.0
    assert config["max_events"] == 10000
    custom = sep.validate_des_replication_config(
        {"replications": 3, "base_seed": 101, "duration_hours": 8.0, "max_events": 50})
    assert (custom["replications"], custom["base_seed"],
            custom["duration_hours"], custom["max_events"]) == (3, 101, 8.0, 50)
    for bad in (
        {"replications": 0},        {"replications": -2},
        {"replications": 2.5},
        {"replications": True},
        {"replications": "three"},
        {"base_seed": "s"},
        {"base_seed": 1.5},
        {"base_seed": True},
        {"base_seed": None},
        {"duration_hours": 0.0},
        {"duration_hours": -8.0},
        {"duration_hours": float("nan")},
        {"max_events": 0},
        {"max_events": -5},
        {"max_events": 10.5},
        {"max_events": True},
        {"unknown_key": 1},
    ):
        with pytest.raises(ValueError):
            sep.validate_des_replication_config(bad)


def test_replication_defaults_mirror_engine_conventions():
    from backend.queueing_engine.simulation import simulation as sim

    assert sep.DES_DEFAULT_BASE_SEED == sim.RANDOM_SEED
    assert sep.DES_DEFAULT_DURATION_HOURS == sim.SIM_HOURS_PER_SEGMENT
    assert sep.DES_DEFAULT_MAX_EVENTS == 10000


# --- deterministic seed schedule ------------------------------------------------

def test_replication_seed_schedule_is_deterministic_and_sequential():
    assert hasattr(sep, "replication_seeds")
    assert sep.replication_seeds(101, 4) == [101, 102, 103, 104]
    assert sep.replication_seeds(101, 1) == [101]
    assert sep.replication_seeds(101, 4) == sep.replication_seeds(101, 4)
    assert sep.replication_seeds(102, 4) != sep.replication_seeds(101, 4)
    for bad in (0, -3, 2.5, True, "four", None):
        with pytest.raises(ValueError):
            sep.replication_seeds(101, bad)


# --- aggregation arithmetic (stubbed single-run results) -----------------------

def _rep_result(seed, lanes, *, server_cost, waiting_cost, total_cost,
                total_lambda=6.0, conservation=True, status="FEASIBLE"):
    """Canned single-run evaluator result. lanes: (qid, arrivals, served,
    waiting, in_service, Wq, rho)."""
    evaluations = [
        {"queue_id": qid, "active": True, "lambda": 4.0,
         "lambda_routed_sim": arrivals / 8.0, "mu": 10.0, "c": 1,
         "server_id": f"server:{qid}", "arrivals": arrivals, "served": served,
         "waiting": waiting, "in_service": in_service, "Wq": wq, "rho": rho,
         "stable": True, "max_queue": waiting + in_service}
        for qid, arrivals, served, waiting, in_service, wq, rho in lanes
    ]
    return {
        "time": "08:00", "status": status, "reason": None,
        "evaluations": evaluations, "total_lambda": total_lambda,
        "total_cost": total_cost, "server_cost": server_cost,
        "waiting_cost": waiting_cost, "customer_conservation": conservation,
        "metric_provenance": "simulated",
        "trace_events": [{"t": 1.0, "seed": seed}], "trace_truncated": False,
    }


def _stub_run_factory(results_by_seed):
    calls = []

    def run(candidate, queues_by_id, *, duration_hours, seed, target,
            server_cost, waiting_cost, max_events):
        calls.append({"seed": seed, "duration_hours": duration_hours,
                      "target": target, "server_cost": server_cost,
                      "waiting_cost": waiting_cost, "max_events": max_events})
        return results_by_seed[seed]

    run.calls = calls
    return run


def test_aggregate_arithmetic_is_exact_for_controlled_replications():
    import statistics

    from scipy.stats import t as student_t

    lanes_by_seed = {
        101: [("east-07", 48, 47, 1, 0, 0.10, 0.50)],
        102: [("east-07", 52, 52, 0, 0, 0.20, 0.60)],
        103: [("east-07", 50, 49, 1, 0, 0.30, 0.70)],
    }
    results = {
        seed: _rep_result(seed, lanes, server_cost=174.0,
                          waiting_cost=10.0 * (seed - 100),
                          total_cost=174.0 + 10.0 * (seed - 100))
        for seed, lanes in lanes_by_seed.items()
    }
    run = _stub_run_factory(results)
    by_id = {"east-07": _sampled("east-07", 4.0, 10.0, [0.05, 0.08])}
    candidate = _candidate(["east-07"], ["east-07"])
    config = {"replications": 3, "base_seed": 101, "duration_hours": 8.0,
              "max_events": 1000}
    assert hasattr(sep, "evaluate_candidate_with_des_replications")
    outcome = sep.evaluate_candidate_with_des_replications(
        candidate, by_id, config, run_fn=run)
    assert [call["seed"] for call in run.calls] == [101, 102, 103]
    assert all(call["duration_hours"] == 8.0 for call in run.calls)
    assert outcome["status"] == "VALID_AGGREGATE_EVIDENCE"
    assert outcome["rankable"] is True
    assert outcome["evaluation_method"] == "DES_REPLICATIONS"
    assert outcome["metric_source"] == "SIMULATED"
    assert outcome["replication_count"] == 3
    assert outcome["base_seed"] == 101
    assert outcome["replication_seeds"] == [101, 102, 103]
    assert outcome["all_replications_conserved"] is True

    wq = outcome["waiting_time"]
    assert wq["mean"] == pytest.approx(0.20)
    assert wq["sd"] == pytest.approx(statistics.stdev([0.10, 0.20, 0.30]))
    assert wq["se"] == pytest.approx(0.10 / (3 ** 0.5))
    half_width = student_t.ppf(0.975, 2) * (0.10 / (3 ** 0.5))
    assert wq["ci_lower"] == pytest.approx(0.20 - half_width)
    assert wq["ci_upper"] == pytest.approx(0.20 + half_width)
    assert wq["n"] == 3

    (lane,) = outcome["per_lane"]
    assert lane["queue_id"] == "east-07"
    assert lane["utilization"]["mean"] == pytest.approx(0.60)
    assert lane["arrivals"]["mean"] == pytest.approx(50.0)
    assert lane["served"]["mean"] == pytest.approx(49.333333333333336)
    assert lane["Wq"]["mean"] == pytest.approx(0.20)

    assert outcome["costs"]["staffing"]["mean"] == pytest.approx(174.0)
    assert outcome["costs"]["waiting"]["mean"] == pytest.approx(20.0)
    assert outcome["costs"]["total"]["mean"] == pytest.approx(194.0)
    assert outcome["costs"]["abandonment"] is None
    assert outcome["abandoned"] is None
    assert outcome["max_mean_lane_utilization"] == pytest.approx(0.60)
    assert outcome["feasibility"]["policy"] == "FEASIBILITY_POLICY_REQUIRED"
    assert outcome["representative_trace"]["replication"] == 0
    assert outcome["representative_trace"]["seed"] == 101


# --- status propagation, conservation, nulls -----------------------------------

def _good_rep(seed):
    return _rep_result(seed, [("east-07", 48, 47, 1, 0, 0.10, 0.50)],
                       server_cost=174.0, waiting_cost=10.0, total_cost=184.0)


def test_one_bad_replication_poisons_the_aggregate():
    by_id = {"east-07": _sampled("east-07", 4.0, 10.0, [0.05, 0.08])}
    candidate = _candidate(["east-07"], ["east-07"])
    config = {"replications": 3, "base_seed": 101, "duration_hours": 8.0}

    poisoned = {101: _good_rep(101), 102: _good_rep(102), 103: _good_rep(103)}
    poisoned[102] = {**_good_rep(102), "status": "INVALID_INPUT",
                     "reason": "broken row", "evaluations": None, "total_cost": None}
    outcome = sep.evaluate_candidate_with_des_replications(
        candidate, by_id, config, run_fn=_stub_run_factory(poisoned))
    assert outcome["status"] == "INVALID_INPUT"
    assert "102" in outcome["reason"]
    assert outcome["rankable"] is False

    poisoned[102] = {**_good_rep(102), "status": "UNSUPPORTED",
                     "reason": "no samples", "evaluations": None, "total_cost": None}
    outcome = sep.evaluate_candidate_with_des_replications(
        candidate, by_id, config, run_fn=_stub_run_factory(poisoned))
    assert outcome["status"] == "UNSUPPORTED"
    assert outcome["rankable"] is False

    poisoned[102] = {**_good_rep(102), "customer_conservation": False}
    outcome = sep.evaluate_candidate_with_des_replications(
        candidate, by_id, config, run_fn=_stub_run_factory(poisoned))
    assert outcome["status"] == "AGGREGATION_ERROR"
    assert outcome["rankable"] is False
    assert outcome["all_replications_conserved"] is False
    assert "102" in outcome["reason"]

    def _boom(*args, **kwargs):
        raise RuntimeError("simulator exploded")

    outcome = sep.evaluate_candidate_with_des_replications(
        candidate, by_id, config, run_fn=_boom)
    assert outcome["status"] == "AGGREGATION_ERROR"
    assert outcome["rankable"] is False


def test_missing_metrics_stay_missing_and_never_become_zero():
    lanes_by_seed = {
        101: [("east-07", 0, 0, 0, 0, None, 0.0)],
        102: [("east-07", 0, 0, 0, 0, None, 0.0)],
    }
    results = {seed: _rep_result(seed, lanes, server_cost=87.0,
                                 waiting_cost=None, total_cost=None)
               for seed, lanes in lanes_by_seed.items()}
    by_id = {"east-07": _sampled("east-07", 0.0, 10.0, [0.05, 0.08])}
    outcome = sep.evaluate_candidate_with_des_replications(
        _candidate(["east-07"], ["east-07"]), by_id,
        {"replications": 2, "base_seed": 101, "duration_hours": 8.0},
        run_fn=_stub_run_factory(results))
    assert outcome["status"] == "VALID_AGGREGATE_EVIDENCE"
    (lane,) = outcome["per_lane"]
    assert lane["Wq"] is None
    assert outcome["waiting_time"] is None
    assert outcome["costs"]["waiting"] is None
    assert outcome["costs"]["total"] is None
    assert outcome["costs"]["staffing"]["mean"] == pytest.approx(87.0)


# --- live-evaluator properties ---------------------------------------------------

def _live_pair():
    return {
        "cashier-east": _sampled("cashier-east", 4.0, 6.0, [0.05, 0.08, 0.10, 0.12]),
        "express": _sampled("express", 2.0, 9.0, [0.05, 0.08, 0.10, 0.12]),
    }


def test_single_replication_matches_single_run_evaluator():
    by_id = _live_pair()
    available = ["cashier-east", "express"]
    candidate = _candidate(available, available)
    single = sep.evaluate_candidate_with_des(
        candidate, by_id, duration_hours=8.0, seed=11)
    assert single["status"] == "FEASIBLE"
    outcome = sep.evaluate_candidate_with_des_replications(
        candidate, by_id,
        {"replications": 1, "base_seed": 11, "duration_hours": 8.0})
    assert outcome["status"] == "VALID_AGGREGATE_EVIDENCE"
    assert outcome["replication_seeds"] == [11]
    single_lanes = {item["queue_id"]: item for item in single["evaluations"]}
    for lane in outcome["per_lane"]:
        if not lane["active"]:
            continue
        expected = single_lanes[lane["queue_id"]]
        assert lane["arrivals"]["mean"] == expected["arrivals"]
        assert lane["served"]["mean"] == expected["served"]
        assert lane["utilization"]["mean"] == expected["rho"]
        assert lane["Wq"]["mean"] == expected["Wq"]
        for key in ("sd", "se", "ci_lower", "ci_upper"):
            assert lane["Wq"][key] is None
            assert lane["utilization"][key] is None
    assert outcome["costs"]["staffing"]["mean"] == single["server_cost"]
    assert outcome["waiting_time"]["mean"] is not None


def test_same_base_seed_reproduces_aggregate_and_matched_candidates_share_schedule():
    by_id = _live_pair()
    available = ["cashier-east", "express"]
    config = {"replications": 2, "base_seed": 101, "duration_hours": 2.0}
    full = _candidate(available, available)
    reduced = _candidate(["cashier-east"], available)
    first = sep.evaluate_candidate_with_des_replications(full, by_id, config)
    second = sep.evaluate_candidate_with_des_replications(full, by_id, config)
    assert first == second
    other_seed = sep.evaluate_candidate_with_des_replications(
        full, by_id, {**config, "base_seed": 202})
    assert other_seed["replication_seeds"] == [202, 203]
    assert other_seed["arrivals"]["mean"] != first["arrivals"]["mean"]
    reduced_outcome = sep.evaluate_candidate_with_des_replications(
        reduced, by_id, config)
    assert reduced_outcome["replication_seeds"] == first["replication_seeds"] == [101, 102]
