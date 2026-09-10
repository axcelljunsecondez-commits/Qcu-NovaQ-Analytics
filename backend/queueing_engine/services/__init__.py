"""Domain services: optimization, costing, and data processing."""

from __future__ import annotations

from .costing import (
    compute_all_costs,
    compute_cost_summary,
    compute_segment_costs,
)
from .data_processing import (
    CURRENT_COLUMNS,
    compute_kpis,
    process_segments,
)
from .optimization import (
    compute_blended_rate,
    optimize_segment,
    optimize_segments,
    summarize_optimization,
)

__all__ = [
    "CURRENT_COLUMNS",
    "compute_all_costs",
    "compute_blended_rate",
    "compute_cost_summary",
    "compute_kpis",
    "compute_segment_costs",
    "optimize_segment",
    "optimize_segments",
    "process_segments",
    "summarize_optimization",
]
