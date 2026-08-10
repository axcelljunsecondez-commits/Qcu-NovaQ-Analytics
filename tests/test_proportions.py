"""Unit tests for the Wilson confidence interval and precision bands."""

from __future__ import annotations

import math
import unittest

from backend.queueing_engine.statistics.proportions import (
    failure_rate_precision,
    wilson_ci,
)


class WilsonCiTests(unittest.TestCase):

    def assert_in_01(self, lo, hi, hw):
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)
        self.assertGreaterEqual(hw, 0.0)

    def test_contains_point_estimate(self):
        lo, hi, hw = wilson_ci(k=5, n=100)
        p = 5 / 100
        self.assertLessEqual(lo, p)
        self.assertGreaterEqual(hi, p)
        self.assert_in_01(lo, hi, hw)

    def test_k_zero_lower_bound(self):
        lo, hi, hw = wilson_ci(k=0, n=100)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 0.05)
        self.assert_in_01(lo, hi, hw)

    def test_k_equal_n_upper_bound(self):
        lo, hi, hw = wilson_ci(k=100, n=100)
        self.assertEqual(hi, 1.0)
        self.assertGreater(lo, 0.95)
        self.assert_in_01(lo, hi, hw)

    def test_single_trial_no_nan(self):
        lo, hi, hw = wilson_ci(k=0, n=1)
        self.assertFalse(math.isnan(lo))
        self.assertFalse(math.isinf(hi))
        self.assert_in_01(lo, hi, hw)

    def test_single_trial_success(self):
        lo, hi, hw = wilson_ci(k=1, n=1)
        self.assertEqual(hi, 1.0)
        self.assertFalse(math.isnan(lo))
        self.assert_in_01(lo, hi, hw)

    def test_zero_trials_returns_none(self):
        self.assertEqual(wilson_ci(k=0, n=0), (None, None, None))
        self.assertEqual(wilson_ci(k=5, n=-1), (None, None, None))

    def test_large_n_narrows_interval(self):
        lo_small, hi_small, hw_small = wilson_ci(k=50, n=200)
        lo_large, hi_large, hw_large = wilson_ci(k=5000, n=20000)
        self.assertLess(hw_large, hw_small)
        self.assertLess(hw_large, 0.01)
        self.assert_in_01(lo_small, hi_small, hw_small)
        self.assert_in_01(lo_large, hi_large, hw_large)

    def test_half_width_is_half_range(self):
        lo, hi, hw = wilson_ci(k=7, n=300)
        self.assertAlmostEqual(hw, (hi - lo) / 2, places=12)

    def test_k_clamped(self):
        lo, hi, hw = wilson_ci(k=-3, n=10)
        self.assertEqual(lo, 0.0)
        self.assert_in_01(lo, hi, hw)


class PrecisionBandTests(unittest.TestCase):

    def test_none(self):
        self.assertIsNone(failure_rate_precision(None))

    def test_high(self):
        self.assertEqual(failure_rate_precision(0.0), "high")
        self.assertEqual(failure_rate_precision(0.03), "high")

    def test_moderate(self):
        self.assertEqual(failure_rate_precision(0.031), "moderate")
        self.assertEqual(failure_rate_precision(0.05), "moderate")

    def test_low(self):
        self.assertEqual(failure_rate_precision(0.051), "low")
        self.assertEqual(failure_rate_precision(0.14), "low")


if __name__ == "__main__":
    unittest.main()
