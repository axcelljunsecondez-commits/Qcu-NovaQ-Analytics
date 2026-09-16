"""Shared model-selection dispatch for queueing analytics.

Single source of truth for choosing the queueing model and its metrics
function. Used by ``data_processing`` (current-metrics rows) and
``optimization`` (server-count search) so the dispatch chain cannot drift.
"""

from __future__ import annotations

import math
from numbers import Real

from backend.queueing_engine.models import erlang_a, mg1, mgc, mgck, mm1, mmc, mmck

UNSUPPORTED_SEPARATE_MODEL = "Separate FIFO Queues (unsupported)"


def _unsupported_separate_model(reason: str) -> dict:
    return {
        "name": UNSUPPORTED_SEPARATE_MODEL,
        "model_id": "separate_fifo_unsupported",
        "metrics": {
            "rho": None,
            "L": None,
            "Lq": None,
            "W": None,
            "Wq": None,
            "stable": False,
            "error": reason,
        },
        "servers": 1,
        "theta": None,
    }


def _is_number(value) -> bool:
    """Return True when a value is a finite real number."""
    return isinstance(value, Real) and math.isfinite(float(value))


def _select_model(lambda_, mu, c, variance=None, K=None, theta=None, queue_structure=None) -> dict:
    """Select the queueing model for a segment and compute its metrics.

    Dispatch precedence retains the frozen legacy contract, with a separate-queue
    extension for dedicated single-server lines.

    1. separate queue + valid variance + ``c == 1`` → Parallel M/G/1
    2. ``theta > 0``              → M/M/c+M (Erlang-A)
    3. ``K`` + ``variance``       → M/G/c/K
    4. ``K``                      → M/M/c/K
    5. ``variance``               → M/G/c
    6. ``c == 1``                 → M/M/1
    7. otherwise                  → M/M/c

    Non-numeric, NaN, and infinite values are treated as absent, so
    garbage input falls through to the plain M/M/c family.
    """
    if queue_structure == "separate_queues":
        if c != 1:
            return _unsupported_separate_model(
                "Separate FIFO queues require one dedicated server per queue."
            )
        if K is not None or (theta is not None and _is_number(theta) and float(theta) > 0):
            return _unsupported_separate_model(
                "Separate FIFO analytical support currently requires unlimited capacity and no abandonment model."
            )
        if not _is_number(variance):
            return _unsupported_separate_model(
                "Separate FIFO analytical support requires service-time variance for every queue."
            )
        return {
            "name": "Parallel M/G/1",
            "model_id": "parallel_mg1",
            "metrics": mg1(lambda_, mu, float(variance)),
            "servers": 1,
            "theta": None,
        }
    if theta is not None and _is_number(theta) and float(theta) > 0:
        return {
            "name": "M/M/c+M (Erlang-A)",
            "metrics": erlang_a(lambda_, mu, c, float(theta)),
            "servers": c,
            "theta": float(theta),
            "model_id": "mmc_erlang_a",
        }
    if _is_number(K) and _is_number(variance):
        return {
            "name": "M/G/c/K",
            "metrics": mgck(lambda_, mu, c, variance, int(K)),
            "servers": c,
            "theta": None,
            "model_id": "mgc_k",
        }
    if _is_number(K):
        return {
            "name": "M/M/c/K",
            "metrics": mmck(lambda_, mu, c, int(K)),
            "servers": c,
            "theta": None,
            "model_id": "mmc_k",
        }
    if _is_number(variance):
        return {
            "name": "M/G/c",
            "metrics": mgc(lambda_, mu, c, variance),
            "servers": c,
            "theta": None,
            "model_id": "mgc",
        }
    if c == 1:
        return {"name": "M/M/1", "model_id": "mm1", "metrics": mm1(lambda_, mu), "servers": 1, "theta": None}
    return {"name": "M/M/c", "model_id": "mmc", "metrics": mmc(lambda_, mu, c), "servers": c, "theta": None}


def select_model(lambda_, mu, c, variance=None, K=None, theta=None, queue_structure=None) -> dict:
    """Select once and disclose the supplied inputs that determined dispatch."""
    result = _select_model(lambda_, mu, c, variance, K, theta, queue_structure)
    reasons = {
        "M/M/c+M (Erlang-A)": "Positive patience rate theta supplied; it takes dispatch precedence.",
        "M/G/c/K": "Finite capacity and service-time variance supplied; approximation.",
        "M/M/c/K": "Finite capacity supplied without service-time variance.",
        "M/G/c": "Service-time variance supplied; approximation.",
        "Parallel M/G/1": "Separate queue structure, one dedicated server, and measured service-time variance supplied; exact M/G/1 analysis.",
        UNSUPPORTED_SEPARATE_MODEL: "Separate FIFO analysis is unavailable until one dedicated server, unlimited capacity, no abandonment, and service variance are supplied.",
        "M/M/1": "One server and no advanced model parameters supplied.",
        "M/M/c": "Multiple servers and no advanced model parameters supplied.",
    }
    result["selection_reason"] = reasons[result["name"]]
    result["service_cv"] = math.sqrt(variance) * mu if _is_number(variance) and variance >= 0 and _is_number(mu) else None
    result["assumptions"] = "Poisson arrivals; rates per hour; service variance in hours squared; theta is patience rate per hour. Variability is supplied, not inferred from aggregate rates."
    if result["name"] == "Parallel M/G/1":
        result["assumptions"] += " Separate queues are grouped independently by segment and queue_id."
    if result["name"] == "M/M/c+M (Erlang-A)":
        result["assumptions"] += " Wq is queue workload divided by served throughput, not a directly observed served-customer wait."
    return result
