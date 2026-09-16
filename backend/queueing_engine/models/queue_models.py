"""Core M/M/1, M/G/1, M/M/c, M/G/c, M/M/c/K, and M/G/c/K formulas."""

from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Any

from backend.queueing_engine.log import get_logger

logger = get_logger(__name__)


def _result(
    rho: float | None = None,
    L: float | None = None,
    Lq: float | None = None,
    W: float | None = None,
    Wq: float | None = None,
    stable: bool = False,
    error: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Return a consistent result structure for all queue model calculations."""
    import inspect

    result = {
        "rho": rho,
        "L": L,
        "Lq": Lq,
        "W": W,
        "Wq": Wq,
        "stable": stable,
        "error": error,
    }
    result.update(extra)
    frame = inspect.currentframe()
    caller = frame.f_back.f_code.co_name if (frame and frame.f_back) else "?"
    if error:
        logger.warning("%s: %s", caller, error)
    elif stable:
        logger.debug("%s: rho=%.4g Lq=%.4g Wq=%.4g", caller, rho, Lq, Wq)
    return result


def _is_valid_rate(value: object) -> bool:
    """Check that a rate input is numeric and finite."""
    return isinstance(value, Real) and math.isfinite(float(value))


def mm1(lambda_: float, mu: float) -> dict[str, Any]:
    """Compute steady-state metrics for an M/M/1 queue."""
    if not _is_valid_rate(lambda_) or not _is_valid_rate(mu):
        return _result(error="Invalid input: lambda and mu must be finite numbers.")

    lambda_ = float(lambda_)
    mu = float(mu)

    if lambda_ < 0 or mu <= 0:
        return _result(error="Invalid input: lambda must be >= 0 and mu must be > 0.")

    rho = lambda_ / mu

    if lambda_ >= mu:
        return _result(
            rho=rho,
            stable=False,
            error="Unstable system: lambda must be less than mu for M/M/1.",
        )

    try:
        gap = mu - lambda_
        L = lambda_ / gap
        Lq = (lambda_ ** 2) / (mu * gap)
        W = 1.0 / gap
        Wq = lambda_ / (mu * gap)
        return _result(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq, stable=True)
    except ZeroDivisionError:
        return _result(
            rho=rho,
            stable=False,
            error="Calculation failed because the service margin reached zero.",
        )


def mg1(lambda_: float, mu: float, service_variance: float) -> dict[str, Any]:
    """Compute exact steady-state metrics for an M/G/1 queue."""
    if (
        not _is_valid_rate(lambda_)
        or not _is_valid_rate(mu)
        or not _is_valid_rate(service_variance)
    ):
        return _result(
            error="Invalid input: lambda, mu, and service_variance must be finite numbers."
        )

    lambda_ = float(lambda_)
    mu = float(mu)
    service_variance = float(service_variance)
    if lambda_ < 0 or mu <= 0 or service_variance < 0:
        return _result(
            error=(
                "Invalid input: lambda must be >= 0, mu > 0, "
                "and service_variance must be >= 0."
            )
        )

    service_mean = 1.0 / mu
    rho = lambda_ * service_mean
    if rho >= 1.0:
        return _result(
            rho=rho,
            stable=False,
            error="Unstable system: rho must be less than 1 for M/G/1.",
        )

    try:
        second_moment = service_variance + service_mean**2
        Wq = 0.0 if lambda_ == 0 else lambda_ * second_moment / (2.0 * (1.0 - rho))
        W = Wq + service_mean
        Lq = lambda_ * Wq
        L = lambda_ * W
        return _result(
            rho=rho,
            L=L,
            Lq=Lq,
            W=W,
            Wq=Wq,
            stable=True,
            service_mean=service_mean,
            service_variance=service_variance,
            service_second_moment=second_moment,
        )
    except (OverflowError, ZeroDivisionError, ValueError):
        return _result(
            rho=rho,
            stable=False,
            error="M/G/1 calculation failed due to numerical instability.",
        )


def mmc(lambda_: float, mu: float, c: int) -> dict[str, Any]:
    """Compute steady-state metrics for an M/M/c queue."""
    if not _is_valid_rate(lambda_) or not _is_valid_rate(mu):
        return _result(error="Invalid input: lambda and mu must be finite numbers.")

    if not isinstance(c, Integral):
        return _result(error="Invalid input: c must be a positive integer.")

    lambda_ = float(lambda_)
    mu = float(mu)
    c = int(c)

    if lambda_ < 0 or mu <= 0 or c <= 0:
        return _result(
            error="Invalid input: lambda must be >= 0, mu > 0, and c > 0."
        )

    rho = lambda_ / (c * mu)

    if lambda_ >= c * mu:
        return _result(
            rho=rho,
            stable=False,
            error="Unstable system: lambda must be less than c * mu for M/M/c.",
        )

    try:
        offered_load = lambda_ / mu
        tail_term = (offered_load ** c) / (math.factorial(c) * (1.0 - rho))
        p0_denominator = sum(
            (offered_load ** n) / math.factorial(n) for n in range(c)
        ) + tail_term
        p0 = 1.0 / p0_denominator

        Lq = (
            p0
            * (offered_load ** c)
            * rho
            / (math.factorial(c) * ((1.0 - rho) ** 2))
        )
        Wq = 0.0 if lambda_ == 0 else Lq / lambda_
        W = Wq + (1.0 / mu)
        L = lambda_ * W

        return _result(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq, stable=True)
    except (OverflowError, ZeroDivisionError, ValueError):
        return _result(
            rho=rho,
            stable=False,
            error="Calculation failed due to numerical instability.",
        )


def mgc(lambda_: float, mu: float, c: int, service_variance: float) -> dict[str, Any]:
    """Approximate steady-state metrics for an M/G/c queue.

    The approximation uses Allen-Cunneen scaling over the M/M/c waiting time:
    Wq(M/G/c) ~= ((Ca^2 + Cs^2) / 2) * Wq(M/M/c), with Poisson arrivals
    so Ca^2 = 1. For exponential service, Cs^2 = 1 and the result matches
    M/M/c.
    """
    if (
        not _is_valid_rate(lambda_)
        or not _is_valid_rate(mu)
        or not _is_valid_rate(service_variance)
    ):
        return _result(
            error="Invalid input: lambda, mu, and service_variance must be finite numbers."
        )

    if not isinstance(c, Integral):
        return _result(error="Invalid input: c must be a positive integer.")

    lambda_ = float(lambda_)
    mu = float(mu)
    c = int(c)
    service_variance = float(service_variance)

    if lambda_ < 0 or mu <= 0 or c <= 0 or service_variance < 0:
        return _result(
            error=(
                "Invalid input: lambda must be >= 0, mu > 0, c > 0, "
                "and service_variance must be >= 0."
            )
        )

    base = mmc(lambda_, mu, c)
    rho = base.get("rho")

    if not base.get("stable", False):
        return _result(
            rho=rho,
            stable=False,
            error="Unstable system: lambda must be less than c * mu for M/G/c.",
        )

    try:
        squared_coefficient_of_service_variation = service_variance * (mu ** 2)
        variability_factor = (1.0 + squared_coefficient_of_service_variation) / 2.0
        Wq = base["Wq"] * variability_factor
        Lq = lambda_ * Wq
        W = Wq + (1.0 / mu)
        L = lambda_ * W
        return _result(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq, stable=True)
    except (OverflowError, ZeroDivisionError, ValueError):
        return _result(
            rho=rho,
            stable=False,
            error="M/G/c calculation failed due to numerical instability.",
        )


def _is_valid_capacity(value: object) -> bool:
    """Check that a capacity input is a positive integer."""
    return isinstance(value, Integral)


def mmck(lambda_: float, mu: float, c: int, K: int) -> dict[str, Any]:
    """Compute exact steady-state metrics for an M/M/c/K finite-capacity queue.

    K is total system capacity: customers in service plus customers waiting.
    Arrivals that find K customers in the system are blocked.
    """
    if not _is_valid_rate(lambda_) or not _is_valid_rate(mu):
        return _result(error="Invalid input: lambda and mu must be finite numbers.")

    if not isinstance(c, Integral):
        return _result(error="Invalid input: c must be a positive integer.")

    if not _is_valid_capacity(K):
        return _result(error="Invalid input: K must be a positive integer.")

    lambda_ = float(lambda_)
    mu = float(mu)
    c = int(c)
    K = int(K)

    if lambda_ < 0 or mu <= 0 or c <= 0 or K <= 0 or K < c:
        return _result(
            error=(
                "Invalid input: lambda must be >= 0, mu > 0, c > 0, "
                "and K must be >= c."
            )
        )

    try:
        offered_load = lambda_ / mu
        weights = []
        for n in range(K + 1):
            if n <= c:
                weight = (offered_load ** n) / math.factorial(n)
            else:
                weight = (offered_load ** n) / (
                    math.factorial(c) * (c ** (n - c))
                )
            weights.append(weight)

        p0 = 1.0 / sum(weights)
        probabilities = [p0 * weight for weight in weights]
        blocking_probability = probabilities[K]
        effective_lambda = lambda_ * (1.0 - blocking_probability)

        L = sum(n * probabilities[n] for n in range(K + 1))
        Lq = sum(max(n - c, 0) * probabilities[n] for n in range(K + 1))
        W = 0.0 if effective_lambda == 0 else L / effective_lambda
        Wq = 0.0 if effective_lambda == 0 else Lq / effective_lambda
        rho = sum(min(n, c) * probabilities[n] for n in range(K + 1)) / c

        return _result(
            rho=rho,
            L=L,
            Lq=Lq,
            W=W,
            Wq=Wq,
            stable=True,
            blocking_probability=blocking_probability,
            effective_lambda=effective_lambda,
            K=K,
        )
    except (OverflowError, ZeroDivisionError, ValueError):
        return _result(
            stable=False,
            error="M/M/c/K calculation failed due to numerical instability.",
            K=K,
        )


def mgck(lambda_: float, mu: float, c: int, service_variance: float, K: int) -> dict[str, Any]:
    """Approximate steady-state metrics for an M/G/c/K finite-capacity queue.

    The finite-capacity blocking probability comes from M/M/c/K. Waiting time
    is adjusted by the same variability factor used for M/G/c.
    """
    if not _is_valid_rate(service_variance):
        return _result(error="Invalid input: service_variance must be finite.")

    service_variance = float(service_variance)
    if service_variance < 0:
        return _result(error="Invalid input: service_variance must be >= 0.")

    base = mmck(lambda_, mu, c, K)
    if not base.get("stable", False):
        return base

    try:
        mu = float(mu)
        effective_lambda = base.get("effective_lambda", 0.0)
        squared_coefficient_of_service_variation = service_variance * (mu ** 2)
        variability_factor = (1.0 + squared_coefficient_of_service_variation) / 2.0
        Wq = base["Wq"] * variability_factor
        Lq = effective_lambda * Wq
        W = Wq + (1.0 / mu)
        L = effective_lambda * W
        if not all(math.isfinite(v) and v >= 0 for v in (L, Lq, W, Wq)) or L > K + 1e-10 or Lq > K - c + 1e-10:
            return _result(rho=base.get("rho"), stable=False, K=K,
                           error="M/G/c/K approximation exceeds finite-capacity bounds.")

        return _result(
            rho=base["rho"],
            L=L,
            Lq=Lq,
            W=W,
            Wq=Wq,
            stable=True,
            blocking_probability=base.get("blocking_probability"),
            effective_lambda=effective_lambda,
            K=base.get("K"),
            approximation="Allen-Cunneen adjustment over M/M/c/K",
        )
    except (OverflowError, ZeroDivisionError, ValueError):
        return _result(
            rho=base.get("rho"),
            stable=False,
            error="M/G/c/K calculation failed due to numerical instability.",
            K=base.get("K"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Non-preemptive two-class M/M/c priority queue  —  Kleinrock (1975)
# ─────────────────────────────────────────────────────────────────────────────

def mmc_priority(lambda1: float, lambda2: float, mu: float, c: int) -> dict[str, Any]:
    """
    Compute steady-state metrics for a two-class non-preemptive priority
    M/M/c queue.

    Class 1 (priority) — express lane customers (≤10 items).
    Class 2 (regular)  — regular lane customers.

    The total waiting time Wq_mmc is computed from the standard M/M/c model
    at the aggregate load (λ = λ1 + λ2). Priority class waiting times then
    follow the Kleinrock conservation law:

      Wq₁ = Wq_mmc  /  (1 - σ₁)
      Wq₂ = Wq_mmc  /  ((1 - σ₁)(1 - σ₁ - σ₂))

    where σᵢ = λᵢ / (c·μ).

    Parameters
    ----------
    lambda1 : float
        Arrival rate of priority (class 1) customers.
    lambda2 : float
        Arrival rate of regular (class 2) customers.
    mu : float
        Service rate per server.
    c : int
        Number of shared servers.

    Returns
    -------
    dict
        {rho, stable, error,
         Wq_priority, Wq_regular, Lq_priority, Lq_regular,
         W_priority, W_regular}

    References
    ----------
    Kleinrock, L. (1975).  *Queueing Systems, Volume I: Theory*.
    Wiley-Interscience.  Section 3.3.
    """
    if not (_is_valid_rate(lambda1) and _is_valid_rate(lambda2) and _is_valid_rate(mu)):
        return _result(
            error="Invalid input: lambda1, lambda2, and mu must be finite numbers."
        )
    if not isinstance(c, Integral):
        return _result(error="Invalid input: c must be a positive integer.")

    lambda1 = float(lambda1)
    lambda2 = float(lambda2)
    mu = float(mu)
    c = int(c)

    if lambda1 <= 0 or lambda2 <= 0 or mu <= 0 or c < 1:
        return _result(
            error="Invalid input: lambda1, lambda2, mu must be > 0 and c >= 1."
        )

    total_lambda = lambda1 + lambda2
    rho = total_lambda / (c * mu)          # total per-server utilisation
    sigma1 = lambda1 / (c * mu)
    sigma2 = lambda2 / (c * mu)

    if rho >= 1.0 or (sigma1 + sigma2) >= 1.0:
        return _result(
            rho=rho,
            stable=False,
            error="Unstable system: total utilisation must be < 1.",
        )

    # Base M/M/c waiting time at the aggregate load
    base = mmc(total_lambda, mu, c)
    wq_mmc = base["Wq"]                     # overall mean waiting time

    # Priority-class waiting times  (Kleinrock conservation law)
    denom1 = 1.0 - sigma1
    denom2 = denom1 * (1.0 - sigma1 - sigma2)

    wq1 = wq_mmc / denom1
    wq2 = wq_mmc / denom2

    w1 = wq1 + 1.0 / mu
    w2 = wq2 + 1.0 / mu

    lq1 = lambda1 * wq1
    lq2 = lambda2 * wq2

    return {
        "rho": rho,
        "stable": True,
        "error": None,
        "Wq_priority": wq1,
        "Wq_regular": wq2,
        "Lq_priority": lq1,
        "Lq_regular": lq2,
        "W_priority": w1,
        "W_regular": w2,
    }


# ─────────────────────────────────────────────────────────────────────────────
# M/M/c+M (Erlang-A)  —  Garnett, Mandelbaum & Reiman (2002)
# ─────────────────────────────────────────────────────────────────────────────

ERLANG_A_TOLERANCE = 1e-12
ERLANG_A_MAX_STATES = 100000


def _logadd(a: float, b: float) -> float:
    peak = max(a, b)
    return peak + math.log1p(math.exp(min(a, b) - peak))


def erlang_a(lambda_: float, mu: float, c: int, theta: float) -> dict[str, Any]:
    """Erlang-A birth/death distribution with bounded omitted mass/first moment.

    Descending tail ratios bound the remaining terms by a geometric sequence.
    Both tail probability and first moment must be <= 1e-12 of accumulated
    values before stopping. At 100000 states an unconverged result is rejected.
    W/Wq preserve legacy workload-per-served-throughput ratios, not all-arrival
    or served-customer mean sojourn/wait times. ``metric_basis`` states this.
    """
    if (not all(_is_valid_rate(v) for v in (lambda_, mu, theta))
            or isinstance(c, bool) or not isinstance(c, Integral)
            or lambda_ < 0 or mu <= 0 or c < 1 or theta < 0):
        return _result(error="Invalid input: finite lambda >= 0, mu > 0, integer c >= 1, theta >= 0 required.")
    lambda_, mu, theta, c = float(lambda_), float(mu), float(theta), int(c)
    if theta == 0:
        return mmc(lambda_, mu, c)
    capacity = c * mu
    if not math.isfinite(capacity):
        return _result(error="Numerical range exceeded by service capacity.")
    metadata = {"theta": theta, "metric_basis": "workload_per_served_throughput",
                "numerical_tolerance": ERLANG_A_TOLERANCE}
    if lambda_ == 0:
        return _result(rho=0.0, L=0.0, Lq=0.0, W=1 / mu, Wq=0.0, stable=True,
                       lambda_eff=0.0, rho_effective=0.0, abandonment_rate=0.0, **metadata)
    logs = [0.0]
    log_total = 0.0
    log_moment = -math.inf
    log_lambda = math.log(lambda_)
    converged = False
    for n in range(1, ERLANG_A_MAX_STATES + 1):
        log_death = math.log(n) + math.log(mu) if n <= c else _logadd(math.log(capacity), math.log(n - c) + math.log(theta))
        log_weight = logs[-1] + log_lambda - log_death
        logs.append(log_weight)
        log_total = _logadd(log_total, log_weight)
        log_moment = _logadd(log_moment, log_weight + math.log(n))
        if n >= c:
            log_next_death = _logadd(math.log(capacity), math.log(n + 1 - c) + math.log(theta))
            log_ratio = log_lambda - log_next_death
            if log_ratio < 0:
                ratio = math.exp(log_ratio)
                gap = -math.expm1(log_ratio)
                tail_log = log_weight + log_ratio - math.log(gap)
                moment_tail_log = tail_log + math.log(n + 1 + ratio / gap)
                if (tail_log <= log_total + math.log(ERLANG_A_TOLERANCE)
                        and moment_tail_log <= log_moment + math.log(ERLANG_A_TOLERANCE)):
                    converged = True
                    break
    if not converged:
        return _result(error="Erlang-A did not converge within the state budget.", **metadata)
    peak = max(logs)
    weights = [math.exp(value - peak) for value in logs]
    total = math.fsum(weights)
    probabilities = [value / total for value in weights]
    if abs(math.fsum(probabilities) - 1.0) > ERLANG_A_TOLERANCE:
        return _result(error="Erlang-A probability normalization failed.", **metadata)
    busy = math.fsum(min(n, c) * probability for n, probability in enumerate(probabilities))
    lq = math.fsum(max(n - c, 0) * probability for n, probability in enumerate(probabilities))
    throughput = min(capacity, mu * busy)  # roundoff safeguard on the bounded expectation
    abandoned = theta * lq
    if throughput <= 0 or not math.isclose(throughput + abandoned, lambda_, rel_tol=1e-9, abs_tol=1e-12):
        return _result(error="Erlang-A flow conservation failed.", **metadata)
    length = lq + busy
    wait, sojourn = lq / throughput, length / throughput
    if not all(math.isfinite(v) and v >= 0 for v in (lq, length, wait, sojourn)):
        return _result(error="Erlang-A metrics exceed numerical range.", **metadata)
    return _result(rho=lambda_ / capacity, L=length, Lq=lq, W=sojourn, Wq=wait, stable=True,
                   lambda_eff=throughput, rho_effective=throughput / capacity,
                   abandonment_rate=abandoned / lambda_, **metadata)
