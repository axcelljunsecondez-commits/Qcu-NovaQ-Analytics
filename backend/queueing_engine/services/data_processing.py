"""Data preparation helpers for the queueing dashboard."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from backend.queueing_engine.log import get_logger

logger = get_logger(__name__)

from backend.queueing_engine.config import DEFAULT_CUSTOMER_WAITING_COST, UNSTABLE_PENALTY_MULTIPLIER
from backend.queueing_engine.services.model_selection import select_model

CURRENT_COLUMNS = [
    "time",
    "lambda",
    "mu",
    "c",
    "model",
    "theta",
    "rho",
    "L",
    "Lq",
    "W",
    "Wq",
    "lambda_eff",
    "abandonment_rate",
    "stable",
    "status",
    "warning",
]

def _empty_frame(columns: list[str]) -> pd.DataFrame:
    """Return an empty DataFrame with the requested columns."""
    return pd.DataFrame(columns=columns)


def _classify_utilization_status(rho) -> str:
    """Classify queue utilization status based on rho value.
    
    Categories:
    - Lean: ρ < 60%
    - Normal: 60% ≤ ρ ≤ 79%
    - Peak: 80% < ρ ≤ 89%
    - Critical: ρ > 90%
    - Unstable: ρ > 1 (system unstable)
    """
    if rho is None:
        return "—"
    if rho > 1.0:
        return "Unstable"
    if rho >= 0.90:
        return "Critical"
    if rho > 0.80:
        return "Peak"
    if rho >= 0.60:
        return "Normal"
    return "Lean"


def _current_row(time_label, lambda_, mu, c, model_name, metrics, theta=None) -> dict:
    """Build one normalized current-system result row."""
    stable = bool(metrics.get("stable"))
    rho = metrics.get("rho")
    status = _classify_utilization_status(rho)

    return {
        "time": str(time_label),
        "lambda": lambda_,
        "mu": mu,
        "c": c,
        "model": model_name,
        "theta": theta,
        "rho": rho,
        "L": metrics.get("L"),
        "Lq": metrics.get("Lq"),
        "W": metrics.get("W"),
        "Wq": metrics.get("Wq"),
        "lambda_eff": metrics.get("lambda_eff"),
        "abandonment_rate": metrics.get("abandonment_rate"),
        "stable": stable,
        "status": status,
        "warning": metrics.get("error"),
    }


def process_segments(time_segments: Iterable[Mapping]) -> pd.DataFrame:
    """Process Page 1 current-system segments into a DataFrame."""
    if time_segments is None:
        logger.info("process_segments: no input (None)")
        return _empty_frame(CURRENT_COLUMNS)

    seg_list = list(time_segments)
    logger.info("process_segments: %d segments", len(seg_list))

    rows = []
    for index, segment in enumerate(seg_list, start=1):
        if not isinstance(segment, Mapping):
            rows.append(
                _current_row(
                    time_label=f"Segment {index}",
                    lambda_=None,
                    mu=None,
                    c=None,
                    model_name=None,
                    metrics={
                        "rho": None,
                        "L": None,
                        "Lq": None,
                        "W": None,
                        "Wq": None,
                        "stable": False,
                        "error": "Invalid segment format: each segment must be a dictionary.",
                    },
                )
            )
            continue

        time_label = segment.get("time", f"Segment {index}")
        lambda_ = segment.get("lambda")
        mu = segment.get("mu")
        c = segment.get("c", 1)
        variance = segment.get("variance")
        capacity = segment.get("K")
        theta = segment.get("theta")

        if lambda_ is None or mu is None:
            continue

        selection = select_model(lambda_, mu, c, variance=variance, K=capacity, theta=theta)
        rows.append(
            _current_row(
                time_label,
                lambda_,
                mu,
                selection["servers"],
                selection["name"],
                selection["metrics"],
                theta=selection["theta"],
            )
        )

    return pd.DataFrame(rows, columns=CURRENT_COLUMNS) if rows else _empty_frame(CURRENT_COLUMNS)


def compute_kpis(results_df: pd.DataFrame, customer_waiting_cost: float | None = None) -> dict[str, Any]:
    """Compute Page 1 KPI summary values including waiting costs.
    
    Waiting Cost calculation:
    - Stable (ρ < 1): cost = Lq × customer_waiting_cost
    - Unstable (ρ ≥ 1): cost = λ × UNSTABLE_PENALTY_MULTIPLIER × customer_waiting_cost
    """
    if customer_waiting_cost is None:
        customer_waiting_cost = DEFAULT_CUSTOMER_WAITING_COST

    if results_df is None or results_df.empty:
        return {
            "avg_utilization": None,
            "max_utilization": None,
            "max_utilization_time": None,
            "avg_waiting_time": None,
            "total_waiting_cost": 0.0,
            "avg_waiting_cost": 0.0,
            "stable_count": 0,
            "unstable_count": 0,
        }

    # Calculate waiting costs for ALL rows (stable + unstable)
    total_wait_cost = 0.0
    total_waits = 0.0

    for idx, row in results_df.iterrows():
        is_stable = row.get("stable", False)

        if is_stable:
            # Stable system: use actual Lq
            lq = row.get("Lq")
            if lq is not None and not pd.isna(lq):
                total_wait_cost += lq * customer_waiting_cost

            wq = row.get("Wq")
            if wq is not None and not pd.isna(wq):
                total_waits += wq
        else:
            # Unstable system (ρ ≥ 1): apply penalty multiplier
            lambda_ = row.get("lambda")
            if lambda_ is not None and not pd.isna(lambda_):
                total_wait_cost += lambda_ * UNSTABLE_PENALTY_MULTIPLIER * customer_waiting_cost

    count_total = len(results_df)
    count_stable = int(results_df["stable"].sum())
    count_unstable = count_total - count_stable
    avg_cost = total_wait_cost / count_total if count_total > 0 else 0.0
    avg_wait_time: float | None = total_waits / count_stable if count_stable > 0 else None

    # Find worst utilization (from stable segments only)
    stable_df = results_df[results_df["stable"]].copy()
    if stable_df.empty:
        return {
            "avg_utilization": None,
            "max_utilization": None,
            "max_utilization_time": None,
            "avg_waiting_time": None,
            "total_waiting_cost": total_wait_cost,
            "avg_waiting_cost": avg_cost,
            "stable_count": 0,
            "unstable_count": count_unstable,
        }

    worst_index = stable_df["rho"].idxmax()

    return {
        "avg_utilization": results_df["rho"].mean(),
        "max_utilization": stable_df["rho"].max(),
        "max_utilization_time": stable_df.loc[worst_index, "time"],
        "avg_waiting_time": avg_wait_time,
        "total_waiting_cost": total_wait_cost,
        "avg_waiting_cost": avg_cost,
        "stable_count": count_stable,
        "unstable_count": count_unstable,
    }


def get_unstable_messages(results_df: pd.DataFrame) -> list[str]:
    """Collect validation messages for unstable current-system segments."""
    if results_df is None or results_df.empty:
        return []

    issue_rows = results_df[~results_df["stable"]]
    messages = []
    for _, row in issue_rows.iterrows():
        details = row["warning"] or "Segment could not be evaluated."
        messages.append(f"{row['time']}: {details}")
    return messages



