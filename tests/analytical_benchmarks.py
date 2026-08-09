"""Analytical benchmarks for the queueing engine (Phase 1).

Reference values are derived from the closed-form steady-state formulas
(M/M/1 and Erlang-C M/M/c) computed independently by hand/calculator —
never by calling the implementation under test. They lock the existing
mathematical behavior: per the design spec, formulas change ONLY when
one of these benchmarks proves an actual error.
"""

from __future__ import annotations

import math

import pytest

from queue_models import mm1, mmc


def _expect_unstable(result: dict, *, message: str, rho: float) -> None:
    assert result["stable"] is False
    assert result["error"] is not None and message in result["error"]
    assert result["rho"] == pytest.approx(rho)
    assert result["L"] is None
    assert result["Lq"] is None
    assert result["W"] is None
    assert result["Wq"] is None


class TestMM1AnalyticalBenchmarks:
    def test_mm1_textbook_case_lambda2_mu3(self) -> None:
        # Closed form: rho = l/m, L = l/(m-l), Lq = l^2/(m(m-l)),
        # W = 1/(m-l), Wq = l/(m(m-l)).
        result = mm1(2, 3)

        assert result["stable"] is True
        assert result["rho"] == pytest.approx(2 / 3)
        assert result["L"] == pytest.approx(2.0)
        assert result["W"] == pytest.approx(1.0)
        assert result["Lq"] == pytest.approx(4 / 3)
        assert result["Wq"] == pytest.approx(2 / 3)

    def test_mm1_internal_consistency_relations(self) -> None:
        result = mm1(2, 3)

        assert result["L"] == pytest.approx(result["Lq"] + result["rho"])
        assert result["W"] == pytest.approx(result["Wq"] + 1 / 3)
        assert result["L"] == pytest.approx(2 * result["W"])

    def test_mm1_zero_arrivals(self) -> None:
        result = mm1(0, 5)

        assert result["stable"] is True
        assert result["rho"] == pytest.approx(0.0)
        assert result["L"] == pytest.approx(0.0)
        assert result["Lq"] == pytest.approx(0.0)
        assert result["Wq"] == pytest.approx(0.0)
        # Documented convention: W = 1/mu (mean service time) for an empty system.
        assert result["W"] == pytest.approx(1 / 5)

    def test_mm1_utilization_near_one(self) -> None:
        result = mm1(9.9, 10)

        assert result["stable"] is True
        assert result["rho"] == pytest.approx(0.99)
        assert result["L"] == pytest.approx(99.0)
        assert result["Lq"] == pytest.approx(98.01)
        assert result["W"] == pytest.approx(10.0)
        assert result["Wq"] == pytest.approx(9.9)

    def test_mm1_utilization_boundary_is_unstable(self) -> None:
        result = mm1(5, 5)

        _expect_unstable(result, message="Unstable", rho=1.0)

    def test_mm1_unstable_lambda_greater_than_mu(self) -> None:
        result = mm1(3, 2)

        _expect_unstable(result, message="Unstable", rho=1.5)

    def test_mm1_invalid_negative_lambda(self) -> None:
        result = mm1(-1, 5)

        assert result["stable"] is False
        assert result["error"] is not None

    def test_mm1_invalid_zero_mu(self) -> None:
        result = mm1(2, 0)

        assert result["stable"] is False
        assert result["error"] is not None

    def test_mm1_invalid_negative_mu(self) -> None:
        result = mm1(2, -3)

        assert result["stable"] is False
        assert result["error"] is not None

    def test_mm1_invalid_non_finite_rates(self) -> None:
        for lambda_, mu in [(math.inf, 5), (math.nan, 5), (2, math.inf), (2, math.nan)]:
            result = mm1(lambda_, mu)

            assert result["stable"] is False
            assert result["error"] is not None and "finite" in result["error"]

    def test_mm1_invalid_non_numeric_rates(self) -> None:
        for lambda_, mu in [(None, 5), ("2", 5), (2, None), (2, "3")]:
            result = mm1(lambda_, mu)  # type: ignore[arg-type]

            assert result["stable"] is False
            assert result["error"] is not None and "finite" in result["error"]


class TestMMcAnalyticalBenchmarks:
    def test_mmc_clean_rational_case_lambda8_mu4_c3(self) -> None:
        # Erlang-C closed form with a = l/m = 2, rho = a/c = 2/3:
        # P0 = [1 + 2 + 2^2/2 + 2^3/(6(1-2/3))]^-1 = 1/9
        # Lq = P0 * a^c * rho / (c!(1-rho)^2) = 8/9
        # Wq = Lq/l = 1/9, W = Wq + 1/mu = 13/36, L = l*W = 26/9.
        result = mmc(8, 4, 3)

        assert result["stable"] is True
        assert result["rho"] == pytest.approx(2 / 3)
        assert result["Lq"] == pytest.approx(8 / 9)
        assert result["Wq"] == pytest.approx(1 / 9)
        assert result["W"] == pytest.approx(13 / 36)
        assert result["L"] == pytest.approx(26 / 9)

    def test_mmc_textbook_case_lambda10_mu4_c3(self) -> None:
        # Erlang-C with a = 2.5, rho = 5/6:
        # P0 = [1 + 2.5 + 2.5^2/2 + 2.5^3/(6(1-5/6))]^-1 = 0.0449438202247191
        # Lq = P0 * a^3 * rho / (3!(1-rho)^2) = 3.5112359550561796
        result = mmc(10, 4, 3)

        assert result["stable"] is True
        assert result["rho"] == pytest.approx(5 / 6)
        assert result["Lq"] == pytest.approx(3.5112359550561796)
        assert result["Wq"] == pytest.approx(0.351123595505618)
        assert result["W"] == pytest.approx(0.601123595505618)
        assert result["L"] == pytest.approx(6.01123595505618)

    def test_mmc_internal_consistency_relations(self) -> None:
        result = mmc(10, 4, 3)

        assert result["L"] == pytest.approx(result["Lq"] + 10 / 4)
        assert result["W"] == pytest.approx(result["Wq"] + 1 / 4)
        assert result["L"] == pytest.approx(10 * result["W"])

    def test_mmc_single_server_equals_mm1(self) -> None:
        # M/M/c with c=1 must reduce exactly to M/M/1.
        mmc_result = mmc(2, 3, 1)
        mm1_result = mm1(2, 3)

        for key in ("rho", "L", "Lq", "W", "Wq"):
            assert mmc_result[key] == pytest.approx(mm1_result[key])
        assert mmc_result["stable"] == mm1_result["stable"]
        assert mmc_result["rho"] == pytest.approx(2 / 3)
        assert mmc_result["L"] == pytest.approx(2.0)
        assert mmc_result["W"] == pytest.approx(1.0)

    def test_mmc_zero_arrivals(self) -> None:
        result = mmc(0, 5, 2)

        assert result["stable"] is True
        assert result["rho"] == pytest.approx(0.0)
        assert result["L"] == pytest.approx(0.0)
        assert result["Lq"] == pytest.approx(0.0)
        assert result["Wq"] == pytest.approx(0.0)
        # Same documented convention as M/M/1: W = 1/mu.
        assert result["W"] == pytest.approx(1 / 5)

    def test_mmc_utilization_near_one(self) -> None:
        # a = 1.998, rho = 0.999:
        # P0 = [1 + 1.998 + 1.998^2/(2(1-0.999))]^-1 = 0.0005002501250625312
        # Lq = P0 * a^2 * rho / (2(1-rho)^2) = 997.5017498749374
        result = mmc(9.99, 5, 2)

        assert result["stable"] is True
        assert result["rho"] == pytest.approx(0.999)
        assert result["Lq"] == pytest.approx(997.5017498749374, rel=1e-9)
        assert result["Wq"] == pytest.approx(99.85002501250625, rel=1e-9)
        assert result["W"] == pytest.approx(100.05002501250625, rel=1e-9)
        assert result["L"] == pytest.approx(999.4997498749375, rel=1e-9)

    def test_mmc_utilization_boundary_is_unstable(self) -> None:
        # lambda == c * mu exactly (10 == 2 * 5).
        result = mmc(10, 5, 2)

        _expect_unstable(result, message="Unstable", rho=1.0)

    def test_mmc_unstable_lambda_exceeds_capacity(self) -> None:
        # lambda > c * mu (6 > 2 * 2).
        result = mmc(6, 2, 2)

        _expect_unstable(result, message="Unstable", rho=1.5)

    def test_mmc_unstable_high_load(self) -> None:
        # lambda > c * mu (10 > 2 * 4).
        result = mmc(10, 4, 2)

        _expect_unstable(result, message="Unstable", rho=1.25)

    def test_mmc_invalid_zero_c(self) -> None:
        result = mmc(2, 3, 0)

        assert result["stable"] is False
        assert result["error"] is not None

    def test_mmc_invalid_negative_c(self) -> None:
        result = mmc(2, 3, -1)

        assert result["stable"] is False
        assert result["error"] is not None

    def test_mmc_invalid_non_integer_c(self) -> None:
        for c in (2.5, 3.0, "2"):
            result = mmc(2, 3, c)  # type: ignore[arg-type]

            assert result["stable"] is False
            assert result["error"] is not None and "c" in result["error"]

    def test_mmc_invalid_rates(self) -> None:
        for lambda_, mu in [(-1, 3), (2, 0), (math.inf, 3), (math.nan, 3), (None, 3)]:
            result = mmc(lambda_, mu, 2)  # type: ignore[arg-type]

            assert result["stable"] is False
            assert result["error"] is not None
