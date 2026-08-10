"""Shared model-selection dispatch for queueing analytics.

Single source of truth for choosing the queueing model and its metrics
function. Used by ``data_processing`` (current-metrics rows) and
``optimization`` (server-count search) so the dispatch chain cannot drift.
"""

from __future__ import annotations

import math
from numbers import Real

from backend.queueing_engine.models import erlang_a, mgc, mgck, mm1, mmc, mmck


def _is_number(value) -> bool:
    """Return True when a value is a finite real number."""
    return isinstance(value, Real) and math.isfinite(float(value))


def select_model(lambda_, mu, c, variance=None, K=None, theta=None) -> dict:
    """Select the queueing model for a segment and compute its metrics.

    Dispatch precedence (matches the frozen legacy contract):

    1. ``theta > 0``              → M/M/c+M (Erlang-A)
    2. ``K`` + ``variance``       → M/G/c/K
    3. ``K``                      → M/M/c/K
    4. ``variance``               → M/G/c
    5. ``c == 1``                 → M/M/1
    6. otherwise                  → M/M/c

    Non-numeric, NaN, and infinite values are treated as absent, so
    garbage input falls through to the plain M/M/c family.

    Returns
    -------
    dict
        Keys: ``name`` (model label), ``metrics`` (model output dict),
        ``servers`` (server count), ``theta`` (abandonment rate or None).
    """
    if theta is not None and _is_number(theta) and float(theta) > 0:
        return {
            "name": "M/M/c+M (Erlang-A)",
            "metrics": erlang_a(lambda_, mu, c, float(theta)),
            "servers": c,
            "theta": float(theta),
        }
    if _is_number(K) and _is_number(variance):
        return {
            "name": "M/G/c/K",
            "metrics": mgck(lambda_, mu, c, variance, int(K)),
            "servers": c,
            "theta": None,
        }
    if _is_number(K):
        return {
            "name": "M/M/c/K",
            "metrics": mmck(lambda_, mu, c, int(K)),
            "servers": c,
            "theta": None,
        }
    if _is_number(variance):
        return {
            "name": "M/G/c",
            "metrics": mgc(lambda_, mu, c, variance),
            "servers": c,
            "theta": None,
        }
    if c == 1:
        return {"name": "M/M/1", "metrics": mm1(lambda_, mu), "servers": 1, "theta": None}
    return {"name": "M/M/c", "metrics": mmc(lambda_, mu, c), "servers": c, "theta": None}
