"""DES aggregate feasibility + ranking policy for Separate-Queue optimization.

Feasibility is determined by the most heavily utilized ACTIVE lane
(max mean lane utilization <= target); economic ranking uses mean
replicated total cost with the existing fewer-lanes tie rule. Uncertainty
(SD/SE/CI) stays informational. One ranking never mixes analytical and
simulated evidence, and no optimum is claimed over an incomplete search.
"""
from __future__ import annotations

import pytest

from backend.queueing_engine.services import separate_optimization as sep


def _lane(queue_id, mean_rho):
    return {"queue_id": queue_id, "active": True,
            "utilization": None if mean_rho is None else {"mean": mean_rho}}


def _aggregate(active_means, *, status="VALID_AGGREGATE_EVIDENCE", target=0.70,
               total_mean=300.0):
    return {
        "time": "08:00",
        "available_queue_ids": ["q1", "q2", "q3"],
        "active_queue_ids": ["q1", "q2", "q3"][:len(active_means)],
        "inactive_queue_ids": [],
        "status": status,
        "reason": None,
        "rankable": status == "VALID_AGGREGATE_EVIDENCE",
        "evaluation_method": "DES_REPLICATIONS",
        "replication_count": 5,
        "base_seed": 42,
        "replication_seeds": [42, 43, 44, 45, 46],
        "duration_hours": 24.0,
        "target_utilization": target,
        "metric_source": "SIMULATED",
        "all_replications_conserved": True,
        "per_lane": [_lane(f"q{i + 1}", mean) for i, mean in enumerate(active_means)],
        "max_mean_lane_utilization": max(active_means),
        "costs": {"total": {"mean": total_mean}},
    }


# --- feasibility classifier -----------------------------------------------------

def test_classifier_uses_max_mean_active_lane_utilization():
    assert hasattr(sep, "apply_des_aggregate_feasibility")
    feasible = sep.apply_des_aggregate_feasibility(_aggregate([0.54, 0.66, 0.69]))
    assert feasible["status"] == "FEASIBLE"
    assert feasible["candidate_utilization"] == pytest.approx(0.69)
    assert feasible["reason"] is None

    over = sep.apply_des_aggregate_feasibility(_aggregate([0.54, 0.66, 0.81]))
    assert over["status"] == "INFEASIBLE"
    assert over["candidate_utilization"] == pytest.approx(0.81)
    assert "81.00%" in over["reason"]
    assert "70%" in over["reason"]
    assert "q3" in over["reason"]

    at_target = sep.apply_des_aggregate_feasibility(_aggregate([0.70]))
    assert at_target["status"] == "FEASIBLE"

    single_over = sep.apply_des_aggregate_feasibility(_aggregate([0.7001], target=0.70))
    assert single_over["status"] == "INFEASIBLE"


def test_classifier_never_averages_away_or_converts_other_states():
    mixed = _aggregate([0.10, 0.20, 0.95])
    assert sep.apply_des_aggregate_feasibility(mixed)["status"] == "INFEASIBLE"

    for status in ("INVALID_INPUT", "UNSUPPORTED", "AGGREGATION_ERROR"):
        outcome = sep.apply_des_aggregate_feasibility(_aggregate([0.5], status=status))
        assert outcome["status"] == status

    inactive_none = _aggregate([0.60])
    inactive_none["per_lane"].append({"queue_id": "closed", "active": False,
                                      "utilization": None})
    outcome = sep.apply_des_aggregate_feasibility(inactive_none)
    assert outcome["status"] == "FEASIBLE"
    assert outcome["candidate_utilization"] == pytest.approx(0.60)


# --- ranking ---------------------------------------------------------------------

def _ranked_entry(lanes, status, mean_cost, method="DES_REPLICATIONS"):
    return {"active_lane_count": lanes, "status": status,
            "evaluation_method": method, "mean_total_cost": mean_cost,
            "active_queue_ids": [f"q{i + 1}" for i in range(lanes)]}


def test_ranking_uses_mean_cost_with_fewer_lanes_tiebreak():
    assert hasattr(sep, "rank_des_candidates")
    entries = [
        _ranked_entry(5, "FEASIBLE", 430.0),
        _ranked_entry(4, "FEASIBLE", 370.0),
        _ranked_entry(3, "INFEASIBLE", 350.0),
    ]
    ranking = sep.rank_des_candidates(entries)
    assert [entry["active_lane_count"] for entry in ranking] == [4, 5]

    tied = [_ranked_entry(5, "FEASIBLE", 370.0), _ranked_entry(4, "FEASIBLE", 370.0)]
    assert [entry["active_lane_count"] for entry in sep.rank_des_candidates(tied)] == [4, 5]


def test_ranking_excludes_non_feasible_and_rejects_mixed_methods():
    entries = [
        _ranked_entry(2, "UNSUPPORTED", 200.0),
        _ranked_entry(3, "FEASIBLE", 350.0),
        _ranked_entry(4, "INVALID_INPUT", 100.0),
        _ranked_entry(5, "AGGREGATION_ERROR", 50.0),
        _ranked_entry(6, "FEASIBLE", None),
    ]
    ranking = sep.rank_des_candidates(entries)
    assert [entry["active_lane_count"] for entry in ranking] == [3]

    mixed = [_ranked_entry(3, "FEASIBLE", 350.0),
             _ranked_entry(4, "FEASIBLE", 340.0, method="ANALYTICAL")]
    with pytest.raises(ValueError):
        sep.rank_des_candidates(mixed)


# --- complete search -----------------------------------------------------------------

def test_search_complete_only_for_fully_evaluated_sets():
    assert hasattr(sep, "check_des_search_complete")
    full = [_ranked_entry(2, "FEASIBLE", 410.0), _ranked_entry(3, "INFEASIBLE", 350.0),
            _ranked_entry(4, "FEASIBLE", 370.0)]
    complete = sep.check_des_search_complete(full)
    assert complete["complete"] is True

    for bad_status in ("UNSUPPORTED", "INVALID_INPUT", "AGGREGATION_ERROR"):
        partial = [_ranked_entry(2, bad_status, None), _ranked_entry(3, "FEASIBLE", 350.0)]
        incomplete = sep.check_des_search_complete(partial)
        assert incomplete["complete"] is False
        assert "2" in incomplete["reason"]


# --- optimize_separate DES wiring --------------------------------------------------

def _live_rows():
    samples = [0.05, 0.08, 0.10, 0.12]
    return [
        {"queue_id": "a", "lambda": 4.0, "mu": 11.0, "c": 1, "service_samples_hours": samples},
        {"queue_id": "b", "lambda": 3.0, "mu": 11.0, "c": 1, "service_samples_hours": samples},
        {"queue_id": "c", "lambda": 2.0, "mu": 11.0, "c": 1, "service_samples_hours": samples},
    ]


def _des_config():
    return {"replications": 3, "base_seed": 101, "duration_hours": 8.0, "max_events": 1000}


def test_optimize_separate_uses_des_path_when_samples_cover_search():
    result = sep.optimize_separate("08:00", _live_rows(), current_active=3,
                                   des_replications=_des_config())
    assert result["overall"] == "OPTIMAL"
    assert result["evaluation_method"] == "DES_REPLICATIONS"
    assert result["replication_count"] == 3
    assert result["base_seed"] == 101
    assert result["replication_seeds"] == [101, 102, 103]
    statuses = [c["active_lane_count"] for c in result["candidates"]]
    assert statuses == [1, 2, 3]
    by_count = {c["active_lane_count"]: c for c in result["candidates"]}
    assert by_count[1]["status"] == "INFEASIBLE"
    assert by_count[2]["status"] == "FEASIBLE"
    assert by_count[3]["status"] == "FEASIBLE"
    assert all(c["evaluation_method"] == "DES_REPLICATIONS" for c in result["candidates"])
    optimum = result["optimum"]
    assert optimum["active_lane_count"] == 2
    assert optimum["recommendation"] == "REDUCE"
    assert optimum["total_cost"] == pytest.approx(by_count[2]["total_cost"])
    assert by_count[2]["total_cost"] < by_count[3]["total_cost"]
    assert optimum["evidence"]["per_lane"]


def test_optimize_separate_keeps_legacy_path_without_samples():
    rows = [{"queue_id": "a", "lambda": 4.0, "mu": 11.0, "c": 1, "variance": 0.001}]
    legacy = sep.optimize_separate("08:00", rows)
    assert legacy["overall"] == "OPTIMAL"
    assert "evaluation_method" not in legacy

    partial = [dict(_live_rows()[0]), {"queue_id": "b", "lambda": 3.0, "mu": 11.0, "c": 1}]
    result = sep.optimize_separate("08:00", partial, des_replications=_des_config())
    assert result["overall"] == "UNSUPPORTED"
    assert result["optimum"] is None


def test_full_active_des_replicates_agree_with_analytical_diagnostically():
    import statistics

    samples = [0.05, 0.08, 0.10, 0.12, 0.15, 0.18]
    rows = [
        {"queue_id": "a", "lambda": 4.0, "mu": 11.0, "c": 1,
         "variance": statistics.variance(samples), "service_samples_hours": samples},
        {"queue_id": "b", "lambda": 3.0, "mu": 11.0, "c": 1,
         "variance": statistics.variance(samples), "service_samples_hours": samples},
    ]
    by_id = {row["queue_id"]: row for row in rows}
    full = {"time": "08:00", "available_queue_ids": ["a", "b"],
            "active_queue_ids": ["a", "b"], "inactive_queue_ids": []}
    analytical = sep.evaluate_candidate(full, by_id, target=0.70)
    assert analytical["status"] == "FEASIBLE"
    aggregate = sep.evaluate_candidate_with_des_replications(
        full, by_id, {"replications": 3, "base_seed": 101, "duration_hours": 8.0})
    assert aggregate["status"] == "VALID_AGGREGATE_EVIDENCE"
    assert aggregate["costs"]["total"]["mean"] == pytest.approx(
        analytical["total_cost"], rel=0.25)
    analytical_peak = max(item["rho"] for item in analytical["evaluations"])
    assert aggregate["max_mean_lane_utilization"] == pytest.approx(analytical_peak, abs=0.10)


def test_des_target_contract_enforced_at_optimizer():
    for good in (0.40, 0.70, 0.90):
        result = sep.optimize_separate("08:00", _live_rows(), target=good,
                                       des_replications=_des_config())
        assert result["target_utilization"] == good
    for bad in (0.39, 0.91, float("nan"), True, "high"):
        with pytest.raises(ValueError):
            sep.optimize_separate("08:00", _live_rows(), target=bad,
                                  des_replications=_des_config())


def test_incomplete_search_claims_no_optimum():
    Jared = {"replications": 2, "base_seed": 101, "duration_hours": 8.0}

    def _stub(candidate, queues_by_id, **kwargs):
        active = candidate["active_queue_ids"]
        if active == ["a"]:
            return {"status": "UNSUPPORTED", "reason": "no samples",
                    "evaluations": None, "total_cost": None}
        return sep.evaluate_candidate_with_des_replications(
            candidate, queues_by_id, Jared)

    result = sep.optimize_separate("08:00", _live_rows(), run_fn=_stub,
                                   des_replications=_des_config())
    assert result["overall"] == "UNSUPPORTED"
    assert result["optimum"] is None
    assert "1" in result["reason"]
