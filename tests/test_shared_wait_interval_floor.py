"""Shared lines: simulated wait intervals stop at 0 (OD-W3 / N2).

Spec: docs/superpowers/specs/2026-10-29-shared-wait-interval-floor.md. Reference values (S1-S5) are
hand-computed with the Student-t table values t(0.975, 2) = 4.302653 and t(0.975, 4) = 2.776445. The
floored keys below are written out from spec §3, not imported from the implementation.
"""

from __future__ import annotations

import pytest

from backend.queueing_engine.simulation.shared_continuous_des import DRAIN, HARD_CUTOFF
from backend.queueing_engine.simulation.shared_named_replications import aggregate_named_replications
from backend.queueing_engine.simulation.shared_replications import (
    CONTINUOUS_INTERVAL_METHOD,
    CONTINUOUS_METRICS,
    aggregate_replications,
    run_shared_replications,
    summarize_metric,
)
from tests.test_shared_named_replications import replicate
from tests.test_shared_replications import OVERLOAD, RATES

ANONYMOUS_FLOORED_METRICS = {
    "wait_sum_hours", "mean_wait_hours", "waiting_hours_before_close", "waiting_hours_after_close",
    "total_waiting_hours", "time_average_queue_in_horizon", "max_queue_in_horizon",
}
NAMED_FLOORED = {
    ("waiting", "wait_sum_hours"), ("waiting", "mean_wait_hours"), ("waiting", "customer_hours_in_horizon"),
    ("waiting", "customer_hours_after_closing"), ("waiting", "customer_hours_total"),
    ("waiting", "max_queue_in_horizon"), ("closing", "waiting_at_close"),
}
NAMED_FLOORED_CUSTOMERS = {"unserved", "unserved_hard_cutoff", "unserved_no_eligible_employee"}


# ── summarize_metric reference cases ─────────────────────────────────────────


def test_s1_a_wait_interval_that_dips_below_zero_is_cut_at_zero():
    plain = summarize_metric([0.0, 0.0, 0.0, 0.0, 0.1])
    floored = summarize_metric([0.0, 0.0, 0.0, 0.0, 0.1], floor=0.0)
    assert plain["ci_lower"] == pytest.approx(-0.0355289, abs=1e-6)
    assert floored["ci_lower"] == 0.0
    assert floored["ci_upper"] == pytest.approx(0.0755289, abs=1e-6)
    assert floored["ci_half_width"] == pytest.approx(0.0555289, abs=1e-6)
    assert (floored["mean"], floored["se"], floored["n"]) == (pytest.approx(0.02), pytest.approx(0.02), 5)
    assert {k: v for k, v in floored.items() if k != "ci_lower"} == {k: v for k, v in plain.items() if k != "ci_lower"}


def test_s2_an_interval_above_zero_is_left_as_it_is():
    floored = summarize_metric([0.10, 0.12, 0.14], floor=0.0)
    assert floored["ci_lower"] == pytest.approx(0.0703172, abs=1e-6)
    assert floored["ci_upper"] == pytest.approx(0.1696828, abs=1e-6)
    assert floored == summarize_metric([0.10, 0.12, 0.14])


def test_s3_s4_s5_undefined_values_counts_and_one_value():
    with_none = summarize_metric([None, 0.0, 0.0, 0.0, 0.0, 0.1], floor=0.0)
    assert (with_none["n"], with_none["n_undefined"], with_none["ci_lower"]) == (5, 1, 0.0)
    assert with_none["ci_upper"] == pytest.approx(0.0755289, abs=1e-6)
    count = summarize_metric([0, 0, 0, 0, 2], floor=0.0)
    assert count["ci_lower"] == 0.0 and count["ci_upper"] == pytest.approx(1.510578, abs=1e-6)
    one = summarize_metric([0.3], floor=0.0)
    assert (one["mean"], one["ci_lower"], one["ci_upper"], one["ci_half_width"]) == (0.3, None, None, None)


def test_the_method_text_states_the_floor():
    assert "max(0, mean - t*SE)" in CONTINUOUS_INTERVAL_METHOD
    assert "ci_half_width stays t*SE" in CONTINUOUS_INTERVAL_METHOD


# ── Helpers ──────────────────────────────────────────────────────────────────


def _check(summary: dict, values: list, floored: bool) -> bool:
    """Assert ``summary`` is the plain summary of ``values``, floored at 0 when ``floored``; True if the floor bound."""
    plain = summarize_metric(values)
    expected = dict(plain)
    if floored and plain["ci_lower"] is not None:
        expected["ci_lower"] = max(0.0, plain["ci_lower"])
    assert {k: summary[k] for k in expected} == expected
    return floored and plain["ci_lower"] is not None and plain["ci_lower"] < 0


# ── Anonymous aggregator ────────────────────────────────────────────────────


def _anonymous_rows() -> list[dict]:
    rows = []
    for index in range(5):
        last = index == 4
        row = {key: (0.5 if last else 0.0) for key in CONTINUOUS_METRICS}  # plain lower < 0 for every metric
        row["server_hours_above_schedule_in_horizon"] = -1.0 if index == 0 else (0.5 if last else 0.0)
        row.update({"replication_index": index, "arrivals": 4 if last else 0, "served": 2 if last else 0,
                    "unserved": 2 if last else 0, "customer_conservation": True})
        rows.append(row)
    return rows


def test_the_anonymous_aggregate_floors_exactly_the_wait_queue_and_unserved_quantities():
    rows = _anonymous_rows()
    summary = aggregate_replications(rows)
    for key in CONTINUOUS_METRICS:
        _check(summary["metrics"][key], [row[key] for row in rows], key in ANONYMOUS_FLOORED_METRICS)
    assert summary["metrics"]["mean_wait_hours"]["ci_lower"] == 0.0
    assert summary["metrics"]["utilization_in_horizon"]["ci_lower"] < 0  # not floored (OD-W2 parity)
    assert summary["metrics"]["server_hours_above_schedule_in_horizon"]["ci_lower"] < 0  # can be negative
    for key in ("arrivals", "served", "unserved"):
        _check(summary["customers"]["per_replication"][key], [row[key] for row in rows], key == "unserved")
    means = summary["waiting_time"]["mean_of_replication_means_hours"]
    assert _check(means, [row["mean_wait_hours"] for row in rows], True)


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_real_anonymous_runs_floor_the_spec_keys_and_costs(policy):
    bound = False
    for seed in range(1, 11):
        result = run_shared_replications(*OVERLOAD, replications=3, seed=seed, closing_policy=policy, cost_rates=RATES)
        rows, summary = result["replications"], result["summary"]
        for key in CONTINUOUS_METRICS:
            bound |= _check(summary["metrics"][key], [row[key] for row in rows], key in ANONYMOUS_FLOORED_METRICS)
        for key in ("arrivals", "served", "unserved"):
            bound |= _check(summary["customers"]["per_replication"][key], [row[key] for row in rows], key == "unserved")
        bound |= _check(summary["waiting_time"]["mean_of_replication_means_hours"],
                        [row["mean_wait_hours"] for row in rows], True)
        cost = summary["cost"]
        bound |= _check(cost["total_cost"], [row["cost"]["total_cost"] for row in rows], True)
        for name, component in cost["components"].items():
            if component["per_replication"] is not None:
                bound |= _check(component["per_replication"], [row["cost"]["components"][name] for row in rows], True)
        assert "max(0, mean - t*SE)" in result["provenance"]["interval_methods"]["continuous"]
    assert bound  # at least one of these runs had a plain lower bound below 0 on a floored key


# ── Named aggregator ────────────────────────────────────────────────────────


def _named_rows() -> list[dict]:
    rows = []
    for index in range(5):
        v = 2.0 if index == 4 else 0.0
        rows.append({
            "replication_index": index, "customer_conservation": True,
            "customers": {"arrivals": v, "served": v, "unserved": v, "unserved_hard_cutoff": v,
                          "unserved_no_eligible_employee": v, "served_after_closing": v},
            "waiting": {"wait_sum_hours": v, "mean_wait_hours": v, "customer_hours_in_horizon": v,
                        "customer_hours_after_closing": v, "customer_hours_total": v, "max_queue_in_horizon": v},
            "closing": {"waiting_at_close": v, "in_service_at_close": v, "drain_crew_size": v,
                        "run_after_closing_hours": v},
            "staffing": {"horizon": {"requirement_gap_shortfall_hours": v}},
            "employees": {"shifts_with_overrun": v, "breaks_unfulfilled": v, "employee_hours_by_state": {"ON_BREAK": v}},
        })
    return rows


def _named_checks(rows: list[dict], summary: dict) -> bool:
    bound = False
    for key in rows[0]["customers"]:
        bound |= _check(summary["customers"]["per_replication"][key], [row["customers"][key] for row in rows],
                        key in NAMED_FLOORED_CUSTOMERS)
    for block in ("waiting", "closing"):
        for key in rows[0][block]:
            bound |= _check(summary["metrics"][block][key], [row[block][key] for row in rows], (block, key) in NAMED_FLOORED)
    bound |= _check(summary["waiting_time"]["mean_of_replication_means_hours"],
                    [row["waiting"]["mean_wait_hours"] for row in rows], True)
    return bound


def test_the_named_aggregate_floors_exactly_the_wait_queue_and_unserved_quantities():
    rows = _named_rows()
    summary = aggregate_named_replications(rows)
    assert _named_checks(rows, summary)
    assert summary["metrics"]["waiting"]["customer_hours_total"]["ci_lower"] == 0.0
    assert summary["metrics"]["closing"]["drain_crew_size"]["ci_lower"] < 0  # outside the approved scope
    assert summary["metrics"]["staffing"]["horizon"]["requirement_gap_shortfall_hours"]["ci_lower"] < 0
    assert summary["metrics"]["employees"]["employee_hours_by_state"]["ON_BREAK"]["ci_lower"] < 0
    assert summary["customers"]["per_replication"]["arrivals"]["ci_lower"] < 0  # OD-W2 parity


def test_real_named_runs_floor_the_spec_keys():
    bound = False
    for seed in range(1, 9):
        result = replicate("stable", replications=3, seed=seed, policy=DRAIN)
        bound |= _named_checks(result["replications"], result["summary"])
        assert "max(0, mean - t*SE)" in result["provenance"]["interval_method"]
    assert bound
