"""Separate-queue optimization foundation: candidates around verified math.

No queueing formula is reimplemented here. The engine evaluates only what
existing mathematics supports (today: the full-active lane set, per queue,
through central model selection); anything else resolves to UNSUPPORTED,
never to fabricated numbers.
"""
from __future__ import annotations

import pytest

from backend.queueing_engine.services import model_selection
from backend.queueing_engine.services import separate_optimization as sep


def _queue(queue_id, lam, mu, variance=0.004, extra=None):
    row = {"queue_id": queue_id, "lambda": lam, "mu": mu, "c": 1, "variance": variance}
    if extra:
        row.update(extra)
    return row


def _inputs():
    return [
        _queue("cashier-east", 4.0, 6.0),
        _queue("express", 2.0, 9.0, variance=0.008),
        _queue("lane_03", 6.0, 10.0, variance=0.002),
    ]


def _ids(rows):
    return [row["queue_id"] for row in rows]


# --- utilization target contract -------------------------------------------

def test_target_defaults_to_070_and_rejects_outside_040_090():
    assert sep.validate_separate_target(None) == 0.70
    assert sep.validate_separate_target(0.40) == 0.40
    assert sep.validate_separate_target(0.90) == 0.90
    for bad in (0.39, 0.91, 0.0, 1.5, float("nan"), "high", True):
        with pytest.raises(ValueError):
            sep.validate_separate_target(bad)


# --- candidate generation ----------------------------------------------------

def test_build_candidates_single_queue():
    candidates = sep.build_candidates(["solo"])
    assert [c["active_queue_ids"] for c in candidates] == [["solo"]]
    assert candidates[0]["inactive_queue_ids"] == []


def test_build_candidates_preserves_configured_order_and_ids():
    candidates = sep.build_candidates(["cashier-east", "express", "lane_03"])
    assert [c["active_queue_ids"] for c in candidates] == [
        ["cashier-east"],
        ["cashier-east", "express"],
        ["cashier-east", "express", "lane_03"],
    ]
    assert candidates[0]["inactive_queue_ids"] == ["express", "lane_03"]


def test_build_candidates_respects_min_max_lane_constraints():
    candidates = sep.build_candidates(["a", "b", "c"], min_lanes=2, max_lanes=2)
    assert [c["active_queue_ids"] for c in candidates] == [["a", "b"]]
    with pytest.raises(ValueError):
        sep.build_candidates(["a", "b"], min_lanes=3)
    with pytest.raises(ValueError):
        sep.build_candidates([], min_lanes=1)


# --- demand conservation -----------------------------------------------------

def test_demand_conserved_all_active():
    rows = _inputs()
    total = sep.candidate_total_lambda(rows, _ids(rows))
    assert total == sum(row["lambda"] for row in rows)


def test_demand_conserved_one_closed():
    rows = _inputs()
    original = sep.candidate_total_lambda(rows, _ids(rows))
    assert sep.candidate_total_lambda(rows, ["cashier-east", "express"]) == original


def test_demand_conserved_only_one_active_and_heterogeneous():
    rows = _inputs()
    original = sep.candidate_total_lambda(rows, _ids(rows))
    assert sep.candidate_total_lambda(rows, ["lane_03"]) == original
    assert original == pytest.approx(12.0)


def test_demand_tampering_detected():
    rows = _inputs()
    original = sep.candidate_total_lambda(rows, _ids(rows))
    assert not sep.check_demand_conserved(original, original - rows[0]["lambda"])


def test_demand_duplicate_ids_rejected():
    rows = _inputs()
    with pytest.raises(ValueError):
        sep.candidate_total_lambda(rows + [dict(rows[0])], _ids(rows))


# --- routing ------------------------------------------------------------------

def test_route_single_active_queue():
    assert sep.route_arrival(["only"], {"only": 3}, ("only",)) == "only"


def test_route_shortest_active_queue():
    active = ["a", "b", "c"]
    assert sep.route_arrival(active, {"a": 5, "b": 1, "c": 3}, tuple(active)) == "b"


def test_route_tie_uses_configured_order_deterministically():
    active = ["express", "cashier-east", "lane_03"]
    assert sep.route_arrival(active, {"express": 2, "cashier-east": 2, "lane_03": 2}, tuple(active)) == "express"
    assert sep.route_arrival(active, {"express": 2, "cashier-east": 2, "lane_03": 2}, tuple(active)) == \
        sep.route_arrival(active, {"express": 2, "cashier-east": 2, "lane_03": 2}, tuple(active))


def test_route_excludes_inactive_queues():
    with pytest.raises(ValueError):
        sep.route_arrival([], {}, ())


def test_route_ignores_lengths_of_inactive_queues():
    assert sep.route_arrival(["a"], {"a": 9, "ghost": 0}, ("a", "ghost")) == "a"


def test_route_rng_breaks_ties_fairly_and_reproducibly():
    import random

    lengths = {"a": 0, "b": 0}

    def _draws(seed, count=200):
        rng = random.Random(seed)
        return [sep.route_arrival(["a", "b"], lengths, ("a", "b"), rng) for _ in range(count)]

    first, second = _draws(9), _draws(9)
    assert first == second
    share_a = sum(1 for queue_id in first if queue_id == "a")
    assert 60 < share_a < 140
    assert {sep.route_arrival(["a", "b"], lengths, ("a", "b")) for _ in range(5)} == {"a"}


# --- evaluation adapter ---------------------------------------------------------

def test_full_active_candidate_evaluates_through_central_selection():
    rows = _inputs()
    result = sep.evaluate_candidate(
        {"time": "08:00", "available_queue_ids": _ids(rows),
         "active_queue_ids": _ids(rows), "inactive_queue_ids": []},
        {row["queue_id"]: row for row in rows},
        target=0.70,
    )
    assert result["status"] == "FEASIBLE"
    assert result["total_lambda"] == pytest.approx(12.0)
    by_queue = {item["queue_id"]: item for item in result["evaluations"]}
    for row in rows:
        expected = model_selection.select_model(
            row["lambda"], row["mu"], 1, variance=row["variance"], queue_structure="separate_queues")
        assert by_queue[row["queue_id"]]["model"] == expected["name"]
        assert by_queue[row["queue_id"]]["rho"] == pytest.approx(expected["metrics"]["rho"])
    assert result["total_cost"] is not None and result["total_cost"] >= 0


def test_reduced_lane_candidate_is_unsupported_not_evaluated():
    rows = _inputs()
    result = sep.evaluate_candidate(
        {"time": "08:00", "available_queue_ids": _ids(rows),
         "active_queue_ids": ["cashier-east", "express"], "inactive_queue_ids": ["lane_03"]},
        {row["queue_id"]: row for row in rows},
        target=0.70,
    )
    assert result["status"] == "UNSUPPORTED"
    assert result["evaluations"] is None
    assert result["total_cost"] is None
    assert "reason" in result and result["reason"]


def test_unstable_full_active_candidate_is_infeasible_with_null_wait():
    rows = [_queue("hot", 9.0, 6.0)]
    result = sep.evaluate_candidate(
        {"time": "08:00", "available_queue_ids": ["hot"],
         "active_queue_ids": ["hot"], "inactive_queue_ids": []},
        {"hot": rows[0]},
        target=0.70,
    )
    assert result["status"] == "INFEASIBLE"
    assert result["evaluations"][0]["Wq"] is None


def test_invalid_inputs_rejected_not_zeroed():
    rows = _inputs()
    by_id = {row["queue_id"]: row for row in rows}
    base = {"time": "08:00", "available_queue_ids": _ids(rows),
            "active_queue_ids": _ids(rows), "inactive_queue_ids": []}
    assert sep.evaluate_candidate(base, {}, target=0.70)["status"] == "INVALID_INPUT"
    assert sep.evaluate_candidate(base, {**by_id, "cashier-east": {**by_id["cashier-east"], "lambda": None}},
                                  target=0.70)["status"] == "INVALID_INPUT"
    assert sep.evaluate_candidate(base, {**by_id, "cashier-east": {**by_id["cashier-east"], "c": 3}},
                                  target=0.70)["status"] == "INVALID_INPUT"
    with pytest.raises(ValueError):
        sep.evaluate_candidate(base, by_id, target=0.95)


def test_missing_variance_is_unsupported():
    rows = [_queue("novar", 4.0, 6.0, variance=None)]
    result = sep.evaluate_candidate(
        {"time": "08:00", "available_queue_ids": ["novar"],
         "active_queue_ids": ["novar"], "inactive_queue_ids": []},
        {"novar": rows[0]},
        target=0.70,
    )
    assert result["status"] == "UNSUPPORTED"


# --- generation, feasibility, ranking --------------------------------------------

def test_optimize_returns_single_optimum_without_personas():
    rows = _inputs()
    outcome = sep.optimize_separate("08:00", rows, target=0.70, current_active=3)
    assert outcome["overall"] == "OPTIMAL"
    assert outcome["optimum"]["active_lane_count"] == 3
    assert outcome["optimum"]["recommendation"] == "KEEP"
    assert "personas" not in outcome
    assert outcome["target_utilization"] == 0.70


def test_optimize_recommends_relative_to_current_staffing():
    rows = _inputs()
    assert sep.optimize_separate("08:00", rows, target=0.70, current_active=1)["optimum"]["recommendation"] == "INCREASE"
    assert sep.optimize_separate("08:00", rows, target=0.70, current_active=5)["optimum"]["recommendation"] == "REDUCE"


def test_optimize_infeasible_when_target_violated_without_relaxation():
    rows = [_queue("hot", 9.0, 10.0)]  # rho 0.9 stable but above 0.70
    outcome = sep.optimize_separate("08:00", rows, target=0.70, current_active=1)
    assert outcome["overall"] == "INFEASIBLE"
    assert outcome["optimum"] is None
    assert all(c["status"] in ("INFEASIBLE", "UNSUPPORTED") for c in outcome["candidates"])


def test_optimize_never_reports_closed_lane_identities():
    rows = _inputs()
    outcome = sep.optimize_separate("08:00", rows, target=0.70, current_active=3)
    assert outcome["optimum"]["active_lane_count"] == 3
    assert "closed_queue_ids" not in outcome["optimum"]
    for candidate in outcome["candidates"]:
        assert set(candidate["active_queue_ids"]) | set(candidate["inactive_queue_ids"]) == set(_ids(rows))


# --- protected behavior ------------------------------------------------------------

def test_shared_optimizer_outputs_unchanged():
    from backend.queueing_engine.services.optimization import optimize_segment
    result = optimize_segment({"time": "t", "lambda": 30.0, "mu": 12.0, "c": 3})
    assert result["c_optimal"] == 4
    assert result["feasibility_status"] == "FEASIBLE"
