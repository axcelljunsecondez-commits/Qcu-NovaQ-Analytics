"""Optimization and comparison utilities for the queueing dashboard."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from numbers import Integral, Real

from backend.queueing_engine.config import (
    DEFAULT_MAX_SERVERS,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_TARGET_UTILIZATION,
    DEFAULT_WAIT_COST_HR,
    OT_RATE,
    REGULAR_RATE,
)
from backend.queueing_engine.log import get_logger
from backend.queueing_engine.services.model_selection import select_model

logger = get_logger(__name__)


def compute_blended_rate(regular_hours, ot_hours, total_hours) -> float:
    """Compute blended server cost rate: (reg_hrs*87 + OT_hrs*109) / total_hrs.

    Falls back to DEFAULT_SERVER_COST_HR when any value is missing or invalid.
    """
    try:
        reg = float(regular_hours)
        ot = float(ot_hours)
        tot = float(total_hours)
        if tot <= 0:
            return DEFAULT_SERVER_COST_HR
        return (reg * REGULAR_RATE + ot * OT_RATE) / tot
    except (TypeError, ValueError, ZeroDivisionError):
        return DEFAULT_SERVER_COST_HR


def _is_number(value) -> bool:
    """Return True when a value is a finite real number."""
    return isinstance(value, Real) and math.isfinite(float(value))


def _compute_waiting_cost(lambda_, wq_value, customer_waiting_cost=DEFAULT_WAIT_COST_HR):
    """Compute waiting cost only from a valid analytical waiting time.

    An unstable infinite-capacity baseline has no steady-state ``Wq``.  Its
    waiting cost must therefore remain unavailable rather than being replaced
    by a synthetic penalty that could be mistaken for measured cost or savings.
    """
    if not _is_number(lambda_) or not _is_number(wq_value):
        return None
    return float(lambda_) * float(wq_value) * customer_waiting_cost


def _compute_abandonment_cost(lambda_, abandonment_rate, cost_per_abandonment):
    """Compute abandonment cost. Returns 0 when either param is 0/None."""
    if not lambda_ or not abandonment_rate or not cost_per_abandonment:
        return 0.0
    return lambda_ * abandonment_rate * cost_per_abandonment


def _queue_metrics(lambda_, mu, c, variance=None, K=None, theta=None):
    """Evaluate a segment using the appropriate infinite or finite-capacity model.

    Dispatch is delegated to ``select_model`` so the model-selection chain
    cannot drift from ``process_segments`` and the API dispatch chain.
    """
    return select_model(lambda_, mu, c, variance=variance, K=K, theta=theta)["metrics"]


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
    default_server_cost: float = DEFAULT_SERVER_COST_HR,
    max_servers: int = DEFAULT_MAX_SERVERS,
    customer_waiting_cost: float = DEFAULT_WAIT_COST_HR,
    cost_per_abandonment: float = 0.0,
    abandonment_rate: float = 0.0,
    min_servers: int = 1,
    max_wait_minutes: float | None = None,
) -> dict:
    """Compare current and optimized configuration for one time segment.
    
    Uses LEAN COST OPTIMIZATION:
    - Minimizes total cost (server + waiting + optional abandonment)
    - Detects waste hours (if ρ ≤ 30%, tries to remove servers)
    - Enforces the requested utilization ceiling and server/capacity bounds
    """
    empty_result = {
        "feasibility_status": "INVALID_INPUT", "constraints_passed": False,
        "violated_constraints": ["input_validation"],
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

    if segment.get("queue_structure") == "separate_queues" or segment.get("model_id") == "parallel_mg1":
        empty_result["warning"] = (
            "Optimization is not supported for Parallel M/G/1 separate FIFO queues in Phase A."
        )
        empty_result["time"] = str(segment.get("time", "Unknown"))
        for key in ("lambda", "mu"):
            value = segment.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                empty_result[key] = value
        current_c = segment.get("c", 1)
        if isinstance(current_c, int) and not isinstance(current_c, bool) and 1 <= current_c <= 100000:
            empty_result["c_current"] = current_c
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
        lambda_ is None or not _is_number(lambda_) or lambda_ < 0
        or mu is None or not _is_number(mu) or mu <= 0
        or isinstance(current_c, bool) or not isinstance(current_c, Integral)
        or int(current_c) <= 0
        or not _is_number(target_utilization)
        or not 0 < float(target_utilization) <= 1
        or cost_per_server is None
        or not isinstance(max_servers, Integral)
        or not 1 <= int(max_servers) <= 256
        or isinstance(min_servers, bool) or not isinstance(min_servers, Integral)
        or not 1 <= min_servers <= max_servers
        or (max_wait_minutes is not None and (not _is_number(max_wait_minutes) or max_wait_minutes < 0))
        or not _is_number(customer_waiting_cost) or customer_waiting_cost < 0
        or not _is_number(abandonment_rate) or not 0 <= abandonment_rate <= 1
        or not _is_number(cost_per_abandonment) or cost_per_abandonment < 0
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
    current_total_cost = (
        current_server_cost + current_waiting_cost + current_abandonment_cost
        if current_waiting_cost is not None else None
    )
    current_rho = current_metrics.get("rho")

    rejected: set[str] = set()

    def _eval_cost(c):
        m = _queue_metrics(lambda_, mu, c, variance, capacity, theta)
        reasons = []
        if not m.get("stable"):
            reasons.append("model_stability")
        if not _is_number(m.get("rho")) or m["rho"] > target_utilization + 1e-12:
            reasons.append("target_utilization")
        if not _is_number(m.get("Wq")) or not _is_number(m.get("Lq")):
            reasons.append("analytical_metrics")
        if max_wait_minutes is not None and (not _is_number(m.get("Wq")) or m["Wq"] * 60 > max_wait_minutes + 1e-12):
            reasons.append("max_wait_minutes")
        if reasons:
            rejected.update(reasons)
            return float("inf")
        sc = c * cost_per_server
        wc = _compute_waiting_cost(lambda_, m.get("Wq"), customer_waiting_cost)
        ac = _compute_abandonment_cost(lambda_, abandonment_rate, cost_per_abandonment)
        if wc is None:
            rejected.add("analytical_metrics")
            return float("inf")
        return sc + wc + ac

    selection = select_model(lambda_, mu, current_c, variance, capacity, theta)
    upper_bound = max_servers
    if selection["name"] in ("M/M/c/K", "M/G/c/K") and _is_number(capacity):
        upper_bound = min(upper_bound, int(capacity))
    candidates = [(c, _eval_cost(c)) for c in range(min_servers, upper_bound + 1)]
    if upper_bound < min_servers:
        rejected.add("server_capacity_bounds")
    feasible = [(c, cost) for c, cost in candidates if math.isfinite(cost)]
    optimal_c = min(feasible, key=lambda item: (item[1], item[0]))[0] if feasible else None

    def _build_result(c_val, sv_cost, w_cost, a_cost, rec_override=None):
        output_selection = select_model(lambda_, mu, c_val if c_val is not None else current_c, variance, capacity, theta)
        opt_metrics = output_selection["metrics"] if c_val is not None else {}
        return {
            "feasibility_status": "FEASIBLE" if c_val is not None else "NO_FEASIBLE_CONFIGURATION",
            "constraints_passed": c_val is not None,
            "violated_constraints": [] if c_val is not None else sorted(rejected),
            "selected_model": output_selection["name"],
            "model_selection_reason": output_selection["selection_reason"],
            "model_assumptions": output_selection["assumptions"],
            "service_cv": output_selection["service_cv"],
            "metric_provenance": "analytical",
            "effective_constraints": {"min_servers": min_servers, "max_servers": max_servers, "max_wait_minutes": max_wait_minutes, "target_utilization": target_utilization, "K": capacity},
            "effective_costs": {"server_cost_per_hr": cost_per_server, "customer_waiting_cost": customer_waiting_cost, "cost_per_abandonment": cost_per_abandonment, "abandonment_rate": abandonment_rate, "basis": "configured assumption"},
            "explanation": (f"{c_val} servers minimize configured cost among candidates satisfying all enabled constraints; ties choose fewer servers." if c_val is not None else "No candidate satisfies all enabled constraints. Rejected constraints: " + ", ".join(sorted(rejected))),
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
            "cost_optimal": None if c_val is None else (sv_cost + w_cost + a_cost),
            "waiting_cost_optimal": w_cost,
            "abandonment_cost_optimal": a_cost,
            "delta_c": None if c_val is None else c_val - current_c,
            "delta_rho": None if c_val is None else _safe_diff(opt_metrics.get("rho"), current_rho),
            "delta_Wq": None if c_val is None else _safe_diff(opt_metrics.get("Wq"), current_metrics.get("Wq")),
            "delta_Lq": None if c_val is None else _safe_diff(opt_metrics.get("Lq"), current_metrics.get("Lq")),
            "delta_cost": (
                None if c_val is None or current_total_cost is None
                else (sv_cost + w_cost + a_cost) - current_total_cost
            ),
            "current_stable": bool(current_metrics.get("stable")),
            "optimized_stable": bool(c_val is not None and opt_metrics.get("stable")),
            "recommendation": rec_override or ("Unable to find a stable staffing plan." if c_val is None else _format_recommendation(time_label, current_c, c_val)),
            "warning": ("No feasible staffing plan satisfies the utilization and server/capacity bounds."
                        if c_val is None else current_metrics.get("error") or ""),
        }

    if optimal_c is None:
        return _build_result(None, None, None, None)

    candidate_metrics = _queue_metrics(lambda_, mu, optimal_c, variance, capacity, theta)
    optimal_wq = candidate_metrics.get("Wq")
    optimal_server_cost = optimal_c * cost_per_server
    optimal_waiting_cost = _compute_waiting_cost(lambda_, optimal_wq, customer_waiting_cost)
    optimal_abandonment_cost = _compute_abandonment_cost(lambda_, abandonment_rate, cost_per_abandonment)

    return _build_result(optimal_c, optimal_server_cost, optimal_waiting_cost, optimal_abandonment_cost)


def optimize_segments(
    time_segments: Iterable[Mapping],
    target_utilization: float = DEFAULT_TARGET_UTILIZATION,
    default_server_cost: float = DEFAULT_SERVER_COST_HR,
    max_servers: int = DEFAULT_MAX_SERVERS,
    customer_waiting_cost: float = DEFAULT_WAIT_COST_HR,
    cost_per_abandonment: float = 0.0,
    abandonment_rate: float = 0.0,
    min_servers: int = 1,
    max_wait_minutes: float | None = None,
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
            min_servers=min_servers, max_wait_minutes=max_wait_minutes,
        )
        for segment in time_segments
    ]


def comparable_result(row: Mapping) -> bool:
    """A financial comparison requires real, feasible results on both sides."""
    return (
        row.get("current_stable") is True and row.get("optimized_stable") is True
        and isinstance(row.get("c_optimal"), Integral) and row["c_optimal"] > 0
        and all(_is_number(row.get(key)) and row[key] >= 0 for key in ("cost_current", "cost_optimal"))
    )


def summarize_optimization(comparison_rows: list[dict]) -> dict:
    """Never extrapolate partial or infeasible rows into complete-plan savings."""
    matched = [row for row in comparison_rows if comparable_result(row)]
    complete = bool(comparison_rows) and len(matched) == len(comparison_rows)

    def total(key, available=True):
        values = [row.get(key) for row in comparison_rows]
        if not available or any(not _is_number(v) for v in values):
            return None
        return sum(values)

    def mean_pair(current, optimal):
        pairs = [(row.get(current), row.get(optimal)) for row in matched]
        if not complete or any(not _is_number(v) for pair in pairs for v in pair):
            return None, None
        return (sum(pair[0] for pair in pairs) / len(pairs), sum(pair[1] for pair in pairs) / len(pairs))

    current_cost = total("cost_current")
    optimal_cost = total("cost_optimal", complete)
    rho_current, rho_optimal = mean_pair("rho_current", "rho_optimal")
    wait_current, wait_optimal = mean_pair("Wq_current", "Wq_optimal")
    return {
        "comparison_complete": complete,
        "comparable_segment_count": len(matched),
        "segment_count": len(comparison_rows),
        "total_current_cost": current_cost,
        "total_optimized_cost": optimal_cost,
        "total_savings": current_cost - optimal_cost if complete else None,
        "total_waiting_cost_current": total("waiting_cost_current"),
        "total_waiting_cost_optimal": total("waiting_cost_optimal", complete),
        "total_abandonment_cost_current": total("abandonment_cost_current"),
        "total_abandonment_cost_optimal": total("abandonment_cost_optimal", complete),
        "avg_utilization_current": rho_current,
        "avg_utilization_optimized": rho_optimal,
        "avg_utilization_improvement": rho_current - rho_optimal if rho_current is not None else None,
        "total_server_change": total("delta_c", complete),
        "avg_waiting_current": wait_current,
        "avg_waiting_optimized": wait_optimal,
        "waiting_time_improvement_pct": (wait_current - wait_optimal) / wait_current * 100
            if wait_current not in (None, 0) and wait_optimal is not None else None,
    }


def build_recommendations(comparison_rows: list[dict]) -> list[str]:
    """Generate recommendation messages from optimized segment rows."""
    summary = summarize_optimization(comparison_rows)

    segment_actions = [
        row["recommendation"]
        for row in comparison_rows
        if row.get("recommendation") and row.get("delta_c") not in (None, 0)
    ]

    if not summary["comparison_complete"]:
        return ["Comparison incomplete: no aggregate savings or staffing assurance is available."]

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




