"""Independent exact cases for identical-exponential nonpreemptive priorities.

Larson/Odoni, Urban Operations Research, section 4.9.3, (4.111)-(4.112).
All arrivals and services are synthetic rates per hour, waits in hours.
"""

from fractions import Fraction
from math import factorial

import pytest

from backend.queueing_engine.models.queue_models import mmc_priority


@pytest.mark.parametrize("lambda1,lambda2,mu,c,priority,regular", [
    (2, 2, 6, 1, Fraction(1, 6), Fraction(1, 2)),
    (1, 1, 2, 2, Fraction(1, 9), Fraction(2, 9)),
    (2, 2, 2, 4, Fraction(2, 69), Fraction(4, 69)),
    (3, 1, 3, 2, Fraction(8, 45), Fraction(8, 15)),
])
def test_exact_textbook_priority_cases(lambda1, lambda2, mu, c, priority, regular):
    result = mmc_priority(lambda1, lambda2, mu, c)
    assert result["stable"] is True
    assert result["Wq_priority"] == pytest.approx(float(priority), rel=1e-12)
    assert result["Wq_regular"] == pytest.approx(float(regular), rel=1e-12)
    assert result["Lq_priority"] == pytest.approx(float(lambda1 * priority))
    assert result["Lq_regular"] == pytest.approx(float(lambda2 * regular))
    assert result["W_priority"] == pytest.approx(float(priority + Fraction(1, mu)))
    assert result["W_regular"] == pytest.approx(float(regular + Fraction(1, mu)))


@pytest.mark.parametrize("lambda1,lambda2,mu,c", [
    (Fraction(1, 1000), Fraction(3, 1000), 6, 1),
    (Fraction(2), Fraction(2), 6, 1),
    (Fraction(3), Fraction(1), 3, 2),
    (Fraction(1, 10), Fraction(9, 10), 2, 4),
    (Fraction(399, 100), Fraction(399, 100), 2, 4),
])
def test_priority_conserves_independent_aggregate_stationary_queue(lambda1, lambda2, mu, c):
    # Exact rational normalization, including the infinite geometric tail.
    # It does not call NovaQ's M/M/c or its Erlang-B recursion.
    offered = (lambda1 + lambda2) / mu
    rho = offered / c
    head = sum((offered ** n / factorial(n) for n in range(c)), Fraction(0))
    tail_start = offered ** c / factorial(c)
    normalizer = head + tail_start / (1 - rho)
    queue_length = tail_start * rho / (1 - rho) ** 2 / normalizer
    result = mmc_priority(float(lambda1), float(lambda2), mu, c)
    assert result["stable"] is True
    assert result["Lq_priority"] + result["Lq_regular"] == pytest.approx(float(queue_length), rel=1e-11)
    assert 0 <= result["Wq_priority"] <= result["Wq_regular"]


@pytest.mark.parametrize("lambda1,lambda2,mu,c", [
    (0, 1, 6, 1), (-1, 1, 6, 1), (1, 1, 0, 1), (1, 1, 6, 0),
    (1, 1, 6, 1.5), (float("nan"), 1, 6, 1), (1, float("inf"), 6, 1),
    (3, 3, 6, 1), (4, 4, 6, 1), (1, 2.15, 1.05, 3),
])
def test_priority_invalid_or_saturated_inputs_refuse_without_a_number(lambda1, lambda2, mu, c):
    result = mmc_priority(lambda1, lambda2, mu, c)
    assert result["stable"] is False
    assert result["error"]
    assert result.get("Wq_priority") is None


def test_priority_propagates_base_numerical_refusal(monkeypatch):
    from backend.queueing_engine.models import queue_models

    monkeypatch.setattr(queue_models, "mmc", lambda *_: {
        "stable": False, "Wq": None, "error": "Reference-injected numerical refusal",
    })
    result = mmc_priority(1, 1, 6, 2)
    assert result["stable"] is False
    assert result["error"] == "Reference-injected numerical refusal"
    assert result.get("Wq_priority") is None
