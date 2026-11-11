"""Conservative selected-load inference, separate from raw DES/MC diagnostics.

The fixed-n Hoeffding/Poisson-envelope derivation is specified in
docs/superpowers/specs/2026-11-10-seed-001-correctness-guard.md, section 2.
Coverage is conditional on the audited domination and ideal independent marginal
replications; this module neither establishes PRNG independence nor estimates
uncertainty in real-world input parameters. Numerical guards are reference-checked
on Lambda 0..1000, not a universal floating-point certificate.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from numbers import Integral, Real
from typing import Any, TypeGuard

from scipy.stats import poisson

SELECTED_LOAD_METHOD = "selected-load-truncated-hoeffding-v1"
ESTIMAND = "conditional_stress_at_expected_routed_load"
CONFIDENCE_LEVEL = 0.95
ALPHA = 0.05
MAX_ENVELOPE_MEAN = 1000.0
MAX_REPLICATIONS = 20
SETTINGS_CACHE_SIZE = 1024
ASSUMPTIONS = (
    "frozen_inputs",
    "ideal_independent_marginal_replications",
    "potential_arrival_poisson_domination",
)
REASON_CODES = frozenset({
    "insufficient_replications", "invalid_family", "missing_replication_evidence",
    "inconsistent_replication_evidence", "failed_conservation", "invalid_count",
    "invalid_duration", "unsupported_envelope_domain", "unsupported_seed_domain",
    "inconsistent_zero_envelope", "unsupported_mc_configuration", "raw_mc_inadequate",
    "numeric_failure", "threshold_overlap",
})


def _integer(value: object) -> TypeGuard[int]:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _number(value: object) -> float | None:
    if not isinstance(value, Real) or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return None
    return result if math.isfinite(result) else None


def required_family_size(required_pairs: object) -> int | None:
    """Count the entire unique required family, including later abstentions."""
    if not isinstance(required_pairs, Sequence) or isinstance(required_pairs, (str, bytes)):
        return None
    seen: set[tuple[str, str]] = set()
    for pair in required_pairs:
        if (not isinstance(pair, (tuple, list)) or len(pair) != 2
                or not all(isinstance(value, str) and value.strip() for value in pair)):
            return None
        key = (pair[0], pair[1])
        if key in seen:
            return None
        seen.add(key)
    return len(seen) or None


@dataclass(frozen=True)
class BoundSettings:
    envelope_mean: float
    replications: int
    family_size: int
    cutoff: int
    coefficient: float
    radius: float
    tail_allowance: float


def _guard(*values: float) -> float:
    return 64 * sys.float_info.epsilon * max(1.0, *values)


def poisson_tail_allowance(envelope_mean: object, cutoff: object) -> float | None:
    """Outward-guarded E[(Poisson(Lambda)-B)+], within the checked domain."""
    lam = _number(envelope_mean)
    if lam is None or not 0 <= lam <= MAX_ENVELOPE_MEAN or not _integer(cutoff) or cutoff < 1:
        return None
    if lam == 0:
        return 0.0
    try:
        b = int(cutoff)
        tail = math.fsum([lam * float(poisson.sf(b - 1, lam)), -b * float(poisson.sf(b, lam))])
        padding = _guard(lam, float(b))
        if not math.isfinite(tail) or tail < -padding:
            return None
        result = math.nextafter(max(0.0, tail) + padding, math.inf)
        return result if math.isfinite(result) else None
    except (OverflowError, ValueError, TypeError):
        return None


@lru_cache(maxsize=SETTINGS_CACHE_SIZE)
def _cached_settings(lam: float, n: int, m: int) -> BoundSettings | None:
    if lam == 0:
        return BoundSettings(lam, n, m, 1, 0.0, 0.0, 0.0)
    # log(40*m) without overflowing a large, valid integer family size.
    coefficient = math.sqrt((math.log(2 / ALPHA) + math.log(m)) / (2 * n))
    quantile = 1.0 if coefficient >= 1 else float(poisson.isf(coefficient, lam))
    if not math.isfinite(quantile):
        return None
    cutoff = max(1, int(quantile))
    tail = poisson_tail_allowance(lam, cutoff)
    radius = cutoff * coefficient
    radius = math.nextafter(radius + _guard(radius), math.inf)
    if tail is None or not math.isfinite(radius):
        return None
    return BoundSettings(lam, n, m, cutoff, coefficient, radius, tail)


def bound_settings(envelope_mean: object, replications: object, family_size: object) -> BoundSettings | None:
    """Immutable input-only settings; no measurements or job identities are cached."""
    lam = _number(envelope_mean)
    if (lam is None or not 0 <= lam <= MAX_ENVELOPE_MEAN
            or not _integer(replications) or not 2 <= replications <= MAX_REPLICATIONS
            or not _integer(family_size) or family_size < 1):
        return None
    try:
        return _cached_settings(lam, int(replications), int(family_size))
    except (OverflowError, ValueError):
        return None


def _context_reasons(*, replications: object, family_size: object, base_seed: object,
                     duration_hours: object, envelope_mean: object, conserved: object) -> list[str]:
    reasons = []
    if not _integer(replications) or not 2 <= replications <= MAX_REPLICATIONS:
        reasons.append("insufficient_replications")
    if not _integer(family_size) or family_size < 1:
        reasons.append("invalid_family")
    if not _integer(base_seed) or base_seed < 0:
        reasons.append("unsupported_seed_domain")
    duration = _number(duration_hours)
    if duration is None or duration <= 0:
        reasons.append("invalid_duration")
    lam = _number(envelope_mean)
    if lam is None or not 0 <= lam <= MAX_ENVELOPE_MEAN:
        reasons.append("unsupported_envelope_domain")
    if conserved is not True:
        reasons.append("failed_conservation" if conserved is False else "missing_replication_evidence")
    return reasons


def _empty_summary(duration_hours: object, envelope_mean: object) -> dict[str, Any]:
    return {"duration_hours": _number(duration_hours), "envelope_mean": _number(envelope_mean),
            "cutoff": None, "sum_truncated": None, "mean_rate_lower": None, "mean_rate_upper": None,
            "status": "insufficient", "reason_codes": []}


def summary_bounds(summary: Mapping[str, Any], *, replications: object, family_size: object,
                   base_seed: object, conserved: object) -> dict[str, Any]:
    """Validate sufficient statistics and recompute bounds, without trusting saved endpoints.

    The caller supplies the complete family size and replication-wide conservation;
    missing coordinates must not reduce either. No input mapping is mutated.
    """
    duration, lam = summary.get("duration_hours"), summary.get("envelope_mean")
    result = _empty_summary(duration, lam)
    reasons = _context_reasons(replications=replications, family_size=family_size, base_seed=base_seed,
                               duration_hours=duration, envelope_mean=lam, conserved=conserved)
    recorded_reasons = summary.get("reason_codes", [])
    if not isinstance(recorded_reasons, list) or any(
            not isinstance(code, str) or code not in REASON_CODES for code in recorded_reasons):
        reasons.append("inconsistent_replication_evidence")
    elif summary.get("status") == "insufficient":
        reasons.extend(recorded_reasons or ["missing_replication_evidence"])
    elif recorded_reasons or summary.get("status") not in (None, "bounded"):
        reasons.append("inconsistent_replication_evidence")
    if reasons:
        result["reason_codes"] = list(dict.fromkeys(reasons))
        return result
    settings = bound_settings(lam, replications, family_size)
    if settings is None:
        result["reason_codes"] = ["numeric_failure"]
        return result
    cutoff, total = summary.get("cutoff"), summary.get("sum_truncated")
    if cutoff is None or total is None:
        result["reason_codes"] = ["missing_replication_evidence"]
        return result
    if not _integer(total) or total < 0:
        result["reason_codes"] = ["invalid_count"]
        return result
    if not _integer(cutoff) or cutoff != settings.cutoff or total > settings.replications * settings.cutoff:
        result["reason_codes"] = ["inconsistent_replication_evidence"]
        return result
    result.update(cutoff=settings.cutoff, sum_truncated=int(total))
    if settings.envelope_mean == 0:
        if total != 0:
            result["reason_codes"] = ["inconsistent_zero_envelope"]
            return result
        lower, upper = 0.0, 0.0
    else:
        center = int(total) / settings.replications
        padding = _guard(settings.envelope_mean, float(settings.cutoff), center, settings.radius)
        lower_count = max(0.0, math.nextafter(center - settings.radius - padding, -math.inf))
        upper_count = min(settings.envelope_mean, math.nextafter(
            math.fsum([center, settings.radius, settings.tail_allowance, padding]), math.inf))
        h = _number(duration)
        assert h is not None
        lower = max(0.0, math.nextafter(lower_count / h, -math.inf))
        upper = math.nextafter(upper_count / h, math.inf)
        if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
            result["reason_codes"] = ["numeric_failure"]
            return result
    result.update(mean_rate_lower=lower, mean_rate_upper=upper, status="bounded", reason_codes=[])
    return result


def summarize_counts(counts: object, *, duration_hours: object, envelope_mean: object,
                     replications: object, family_size: object, base_seed: object,
                     conserved: object) -> dict[str, Any]:
    """Summarize existing integer counts only; never fill missing data or run DES."""
    result = _empty_summary(duration_hours, envelope_mean)
    reasons = _context_reasons(replications=replications, family_size=family_size, base_seed=base_seed,
                               duration_hours=duration_hours, envelope_mean=envelope_mean, conserved=conserved)
    if not isinstance(counts, Sequence) or isinstance(counts, (str, bytes)):
        reasons.append("missing_replication_evidence")
    elif _integer(replications) and len(counts) != replications:
        reasons.append("missing_replication_evidence" if len(counts) < replications
                       else "inconsistent_replication_evidence")
    elif any(not _integer(value) or value < 0 for value in counts):
        reasons.append("invalid_count")
    if reasons:
        result["reason_codes"] = list(dict.fromkeys(reasons))
        return result
    assert isinstance(counts, Sequence)
    settings = bound_settings(envelope_mean, replications, family_size)
    if settings is None:
        result["reason_codes"] = ["numeric_failure"]
        return result
    if settings.envelope_mean == 0 and any(counts):
        result["reason_codes"] = ["inconsistent_zero_envelope"]
        return result
    result.update(cutoff=settings.cutoff, sum_truncated=sum(min(int(value), settings.cutoff) for value in counts))
    result.pop("status")
    return summary_bounds(result, replications=replications, family_size=family_size,
                          base_seed=base_seed, conserved=conserved)


def _certified_stress_corner(rate: float, mu: float, threshold: float) -> float | None:
    """Certify saturation from exact ratios of the finite input floats.

    No rounded rate/mu or scaled-threshold multiplication establishes certainty.
    Python integer products cannot underflow/overflow at subnormal/large floats.
    """
    rate_num, rate_den = rate.as_integer_ratio()
    mu_num, mu_den = mu.as_integer_ratio()
    threshold_num, threshold_den = threshold.as_integer_ratio()
    numerator = rate_num * mu_den * threshold_den
    denominator = rate_den * mu_num * threshold_num
    if 4 * numerator <= 3 * denominator:
        return 0.0
    if 8 * numerator >= 11 * denominator:
        return 1.0
    return None


def conditional_stress_probability(rho: object, threshold: object) -> float | None:
    """Exact rectangle area in real arithmetic for the specified uniform factors.

    Dimensionless comparisons also avoid erroneous subnormal scaled-threshold
    branches. Saturate before integrating; large rho cannot cancel back to zero.
    """
    r, t = _number(rho), _number(threshold)
    if r is None or r < 0 or t is None or t <= 0:
        return None
    certain = _certified_stress_corner(r, 1.0, t)
    if certain is not None:
        return certain
    q = r / t
    start, end = max(0.8, 0.9 / q), min(1.2, 1.1 / q)
    partial = 0.0
    if end > start:
        low = min(0.2, max(0.0, q * start - 0.9))
        high = min(0.2, max(0.0, q * end - 0.9))
        partial = (end - start) * (low + high) / 2
    full = max(0.0, 1.2 - max(0.8, 1.1 / q)) * 0.2
    return min(1.0, max(0.0, math.fsum([partial, full]) / 0.08))


def classify_probability_bounds(lower: object, upper: object, cap: object) -> str:
    """Compare unrounded endpoints; equality at the upper endpoint is a pass."""
    low, high, allowance = _number(lower), _number(upper), _number(cap)
    if (low is None or high is None or allowance is None
            or not 0 <= low <= high <= 1 or not 0 <= allowance <= 1):
        return "insufficient"
    if high <= allowance:
        return "pass"
    if low > allowance:
        return "fail"
    return "insufficient"


def assess_probability_bounds(lower: object, upper: object, mc_row: Mapping[str, Any]) -> dict[str, Any]:
    """Propagate a validated mean-rate interval; raw MC is read but never changed."""
    result: dict[str, Any] = {"mean_rate_lower": _number(lower), "mean_rate_upper": _number(upper),
              **{key: mc_row.get(key) for key in ("mu", "failure_threshold", "failure_rate_cap",
                 "arrival_noise_fraction", "service_noise_fraction", "noise_distribution")},
              "failure_probability_lower": None, "failure_probability_upper": None,
              "status": "insufficient", "reason_codes": []}
    mu, threshold, cap = (_number(mc_row.get(key)) for key in ("mu", "failure_threshold", "failure_rate_cap"))
    if (mu is None or mu <= 0 or threshold is None or threshold <= 0 or cap is None or not 0 <= cap <= 1
            or not _integer(mc_row.get("c")) or mc_row["c"] != 1
            or mc_row.get("selected_model") != "Parallel M/G/1"
            or _number(mc_row.get("arrival_noise_fraction")) != 0.2
            or _number(mc_row.get("service_noise_fraction")) != 0.1
            or mc_row.get("noise_distribution") != "independent_uniform"):
        result["reason_codes"] = ["unsupported_mc_configuration"]
        return result
    k, n = mc_row.get("failure_count"), mc_row.get("trials_completed")
    rate = _number(mc_row.get("failure_rate"))
    if (mc_row.get("simulation_supported") is not True or mc_row.get("failure_rate_adequate") is not True
            or mc_row.get("status") not in ("PASS", "FAIL") or mc_row.get("error") is not None
            or not _integer(k) or not _integer(n) or n < 1 or not 0 <= k <= n
            or rate is None or not 0 <= rate <= 1):
        result["reason_codes"] = ["raw_mc_inadequate"]
        return result
    low, high = _number(lower), _number(upper)
    if low is None or high is None or not 0 <= low <= high:
        result["reason_codes"] = ["numeric_failure"]
        return result
    # Deliberately abstain on unverified subnormal rate-to-rho arithmetic, rather
    # than confuse an underflowed positive load with a known zero load.
    values = (low, high, mu, threshold)
    rhos = (low / mu, high / mu)
    if (any(0 < value < sys.float_info.min for value in (*values, *rhos))
            or any(not math.isfinite(rho) or (value > 0 and rho == 0) for value, rho in zip((low, high), rhos))):
        result["reason_codes"] = ["numeric_failure"]
        return result
    # Enlarge rate/mu before evaluating the monotone function. Certify exact
    # corners against the original rate, mu and threshold, not rounded rhos.
    corners = [_certified_stress_corner(value, mu, threshold) for value in (low, high)]
    outward_rhos = (math.nextafter(rhos[0], -math.inf), math.nextafter(rhos[1], math.inf))
    if any(corner is None and (not math.isfinite(rho) or 0 < rho < sys.float_info.min)
           for corner, rho in zip(corners, outward_rhos)):
        result["reason_codes"] = ["numeric_failure"]
        return result
    probabilities = [corner if corner is not None else conditional_stress_probability(rho, threshold)
                     for corner, rho in zip(corners, outward_rhos)]
    if any(value is None for value in probabilities):
        result["reason_codes"] = ["numeric_failure"]
        return result
    p_low, p_high = probabilities
    assert p_low is not None and p_high is not None
    # A computed 0/1 is not proof of saturation: pad every uncertified endpoint.
    p_low = p_low if corners[0] is not None else max(0.0, math.nextafter(p_low - _guard(p_low), -math.inf))
    p_high = p_high if corners[1] is not None else min(1.0, math.nextafter(p_high + _guard(p_high), math.inf))
    if p_low > p_high:
        result["reason_codes"] = ["numeric_failure"]
        return result
    status = classify_probability_bounds(p_low, p_high, cap)
    result.update(failure_probability_lower=p_low, failure_probability_upper=p_high, status=status,
                  reason_codes=["threshold_overlap"] if status == "insufficient" else [])
    return result


def aggregate_assessment_status(statuses: Sequence[str], *, family_size: object) -> str:
    """A supported fail dominates; an empty/incomplete family never passes."""
    if not _integer(family_size) or family_size < 1:
        return "insufficient"
    if len(statuses) > family_size:
        return "insufficient"
    if "fail" in statuses:
        return "fail"
    if len(statuses) != family_size or any(status != "pass" for status in statuses):
        return "insufficient"
    return "pass"
