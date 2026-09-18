"""Data preparation helpers for the queueing dashboard."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from backend.queueing_engine.log import get_logger

logger = get_logger(__name__)

from backend.queueing_engine.config import DEFAULT_WAIT_COST_HR, UNSTABLE_PENALTY_MULTIPLIER
from backend.queueing_engine.services.model_selection import select_model

CURRENT_COLUMNS = [
    "time",
    "queue_id",
    "queue_structure",
    "model_id",
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


def _current_row(time_label, lambda_, mu, c, model_name, metrics, theta=None, model_id=None, queue_structure=None) -> dict:
    """Build one normalized current-system result row."""
    stable = bool(metrics.get("stable"))
    rho = metrics.get("rho")
    status = _classify_utilization_status(rho)

    return {
        "time": str(time_label),
        "queue_id": None,
        "queue_structure": queue_structure,
        "model_id": model_id,
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


def group_separate_queue_segments(time_segments: Iterable[Mapping]) -> list[Mapping]:
    """Group separate-queue rows by segment and queue without pooling queues."""
    grouped: dict[tuple[str, str], dict] = {}
    output: list[Mapping] = []
    for segment in time_segments:
        if not isinstance(segment, Mapping):
            output.append(segment)
            continue
        structure = segment.get("queue_structure")
        if structure != "separate_queues" and segment.get("queue_id") is None:
            output.append(segment)
            continue
        queue_id = str(segment.get("queue_id", "")).strip()
        key = (str(segment.get("time", "")), queue_id)
        current = grouped.get(key)
        if current is None:
            current = dict(segment)
            current["queue_structure"] = "separate_queues"
            current["queue_id"] = queue_id
            current["lambda"] = 0.0
            current["_lambda_weighted_service"] = 0.0
            current["_lambda_weighted_second_moment"] = 0.0
            grouped[key] = current
            output.append(current)
        lambda_value = float(segment.get("lambda", 0.0))
        mu_value = float(segment.get("mu", 0.0))
        variance = segment.get("variance")
        if lambda_value < 0 or mu_value <= 0 or variance is None:
            continue
        current["lambda"] = float(current.get("lambda", 0.0)) + lambda_value
        service_mean = 1.0 / mu_value
        current["_lambda_weighted_service"] += lambda_value * service_mean
        current["_lambda_weighted_second_moment"] += lambda_value * (float(variance) + service_mean**2)
    for current in grouped.values():
        if current.get("queue_structure") != "separate_queues":
            continue
        lambda_value = float(current.get("lambda", 0.0))
        if lambda_value > 0:
            service_mean = current["_lambda_weighted_service"] / lambda_value
            second_moment = current["_lambda_weighted_second_moment"] / lambda_value
            current["mu"] = 1.0 / service_mean
            current["variance"] = max(0.0, second_moment - service_mean**2)
        current.pop("_lambda_weighted_service", None)
        current.pop("_lambda_weighted_second_moment", None)
    return output


def process_segments(time_segments: Iterable[Mapping]) -> pd.DataFrame:
    """Process Page 1 current-system segments into a DataFrame."""
    if time_segments is None:
        logger.info("process_segments: no input (None)")
        return _empty_frame(CURRENT_COLUMNS)

    seg_list = group_separate_queue_segments(list(time_segments))
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
        queue_id = segment.get("queue_id")
        queue_structure = segment.get("queue_structure")
        lambda_ = segment.get("lambda")
        mu = segment.get("mu")
        c = segment.get("c", 1)
        variance = segment.get("variance")
        capacity = segment.get("K")
        theta = segment.get("theta")

        if lambda_ is None or mu is None:
            continue

        selection = select_model(
            lambda_,
            mu,
            c,
            variance=variance,
            K=capacity,
            theta=theta,
            queue_structure=queue_structure or ("separate_queues" if queue_id is not None else None),
        )
        row = _current_row(
            time_label,
            lambda_,
            mu,
            selection["servers"],
            selection["name"],
            selection["metrics"],
            theta=selection["theta"],
        )
        row["queue_id"] = queue_id
        row["queue_structure"] = queue_structure or ("separate_queues" if queue_id is not None else None)
        row["model_id"] = selection["model_id"]
        rows.append(row)

    return pd.DataFrame(rows, columns=CURRENT_COLUMNS) if rows else _empty_frame(CURRENT_COLUMNS)


def _is_separate_frame(results_df: pd.DataFrame) -> bool:
    """True only when every row belongs to an explicitly separate queue."""
    if results_df is None or results_df.empty or "queue_structure" not in results_df.columns:
        return False
    structures = {
        None if value is None or pd.isna(value) else str(value)
        for value in results_df["queue_structure"]
    }
    return structures == {"separate_queues"}


def _weighted_wait(results_df: pd.DataFrame) -> float | None:
    """Arrival-rate-weighted mean wait across separate queue-period rows.

    Each stable separate queue serves its own arrivals at rate lambda with no
    blocking or abandonment under the supported contract, so throughput equals
    lambda and sum(lambda * Wq) / sum(lambda) is the expected wait of a random
    arrival. Any non-finite lambda or wait makes the aggregate unavailable;
    an all-idle frame has no arrivals to average over. Never zero-filled.
    """
    weighted = 0.0
    total_weight = 0.0
    for _, row in results_df.iterrows():
        arrival = row.get("lambda")
        wait = row.get("Wq")
        try:
            arrival_value = float(arrival)
            wait_value = float(wait)
        except (TypeError, ValueError):
            return None
        if (
            not math.isfinite(arrival_value)
            or not math.isfinite(wait_value)
            or arrival_value < 0
            or wait_value < 0
        ):
            return None
        total_weight += arrival_value
        weighted += arrival_value * wait_value
    if total_weight <= 0:
        return None
    return weighted / total_weight


def compute_kpis(results_df: pd.DataFrame, customer_waiting_cost: float | None = None) -> dict[str, Any]:
    """Compute Page 1 KPI summary values including waiting costs.
    
    Waiting Cost calculation:
    - Stable (ρ < 1): cost = Lq × customer_waiting_cost
    - Unstable (ρ ≥ 1): cost = λ × UNSTABLE_PENALTY_MULTIPLIER × customer_waiting_cost
    """
    if customer_waiting_cost is None:
        customer_waiting_cost = DEFAULT_WAIT_COST_HR

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
    if _is_separate_frame(results_df):
        avg_wait_time = _weighted_wait(results_df)

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
