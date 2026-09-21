"""Utilization status bands at their exact boundaries, including float noise.

λ / (cμ) for CSV-style inputs whose exact ρ sits on a boundary often computes a
hair off it (0.99 / 1.1 = 0.8999999999999999). Every classifier must place such
a value on the boundary, not beside it.
"""

from __future__ import annotations

import math

import pytest

from backend.queueing_engine.models.queue_models import mm1
from backend.queueing_engine.services.data_processing import _classify_utilization_status
from backend.queueing_engine.simulation.simulation import _classify_status
from backend.queueing_engine.utilization import utilization_band
from backend.reports.report_export import _utilization_status

CLASSIFIERS = {
    "band": utilization_band,
    "current": _classify_utilization_status,
    "simulation": lambda rho: _classify_status(rho, 0, 20),
    "report": _utilization_status,
}


@pytest.mark.parametrize("classify", CLASSIFIERS.values(), ids=CLASSIFIERS.keys())
@pytest.mark.parametrize(
    ("rho", "expected"),
    [
        (0.59999, "Lean"),
        (0.6, "Normal"),
        (0.5999999999999999, "Normal"),
        (0.6000000000000001, "Normal"),
        (0.8, "Normal"),
        (0.7999999999999999, "Normal"),
        (0.8000000000000002, "Normal"),
        (0.80001, "Peak"),
        (0.8999, "Peak"),
        (0.9, "Critical"),
        (0.8999999999999999, "Critical"),
        (0.9000000000000001, "Critical"),
        (1.0, "Critical"),
        (1.0000000000000002, "Critical"),
        (1.00001, "Unstable"),
    ],
)
def test_boundaries_ignore_float_noise(classify, rho: float, expected: str) -> None:
    assert classify(rho) == expected


@pytest.mark.parametrize(
    ("lambda_", "mu", "expected"),
    [
        (0.99, 1.1, "Critical"),   # exact ρ = 0.9, computes 0.8999999999999999
        (1.12, 1.4, "Normal"),     # exact ρ = 0.8, computes 0.8000000000000002
        (2.01, 3.35, "Normal"),    # exact ρ = 0.6, computes 0.5999999999999999
    ],
)
def test_engine_rho_on_a_boundary_gets_the_boundary_status(lambda_: float, mu: float, expected: str) -> None:
    rho = mm1(lambda_, mu)["rho"]
    assert rho != round(rho, 12)  # the engine value really is off the boundary
    assert _classify_utilization_status(rho) == expected


def test_queue_depth_still_forces_critical_below_unstable() -> None:
    assert _classify_status(0.3, 20, 20) == "Critical"
    assert _classify_status(1.5, 20, 20) == "Unstable"


def test_missing_and_invalid_rho_keep_their_existing_labels() -> None:
    assert _classify_utilization_status(None) == "—"
    assert _utilization_status(None) == "Unavailable"
    assert _utilization_status(math.nan) == "Unavailable"
    assert _classify_status(math.nan, 0, 20) == "Lean"
