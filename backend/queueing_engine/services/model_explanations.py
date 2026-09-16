"""Structured, provenance-aware explanations for existing model selection."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from backend.queueing_engine.services.data_processing import (
    CURRENT_COLUMNS,
    _current_row,
    group_separate_queue_segments,
)
from backend.queueing_engine.services.model_selection import select_model

MODEL_ASSUMPTIONS = {
    "M/M/1": ["Poisson arrivals", "Exponential service times", "One server", "Unlimited queue capacity"],
    "Parallel M/G/1": ["Independent queue per cashier", "One dedicated server per queue", "General service-time variation supplied", "Separate FIFO discipline"],
    "Separate FIFO Queues (unsupported)": ["Separate queue structure detected", "Analytical capability requirements were not met"],
    "M/M/c": ["Poisson arrivals", "Exponential service times", "Shared queue", "Multiple parallel servers"],
    "M/G/c": ["Poisson arrivals", "General service-time variability supplied by the data", "Shared queue", "Approximation"],
    "M/M/c/K": ["Poisson arrivals", "Exponential service times", "Finite total system capacity K"],
    "M/G/c/K": ["Poisson arrivals", "General service-time variability supplied by the data", "Finite total system capacity K", "Approximation"],
    "M/M/c+M (Erlang-A)": ["Poisson arrivals", "Exponential service times", "Exponential patience with supplied theta", "Shared queue"],
}


def _operational_facts(setup: Mapping) -> list[str]:
    facts: list[str] = []
    labels = {
        "shared_queue": "The operation uses one shared queue.",
        "single_server": "The operation has one server.",
        "separate_queues": "The operation has separate queues.",
    }
    structure = setup.get("queue_structure")
    if structure in labels:
        facts.append(labels[structure])
    if setup.get("fixed_server_count") is not None:
        facts.append(f"The configured fixed server count is {setup['fixed_server_count']}.")
    if setup.get("staffing_varies_by_period"):
        facts.append("Staffing varies by time period.")
    if setup.get("capacity_mode") == "finite" and setup.get("total_system_capacity") is not None:
        facts.append(
            f"Configured total system capacity is {setup['total_system_capacity']}, including customers in service."
        )
    if setup.get("abandonment_mode") == "modeled" and setup.get("patience_rate_per_hour") is not None:
        facts.append(f"Configured patience rate is {setup['patience_rate_per_hour']} per hour.")
    return facts


def analyze_segments(
    segments: list[Mapping], setup: Mapping, provenance: Mapping | None = None
) -> tuple[pd.DataFrame, list[dict], str | None]:
    """Select exactly once per segment and return current rows plus explanations."""
    rows: list[dict] = []
    explanations: list[dict] = []
    field_sources = (provenance or {}).get("field_provenance", {})
    for index, segment in enumerate(group_separate_queue_segments(segments), start=1):
        if segment.get("lambda") is None or segment.get("mu") is None:
            continue
        selection = select_model(
            segment["lambda"],
            segment["mu"],
            segment.get("c", 1),
            variance=segment.get("variance"),
            K=segment.get("K"),
            theta=segment.get("theta"),
            queue_structure=segment.get("queue_structure") or setup.get("queue_structure"),
        )
        time_label = str(segment.get("time", f"Segment {index}"))
        row = _current_row(
            time_label,
            segment["lambda"],
            segment["mu"],
            selection["servers"],
            selection["name"],
            selection["metrics"],
            theta=selection["theta"],
        )
        row["queue_id"] = segment.get("queue_id")
        row["queue_structure"] = segment.get("queue_structure") or setup.get("queue_structure")
        row["model_id"] = selection["model_id"]
        rows.append(row)
        measured = []
        for field in ("lambda", "mu", "variance", "K", "theta", "c"):
            if segment.get(field) is not None and field_sources.get(field) == "data_derived":
                measured.append(f"{field} was derived from uploaded customer-event data: {segment[field]}.")
            elif segment.get(field) is not None and field_sources.get(field) == "user_provided":
                measured.append(f"{field} was supplied by the user: {segment[field]}.")
        explanations.append(
            {
                "time": time_label,
                "selected_model": selection["name"],
                "operational_facts": _operational_facts(setup),
                "measured_characteristics": measured,
                "model_assumptions": MODEL_ASSUMPTIONS[selection["name"]],
                "selection_reason": selection["selection_reason"],
            }
        )
    names = {item["selected_model"] for item in explanations}
    selected = next(iter(names)) if len(names) == 1 else None
    if len(names) > 1:
        selected = "Multiple models by time period"
    frame = pd.DataFrame(rows, columns=CURRENT_COLUMNS) if rows else pd.DataFrame(columns=CURRENT_COLUMNS)
    return frame, explanations, selected
