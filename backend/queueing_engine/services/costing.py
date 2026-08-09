"""
costing.py — Configurable cost calculation engine.

Computes operational cost breakdown for queueing segments:

  Server Cost     = c × cost_per_server_hr × hours_per_interval
  Waiting Cost    = Wq × λ × cost_per_wait_hr
  Abandonment Cost = λ × abandonment_rate × cost_per_abandonment
  Total Cost      = Server + Waiting + Abandonment

All cost parameters are user-configurable (defaults = QCU PHP rates).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from backend.queueing_engine.log import get_logger

logger = get_logger(__name__)

from backend.queueing_engine.config import (
    DEFAULT_ABANDONMENT_COST,
    DEFAULT_ABANDONMENT_RATE,
    DEFAULT_HOURS_PER_INTERVAL,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
    UNSTABLE_FIXED_COST,
)


def compute_segment_costs(
    servers: float,
    arrival_rate: float,
    wq: float,
    cost_per_server_hr: float = DEFAULT_SERVER_COST_HR,
    cost_per_wait_hr: float = DEFAULT_WAIT_COST_HR,
    cost_per_abandonment: float = DEFAULT_ABANDONMENT_COST,
    abandonment_rate: float = DEFAULT_ABANDONMENT_RATE,
    hours_per_interval: float = DEFAULT_HOURS_PER_INTERVAL,
) -> dict:
    """
    Compute cost breakdown for a single segment.

    Parameters
    ----------
    servers : float
        Number of servers (c).
    arrival_rate : float
        Customer arrival rate (λ).
    wq : float
        Mean waiting time in queue (hours).
    cost_per_server_hr : float
        Hourly cost per server.
    cost_per_wait_hr : float
        Hourly customer waiting cost.
    cost_per_abandonment : float
        Cost per abandoned customer.
    abandonment_rate : float
        Fraction of customers who abandon.
    hours_per_interval : float
        Duration of the time interval.

    Returns
    -------
    dict
        server_cost, wait_cost, abandonment_cost, total_cost
    """
    # Handle invalid / missing / NaN server or arrival inputs
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in [servers, arrival_rate]):
        return {
            "server_cost": None,
            "wait_cost": None,
            "abandonment_cost": None,
            "total_cost": None,
        }

    servers = int(servers) if not isinstance(servers, int) else servers

    server_cost = servers * cost_per_server_hr * hours_per_interval

    # Unstable system (Wq = inf / NaN / negative / missing) → fixed penalty,
    # matching the optimization engine (UNSTABLE_FIXED_COST) instead of 999999.
    if wq is None or (isinstance(wq, float) and math.isnan(wq)) or np.isinf(wq) or wq < 0:
        wait_cost = UNSTABLE_FIXED_COST
    else:
        wait_cost = wq * arrival_rate * cost_per_wait_hr

    # Abandonment applies to stable and unstable rows alike, matching
    # compute_all_costs and the optimization engine.
    abandonment_cost = arrival_rate * abandonment_rate * cost_per_abandonment

    total_cost = server_cost + wait_cost + abandonment_cost

    return {
        "server_cost": round(server_cost, 2),
        "wait_cost": round(wait_cost, 2),
        "abandonment_cost": round(abandonment_cost, 2),
        "total_cost": round(total_cost, 2),
    }

def compute_all_costs(
    df: pd.DataFrame,
    cost_per_server_hr: float = DEFAULT_SERVER_COST_HR,
    cost_per_wait_hr: float = DEFAULT_WAIT_COST_HR,
    cost_per_abandonment: float = DEFAULT_ABANDONMENT_COST,
    abandonment_rate: float = DEFAULT_ABANDONMENT_RATE,
    hours_per_interval: float = DEFAULT_HOURS_PER_INTERVAL,
) -> pd.DataFrame:
    """
    Compute cost columns for every row in a results DataFrame.

    Expects columns: c (servers), lambda (arrival_rate), Wq.
    Appends: server_cost, wait_cost, abandonment_cost, total_cost.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()

    # Resolve column aliases
    server_col = next(c for c in ["c", "servers", "c_optimal"] if c in result.columns)
    arrival_col = next(c for c in ["lambda", "arrival_rate"] if c in result.columns)
    wq_col = next(c for c in ["Wq", "Wq_current", "Wq_optimal"] if c in result.columns)

    servers = pd.to_numeric(result[server_col], errors="coerce")
    arrival_rate = pd.to_numeric(result[arrival_col], errors="coerce")
    wq = pd.to_numeric(result[wq_col], errors="coerce")

    # Valid rows have server and arrival inputs; Wq may be NaN for unstable rows
    valid = servers.notna() & arrival_rate.notna()

    # Initialize cost columns as NaN
    result["server_cost"] = np.nan
    result["wait_cost"] = np.nan
    result["abandonment_cost"] = np.nan
    result["total_cost"] = np.nan

    if valid.any():
        result.loc[valid, "server_cost"] = (servers[valid] * cost_per_server_hr * hours_per_interval).round(2)
        result.loc[valid, "abandonment_cost"] = (arrival_rate[valid] * abandonment_rate * cost_per_abandonment).round(2)

        wq_valid = wq[valid]
        stable_mask = wq_valid.notna() & ~np.isinf(wq_valid) & (wq_valid >= 0)
        wait_cost = pd.Series(UNSTABLE_FIXED_COST, index=wq_valid.index, dtype="float64")
        wait_cost[stable_mask] = wq_valid[stable_mask] * arrival_rate[valid][stable_mask] * cost_per_wait_hr
        result.loc[valid, "wait_cost"] = wait_cost.round(2)

        result.loc[valid, "total_cost"] = (
            result.loc[valid, "server_cost"]
            + result.loc[valid, "wait_cost"]
            + result.loc[valid, "abandonment_cost"]
        ).round(2)

    return result


def compute_cost_summary(
    df: pd.DataFrame,
    cost_per_server_hr: float = DEFAULT_SERVER_COST_HR,
    cost_per_wait_hr: float = DEFAULT_WAIT_COST_HR,
    cost_per_abandonment: float = DEFAULT_ABANDONMENT_COST,
    abandonment_rate: float = DEFAULT_ABANDONMENT_RATE,
    hours_per_interval: float = DEFAULT_HOURS_PER_INTERVAL,
) -> dict:
    """
    Compute aggregated cost KPIs across all segments.

    Returns
    -------
    dict
        total_server_cost, total_wait_cost, total_abandonment_cost,
        total_cost, avg_cost_per_segment
    """
    cost_df = compute_all_costs(
        df,
        cost_per_server_hr=cost_per_server_hr,
        cost_per_wait_hr=cost_per_wait_hr,
        cost_per_abandonment=cost_per_abandonment,
        abandonment_rate=abandonment_rate,
        hours_per_interval=hours_per_interval,
    )

    if cost_df.empty:
        return {
            "total_server_cost": 0.0,
            "total_wait_cost": 0.0,
            "total_abandonment_cost": 0.0,
            "total_cost": 0.0,
            "avg_cost_per_segment": 0.0,
        }

    total_server = cost_df["server_cost"].sum()
    total_wait = cost_df["wait_cost"].sum()
    total_abandon = cost_df["abandonment_cost"].sum()
    total = cost_df["total_cost"].sum()
    count = len(cost_df)

    return {
        "total_server_cost": round(total_server, 2),
        "total_wait_cost": round(total_wait, 2),
        "total_abandonment_cost": round(total_abandon, 2),
        "total_cost": round(total, 2),
        "avg_cost_per_segment": round(total / count, 2) if count else 0.0,
    }
