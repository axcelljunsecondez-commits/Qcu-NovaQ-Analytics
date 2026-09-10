"""Regression tests for analytical queueing formulas."""

from __future__ import annotations

import math
import unittest

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from backend.queueing_engine.models import erlang_a, mgc, mgck, mm1, mmc, mmc_priority, mmck


class QueueModelTests(unittest.TestCase):
    def assert_close(self, actual, expected, places=6):
        self.assertAlmostEqual(actual, expected, places=places)

    def test_mm1_known_values(self):
        result = mm1(2, 3)

        self.assertTrue(result["stable"])
        self.assert_close(result["rho"], 2 / 3)
        self.assert_close(result["L"], 2.0)
        self.assert_close(result["Lq"], 4 / 3)
        self.assert_close(result["W"], 1.0)
        self.assert_close(result["Wq"], 2 / 3)

    def test_mmc_stable_system(self):
        result = mmc(4, 3, 2)

        self.assertTrue(result["stable"])
        self.assert_close(result["rho"], 2 / 3)
        self.assertGreater(result["Lq"], 0)
        self.assertGreater(result["Wq"], 0)

    def test_unstable_infinite_capacity_system_reports_error(self):
        result = mmc(10, 5, 2)

        self.assertFalse(result["stable"])
        self.assertIn("Unstable", result["error"])

    def test_mgc_matches_mmc_with_exponential_variance(self):
        base = mmc(4, 3, 2)
        general = mgc(4, 3, 2, service_variance=1 / (3**2))

        self.assertTrue(general["stable"])
        self.assert_close(general["Wq"], base["Wq"])
        self.assert_close(general["Lq"], base["Lq"])

    def test_mmck_reports_blocking_probability(self):
        result = mmck(10, 3, 2, 5)

        self.assertTrue(result["stable"])
        self.assertGreaterEqual(result["blocking_probability"], 0)
        self.assertLessEqual(result["blocking_probability"], 1)
        self.assertLessEqual(result["effective_lambda"], 10)

    def test_mgck_rejects_capacity_less_than_servers(self):
        result = mgck(10, 3, 4, 0.1, 3)

        self.assertFalse(result["stable"])
        self.assertIn("K must be >= c", result["error"])

    def test_invalid_rates_do_not_raise(self):
        result = mm1(math.inf, 3)

        self.assertFalse(result["stable"])
        self.assertIn("finite", result["error"])

    # ── Property-based tests ─────────────────────────────────────────────

    @settings(max_examples=300, deadline=None)
    @given(st.floats(1, 50), st.floats(1, 50), st.integers(1, 10))
    def test_stability_correctness(self, lambda_, mu, c):
        """Stable when λ/(cμ) < 0.95; unstable when λ/(cμ) > 1.05."""
        load = lambda_ / (c * mu)
        assume(load < 0.95 or load > 1.05)

        result = mmc(lambda_, mu, c)

        if load < 0.95:
            self.assertTrue(result["stable"])
            self.assertIsNotNone(result.get("Wq"))
            wq = result["Wq"]
            self.assertTrue(math.isfinite(wq))
            self.assertGreater(wq, 0)
        else:
            self.assertFalse(result["stable"])

    @settings(max_examples=300, deadline=None)
    @given(st.floats(0.1, 10), st.floats(1, 50))
    def test_mmc_vs_mm1_equivalence(self, lambda_, mu):
        """With c=1, mmc matches mm1 for stable systems."""
        assume(lambda_ / mu < 0.95)
        result_c = mmc(lambda_, mu, 1)
        result_1 = mm1(lambda_, mu)
        assert result_c["stable"] and result_1["stable"]
        self.assertAlmostEqual(result_c["Wq"], result_1["Wq"], places=4)

    @settings(max_examples=300, deadline=None)
    @given(st.floats(1, 20), st.floats(2, 50), st.integers(2, 8))
    def test_mgc_variance_zero_deterministic(self, lambda_, mu, c):
        """Deterministic service (var=0) has lower or equal Wq than exponential."""
        assume(lambda_ / (c * mu) < 0.95)
        result_mm = mmc(lambda_, mu, c)
        result_mg = mgc(lambda_, mu, c, service_variance=0.0)
        assume(result_mg.get("stable"))
        self.assertLessEqual(result_mg["Wq"], result_mm["Wq"] * 1.001)

    @settings(max_examples=300, deadline=None)
    @given(st.floats(1, 30), st.floats(2, 50), st.integers(1, 8))
    def test_mmck_no_buffer_queue(self, lambda_, mu, c):
        """K=c means no waiting room → Lq ≈ 0."""
        result = mmck(lambda_, mu, c, K=c)
        assume(result.get("stable"))
        self.assertLess(result["Lq"], 0.001)

    @settings(max_examples=300, deadline=None)
    @given(st.floats(1, 20), st.floats(3, 50), st.integers(2, 6))
    def test_monotonicity_wq_server_count(self, lambda_, mu, c):
        """More servers never increase waiting time."""
        assume(lambda_ / (c * mu) < 0.95)
        result_c = mmc(lambda_, mu, c)
        result_c1 = mmc(lambda_, mu, c + 1)
        assume(result_c.get("stable") and result_c1.get("stable"))
        self.assertGreaterEqual(result_c["Wq"], result_c1["Wq"])

    @settings(max_examples=300, deadline=None)
    @given(st.floats(1, 20), st.floats(3, 50), st.integers(2, 8))
    def test_littles_law_compliance(self, lambda_, mu, c):
        """For stable M/M/c: |L - λ·W| / max(L, 1e-6) < 0.01."""
        assume(lambda_ / (c * mu) < 0.95)
        result = mmc(lambda_, mu, c)
        assume(result.get("stable"))
        lhs = result["L"]
        rhs = result["lambda"] if "lambda" in result else lambda_
        rhs *= result["W"]
        err = abs(lhs - rhs) / max(lhs, 1e-6)
        self.assertLess(err, 0.01)

    @settings(max_examples=300, deadline=None)
    @given(
        st.floats(1, 30),
        st.floats(2, 40),
        st.integers(2, 6),
        st.integers(1, 10),
    )
    def test_mmck_finite_capacity_reduces_lq(self, lambda_, mu, c, extra):
        """Finite capacity queue cannot exceed infinite capacity Lq."""
        K = c + extra
        result_mmck = mmck(lambda_, mu, c, K=K)
        result_mmc = mmc(lambda_, mu, c)
        assume(result_mmck.get("stable"))
        assume(result_mmc.get("stable"))
        self.assertLessEqual(result_mmck["Lq"], result_mmc["Lq"] + 0.01)

    # ── Erlang-A tests ──────────────────────────────────────────────────────

    def test_erlang_a_valid(self):
        result = erlang_a(10, 4, 3, 0.5)

        expected_keys = {"rho", "L", "Lq", "W", "Wq", "stable", "error",
                         "theta", "lambda_eff", "abandonment_rate"}
        self.assertTrue(expected_keys.issubset(result.keys()))
        self.assertTrue(result["stable"])
        self.assertGreater(result["Lq"], 0)
        self.assertGreater(result["lambda_eff"], 0)
        self.assertGreater(result["abandonment_rate"], 0)
        self.assertLess(result["abandonment_rate"], 1)

    def test_erlang_a_theta_zero_matches_mmc(self):
        mmc_result = mmc(10, 4, 3)
        erl_result = erlang_a(10, 4, 3, 0.0)

        self.assertTrue(erl_result["stable"])
        self.assert_close(erl_result["Lq"], mmc_result["Lq"])
        self.assert_close(erl_result["Wq"], mmc_result["Wq"])

    def test_erlang_a_invalid_inputs(self):
        result = erlang_a(-1, 4, 3, 0.5)
        self.assertFalse(result["stable"])

    # ── Priority queue tests ────────────────────────────────────────────────

    def test_priority_wq1_lt_wq2(self):
        result = mmc_priority(6, 4, 3, 4)

        self.assertTrue(result["stable"])
        self.assertLess(result["Wq_priority"], result["Wq_regular"])

    def test_priority_stable_check(self):
        result = mmc_priority(100, 50, 3, 4)

        self.assertFalse(result["stable"])


if __name__ == "__main__":
    unittest.main()

