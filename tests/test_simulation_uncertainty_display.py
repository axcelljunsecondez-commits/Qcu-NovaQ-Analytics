"""Honest uncertainty on simulated results (R10, R11).

R11: the break optimizer reports the 95 % interval of the PAIRED
per-replication wait difference (proposed - current) and words its verdict
from that interval only. R10: a FEASIBLE staffing candidate whose peak lane's
utilization interval reaches past the target is flagged, never reclassified.
"""
from __future__ import annotations

import math
import statistics

import pytest
from scipy.stats import t as student_t

from backend.api.analysis_schemas import QueueSetup
from backend.data.analysis_ingestion import normalize_analysis_input
from backend.queueing_engine.services import break_optimization as bo
from backend.queueing_engine.services import separate_optimization as sep
from tests.test_break_optimize_api import _events, _setup
from tests.test_separate_des_feasibility import _aggregate, _des_config, _live_rows


def _runs(waits):
    return [{"seed": index, "mean_wait_minutes": wait} for index, wait in enumerate(waits)]


# --- R11: paired wait change -------------------------------------------------------

def test_paired_ci_equals_direct_computation_on_stored_replications():
    setup = _setup()
    records, _ = normalize_analysis_input(_events(), QueueSetup.model_validate(setup))
    result = bo.optimize_separate_breaks(setup, records, replications=4, base_seed=7)
    des = result["des"]
    diffs = [after["mean_wait_minutes"] - before["mean_wait_minutes"]
             for before, after in zip(des["current"]["replications"], des["proposed"]["replications"])]
    mean = sum(diffs) / len(diffs)
    half = student_t.ppf(0.975, len(diffs) - 1) * statistics.stdev(diffs) / math.sqrt(len(diffs))
    change = des["comparison"]["paired_wait_change"]
    assert change["n"] == 4
    assert change["mean"] == pytest.approx(mean)
    assert change["ci_lower"] == pytest.approx(mean - half)
    assert change["ci_upper"] == pytest.approx(mean + half)
    # Existing fields stay as they were.
    assert des["comparison"]["runs"] == 4
    assert "proposed_better_runs" in des["comparison"]
    assert "mean_wait_change_minutes" in des["comparison"]


@pytest.mark.parametrize(("current", "proposed", "verdict"), [
    ([3.0, 3.2, 2.9, 3.1], [2.0, 2.1, 1.9, 2.2], "shorter"),
    ([2.0, 2.1, 1.9, 2.2], [3.0, 3.2, 2.9, 3.1], "longer"),
    ([2.0, 3.0, 2.5, 2.2], [2.6, 2.4, 2.1, 2.9], "no_clear_difference"),
])
def test_wording_follows_the_interval_only(current, proposed, verdict):
    change = bo.paired_wait_change(_runs(current), _runs(proposed))
    assert change["verdict"] == verdict
    if verdict == "shorter":
        assert change["ci_upper"] < 0
    if verdict == "longer":
        assert change["ci_lower"] > 0
    if verdict == "no_clear_difference":
        assert change["ci_lower"] <= 0 <= change["ci_upper"]


def test_one_replication_has_no_interval_and_no_claim():
    change = bo.paired_wait_change(_runs([3.0]), _runs([1.0]))
    assert change["n"] == 1
    assert change["mean"] == pytest.approx(-2.0)
    assert change["ci_lower"] is None and change["ci_upper"] is None
    assert change["verdict"] == "no_clear_difference"


def test_runs_missing_a_wait_are_skipped_not_zeroed():
    change = bo.paired_wait_change(_runs([3.0, None, 2.0]), _runs([1.0, 1.0, None]))
    assert change["n"] == 1
    assert change["mean"] == pytest.approx(-2.0)


# --- R10: feasible but within simulation noise ----------------------------------------

def _with_ci(aggregate, ci_uppers):
    for lane, upper in zip(aggregate["per_lane"], ci_uppers):
        lane["utilization"] = {**lane["utilization"], "ci_upper": upper}
    return aggregate


def test_feasible_peak_lane_interval_past_target_is_flagged_but_stays_feasible():
    outcome = sep.apply_des_aggregate_feasibility(_with_ci(_aggregate([0.50, 0.68]), [0.55, 0.73]))
    assert outcome["status"] == "FEASIBLE"
    assert outcome["near_target_noise"] is True


def test_feasible_peak_lane_interval_inside_target_is_not_flagged():
    outcome = sep.apply_des_aggregate_feasibility(_with_ci(_aggregate([0.50, 0.60]), [0.75, 0.66]))
    assert outcome["status"] == "FEASIBLE"
    assert outcome["near_target_noise"] is False


def test_missing_interval_gives_null_flag_never_a_guess():
    no_ci_key = sep.apply_des_aggregate_feasibility(_aggregate([0.50, 0.68]))
    assert no_ci_key["status"] == "FEASIBLE" and no_ci_key["near_target_noise"] is None
    single_rep = sep.apply_des_aggregate_feasibility(_with_ci(_aggregate([0.50, 0.68]), [0.55, None]))
    assert single_rep["status"] == "FEASIBLE" and single_rep["near_target_noise"] is None


def test_infeasible_candidate_carries_no_flag():
    outcome = sep.apply_des_aggregate_feasibility(_with_ci(_aggregate([0.50, 0.80]), [0.55, 0.85]))
    assert outcome["status"] == "INFEASIBLE"
    assert outcome["near_target_noise"] is None


def test_flag_reaches_every_candidate_and_the_optimum():
    result = sep.optimize_separate("08:00", _live_rows(), target=0.70, des_replications=_des_config())
    assert result["overall"] == "OPTIMAL"
    for candidate in result["candidates"]:
        expected = sep.apply_des_aggregate_feasibility(candidate["evidence"])["near_target_noise"]
        assert candidate["near_target_noise"] is expected
    assert "near_target_noise" in result["optimum"]
