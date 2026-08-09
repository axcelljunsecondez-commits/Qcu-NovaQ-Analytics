"""Optimization and comparison utilities for the queueing dashboard."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from numbers import Integral, Real

from backend.queueing_engine.log import get_logger

logger = get_logger(__name__)

from backend.queueing_engine.config import (
    DEFAULT_CUSTOMER_WAITING_COST,
    DEFAULT_MAX_SERVERS,
    DEFAULT_SERVER_COST,
    DEFAULT_TARGET_UTILIZATION,
    OT_RATE,
    REGULAR_RATE,
    UNSTABLE_FIXED_COST,
)
from backend.queueing_engine.models import erlang_a, mgc, mgck, mm1, mmc, mmck


def compute_blended_rate(regular_hours, ot_hours, total_hours) -> float:
    """Compute blended server cost rate: (reg_hrs*87 + OT_hrs*109) / total_hrs.

    Falls back to DEFAULT_SERVER_COST when any value is missing or invalid.
    """
    try:
        reg = float(regular_hours)
        ot = float(ot_hours)
        tot = float(total_hours)
        if tot <= 0:
            return DEFAULT_SERVER_COST
        return (reg * REGULAR_RATE + ot * OT_RATE) / tot
    except (TypeError, ValueError, ZeroDivisionError):
        return DEFAULT_SERVER_COST


def _is_number(value) -> bool:
    """Return True when a value is a finite real number."""
    return isinstance(value, Real) and math.isfinite(float(value))


def _compute_waiting_cost(lambda_, wq_value, customer_waiting_cost=DEFAULT_CUSTOMER_WAITING_COST):
    """Compute actual waiting cost from Wq, or return fixed cost for unstable systems.
    
    - If Wq is available: cost = λ * Wq * customer_waiting_cost
    - If Wq is None (unstable): cost = UNSTABLE_FIXED_COST (fixed value, not infinite)
    - For unstable systems (ρ ≥ 1), a fixed cost is assigned instead of penalties.
    """
    if lambda_ is None:
        return None

    if wq_value is not None:
        return lambda_ * wq_value * customer_waiting_cost
    else:
        return UNSTABLE_FIXED_COST


def _compute_abandonment_cost(lambda_, abandonment_rate, cost_per_abandonment):
    """Compute abandonment cost. Returns 0 when either param is 0/None."""
    if not lambda_ or not abandonment_rate or not cost_per_abandonment:
        return 0.0
    return lambda_ * abandonment_rate * cost_per_abandonment


def _queue_metrics(lambda_, mu, c, variance=None, K=None, theta=None):
    """Evaluate a segment using the appropriate infinite or finite-capacity model."""
    if _is_number(K) and _is_number(variance):
        return mgck(lambda_, mu, c, variance, int(K))
    if _is_number(K):
        return mmck(lambda_, mu, c, int(K))
    if _is_number(variance):
        return mgc(lambda_, mu, c, variance)
    if _is_number(theta):
        return erlang_a(lambda_, mu, c, theta)
    if c == 1:
        return mm1(lambda_, mu)
    return mmc(lambda_, mu, c)


def _safe_diff(new_value, old_value):
    """Return a difference only when both operands are present."""
    if new_value is None or old_value is None:
        return None
    return new_value - old_value


def _segment_server_cost(segment, default_server_cost):
    """Resolve server cost using blended rate formula when labor hours are provided.

    If the segment contains regular_hours, ot_hours, and total_hours, the cost
    is computed as:
        (regular_hours * 87 + ot_hours * 109) / total_hours

    Otherwise falls back to the segment's explicit server_cost or the default.
    """
    reg = segment.get("regular_hours")
    ot = segment.get("ot_hours")
    tot = segment.get("total_hours")

    if reg is not None and ot is not None and tot is not None:
        return compute_blended_rate(reg, ot, tot)

    # Legacy fallback: explicit server_cost or default
    segment_cost = segment.get("server_cost", default_server_cost)
    if not _is_number(segment_cost) or float(segment_cost) < 0:
        return None
    return float(segment_cost)


def _ternary_search_c(eval_fn, lo, hi):
    """
    Ternary search for the integer c ∈ [*lo*, *hi*] that minimises *eval_fn*(c).

    *eval_fn*(c) must return a finite ``float`` for stable server counts and
    ``float('inf')`` for unstable ones.  The function is assumed unimodal
    (convex) in *c*.

    Parameters
    ----------
    eval_fn : Callable[[int], float]
        Total cost as a function of server count.
    lo, hi : int
        Inclusive search bounds (``lo <= hi``).

    Returns
    -------
    int or None
        The integer *c* with minimum *eval_fn*(c), or ``None`` if all
        candidates are unstable (eval returns inf).
    """
    if lo > hi:
        return None

    # No feasible (stable) candidate in range
    if eval_fn(hi) == float("inf"):
        return None

    # Binary search the leftmost feasible c. Stability is monotone in c, so
    # the feasible set is the suffix [first_feasible, hi].
    left, right = lo, hi
    while left < right:
        mid = (left + right) // 2
        if eval_fn(mid) == float("inf"):
            left = mid + 1
        else:
            right = mid
    lo = left

    # Shrink by thirds until the window is tiny
    while hi - lo > 2:
        m1 = lo + (hi - lo) // 3
        m2 = hi - (hi - lo) // 3

        f1 = eval_fn(m1)
        f2 = eval_fn(m2)

        if f1 < f2:
            hi = m2
        else:
            lo = m1

    # Brute-force the remaining window
    best_c = None
    best_val = float("inf")

    for c in range(lo, hi + 1):
        val = eval_fn(c)
        if val < best_val:
            best_val = val
            best_c = c

    return best_c if best_val != float("inf") else None


def _format_recommendation(time_label, current_c, optimal_c):
    """Build a staffing recommendation message."""
    if current_c is None or optimal_c is None:
        return f"Unable to determine server action at {time_label}."

    if optimal_c > current_c:
        change = optimal_c - current_c
        label = "server" if change == 1 else "servers"
        return f"Add {change} {label} at {time_label}."

    if optimal_c < current_c:
        change = current_c - optimal_c
        label = "server" if change == 1 else "servers"
        return f"Remove {change} {label} at {time_label}."

    return f"Maintain current staffing at {time_label}."


def optimize_segment(
    segment: Mapping,
    target_utilization: float = DEFAULT_TARGET_UTILIZATION,
    default_server_cost: float = DEFAULT_SERVER_COST,
    max_servers: int = DEFAULT_MAX_SERVERS,
    customer_waiting_cost: float = DEFAULT_CUSTOMER_WAITING_COST,
    cost_per_abandonment: float = 0.0,
    abandonment_rate: float = 0.0,
) -> dict:
    """Compare current and optimized configuration for one time segment.
    
    Uses LEAN COST OPTIMIZATION:
    - Minimizes total cost (server + waiting + optional abandonment)
    - Detects waste hours (if ρ ≤ 30%, tries to remove servers)
    - Ensures ρ stays ≤ 70% for stability
    """
    empty_result = {
        "time": "Unknown",
        "lambda": None,
        "mu": None,
        "cost_per_server": None,
        "c_current": None,
        "rho_current": None,
        "Wq_current": None,
        "Lq_current": None,
        "cost_current": None,
        "waiting_cost_current": None,
        "abandonment_cost_current": None,
        "c_optimal": None,
        "rho_optimal": None,
        "Wq_optimal": None,
        "Lq_optimal": None,
        "cost_optimal": None,
        "waiting_cost_optimal": None,
        "abandonment_cost_optimal": None,
        "delta_c": None,
        "delta_rho": None,
        "delta_Wq": None,
        "delta_Lq": None,
        "delta_cost": None,
        "current_stable": False,
        "optimized_stable": False,
        "recommendation": "Unable to optimize invalid segment input.",
        "warning": "Invalid segment format: each segment must be a dictionary.",
    }

    if not isinstance(segment, Mapping):
        return empty_result

    time_label = str(segment.get("time", "Unknown"))
    lambda_ = segment.get("lambda")
    mu = segment.get("mu")
    current_c = segment.get("c", 1)
    variance = segment.get("variance")
    capacity = segment.get("K")
    theta = segment.get("theta")
    cost_per_server = _segment_server_cost(segment, default_server_cost)
    abandonment_rate = float(abandonment_rate or 0.0)
    cost_per_abandonment = float(cost_per_abandonment or 0.0)

    if (
        not isinstance(current_c, Integral)
        or int(current_c) <= 0
        or not _is_number(target_utilization)
        or not 0 < float(target_utilization) < 1
        or cost_per_server is None
        or not isinstance(max_servers, Integral)
        or int(max_servers) <= 0
    ):
        invalid_result = empty_result.copy()
        invalid_result.update(
            {
                "time": time_label,
                "lambda": lambda_,
                "mu": mu,
                "cost_per_server": cost_per_server,
                "c_current": current_c,
                "recommendation": f"Unable to optimize {time_label}.",
                "warning": "Invalid optimization settings, segment cost, or server count.",
            }
        )
        return invalid_result

    current_c = int(current_c)
    target_utilization = float(target_utilization)
    max_servers = int(max_servers)

    current_metrics = _queue_metrics(lambda_, mu, current_c, variance, capacity, theta)
    current_server_cost = current_c * cost_per_server
    current_waiting_cost = _compute_waiting_cost(lambda_, current_metrics.get("Wq"), customer_waiting_cost)
    current_abandonment_cost = _compute_abandonment_cost(lambda_, abandonment_rate, cost_per_abandonment)
    current_total_cost = current_server_cost + (current_waiting_cost if current_waiting_cost is not None else 0) + current_abandonment_cost
    current_rho = current_metrics.get("rho")

    def _eval_cost(c):
        m = _queue_metrics(lambda_, mu, c, variance, capacity, theta)
        if not m.get("stable"):
            return float("inf")
        sc = c * cost_per_server
        wc = _compute_waiting_cost(lambda_, m.get("Wq"), customer_waiting_cost)
        ac = _compute_abandonment_cost(lambda_, abandonment_rate, cost_per_abandonment)
        return sc + (wc if wc is not None else 0) + ac

    optimal_c = _ternary_search_c(_eval_cost, 1, max_servers)

    # Guard sweep: re-evaluate c-1, c, c+1 to protect against non-convexity near the stability boundary
    if optimal_c is not None:
        neighbours = [c for c in (optimal_c - 1, optimal_c, optimal_c + 1) if 1 <= c <= max_servers]
        best_c, best_total = min(((c, _eval_cost(c)) for c in neighbours), key=lambda x: x[1])
        optimal_c = best_c

    def _build_result(c_val, sv_cost, w_cost, a_cost, rec_override=None):
        opt_metrics = _queue_metrics(lambda_, mu, c_val, variance, capacity, theta) if c_val is not None else {}
        return {
            "time": time_label,
            "lambda": lambda_,
            "mu": mu,
            "cost_per_server": cost_per_server,
            "c_current": current_c,
            "rho_current": current_rho,
            "Wq_current": current_metrics.get("Wq"),
            "Lq_current": current_metrics.get("Lq"),
            "cost_current": current_total_cost,
            "waiting_cost_current": current_waiting_cost,
            "abandonment_cost_current": current_abandonment_cost,
            "c_optimal": c_val,
            "rho_optimal": opt_metrics.get("rho"),
            "Wq_optimal": opt_metrics.get("Wq"),
            "Lq_optimal": opt_metrics.get("Lq"),
            "cost_optimal": None if c_val is None else (sv_cost + (w_cost if w_cost is not None else 0) + a_cost),
            "waiting_cost_optimal": w_cost,
            "abandonment_cost_optimal": a_cost,
            "delta_c": None if c_val is None else c_val - current_c,
            "delta_rho": None if c_val is None else _safe_diff(opt_metrics.get("rho"), current_rho),
            "delta_Wq": None if c_val is None else _safe_diff(opt_metrics.get("Wq"), current_metrics.get("Wq")),
            "delta_Lq": None if c_val is None else _safe_diff(opt_metrics.get("Lq"), current_metrics.get("Lq")),
            "delta_cost": None if c_val is None else (sv_cost + (w_cost if w_cost is not None else 0) + a_cost) - current_total_cost,
            "current_stable": bool(current_metrics.get("stable")),
            "optimized_stable": c_val is not None,
            "recommendation": rec_override or ("Unable to find a stable staffing plan." if c_val is None else _format_recommendation(time_label, current_c, c_val)),
            "warning": current_metrics.get("error") or "",
        }

    if optimal_c is None:
        return _build_result(None, None, None, None)

    candidate_metrics = _queue_metrics(lambda_, mu, optimal_c, variance, capacity, theta)
    optimal_wq = candidate_metrics.get("Wq")
    optimal_server_cost = optimal_c * cost_per_server
    optimal_waiting_cost = _compute_waiting_cost(lambda_, optimal_wq, customer_waiting_cost)
    optimal_abandonment_cost = _compute_abandonment_cost(lambda_, abandonment_rate, cost_per_abandonment)

    final_optimal_c = optimal_c
    final_optimal_server_cost = optimal_server_cost
    final_optimal_waiting_cost = optimal_waiting_cost
    final_optimal_abandonment_cost = optimal_abandonment_cost

    waste_recommendation = None

    # Check WASTE HOURS condition: if current ρ ≤ 30% and current_c > 1, try removing a server
    if current_rho is not None and current_rho <= 0.30 and current_c > 1:
        reduced_c = current_c - 1
        reduced_metrics = _queue_metrics(lambda_, mu, reduced_c, variance, capacity, theta)
        reduced_rho = reduced_metrics.get("rho")

        if reduced_rho is not None and reduced_rho <= 0.70 and reduced_metrics.get("stable", False):
            reduced_wq = reduced_metrics.get("Wq")
            reduced_server_cost = reduced_c * cost_per_server
            reduced_waiting_cost = _compute_waiting_cost(lambda_, reduced_wq, customer_waiting_cost)
            reduced_abandonment_cost = _compute_abandonment_cost(lambda_, abandonment_rate, cost_per_abandonment)
            savings = current_total_cost - (reduced_server_cost + (reduced_waiting_cost if reduced_waiting_cost is not None else 0) + reduced_abandonment_cost)

            if savings > 0:
                change = current_c - reduced_c
                label = "server" if change == 1 else "servers"
                waste_recommendation = (
                    f"Remove {change} {label} at {time_label} (waste hours: p={current_rho:.3f} <= 30%). "
                    f"ρ becomes {reduced_rho:.3f} (stable) and save ₱{savings:,.2f} in total cost."
                )
                final_optimal_c = reduced_c
                final_optimal_server_cost = reduced_server_cost
                final_optimal_waiting_cost = reduced_waiting_cost
                final_optimal_abandonment_cost = reduced_abandonment_cost

    return _build_result(
        final_optimal_c,
        final_optimal_server_cost,
        final_optimal_waiting_cost,
        final_optimal_abandonment_cost,
        rec_override=waste_recommendation,
    )


def optimize_segments(
    time_segments: Iterable[Mapping],
    target_utilization: float = DEFAULT_TARGET_UTILIZATION,
    default_server_cost: float = DEFAULT_SERVER_COST,
    max_servers: int = DEFAULT_MAX_SERVERS,
    customer_waiting_cost: float = DEFAULT_CUSTOMER_WAITING_COST,
    cost_per_abandonment: float = 0.0,
    abandonment_rate: float = 0.0,
) -> list[dict]:
    """Optimize a sequence of time segments."""
    if time_segments is None:
        return []

    return [
        optimize_segment(
            segment=segment,
            target_utilization=target_utilization,
            default_server_cost=default_server_cost,
            max_servers=max_servers,
            customer_waiting_cost=customer_waiting_cost,
            cost_per_abandonment=cost_per_abandonment,
            abandonment_rate=abandonment_rate,
        )
        for segment in time_segments
    ]


def summarize_optimization(comparison_rows: list[dict]) -> dict:
    """Compute top-level comparison KPIs from optimized segment rows."""
    if not comparison_rows:
        return {
            "total_current_cost": 0.0,
            "total_optimized_cost": 0.0,
            "total_savings": 0.0,
            "avg_utilization_current": None,
            "avg_utilization_optimized": None,
            "avg_utilization_improvement": None,
            "total_server_change": 0,
            "avg_waiting_current": None,
            "avg_waiting_optimized": None,
            "waiting_time_improvement_pct": None,
        }

    current_cost = sum(
        row["cost_current"] for row in comparison_rows if row["cost_current"] is not None
    )
    optimized_cost = sum(
        row["cost_optimal"] for row in comparison_rows if row["cost_optimal"] is not None
    )
    total_waiting_cost_current = sum(
        row["waiting_cost_current"] for row in comparison_rows if row.get("waiting_cost_current") is not None
    )
    total_waiting_cost_optimal = sum(
        row["waiting_cost_optimal"] for row in comparison_rows if row.get("waiting_cost_optimal") is not None
    )
    total_abandonment_cost_current = sum(
        row.get("abandonment_cost_current", 0) for row in comparison_rows if row.get("abandonment_cost_current") is not None
    )
    total_abandonment_cost_optimal = sum(
        row.get("abandonment_cost_optimal", 0) for row in comparison_rows if row.get("abandonment_cost_optimal") is not None
    )

    utilization_pairs = [
        (row["rho_current"], row["rho_optimal"])
        for row in comparison_rows
        if row["rho_current"] is not None and row["rho_optimal"] is not None
    ]
    waiting_pairs = [
        (row["Wq_current"], row["Wq_optimal"])
        for row in comparison_rows
        if row["Wq_current"] is not None and row["Wq_optimal"] is not None
    ]

    avg_util_current = (
        sum(pair[0] for pair in utilization_pairs) / len(utilization_pairs)
        if utilization_pairs
        else None
    )
    avg_util_optimized = (
        sum(pair[1] for pair in utilization_pairs) / len(utilization_pairs)
        if utilization_pairs
        else None
    )
    avg_wait_current = (
        sum(pair[0] for pair in waiting_pairs) / len(waiting_pairs)
        if waiting_pairs
        else None
    )
    avg_wait_optimized = (
        sum(pair[1] for pair in waiting_pairs) / len(waiting_pairs)
        if waiting_pairs
        else None
    )

    waiting_improvement_pct = None
    if avg_wait_current not in (None, 0) and avg_wait_optimized is not None:
        waiting_improvement_pct = (
            (avg_wait_current - avg_wait_optimized) / avg_wait_current
        ) * 100.0

    return {
        "total_current_cost": current_cost,
        "total_optimized_cost": optimized_cost,
        "total_savings": current_cost - optimized_cost,
        "total_waiting_cost_current": total_waiting_cost_current,
        "total_waiting_cost_optimal": total_waiting_cost_optimal,
        "total_abandonment_cost_current": total_abandonment_cost_current,
        "total_abandonment_cost_optimal": total_abandonment_cost_optimal,
        "avg_utilization_current": avg_util_current,
        "avg_utilization_optimized": avg_util_optimized,
        "avg_utilization_improvement": (
            avg_util_current - avg_util_optimized
            if avg_util_current is not None and avg_util_optimized is not None
            else None
        ),
        "total_server_change": sum(
            row["delta_c"] for row in comparison_rows if row["delta_c"] is not None
        ),
        "avg_waiting_current": avg_wait_current,
        "avg_waiting_optimized": avg_wait_optimized,
        "waiting_time_improvement_pct": waiting_improvement_pct,
    }


def build_recommendations(comparison_rows: list[dict]) -> list[str]:
    """Generate recommendation messages from optimized segment rows."""
    summary = summarize_optimization(comparison_rows)

    segment_actions = [
        row["recommendation"]
        for row in comparison_rows
        if row.get("recommendation") and row.get("delta_c") not in (None, 0)
    ]

    if not segment_actions:
        segment_actions = [
            "No staffing changes are required to satisfy the utilization target."
        ]

    messages = list(segment_actions)

    savings = summary["total_savings"]
    if savings is not None:
        if savings >= 0:
            messages.append(f"Estimated total daily savings: ₱{savings:,.2f}.")
        else:
            messages.append(
                f"Estimated additional daily cost: ₱{abs(savings):,.2f}."
            )

    if summary["waiting_time_improvement_pct"] is not None:
        messages.append(
            f"Average waiting time improvement: {summary['waiting_time_improvement_pct']:.1f}%."
        )

    return messages




