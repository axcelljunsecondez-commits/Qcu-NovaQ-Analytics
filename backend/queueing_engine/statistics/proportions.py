"""Binomial-proportion confidence intervals and precision classification.

Monte Carlo failure rates are proportions (``failures / trials``) that are
often near zero, where the normal approximation is biased and can exit
``[0, 1]``.  This module provides the Wilson score interval, which is
numerically safe at the boundaries (``k == 0``, ``k == n``, ``n == 1``) and
always lies within ``[0, 1]``.
"""

from __future__ import annotations

import math
from typing import Literal

# z-value for a 95 % confidence level.
Z95 = 1.959963984540054

# Precision bands for a failure-rate decision anchored to the existing
# PASS/FAIL threshold of failure_rate <= 0.10 (see simulation.py).  Half-width
# is measured in percentage points as a fraction (0.05 == 5 pp).
HIGH_PRECISION_MAX_HW = 0.03
ADEQUATE_MAX_HW = 0.05

PrecisionLevel = Literal["high", "moderate", "low"]


def wilson_ci(
    k: int,
    n: int,
    z: float = Z95,
) -> tuple[float, float, float] | tuple[None, None, None]:
    """Return ``(lower, upper, half_width)`` for a Wilson score interval.

    Parameters
    ----------
    k : int
        Number of successes (e.g. trials that exceeded the threshold).
    n : int
        Number of trials.
    z : float
        Standard-normal quantile for the desired confidence level (1.96 for
        95 %).

    Returns
    -------
    tuple
        ``(lower, upper, half_width)`` with ``half_width == (upper - lower) / 2``.
        Returns ``(None, None, None)`` when ``n < 1`` so callers can surface a
        missing estimate instead of a NaN.
    """
    if n < 1:
        return None, None, None

    k = max(0, min(int(k), int(n)))
    denom = n + z * z
    center = (k + z * z / 2.0) / denom
    margin = z * math.sqrt((k * (n - k)) / n + z * z / 4.0) / denom
    lower = max(center - margin, 0.0)
    upper = min(center + margin, 1.0)
    half_width = (upper - lower) / 2.0
    return lower, upper, half_width


def failure_rate_precision(half_width: float | None) -> PrecisionLevel | None:
    """Classify a failure-rate CI half-width into a precision band.

    The bands are anchored to the existing PASS/FAIL decision threshold of
    ``failure_rate <= 0.10``:

    - ``high``:      half-width <= 0.03  (a third of the decision band)
    - ``moderate``:  0.03 < half-width <= 0.05  (up to half the decision band)
    - ``low``:       half-width > 0.05  (wider than half the decision band)

    ``half_width`` is measured as a proportion (0.05 == 5 percentage points).
    A ``None`` input (no trials, or a missing estimate) yields ``None``.
    """
    if half_width is None:
        return None
    if half_width <= HIGH_PRECISION_MAX_HW:
        return "high"
    if half_width <= ADEQUATE_MAX_HW:
        return "moderate"
    return "low"
