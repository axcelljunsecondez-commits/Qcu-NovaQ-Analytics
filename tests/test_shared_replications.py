"""Phase 4 continuous shared-queue DES replications.

Every per-replication value is compared with an independent recomputation from the full
customer rows and capacity-transition intervals of the same regenerated replication. That
recomputation never uses the engine's own time integrals. Intervals are compared with scipy
references, and the statistical checks use independent analytical values within 4 standard
errors.
"""

from __future__ import annotations

import math
import statistics
from typing import Any

import numpy as np
import pytest
from scipy.stats import binomtest
from scipy.stats import t as student_t

from backend.queueing_engine.config import MC_MAX_TRIALS
from backend.queueing_engine.services.separate_optimization import _summarize_metric as separate_summarize_metric
from backend.queueing_engine.services.shared_day_cost import DayCostRates
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    DRAIN,
    HARD_CUTOFF,
    simulate_shared_replication,
)
from backend.queueing_engine.simulation.shared_replications import (
    CONTINUOUS_METRICS,
    FailureCriteria,
    aggregate_replications,
    run_shared_replications,
    summarize_metric,
    summarize_proportion,
)
from tests.test_shared_segments import erlang_reference

# Overloaded near closing, with a decrease from 4 to 2 servers at 1:50.
OVERLOAD = (
    OperatingHorizon(0, 120),
    [DemandPeriod("early", 0, 60, 30.0, 10.0), DemandPeriod("late", 60, 120, 36.0, 8.0)],
    [StaffingSegment("a", 0, 60, 3), StaffingSegment("b", 60, 110, 4), StaffingSegment("c", 110, 120, 2)],
)
# Zero-capacity and zero-demand periods, several transitions, and 0 servers at closing.
MULTI_CLOSED_AT_END = (
    OperatingHorizon(480, 780),
    [DemandPeriod("08", 480, 540, 30.0, 12.0), DemandPeriod("09", 540, 600, 0.0, 12.0),
     DemandPeriod("10", 600, 660, 45.0, 15.0), DemandPeriod("11", 660, 780, 20.0, 10.0)],
    [StaffingSegment("a", 480, 510, 3), StaffingSegment("b", 510, 540, 0), StaffingSegment("c", 540, 600, 1),
     StaffingSegment("d", 600, 615, 4), StaffingSegment("e", 615, 660, 2), StaffingSegment("f", 660, 780, 0)],
)
RATES = DayCostRates(regular_server_rate=80.0, overtime_rate=120.0, waiting_rate=100.0, unserved_customer_rate=50.0)


def approx(value: float) -> object:
    return pytest.approx(value, rel=1e-9, abs=1e-12)


def independent_row(horizon, periods, segments, root_entropy: int, index: int, policy: str) -> dict:
    """Recompute one replication from its full customer rows and transition intervals."""
    child = np.random.SeedSequence(entropy=root_entropy, spawn_key=(index,))
    result = simulate_shared_replication(horizon, periods, segments, seed_sequence=child, closing_policy=policy)
    end = result["closing"]["closing_hours"]
    rows = result["customers"]
    served = [row for row in rows if row["status"] == "departed"]
    waited_until = [row["service_start_hours"] if row["service_start_hours"] is not None else end for row in rows]
    # Open intervals per server from the transition log: open .. close / drain_complete.
    opened: dict[int, float] = {}
    open_intervals = []
    for item in result["capacity_transitions"]:
        if item["kind"] == "open":
            opened[item["server_id"]] = item["t"]
        elif item["kind"] in ("close", "drain_complete"):
            open_intervals.append((opened.pop(item["server_id"]), item["t"]))
    assert not opened  # every server that opened also closed

    def split(start: float, stop: float) -> tuple[float, float]:
        return max(0.0, min(stop, end) - start), max(0.0, stop - max(start, end))

    busy = [split(row["service_start_hours"], row["service_end_hours"]) for row in served]
    present = [split(start, stop) for start, stop in open_intervals]
    wait_sum = math.fsum(row["service_start_hours"] - row["arrival_hours"] for row in served)
    releases = [item["t"] for item in result["capacity_transitions"] if item["t"] >= end]
    return {
        "arrivals": len(rows),
        "served": len(served),
        "unserved": sum(1 for row in rows if row["status"] == "unserved_at_close"),
        "wait_sum_hours": wait_sum,
        "mean_wait_hours": wait_sum / len(served) if served else None,
        "waiting_hours_before_close": math.fsum(min(until, end) - row["arrival_hours"]
                                                for row, until in zip(rows, waited_until)),
        "waiting_hours_after_close": math.fsum(max(0.0, until - end) for until in waited_until),
        "busy_server_hours_in_horizon": math.fsum(item[0] for item in busy),
        "busy_server_hours_after_close": math.fsum(item[1] for item in busy),
        "available_server_hours_in_horizon": math.fsum(item[0] for item in present),
        "overtime_server_hours": math.fsum(item[1] for item in present),
        "scheduled_server_hours": math.fsum(s.servers * (s.end_minute - s.start_minute) / 60 for s in segments),
        "overrun_hours": max(releases, default=end) - end,
    }


def assert_row_matches(row: dict, expected: dict) -> None:
    for key, value in expected.items():
        if value is None or isinstance(value, int):
            assert row[key] == value, key
        else:
            assert row[key] == approx(value), key
    available = expected["available_server_hours_in_horizon"]
    if available > 0:
        assert row["utilization_in_horizon"] == approx(expected["busy_server_hours_in_horizon"] / available)
    assert row["total_waiting_hours"] == approx(
        expected["waiting_hours_before_close"] + expected["waiting_hours_after_close"])
    assert row["customer_conservation"] is True
    assert row["arrivals"] == row["served"] + row["unserved"]


# ── Per-replication values against independent recomputation ───────────────


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
@pytest.mark.parametrize("config", [OVERLOAD, MULTI_CLOSED_AT_END], ids=["overload", "multi_closed_at_end"])
def test_every_replication_matches_an_independent_recomputation(config, policy):
    result = run_shared_replications(*config, replications=20, seed=2026, closing_policy=policy)
    rows = result["replications"]
    assert [row["replication_index"] for row in rows] == list(range(20))
    assert [row["spawn_key"] for row in rows] == [[index] for index in range(20)]
    for row in rows:
        assert_row_matches(row, independent_row(*config, 2026, row["replication_index"], policy))
    summary = result["summary"]
    assert summary["customers"]["conserved_in_every_replication"] is True
    assert summary["customers"]["arrivals"] == sum(row["arrivals"] for row in rows)
    assert summary["customers"]["unserved"] == sum(row["unserved"] for row in rows)
    if policy == HARD_CUTOFF or config is MULTI_CLOSED_AT_END:
        assert summary["customers"]["unserved"] > 0  # the closing path is exercised
    else:
        assert summary["customers"]["unserved"] == 0
        assert summary["metrics"]["overtime_server_hours"]["mean"] > 0


def test_retained_rows_hold_no_events_or_customer_rows():
    result = run_shared_replications(*OVERLOAD, replications=3, seed=1, closing_policy=DRAIN)
    assert "trace" not in result and all("customers" not in row and "trace" not in row for row in result["replications"])
    assert set(result) == {"replications", "summary", "provenance"}


# ── Seeds and streams ────────────────────────────────────────────────────────


def test_seeded_runs_are_reproducible_and_seed_none_records_entropy():
    first = run_shared_replications(*OVERLOAD, replications=5, seed=11, closing_policy=DRAIN)
    assert first == run_shared_replications(*OVERLOAD, replications=5, seed=11, closing_policy=DRAIN)
    assert first["replications"] != run_shared_replications(*OVERLOAD, replications=5, seed=12,
                                                            closing_policy=DRAIN)["replications"]
    assert first["provenance"]["root_entropy"] == 11
    free = run_shared_replications(*OVERLOAD, replications=4, seed=None, closing_policy=HARD_CUTOFF)
    entropy = free["provenance"]["root_entropy"]
    assert isinstance(entropy, int) and free["provenance"]["seed"] is None
    replay = run_shared_replications(*OVERLOAD, replications=4, seed=entropy, closing_policy=HARD_CUTOFF)
    assert replay["replications"] == free["replications"]
    # A longer run shares its first replications with a shorter run of the same seed.
    longer = run_shared_replications(*OVERLOAD, replications=8, seed=11, closing_policy=DRAIN)
    assert longer["replications"][:5] == first["replications"]


def test_replication_streams_are_distinct_and_independent():
    root = np.random.SeedSequence(99)
    children = root.spawn(3)
    for index, child in enumerate(children):
        regenerated = np.random.SeedSequence(entropy=99, spawn_key=(index,))
        assert (child.generate_state(8) == regenerated.generate_state(8)).all()
    assert len({tuple(child.generate_state(4)) for child in children}) == 3

    # Arrival counts: Poisson(λT = 60) per replication, and adjacent replications uncorrelated.
    horizon, periods, segments = (OperatingHorizon(0, 120), [DemandPeriod("d", 0, 120, 30.0, 40.0)],
                                  [StaffingSegment("s", 0, 120, 5)])
    rows = run_shared_replications(horizon, periods, segments, replications=400, seed=5,
                                   closing_policy=DRAIN)["replications"]
    counts = np.array([row["arrivals"] for row in rows], dtype=float)
    assert len(set(counts)) > 20
    n = len(counts)
    assert abs(counts.mean() - 60.0) <= 4 * math.sqrt(60.0 / n)
    # No parameter perturbation: the dispersion index stays at 1 (the legacy ±20% arrival noise
    # would add Var(λT) = 60² × 0.4² / 12 = 48 and push it near 1.8).
    assert abs(counts.var(ddof=1) / counts.mean() - 1.0) <= 4 * math.sqrt(2 / (n - 1))
    correlation = float(np.corrcoef(counts[:-1], counts[1:])[0, 1])
    assert abs(correlation) <= 4 / math.sqrt(n - 1)


# ── Aggregation ──────────────────────────────────────────────────────────────


def synthetic_row(index: int, served: int, wait_sum: float, arrivals: int | None = None, unserved: int = 0) -> dict:
    row: dict[str, Any] = {key: 1.0 for key in CONTINUOUS_METRICS}
    row.update({
        "replication_index": index, "spawn_key": [index], "arrivals": served + unserved if arrivals is None else arrivals,
        "served": served, "unserved": unserved, "customer_conservation": True, "wait_sum_hours": wait_sum,
        "mean_wait_hours": wait_sum / served if served else None, "overrun_hours": 0.0,
        "server_hours_above_schedule_in_horizon": 0.0,
    })
    return row


def test_waiting_time_populations_and_denominators_by_hand():
    rows = [synthetic_row(0, 2, 1.0), synthetic_row(1, 0, 0.0, unserved=3), synthetic_row(2, 6, 1.5)]
    waiting = aggregate_replications(rows)["waiting_time"]
    by_replication = waiting["mean_of_replication_means_hours"]
    # Replication means 0.5 and 0.25; the replication with no served customer is counted, not dropped.
    assert (by_replication["mean"], by_replication["n"], by_replication["n_undefined"]) == (0.375, 2, 1)
    weighted = waiting["customer_weighted_mean_hours"]
    assert (weighted["value"], weighted["numerator_wait_hours"], weighted["denominator_served_customers"]) == (
        0.3125, 2.5, 8)
    customers = aggregate_replications(rows)["customers"]
    assert (customers["arrivals"], customers["served"], customers["unserved"]) == (11, 8, 3)


def test_customer_weighted_wait_on_a_real_run():
    result = run_shared_replications(*OVERLOAD, replications=15, seed=8, closing_policy=DRAIN)
    rows = result["replications"]
    weighted = result["summary"]["waiting_time"]["customer_weighted_mean_hours"]
    assert weighted["denominator_served_customers"] == sum(row["served"] for row in rows)
    assert weighted["value"] == approx(math.fsum(row["wait_sum_hours"] for row in rows) / sum(row["served"] for row in rows))
    means = result["summary"]["waiting_time"]["mean_of_replication_means_hours"]
    assert means["mean"] == approx(statistics.fmean(row["mean_wait_hours"] for row in rows))


@pytest.mark.parametrize("values", [
    [0.25, 0.5, 0.125, 1.0], [3.0, 3.0, 3.0], [1.5, None, 2.5, None, 4.0, 0.0], list(np.linspace(0.1, 9.7, 37)),
])
def test_continuous_intervals_match_scipy_and_the_novaq_convention(values):
    summary = summarize_metric(values)
    defined = [value for value in values if value is not None]
    n = len(defined)
    assert (summary["n"], summary["n_undefined"]) == (n, len(values) - n)
    mean = statistics.fmean(defined)
    sd = statistics.stdev(defined)
    assert summary["mean"] == approx(mean) and summary["sd"] == approx(sd)
    if sd > 0:
        lower, upper = student_t.interval(0.95, n - 1, loc=mean, scale=sd / math.sqrt(n))
        assert (summary["ci_lower"], summary["ci_upper"]) == (approx(lower), approx(upper))
    reference = separate_summarize_metric(defined)
    for key in ("mean", "sd", "se", "ci_lower", "ci_upper"):
        assert summary[key] == approx(reference[key])
    assert (summary["min"], summary["max"]) == (min(defined), max(defined))


def test_small_samples_report_no_invented_dispersion():
    one = summarize_metric([2.0])
    assert (one["mean"], one["sd"], one["ci_lower"], one["n"]) == (2.0, None, None, 1)
    none = summarize_metric([None, None])
    assert (none["mean"], none["n"], none["n_undefined"]) == (None, 0, 2)
    single = run_shared_replications(*OVERLOAD, replications=1, seed=3, closing_policy=DRAIN)["summary"]
    assert single["metrics"]["overrun_hours"]["sd"] is None and single["metrics"]["overrun_hours"]["n"] == 1


@pytest.mark.parametrize(("k", "n"), [(0, 20), (3, 20), (20, 20), (1, 1), (17, 250), (0, 1)])
def test_wilson_intervals_match_scipy(k, n):
    proportion = summarize_proportion(k, n)
    reference = binomtest(k, n).proportion_ci(confidence_level=0.95, method="wilson")
    assert (proportion["numerator"], proportion["denominator"], proportion["proportion"]) == (k, n, k / n)
    assert proportion["ci_lower"] == pytest.approx(reference.low, abs=1e-12)
    assert proportion["ci_upper"] == pytest.approx(reference.high, abs=1e-12)
    assert proportion["confidence_level"] == 0.95 and "Wilson" in proportion["method"]
    empty = summarize_proportion(0, 0)
    assert (empty["proportion"], empty["ci_lower"]) == (None, None)


# ── Cost ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_cost_per_replication_then_aggregated(policy):
    result = run_shared_replications(*OVERLOAD, replications=12, seed=21, closing_policy=policy, cost_rates=RATES)
    totals = []
    for row in result["replications"]:
        expected = independent_row(*OVERLOAD, 21, row["replication_index"], policy)
        waiting = expected["waiting_hours_before_close"] + expected["waiting_hours_after_close"]
        manual = (expected["available_server_hours_in_horizon"] * 80.0 + expected["overtime_server_hours"] * 120.0
                  + waiting * 100.0 + (expected["unserved"] * 50.0 if policy == HARD_CUTOFF else 0.0))
        assert row["cost"]["total_cost"] == approx(manual)
        totals.append(row["cost"]["total_cost"])
    cost = result["summary"]["cost"]
    assert cost["total_cost"]["mean"] == approx(statistics.fmean(totals))
    lower, upper = student_t.interval(0.95, len(totals) - 1, loc=statistics.fmean(totals),
                                      scale=statistics.stdev(totals) / math.sqrt(len(totals)))
    assert (cost["total_cost"]["ci_lower"], cost["total_cost"]["ci_upper"]) == (approx(lower), approx(upper))
    unserved = cost["components"]["unserved_customer"]
    assert unserved["status"] == ("COSTED" if policy == HARD_CUTOFF else "NOT_APPLICABLE")
    component_means = [cost["components"][name]["per_replication"]["mean"]
                       for name in ("regular_server", "overtime_server", "waiting")]
    if policy == HARD_CUTOFF:
        component_means.append(unserved["per_replication"]["mean"])
    assert math.fsum(component_means) == approx(cost["total_cost"]["mean"])
    assert "not necessarily paid employee-hours" in cost["server_hours_note"]


def test_missing_rate_withholds_money_but_keeps_operational_statistics():
    rates = DayCostRates(80.0, 120.0, 100.0, None)
    cutoff = run_shared_replications(*OVERLOAD, replications=6, seed=4, closing_policy=HARD_CUTOFF, cost_rates=rates)
    cost = cutoff["summary"]["cost"]
    assert cost["total_cost"] is None
    assert cost["total_withheld_reason"] == "Rates not supplied: unserved_customer_rate."
    assert all(row["cost"]["total_cost"] is None for row in cutoff["replications"])
    assert cost["components"]["unserved_customer"]["status"] == "RATE_MISSING"
    assert cost["components"]["unserved_customer"]["per_replication"] is None
    assert cost["components"]["waiting"]["per_replication"]["mean"] > 0  # costed components remain
    assert cutoff["summary"]["metrics"]["total_waiting_hours"]["n"] == 6  # operations unaffected
    # DRAIN with servers on duty at closing cannot leave anyone unserved: the term does not apply.
    drain = run_shared_replications(*OVERLOAD, replications=6, seed=4, closing_policy=DRAIN, cost_rates=rates)
    assert drain["summary"]["cost"]["total_cost"]["n"] == 6
    # DRAIN with 0 servers at closing can: the rate is required.
    closed = run_shared_replications(*MULTI_CLOSED_AT_END, replications=3, seed=4, closing_policy=DRAIN,
                                     cost_rates=rates)
    assert closed["summary"]["cost"]["total_cost"] is None


def test_no_rates_means_no_monetary_output():
    result = run_shared_replications(*OVERLOAD, replications=3, seed=4, closing_policy=DRAIN)
    assert result["summary"]["cost"] == {
        "evaluated": False, "reason": "No cost rates were supplied; no monetary output is produced.",
    }
    assert all("cost" not in row for row in result["replications"])


# ── Failure criteria ─────────────────────────────────────────────────────────


def test_failure_criteria_counts_and_intervals():
    criteria = FailureCriteria(max_mean_wait_minutes=6.0, max_utilization=0.9, max_unserved_customers=2,
                               max_overrun_minutes=10.0)
    result = run_shared_replications(*OVERLOAD, replications=40, seed=13, closing_policy=HARD_CUTOFF,
                                     failure_criteria=criteria)
    rows = result["replications"]
    expected = {
        "max_mean_wait_minutes": [row["mean_wait_hours"] * 60 > 6.0 for row in rows],
        "max_utilization": [row["utilization_in_horizon"] > 0.9 for row in rows],
        "max_unserved_customers": [row["unserved"] > 2 for row in rows],
        "max_overrun_minutes": [row["overrun_hours"] * 60 > 10.0 for row in rows],
    }
    summary = result["summary"]["criteria"]
    for name, violated in expected.items():
        item = summary["per_criterion"][name]
        assert (item["violations"], item["denominator"], item["not_evaluable"]) == (sum(violated), 40, 0)
        assert item["threshold"] == getattr(criteria, name)
    failed = sum(1 for index in range(40) if any(flags[index] for flags in expected.values()))
    combined = summary["combined"]
    assert (combined["failed"], combined["passed"], combined["denominator"]) == (failed, 40 - failed, 40)
    reference = binomtest(failed, 40).proportion_ci(confidence_level=0.95, method="wilson")
    assert combined["ci_lower"] == pytest.approx(reference.low, abs=1e-12)
    assert 0 < failed < 40  # both outcomes occur, so the check is not vacuous
    assert summary["verdict"] is None and "No approved pass/fail rule" in summary["verdict_reason"]


def test_not_evaluable_replications_are_counted_not_dropped():
    # λ = 0.5 per hour for one hour: about 61% of replications have no customer at all.
    horizon, periods, segments = (OperatingHorizon(0, 60), [DemandPeriod("d", 0, 60, 0.5, 4.0)],
                                  [StaffingSegment("s", 0, 60, 1)])
    result = run_shared_replications(horizon, periods, segments, replications=60, seed=2, closing_policy=DRAIN,
                                     failure_criteria=FailureCriteria(max_mean_wait_minutes=1.0))
    empty = sum(1 for row in result["replications"] if row["served"] == 0)
    assert 0 < empty < 60
    item = result["summary"]["criteria"]["per_criterion"]["max_mean_wait_minutes"]
    assert (item["not_evaluable"], item["denominator"]) == (empty, 60 - empty)
    combined = result["summary"]["criteria"]["combined"]
    assert combined["not_evaluable"] == empty and combined["failed"] + combined["passed"] == 60 - empty
    assert result["summary"]["waiting_time"]["mean_of_replication_means_hours"]["n_undefined"] == empty


def test_utilization_limit_is_independent_and_tolerance_is_the_pipeline_one():
    result = run_shared_replications(*OVERLOAD, replications=5, seed=1, closing_policy=DRAIN)
    row = result["replications"][0]
    value = row["utilization_in_horizon"]
    from backend.queueing_engine.simulation.shared_replications import criterion_outcomes

    at_limit = criterion_outcomes(row, FailureCriteria(max_utilization=value))
    just_below = criterion_outcomes(row, FailureCriteria(max_utilization=value - 1e-6))
    assert at_limit["max_utilization"] == "SATISFIED" and just_below["max_utilization"] == "VIOLATED"
    assert criterion_outcomes(row, FailureCriteria(max_utilization=value - 5e-10))["max_utilization"] == "SATISFIED"
    assert result["summary"]["criteria"] == {
        "evaluated": False, "reason": "No failure criterion was supplied; no failure proportion is computed.",
    }


@pytest.mark.parametrize(("criteria", "message"), [
    (FailureCriteria(), "at least one criterion"),
    (FailureCriteria(max_utilization=0.0), "max_utilization"),
    (FailureCriteria(max_utilization=1.2), "max_utilization"),
    (FailureCriteria(max_mean_wait_minutes=-1.0), "max_mean_wait_minutes"),
    (FailureCriteria(max_overrun_minutes=math.inf), "max_overrun_minutes"),
    (FailureCriteria(max_unserved_customers=1.5), "max_unserved_customers"),  # type: ignore[arg-type]
    (FailureCriteria(max_unserved_customers=True), "max_unserved_customers"),
    ({"max_utilization": 0.8}, "must be a FailureCriteria"),
])
def test_invalid_criteria_are_rejected(criteria, message):
    with pytest.raises(SharedSegmentError, match=message):
        run_shared_replications(*OVERLOAD, replications=1, seed=1, closing_policy=DRAIN, failure_criteria=criteria)


# ── Validation ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"replications": 0}, "replications must be a whole number from 1 to 100000"),
    ({"replications": MC_MAX_TRIALS + 1}, "replications must be a whole number"),
    ({"replications": True}, "replications must be a whole number"),
    ({"replications": 2.0}, "replications must be a whole number"),
    ({"seed": -1}, "seed must be a whole number"),
    ({"closing_policy": "drain"}, "closing_policy must be DRAIN or HARD_CUTOFF"),
    ({"cost_rates": {"regular_server_rate": 1.0}}, "cost_rates must be a DayCostRates"),
    ({"cost_rates": DayCostRates(-1.0, 1.0, 1.0, 1.0)}, "regular_server_rate"),
])
def test_invalid_inputs_are_rejected(kwargs, message):
    arguments = {"replications": 2, "seed": 1, "closing_policy": DRAIN, **kwargs}
    with pytest.raises(SharedSegmentError, match=message):
        run_shared_replications(*OVERLOAD, **arguments)


def test_required_arguments_have_no_defaults():
    for missing in ("replications", "seed", "closing_policy"):
        arguments = {"replications": 2, "seed": 1, "closing_policy": DRAIN}
        del arguments[missing]
        with pytest.raises(TypeError, match=missing):
            run_shared_replications(*OVERLOAD, **arguments)


def test_provenance_discloses_method_seeds_and_no_perturbation():
    provenance = run_shared_replications(*OVERLOAD, replications=2, seed=7, closing_policy=DRAIN)["provenance"]
    assert provenance["metric_provenance"] == "des_continuous_replications"
    assert "not applied" in provenance["parameter_uncertainty"]
    assert "spawn_key=(i,)" in provenance["seed_scheme"]
    assert provenance["replication_limits"] == {"min": 1, "max": MC_MAX_TRIALS, "source": "config.MC_MAX_TRIALS"}
    assert provenance["inputs"]["cost_rates"] is None and provenance["inputs"]["failure_criteria"] is None


# ── Statistical check against Erlang C ──────────────────────────────────────


def test_replicated_queue_and_wait_match_erlang_c():
    # λ = 40, μ = 20, c = 3 for 24 h: Lq = 8/9, Wq = 1/45 h.
    reference = erlang_reference(40.0, 20.0, 3)
    horizon, periods, segments = (OperatingHorizon(0, 1440), [DemandPeriod("d", 0, 1440, 40.0, 20.0)],
                                  [StaffingSegment("s", 0, 1440, 3)])
    summary = run_shared_replications(horizon, periods, segments, replications=60, seed=45,
                                      closing_policy=HARD_CUTOFF)["summary"]
    queue = summary["metrics"]["time_average_queue_in_horizon"]
    assert abs(queue["mean"] - reference["Lq"]) <= 4 * queue["se"], (queue["mean"], reference["Lq"], queue["se"])
    wait = summary["waiting_time"]["mean_of_replication_means_hours"]
    assert abs(wait["mean"] - reference["Wq"]) <= 4 * wait["se"], (wait["mean"], reference["Wq"], wait["se"])
    utilization = summary["metrics"]["utilization_in_horizon"]
    assert abs(utilization["mean"] - 40.0 / 60.0) <= 4 * utilization["se"]
