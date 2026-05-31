"""Core M/M/1, M/M/c, M/G/c, M/M/c/K, and M/G/c/K queueing formulas."""

from __future__ import annotations

import math
from typing import Any
from numbers import Integral, Real

from log import get_logger

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

def erlang_a(lambda_: float, mu: float, c: int, theta: float) -> dict[str, Any]:
    """
    Compute steady-state metrics for an M/M/c+M queue (Erlang-A).

    Customers arriving when all servers are busy enter a FIFO queue and may
    *renege* (abandon) after an exponentially distributed patience time with
    rate *θ* (*M* = Memoryless abandonment).

    The state probabilities follow the Garnett *et al.* (2002) recursion:

      P(n) / P(0) = (λ/μ)ⁿ / n!                          n ≤ c

      P(c+k) / P(0) = P(c) / P(0)  ·  λᵏ / ∏_{j=1}ᵏ (cμ + jθ)   k ≥ 1

    Parameters
    ----------
    lambda_ : float
        Arrival rate (customers / time).
    mu : float
        Service rate per server (customers / time).
    c : int
        Number of servers.
    theta : float
        Reneging (abandonment) rate per customer in queue (1 / patience).

    Returns
    -------
    dict
        {rho, L, Lq, W, Wq, stable, error,
         theta, lambda_eff, abandonment_rate}

    References
    ----------
    Garnett, O., Mandelbaum, A., & Reiman, M. (2002).
    Designing a Call Center with Impatient Customers.
    *Manufacturing & Service Operations Management*, 4(3), 208–227.
    """
    if not _is_valid_rate(lambda_) or not _is_valid_rate(mu):
        return _result(error="Invalid input: lambda and mu must be finite numbers.")
    if not _is_valid_rate(theta):
        return _result(error="Invalid input: theta must be a finite number.")

    lambda_ = float(lambda_)
    mu = float(mu)
    c = int(c)
    theta = float(theta)

    if lambda_ <= 0 or mu <= 0 or c < 1 or theta < 0:
        return _result(
            error=(
                "Invalid input: lambda > 0, mu > 0, c >= 1, "
                "and theta >= 0 are required."
            )
        )

    # θ = 0  →  degenerate to M/M/c (no abandonment)
    if theta == 0.0:
        return mmc(lambda_, mu, c)

    offered_load = lambda_ / mu
    # ── 1.  Compute log-ratios  log(P(n)/P(0))  ──────────────────────────────
    log_ratios: list[float] = [0.0]            # n = 0
    running_max = 0.0
    # n ≤ c
    for n in range(1, c + 1):
        lr = log_ratios[-1] + math.log(lambda_) - math.log(n) - math.log(mu)
        log_ratios.append(lr)
        if lr > running_max:
            running_max = lr
    # n > c
    small_count = 0
    min_tail_terms = max(5, c // 10)
    for k in range(1, 201):                    # hard cap at c + 200
        n = c + k
        lr = log_ratios[-1] + math.log(lambda_) - math.log(c * mu + k * theta)
        log_ratios.append(lr)
        if lr > running_max:
            running_max = lr
        # Stop once the tail is negligible (≤ 1e-16 relative to peak)
        if running_max - lr > 37 and k >= min_tail_terms:
            small_count += 1
            if small_count >= 3:
                break
        else:
            small_count = 0

    N = len(log_ratios) - 1                    # highest index computed

    # ── 2.  Normalise via log-sum-exp trick  ─────────────────────────────────
    weights = [math.exp(lr - running_max) for lr in log_ratios]
    total_weight = sum(weights)
    P = [w / total_weight for w in weights]    # P[0] … P[N]

    # ── 3.  Metrics  ─────────────────────────────────────────────────────────
    # Lq = Σ (n - c) · P(n)   for n > c
    Lq = sum((n - c) * P[n] for n in range(c + 1, N + 1))

    # idle_servers = Σ_{n < c} (c - n) · P(n)
    idle_servers = sum((c - n) * P[n] for n in range(c))
    L = Lq + c - idle_servers

    # Effective arrival rate (throughput):
    #   λ_eff = λ - Σ_{n > c} (n - c) · θ · P(n)
    abandon_customers = sum((n - c) * theta * P[n] for n in range(c + 1, N + 1))
    lambda_eff = lambda_ - abandon_customers

    if lambda_eff <= 0:
        return _result(
            stable=False,
            error="Effective arrival rate is zero or negative — "
                  "all customers abandon.",
        )

    W = L / lambda_eff
    Wq = Lq / lambda_eff
    rho = offered_load / c                     # nominal utilisation
    p_abandon = abandon_customers / lambda_ if lambda_ > 0 else 0.0

    return _result(
        rho=rho,
        L=L,
        Lq=Lq,
        W=W,
        Wq=Wq,
        stable=True,
        theta=theta,
        lambda_eff=lambda_eff,
        abandonment_rate=p_abandon,
    )
