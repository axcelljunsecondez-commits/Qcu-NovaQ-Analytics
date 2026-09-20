"""Routing-capable DES evaluation for reduced separate-queue candidates.

The analytical path (``evaluate_candidate``) honestly returns UNSUPPORTED for
reduced active-lane sets: shortest-queue redistribution has no approved
per-queue formula. These tests pin the DES alternative: a conserved Poisson
arrival stream plus shortest-waiting-count routing, evaluated only when every
active lane carries empirical service samples. Aggregate rows with variance
but no samples stay UNSUPPORTED — inventing a service distribution from a
variance alone would be new mathematics.
"""
from __future__ import annotations

import pytest

from backend.queueing_engine.services import separate_optimization as sep


def _aggregate(queue_id, lam, mu, variance=0.004):
    """Variance-only aggregate row: no empirical service samples."""
    return {"queue_id": queue_id, "lambda": lam, "mu": mu, "c": 1, "variance": variance}


def _candidate(active, available):
    active = list(active)
    return {
        "time": "08:00",
        "available_queue_ids": list(available),
        "active_queue_ids": active,
        "inactive_queue_ids": [qid for qid in available if qid not in active],
    }


# --- INVALID_INPUT contract ------------------------------------------------

def _sampled(queue_id, lam, mu, samples):
    return {"queue_id": queue_id, "lambda": lam, "mu": mu, "c": 1,
            "service_samples_hours": list(samples)}


def _sampled_inputs():
    return {
        "cashier-east": _sampled("cashier-east", 4.0, 6.0, [0.10, 0.20, 0.25]),
        "express": _sampled("express", 2.0, 9.0, [0.08, 0.12]),
    }


def test_des_evaluator_rejects_malformed_candidates_and_inputs():
    by_id = _sampled_inputs()
    available = ["cashier-east", "express"]
    bad_candidates = [
        _candidate([], available),  # no active lane
        {"time": "08:00", "available_queue_ids": available,
         "active_queue_ids": ["cashier-east"],
         "inactive_queue_ids": []},  # not a partition
        {"time": "08:00", "available_queue_ids": available,
         "active_queue_ids": ["cashier-east", "ghost"],
         "inactive_queue_ids": ["express"]},  # unknown ID in partition
    ]
    for bad in bad_candidates:
        result = sep.evaluate_candidate_with_des(bad, by_id, duration_hours=8.0, seed=7)
        assert result["status"] == "INVALID_INPUT", bad
        assert result["evaluations"] is None
        assert result["total_cost"] is None
    good = _candidate(["cashier-east"], available)
    for bad_duration in (0.0, -8.0, float("nan"), "eight", None):
        result = sep.evaluate_candidate_with_des(good, by_id, duration_hours=bad_duration, seed=7)
        assert result["status"] == "INVALID_INPUT", bad_duration
    for bad_row in (
        {"queue_id": "express", "lambda": 2.0, "mu": 9.0, "c": 1,
         "service_samples_hours": []},  # empty samples on an active lane
        {"queue_id": "express", "lambda": 2.0, "mu": 9.0, "c": 1,
         "service_samples_hours": [0.1, float("nan")]},  # non-finite sample
        {"queue_id": "express", "lambda": 2.0, "mu": 9.0, "c": 1,
         "service_samples_hours": [0.1, 0.0]},  # non-positive sample
        {"queue_id": "express", "lambda": -2.0, "mu": 9.0, "c": 1,
         "service_samples_hours": [0.1]},  # invalid rate still rejected first
    ):
        rows = dict(by_id)
        rows["express"] = bad_row
        result = sep.evaluate_candidate_with_des(
            _candidate(["cashier-east", "express"], available),
            rows, duration_hours=8.0, seed=7,
        )
        assert result["status"] == "INVALID_INPUT", bad_row
        assert result["evaluations"] is None
        assert result["total_cost"] is None

def test_des_evaluator_exists_and_refuses_sample_free_aggregate_rows():
    assert hasattr(sep, "evaluate_candidate_with_des")
    rows = [
        _aggregate("cashier-east", 4.0, 6.0),
        _aggregate("express", 2.0, 9.0),
    ]
    by_id = {row["queue_id"]: row for row in rows}
    result = sep.evaluate_candidate_with_des(
        _candidate(["cashier-east"], ["cashier-east", "express"]),
        by_id,
        duration_hours=8.0,
        seed=7,
    )
    assert result["status"] == "UNSUPPORTED"
    assert "empirical service samples" in result["reason"]
    assert result["evaluations"] is None
    assert result["total_cost"] is None


# --- routing DES core: conservation, isolation, feasibility ------------------

def test_des_routing_conserves_demand_and_never_sends_to_inactive():
    by_id = {
        "cashier-east": _sampled("cashier-east", 4.0, 6.0, [0.05, 0.08, 0.10]),
        "express": _sampled("express", 2.0, 9.0, [0.05, 0.08, 0.10]),
    }
    result = sep.evaluate_candidate_with_des(
        _candidate(["cashier-east"], ["cashier-east", "express"]),
        by_id, duration_hours=8.0, seed=7,
    )
    assert result["status"] == "FEASIBLE"
    assert result["total_lambda"] == 6.0
    assert result["customer_conservation"] is True
    assert result["metric_provenance"] == "simulated"
    by_lane = {item["queue_id"]: item for item in result["evaluations"]}
    assert set(by_lane) == {"cashier-east", "express"}
    east = by_lane["cashier-east"]
    assert east["arrivals"] > 0
    assert east["arrivals"] == east["served"] + east["waiting"] + east["in_service"]
    assert by_lane["express"]["arrivals"] == 0
    assert by_lane["express"]["served"] == 0


def _stable_pair():
    return {
        "cashier-east": _sampled("cashier-east", 4.0, 6.0, [0.05, 0.08, 0.10, 0.12]),
        "express": _sampled("express", 2.0, 9.0, [0.05, 0.08, 0.10, 0.12]),
    }


def _snapshot(result):
    return [
        (item["queue_id"], item["arrivals"], item["served"],
         round(item["Wq"], 9) if item["Wq"] is not None else None,
         round(item["rho"], 9) if item["rho"] is not None else None)
        for item in result["evaluations"]
    ]


def test_des_routing_is_deterministic_for_a_fixed_seed():
    by_id = _stable_pair()
    available = ["cashier-east", "express"]
    first = sep.evaluate_candidate_with_des(
        _candidate(available, available), by_id, duration_hours=8.0, seed=11)
    second = sep.evaluate_candidate_with_des(
        _candidate(available, available), by_id, duration_hours=8.0, seed=11)
    assert first["status"] == "FEASIBLE"
    assert _snapshot(first) == _snapshot(second)
    assert first["trace_events"] == second["trace_events"]
    assert first["seed"] == 11
    assert first["duration_hours"] == 8.0


def test_single_lane_des_matches_analytical_mg1_within_tolerance():
    import statistics

    from backend.queueing_engine.services import model_selection as ms

    samples = [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.22, 0.28]
    mean_service = statistics.mean(samples)
    lam = 3.5
    selection = ms.select_model(lam, 1.0 / mean_service, 1,
                                variance=statistics.variance(samples),
                                queue_structure="separate_queues")
    expected_wq = selection["metrics"]["Wq"]
    assert expected_wq is not None and expected_wq > 0
    by_id = {"solo": _sampled("solo", lam, 1.0 / mean_service, samples)}
    candidate = _candidate(["solo"], ["solo"])
    replications = [
        sep.evaluate_candidate_with_des(candidate, by_id, duration_hours=120.0, seed=seed)
        for seed in (3, 11, 42)
    ]
    assert all(item["status"] == "FEASIBLE" for item in replications)
    measured = [item["evaluations"][0]["Wq"] for item in replications]
    assert all(wq is not None for wq in measured)
    average = sum(measured) / len(measured)
    assert average == pytest.approx(expected_wq, rel=0.15)


def test_overloaded_reduced_candidate_is_infeasible_with_named_lanes():
    by_id = {
        "cashier-east": _sampled("cashier-east", 8.0, 13.0, [0.05, 0.08, 0.10]),
        "express": _sampled("express", 4.0, 13.0, [0.05, 0.08, 0.10]),
    }
    result = sep.evaluate_candidate_with_des(
        _candidate(["cashier-east"], ["cashier-east", "express"]),
        by_id, duration_hours=24.0, seed=5,
    )
    assert result["status"] == "INFEASIBLE"
    assert "cashier-east" in result["reason"]
    assert "70%" in result["reason"]
    assert result["total_cost"] is None
    assert result["total_lambda"] == 12.0
    assert result["customer_conservation"] is True
    assert result["evaluations"] is not None


def test_infeasible_candidate_still_carries_its_playback_trace():
    """INFEASIBLE is a measured verdict, not a refusal: the DES has already
    produced the trace by the time the ceiling is checked, so the events ride
    along exactly as they do on the FEASIBLE path. Dropping them left the
    selected-plan playback with an empty floor for the busiest periods."""
    by_id = {
        "cashier-east": _sampled("cashier-east", 8.0, 13.0, [0.05, 0.08, 0.10]),
        "express": _sampled("express", 4.0, 13.0, [0.05, 0.08, 0.10]),
    }
    candidate = _candidate(["cashier-east"], ["cashier-east", "express"])
    result = sep.evaluate_candidate_with_des(
        candidate, by_id, duration_hours=24.0, seed=5)
    assert result["status"] == "INFEASIBLE"
    events = result["trace_events"]
    assert result["trace_truncated"] is False
    assert {event["queue_id"] for event in events} == {"cashier-east"}
    assert {event["type"] for event in events} == {
        "arrival", "service_start", "service_end"}
    active = next(item for item in result["evaluations"]
                  if item["queue_id"] == "cashier-east")
    arrivals = [event for event in events if event["type"] == "arrival"]
    assert len(arrivals) == active["arrivals"] > 0
    bounded = sep.evaluate_candidate_with_des(
        candidate, by_id, duration_hours=24.0, seed=5, max_events=10)
    assert bounded["status"] == "INFEASIBLE"
    assert bounded["trace_truncated"] is True
    assert len(bounded["trace_events"]) == 10


def test_feasible_result_reports_server_plus_measured_waiting_cost():
    from backend.queueing_engine.config import DEFAULT_SERVER_COST_HR

    by_id = _stable_pair()
    available = ["cashier-east", "express"]
    result = sep.evaluate_candidate_with_des(
        _candidate(available, available), by_id, duration_hours=8.0, seed=11)
    assert result["status"] == "FEASIBLE"
    assert result["server_cost"] == pytest.approx(2 * DEFAULT_SERVER_COST_HR)
    assert result["waiting_cost"] > 0
    assert result["total_cost"] == pytest.approx(
        result["server_cost"] + result["waiting_cost"])
    assert result["demand_conserved"] is True


def test_routing_spreads_load_across_symmetric_active_lanes():
    samples = [0.05, 0.08, 0.10, 0.12]
    by_id = {
        "cashier-east": _sampled("cashier-east", 3.0, 10.0, samples),
        "express": _sampled("express", 3.0, 10.0, samples),
    }
    result = sep.evaluate_candidate_with_des(
        _candidate(["cashier-east", "express"], ["cashier-east", "express"]),
        by_id, duration_hours=8.0, seed=11)
    assert result["status"] == "FEASIBLE"
    by_lane = {item["queue_id"]: item for item in result["evaluations"]}
    east, west = by_lane["cashier-east"], by_lane["express"]
    assert east["served"] > 0 and west["served"] > 0
    share = east["arrivals"] / (east["arrivals"] + west["arrivals"])
    assert share == pytest.approx(0.5, abs=0.2)


def test_des_evaluator_validates_seed_and_event_bound():
    by_id = _stable_pair()
    available = ["cashier-east", "express"]
    good = _candidate(available, available)
    for bad_seed in ("seven", 7.5, True):
        result = sep.evaluate_candidate_with_des(
            good, by_id, duration_hours=8.0, seed=bad_seed)
        assert result["status"] == "INVALID_INPUT", bad_seed
    for bad_bound in (0, -100, "many", 10.5, True):
        result = sep.evaluate_candidate_with_des(
            good, by_id, duration_hours=8.0, seed=11, max_events=bad_bound)
        assert result["status"] == "INVALID_INPUT", bad_bound
    bounded = sep.evaluate_candidate_with_des(
        good, by_id, duration_hours=8.0, seed=11, max_events=10)
    assert bounded["status"] == "FEASIBLE"
    assert bounded["trace_truncated"] is True
    assert len(bounded["trace_events"]) == 10
