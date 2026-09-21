"""Stability at exactly ρ = 1 must not depend on float rounding.

A load of exactly 1 has no steady state. λ / (cμ) and λ · (1/μ) can land a hair
under 1 for such inputs (3.15 / (3 · 1.05) = 0.9999999999999999), which a plain
``< 1`` test accepted as stable and turned into waits of ~1e15 hours.
"""

from __future__ import annotations

import math

import pytest

from backend.api.reports import _overloaded
from backend.queueing_engine.models import erlang_a, mg1, mgc, mm1, mmc
from backend.queueing_engine.utilization import is_saturated

EXACT_LOAD_ONE = [
    ("M/M/c", lambda: mmc(3.15, 1.05, 3)),
    ("M/G/c", lambda: mgc(3.15, 1.05, 3, 0.5)),
    ("Erlang-A θ=0", lambda: erlang_a(3.15, 1.05, 3, 0.0)),
    ("M/G/1", lambda: mg1(1.85, 1.85, 0.2)),
    ("M/M/1", lambda: mm1(1.85, 1.85)),
]


@pytest.mark.parametrize("compute", [case[1] for case in EXACT_LOAD_ONE], ids=[case[0] for case in EXACT_LOAD_ONE])
def test_exact_load_of_one_is_unstable_with_no_finite_wait(compute) -> None:
    result = compute()
    assert result["stable"] is False
    assert result["Wq"] is None
    assert result["rho"] == pytest.approx(1.0, abs=1e-12)


def test_the_regression_inputs_really_compute_below_one() -> None:
    # Guards the test itself: without float noise these cases would prove nothing.
    assert 3.15 / (3 * 1.05) < 1.0
    assert 1.85 * (1.0 / 1.85) < 1.0


@pytest.mark.parametrize(("lambda_", "mu", "c"), [(3.14, 1.05, 3), (1.84, 1.85, 1), (9.99, 1.0, 10)])
def test_loads_just_under_one_stay_stable_and_finite(lambda_: float, mu: float, c: int) -> None:
    result = mmc(lambda_, mu, c)
    assert result["stable"] is True
    assert math.isfinite(result["Wq"]) and result["Wq"] > 0


def test_saturation_boundary() -> None:
    assert is_saturated(1.0)
    assert is_saturated(0.9999999999999999)
    assert is_saturated(1.2)
    assert not is_saturated(0.9999)
    assert not is_saturated(0.99999998)


def test_report_overload_flag_matches_the_models() -> None:
    assert _overloaded({"rho": 3.15 / (3 * 1.05)}) is True
    assert _overloaded({"rho": 0.9968}) is False
    assert _overloaded({"rho": None, "lambda": 5, "working": 0}) is True
    assert _overloaded({"rho": None}) is None
