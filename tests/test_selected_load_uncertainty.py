"""Independent synthetic mathematical references for the selected-load helper.

These are not observed operational data or a calibration/coverage experiment.
Positive Decimal PMF sums do not use the candidate's SciPy SF identity; the
rational/quad oracles integrate over service factors, while the helper integrates
over arrival factors. References match Kyoya's separately retained 2026-11-10
reference-check.json without importing that external checker or the old prototype.
"""

from __future__ import annotations

import math
import sys
from copy import deepcopy
from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any

import pytest
from scipy.integrate import quad

from backend.queueing_engine.statistics.selected_load_uncertainty import (
    ASSUMPTIONS,
    CONFIDENCE_LEVEL,
    ESTIMAND,
    REASON_CODES,
    SELECTED_LOAD_METHOD,
    _cached_settings,
    aggregate_assessment_status,
    assess_probability_bounds,
    bound_settings,
    classify_probability_bounds,
    conditional_stress_probability,
    poisson_tail_allowance,
    required_family_size,
    summarize_counts,
    summary_bounds,
)


def positive_poisson_tail(lam: Decimal, cutoff: int) -> tuple[Decimal, Decimal]:
    """80-digit nonnegative PMF sum and an upper bound for its omitted tail."""
    with localcontext() as context:
        context.prec = 80
        end = max(cutoff, math.ceil(float(lam) + 15 * math.sqrt(float(lam)) + 100))
        probability, total = (-lam).exp(), Decimal(0)
        for k in range(1, end + 1):
            probability *= lam / k
            if k > cutoff:
                total += (k - cutoff) * probability
        first_omitted = probability * lam / (end + 1)
        ratio = lam / (end + 2)
        remainder = first_omitted * (
            Decimal(end + 1 - cutoff) / (1 - ratio) + ratio / (1 - ratio) ** 2)
        return +total, +remainder


def decimal_settings(lam: Decimal, n: int, m: int) -> tuple[int, Decimal, Decimal]:
    """Independent input-only cutoff from positive CDF sums, not scipy.isf."""
    with localcontext() as context:
        context.prec = 80
        coefficient = (Decimal(40 * m).ln() / (2 * n)).sqrt()
        if lam == 0:
            return 1, Decimal(0), Decimal(0)
        cutoff = 1
        if coefficient < 1:
            probability = (-lam).exp()
            cumulative = probability
            while True:
                probability *= lam / cutoff
                cumulative += probability
                if 1 - cumulative <= coefficient:
                    break
                cutoff += 1
        tail, remainder = positive_poisson_tail(lam, cutoff)
        assert remainder < Decimal("1e-30")
        return cutoff, +coefficient, +(tail + remainder)


def reference_rate_bounds(counts: list[int], lam: Decimal, hours: Decimal, m: int) -> tuple[Decimal, Decimal, int]:
    with localcontext() as context:
        context.prec = 80
        cutoff, coefficient, tail = decimal_settings(lam, len(counts), m)
        center = Decimal(sum(min(value, cutoff) for value in counts)) / len(counts)
        lower = max(Decimal(0), center - cutoff * coefficient)
        upper = min(lam, center + cutoff * coefficient + tail)
        return +(lower / hours), +(upper / hours), cutoff


def rational_stress(normalized_rho: Fraction) -> Fraction:
    """Clipped rectangle integral over S, independent of production arithmetic."""
    if normalized_rho == 0:
        return Fraction(0)
    inverse = 1 / normalized_rho
    service_low, service_high = Fraction(9, 10), Fraction(11, 10)
    arrival_low, arrival_high = Fraction(4, 5), Fraction(6, 5)
    full = max(Fraction(0), min(service_high, arrival_low / inverse) - service_low)
    start, end = max(service_low, arrival_low / inverse), min(service_high, arrival_high / inverse)
    partial = Fraction(0)
    if end > start:
        partial = (arrival_high * (end - start) - inverse * (end**2 - start**2) / 2) / (arrival_high - arrival_low)
    return (full + partial) / (service_high - service_low)


def summary(counts: object = None, **changes: Any) -> dict[str, Any]:
    arguments = {"duration_hours": 1.0, "envelope_mean": 3.75, "replications": 20,
                 "family_size": 60, "base_seed": 42, "conserved": True}
    arguments.update(changes)
    return summarize_counts([0] * 20 if counts is None else counts, **arguments)


def raw_mc(**changes: Any) -> dict[str, Any]:
    """Synthetic valid diagnostic metadata, not an executed Monte Carlo result."""
    row = {"mu": 1.0, "c": 1, "selected_model": "Parallel M/G/1",
           "failure_threshold": 1.0, "failure_rate_cap": 0.05,
           "arrival_noise_fraction": 0.2, "service_noise_fraction": 0.1,
           "noise_distribution": "independent_uniform", "simulation_supported": True,
           "failure_rate_adequate": True, "failure_count": 20, "trials_completed": 2000,
           "failure_rate": 0.01, "status": "PASS", "error": None}
    return {**row, **changes}


def test_canonical_method_and_conditional_claim():
    assert SELECTED_LOAD_METHOD == "selected-load-truncated-hoeffding-v1"
    assert ESTIMAND == "conditional_stress_at_expected_routed_load"
    assert CONFIDENCE_LEVEL == 0.95
    assert ASSUMPTIONS == ("frozen_inputs", "ideal_independent_marginal_replications",
                           "potential_arrival_poisson_domination")


@pytest.mark.parametrize("lam,cutoff", [
    ("0", 1), ("1e-8", 1), (".4", 1), ("3.75", 1), ("3.75", 3), ("3.75", 4),
    ("24", 1), ("24", 24), ("24", 25), ("1000", 1), ("1000", 1000), ("1000", 1005),
])
def test_tail_against_independent_positive_decimal_sums(lam, cutoff):
    reference, remainder = positive_poisson_tail(Decimal(lam), cutoff)
    measured = poisson_tail_allowance(float(lam), cutoff)
    assert measured is not None
    assert remainder < Decimal("1e-30")
    assert Decimal.from_float(measured) >= reference + remainder
    assert Decimal.from_float(measured) - reference < Decimal("1e-9") * max(1, Decimal(lam), cutoff)


@pytest.mark.parametrize("lam,n,m", [("0", 2, 1), (".4", 2, 60), ("3.75", 20, 1),
                                     ("3.75", 20, 60), ("24", 20, 60), ("1000", 20, 60)])
def test_input_only_cutoff_against_decimal_cdf_rule(lam, n, m):
    expected_cutoff, coefficient, _ = decimal_settings(Decimal(lam), n, m)
    settings = bound_settings(float(lam), n, m)
    assert settings is not None
    assert settings.cutoff == expected_cutoff
    assert settings.coefficient == pytest.approx(float(coefficient), abs=2e-15)
    assert settings.radius >= float(coefficient) * expected_cutoff


def test_settings_cache_is_small_immutable_and_measurement_free():
    first = bound_settings(3.75, 20, 60)
    assert first is not None
    assert bound_settings(3.75, 20, 60) is first
    assert _cached_settings.cache_info().maxsize == 1024
    with pytest.raises(FrozenInstanceError):
        first.cutoff = 100  # type: ignore[misc]
    for m in range(1, 1030):
        assert bound_settings(0, 2, m) is not None
    assert _cached_settings.cache_info().currsize <= 1024
    assert bound_settings(3.75, 20, 60) == first


@pytest.mark.parametrize("counts,lam,hours,m", [
    ([1, 2, 3, 4] * 5, "3.75", "1", 60), ([20] * 20, "24", ".5", 60),
    ([1000] * 20, "1000", "2", 1), ([0, 1], ".4", "1.5", 60),
])
def test_summary_encloses_independent_decimal_bound(counts, lam, hours, m):
    reference_low, reference_high, cutoff = reference_rate_bounds(counts, Decimal(lam), Decimal(hours), m)
    measured = summary(counts, envelope_mean=float(lam), duration_hours=float(hours),
                       replications=len(counts), family_size=m)
    assert measured["status"] == "bounded"
    assert measured["cutoff"] == cutoff
    assert measured["sum_truncated"] == sum(min(value, cutoff) for value in counts)
    low, high = Decimal.from_float(measured["mean_rate_lower"]), Decimal.from_float(measured["mean_rate_upper"])
    assert low <= reference_low <= reference_high <= high
    assert reference_low - low <= Decimal("2e-9") * max(1, reference_high)
    assert high - reference_high <= Decimal("2e-9") * max(1, reference_high)


def test_known_zero_is_distinct_from_all_zero_observations():
    known = summary(envelope_mean=0)
    observed = summary(envelope_mean=0.4)
    assert known["status"] == observed["status"] == "bounded"
    assert known["mean_rate_lower"] == known["mean_rate_upper"] == 0
    assert observed["mean_rate_upper"] > 0
    assert summary([0] * 19 + [1], envelope_mean=0)["reason_codes"] == ["inconsistent_zero_envelope"]


def test_arbitrary_ids_dependent_coordinates_and_unequal_hours_keep_full_family():
    pairs = [("2026-11-09 08:00–08:30", "east-07"), ("09:00", "lane A"), ("09:00", "cashier_α")]
    assert required_family_size(pairs) == 3
    # Perfectly dependent synthetic coordinate vectors are permitted by the union bound.
    counts = [1, 2, 3, 4] * 5
    one = summary(counts, family_size=3)
    half = summary(counts, family_size=3, duration_hours=0.5)
    assert half["mean_rate_lower"] == 2 * one["mean_rate_lower"]
    assert half["mean_rate_upper"] == 2 * one["mean_rate_upper"]
    invalid = summary([1] * 19, family_size=3)
    assert invalid["status"] == "insufficient"
    # The input-only cutoff changes with m; final intervals are not claimed to
    # nest across family sizes. Check the entire m=3 allocation independently.
    expected_low, expected_high, expected_cutoff = reference_rate_bounds(counts, Decimal("3.75"), Decimal(1), 3)
    assert one["cutoff"] == expected_cutoff
    assert Decimal.from_float(one["mean_rate_lower"]) <= expected_low <= expected_high
    assert expected_high <= Decimal.from_float(one["mean_rate_upper"])
    assert aggregate_assessment_status(["pass", "pass", invalid["status"]], family_size=3) == "insufficient"


@pytest.mark.parametrize("pairs", [[], [("a", "q"), ("a", "q")], [("a", "")], [("a", None)],
                                   [("a", True)], ["a/q"], "a/q", None, [("a", "q", "extra")]])
def test_invalid_required_families_never_become_empty_success(pairs):
    assert required_family_size(pairs) is None


@pytest.mark.parametrize("field,value,reason", [
    ("replications", 1, "insufficient_replications"), ("replications", 21, "insufficient_replications"),
    ("replications", True, "insufficient_replications"), ("replications", 2.0, "insufficient_replications"),
    ("family_size", 0, "invalid_family"), ("family_size", True, "invalid_family"),
    ("base_seed", None, "unsupported_seed_domain"), ("base_seed", -1, "unsupported_seed_domain"),
    ("base_seed", True, "unsupported_seed_domain"), ("base_seed", 42.0, "unsupported_seed_domain"),
    ("duration_hours", 0, "invalid_duration"), ("duration_hours", -1, "invalid_duration"),
    ("duration_hours", True, "invalid_duration"), ("duration_hours", math.inf, "invalid_duration"),
    ("envelope_mean", None, "unsupported_envelope_domain"), ("envelope_mean", -1, "unsupported_envelope_domain"),
    ("envelope_mean", 1000.1, "unsupported_envelope_domain"), ("envelope_mean", math.nan, "unsupported_envelope_domain"),
    ("envelope_mean", True, "unsupported_envelope_domain"), ("conserved", False, "failed_conservation"),
    ("conserved", None, "missing_replication_evidence"),
])
def test_invalid_context_abstains_without_rejecting_raw_request(field, value, reason):
    measured = summary(**{field: value})
    assert measured["status"] == "insufficient"
    assert reason in measured["reason_codes"]
    assert measured["mean_rate_lower"] is measured["mean_rate_upper"] is None
    assert set(measured["reason_codes"]) <= REASON_CODES


@pytest.mark.parametrize("bad", [True, False, 1.0, -1, None, "1", math.nan, math.inf])
def test_counts_are_nonnegative_integers_never_coerced(bad):
    counts = [0] * 19 + [bad]
    assert summary(counts)["reason_codes"] == ["invalid_count"]
    assert counts[-1] is bad


def test_missing_extra_and_rare_counts_are_not_zero_filled_or_dropped():
    assert summarize_counts(None, duration_hours=1, envelope_mean=.4, replications=20,
                            family_size=60, base_seed=42, conserved=True)["reason_codes"] == ["missing_replication_evidence"]
    assert summary([0] * 19)["reason_codes"] == ["missing_replication_evidence"]
    assert summary([0] * 21)["reason_codes"] == ["inconsistent_replication_evidence"]
    for rare in (1, 2, 10**1000):
        measured = summary([0] * 19 + [rare], envelope_mean=.4)
        assert measured["status"] == "bounded"
        assert measured["sum_truncated"] == 1
        assert measured["mean_rate_upper"] > 0


def test_summary_validation_does_not_trust_missing_or_corrupt_sufficient_statistics():
    original = summary([1, 2, 3, 4] * 5)
    arguments = {"replications": 20, "family_size": 60, "base_seed": 42, "conserved": True}
    assert summary_bounds(original, **arguments) == original
    for field, value, reason in [("cutoff", None, "missing_replication_evidence"),
                                  ("cutoff", original["cutoff"] + 1, "inconsistent_replication_evidence"),
                                  ("sum_truncated", True, "invalid_count"),
                                  ("sum_truncated", 20 * original["cutoff"] + 1, "inconsistent_replication_evidence"),
                                  ("reason_codes", [{}], "inconsistent_replication_evidence"),
                                  ("status", "invented", "inconsistent_replication_evidence")]:
        corrupted = {**original, field: value}
        assert reason in summary_bounds(corrupted, **arguments)["reason_codes"]
    refused = {**original, "status": "insufficient", "reason_codes": ["failed_conservation"]}
    assert summary_bounds(refused, **arguments)["reason_codes"] == ["failed_conservation"]
    changed_endpoints = {**original, "mean_rate_lower": -100, "mean_rate_upper": -50}
    assert summary_bounds(changed_endpoints, **arguments) == original


def test_contradictory_interval_and_nonfinite_rate_arithmetic_abstain():
    assert summary([1] * 20, envelope_mean=.001, family_size=1)["reason_codes"] == ["numeric_failure"]
    assert summary([20] * 20, envelope_mean=24, duration_hours=5e-324)["reason_codes"] == ["numeric_failure"]


@pytest.mark.parametrize("rho,expected", [(Fraction(0), Fraction(0)), (Fraction(3, 4), Fraction(0)),
    (Fraction(4, 5), Fraction(9, 320)), (Fraction(9, 10), Fraction(9, 40)),
    (Fraction(1), Fraction(1, 2)), (Fraction(11, 10), Fraction(8, 11)),
    (Fraction(6, 5), Fraction(431, 480)), (Fraction(11, 8), Fraction(1)), (Fraction(10), Fraction(1))])
def test_stress_against_independent_exact_rational_rectangles(rho, expected):
    assert rational_stress(rho) == expected
    for threshold in (0.4, 0.85, 1, 2):
        measured = conditional_stress_probability(float(rho) * threshold, threshold)
        assert measured == pytest.approx(float(expected), abs=3e-15)


@pytest.mark.parametrize("rho", [0, .2, .75, .751, .8, .9, 1, 1.1, 1.2, 1.374, 1.375, 10])
def test_stress_against_independent_service_axis_quadrature(rho):
    def conditional(service):
        return 0 if rho == 0 else min(1, max(0, (1.2 - service / rho) / .4))
    points = [value for value in (.8 * rho, 1.2 * rho) if .9 < value < 1.1]
    expected, error = quad(conditional, .9, 1.1, points=points, epsabs=1e-13)
    assert error < 1e-12
    assert conditional_stress_probability(rho, 1) == pytest.approx(expected / .2, abs=3e-14)


def test_stress_extremes_subnormal_ratio_and_monotonicity():
    for rho in (1.375, 10, 1e8, 1e16, 1e308):
        assert conditional_stress_probability(rho, 1) == 1
    assert conditional_stress_probability(1e308, 1e-308) == 1
    assert conditional_stress_probability(1e-308, 1e308) == 0
    assert conditional_stress_probability(5e-324, 5e-324) == pytest.approx(.5, abs=3e-15)
    values = [conditional_stress_probability(k / 1000, 1) for k in range(1501)]
    assert all(value is not None for value in values)
    assert values == sorted(values)
    assert conditional_stress_probability(math.nextafter(.75, -math.inf), 1) == 0
    assert conditional_stress_probability(math.nextafter(1.375, math.inf), 1) == 1


@pytest.mark.parametrize("rho,threshold", [(-1, 1), (True, 1), (None, 1), (math.inf, 1),
                                           (1, 0), (1, -1), (1, True), (1, math.nan)])
def test_invalid_stress_domain_abstains(rho, threshold):
    assert conditional_stress_probability(rho, threshold) is None


def test_unrounded_cap_equality_and_neighboring_floats():
    assert classify_probability_bounds(0, .05, .05) == "pass"
    assert classify_probability_bounds(.05, .06, .05) == "insufficient"
    assert classify_probability_bounds(math.nextafter(.05, math.inf), .06, .05) == "fail"
    assert classify_probability_bounds(0, math.nextafter(.05, math.inf), .05) == "insufficient"
    assert classify_probability_bounds(0, math.nextafter(.05, -math.inf), .05) == "pass"
    for low, high, cap in [(1, 0, .05), (-1, 0, .05), (0, 2, .05), (0, .1, True), (None, .1, .05)]:
        assert classify_probability_bounds(low, high, cap) == "insufficient"


def test_probability_assessment_is_separate_from_raw_point_verdict_and_preserves_inputs():
    passing_raw = raw_mc()
    before = deepcopy(passing_raw)
    failed = assess_probability_bounds(1.5, 2, passing_raw)
    assert failed["status"] == "fail" and failed["failure_probability_lower"] == 1
    assert passing_raw == before
    failing_raw = raw_mc(failure_rate=.1, failure_count=200, status="FAIL")
    passed = assess_probability_bounds(0, .5, failing_raw)
    assert passed["status"] == "pass" and passed["failure_probability_upper"] == 0
    overlap = assess_probability_bounds(.5, 1, failing_raw)
    assert overlap["status"] == "insufficient" and overlap["reason_codes"] == ["threshold_overlap"]
    explicit_threshold = assess_probability_bounds(.5, .6, raw_mc(failure_threshold=.4))
    assert explicit_threshold["status"] == "fail"


@pytest.mark.parametrize("field,value,reason", [
    ("c", 2, "unsupported_mc_configuration"), ("c", True, "unsupported_mc_configuration"),
    ("selected_model", "M/M/1", "unsupported_mc_configuration"),
    ("arrival_noise_fraction", .1, "unsupported_mc_configuration"),
    ("service_noise_fraction", .2, "unsupported_mc_configuration"),
    ("noise_distribution", "normal", "unsupported_mc_configuration"),
    ("mu", 0, "unsupported_mc_configuration"), ("mu", math.inf, "unsupported_mc_configuration"),
    ("failure_threshold", 0, "unsupported_mc_configuration"),
    ("failure_rate_cap", -1, "unsupported_mc_configuration"),
    ("simulation_supported", False, "raw_mc_inadequate"), ("failure_rate_adequate", False, "raw_mc_inadequate"),
    ("failure_rate_adequate", 1, "raw_mc_inadequate"), ("failure_count", True, "raw_mc_inadequate"),
    ("failure_count", 2001, "raw_mc_inadequate"), ("trials_completed", 0, "raw_mc_inadequate"),
    ("status", "ERROR", "raw_mc_inadequate"), ("failure_rate", None, "raw_mc_inadequate"),
])
def test_unsupported_or_inadequate_mc_cannot_support_inference(field, value, reason):
    measured = assess_probability_bounds(0, .5, raw_mc(**{field: value}))
    assert measured["status"] == "insufficient" and measured["reason_codes"] == [reason]
    assert measured["failure_probability_lower"] is measured["failure_probability_upper"] is None


@pytest.mark.parametrize("low,high,mu,threshold", [(5e-324, 5e-324, 1, 1), (0, 1, 5e-324, 1),
    (0, 1, 1, 5e-324), (sys.float_info.min, sys.float_info.min, 1e308, 1), (1e308, 1e308, .1, 1)])
def test_unverified_rate_to_rho_subnormal_underflow_overflow_abstains(low, high, mu, threshold):
    result = assess_probability_bounds(low, high, raw_mc(mu=mu, failure_threshold=threshold))
    assert result["reason_codes"] == ["numeric_failure"]
    assert result["failure_probability_lower"] is result["failure_probability_upper"] is None


def test_probability_endpoint_guards_enclose_rational_values_and_are_monotone():
    prior_low = prior_high = 0.0
    for rho in (Fraction(0), Fraction(3, 4), Fraction(4, 5), Fraction(9, 10), Fraction(1),
                Fraction(11, 10), Fraction(6, 5), Fraction(11, 8), Fraction(10)):
        exact = rational_stress(rho)
        measured = assess_probability_bounds(float(rho), float(rho), raw_mc())
        low, high = measured["failure_probability_lower"], measured["failure_probability_upper"]
        assert Fraction.from_float(low) <= exact <= Fraction.from_float(high)
        assert high - low < 1e-12
        assert low >= prior_low and high >= prior_high
        prior_low, prior_high = low, high


def test_corner_rounding_never_certifies_false_zero_or_one_probability():
    # KS-G1: both rate/mu and rho/threshold can round towards a corner.
    # A tiny positive exact area must not pass merely because float p became 0.
    row = raw_mc(mu=.1, failure_threshold=.1, failure_rate_cap=5e-324,
                 failure_count=0, failure_rate=0)
    high = .0075000000000000015
    exact = rational_stress(Fraction.from_float(high) / Fraction.from_float(.1) / Fraction.from_float(.1))
    assert exact > 0
    measured = assess_probability_bounds(0, high, row)
    assert Fraction.from_float(measured["failure_probability_upper"]) >= exact
    assert measured["status"] == "insufficient"
    for lower in (.01375, math.nextafter(.01375, -math.inf), math.nextafter(.01375, math.inf)):
        exact_lower = rational_stress(Fraction.from_float(lower) / Fraction.from_float(.1) / Fraction.from_float(.1))
        measured = assess_probability_bounds(lower, 1, row)
        assert Fraction.from_float(measured["failure_probability_lower"]) <= exact_lower


def test_supported_fail_insufficient_pass_precedence_never_vacuously_passes():
    assert aggregate_assessment_status([], family_size=0) == "insufficient"
    assert aggregate_assessment_status([], family_size=1) == "insufficient"
    assert aggregate_assessment_status(["pass"], family_size=2) == "insufficient"
    assert aggregate_assessment_status(["fail", "insufficient"], family_size=2) == "fail"
    assert aggregate_assessment_status(["fail"], family_size=2) == "fail"
    assert aggregate_assessment_status(["pass", "insufficient"], family_size=2) == "insufficient"
    assert aggregate_assessment_status(["pass", "pass"], family_size=2) == "pass"
    assert aggregate_assessment_status(["pass", "pass"], family_size=1) == "insufficient"
