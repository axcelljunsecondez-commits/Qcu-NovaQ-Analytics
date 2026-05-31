"""Unit tests for optimization engine."""

from __future__ import annotations

import math
import unittest

from optimization import (
    _compute_abandonment_cost,
    _compute_waiting_cost,
    _format_recommendation,
    _safe_diff,
    _ternary_search_c,
    build_recommendations,
    compute_blended_rate,
    optimize_segment,
    optimize_segments,
    summarize_optimization,
)


class OptimizationTests(unittest.TestCase):
    def test_compute_blended_rate_mixed(self):
        rate = compute_blended_rate(6, 2, 8)
        expected = (6 * 87 + 2 * 109) / 8
        self.assertAlmostEqual(rate, expected)

    def test_compute_blended_rate_fallback(self):
        rate = compute_blended_rate(0, 0, 0)
        self.assertAlmostEqual(rate, 1.0)

    def test_compute_waiting_cost_stable(self):
        cost = _compute_waiting_cost(10, 0.5, 100)
        self.assertEqual(cost, 500.0)

    def test_compute_waiting_cost_unstable(self):
        cost = _compute_waiting_cost(10, None, 100)
        self.assertEqual(cost, 5000.0)

    def test_compute_abandonment_cost(self):
        cost = _compute_abandonment_cost(100, 0.1, 60)
        self.assertEqual(cost, 600.0)

    def test_compute_abandonment_cost_zero_rate(self):
        cost = _compute_abandonment_cost(100, 0.0, 60)
        self.assertEqual(cost, 0.0)

    def test_safe_diff_both_present(self):
        self.assertEqual(_safe_diff(5, 3), 2)

    def test_safe_diff_none(self):
        self.assertIsNone(_safe_diff(None, 3))
        self.assertIsNone(_safe_diff(5, None))

    def test_format_recommendation_add(self):
        rec = _format_recommendation("08:00", 2, 4)
        self.assertIn("Add 2 servers", rec)

    def test_format_recommendation_remove(self):
        rec = _format_recommendation("08:00", 4, 2)
        self.assertIn("Remove 2 servers", rec)

    def test_format_recommendation_maintain(self):
        rec = _format_recommendation("08:00", 3, 3)
        self.assertIn("Maintain", rec)

    def test_ternary_search_convex(self):
        def fn(c):
            return abs(c - 5)

        result = _ternary_search_c(fn, 1, 10)
        self.assertEqual(result, 5)

    def test_ternary_search_all_inf(self):
        def fn(c):
            return float("inf")

        result = _ternary_search_c(fn, 1, 10)
        self.assertIsNone(result)

    def test_optimize_segment_stable_mm1(self):
        result = optimize_segment(
            {"time": "test", "lambda": 2, "mu": 5, "c": 1},
            max_servers=5,
        )
        self.assertIn("c_current", result)
        self.assertIn("c_optimal", result)
        self.assertIsNotNone(result["c_optimal"])

    def test_optimize_segment_invalid_segment(self):
        result = optimize_segment("not a dict")
        self.assertIn("Invalid", result["warning"])

    def test_optimize_segments_empty(self):
        self.assertEqual(optimize_segments([]), [])

    def test_summarize_optimization_empty(self):
        summary = summarize_optimization([])
        self.assertEqual(summary["total_current_cost"], 0.0)

    def test_build_recommendations_no_changes(self):
        rows = [
            {
                "time": "08:00",
                "recommendation": "Maintain current staffing at 08:00.",
                "delta_c": 0,
                "cost_current": 100,
                "cost_optimal": 100,
                "rho_current": 0.5,
                "rho_optimal": 0.5,
                "Wq_current": 0.1,
                "Wq_optimal": 0.1,
                "waiting_cost_current": 10,
                "waiting_cost_optimal": 10,
            }
        ]
        recs = build_recommendations(rows)
        self.assertTrue(any("No staffing changes" in r for r in recs))

    def test_optimize_segment_nan_lambda(self):
        result = optimize_segment(
            {"time": "test", "lambda": math.nan, "mu": 5, "c": 1},
        )
        self.assertIn("Invalid", result.get("warning", ""))

    def test_optimize_segment_inf_lambda(self):
        result = optimize_segment(
            {"time": "test", "lambda": math.inf, "mu": 5, "c": 1},
        )
        self.assertIn("Invalid", result.get("warning", ""))

    def test_optimize_segment_nan_mu(self):
        result = optimize_segment(
            {"time": "test", "lambda": 10, "mu": math.nan, "c": 2},
        )
        self.assertIn("Invalid", result.get("warning", ""))

    def test_optimize_segment_inf_mu(self):
        result = optimize_segment(
            {"time": "test", "lambda": 10, "mu": math.inf, "c": 2},
        )
        self.assertIn("Invalid", result.get("warning", ""))

    def test_optimize_segment_negative_mu(self):
        result = optimize_segment(
            {"time": "test", "lambda": 10, "mu": -5, "c": 2},
        )
        self.assertIn("Invalid", result.get("warning", ""))

    def test_optimize_segment_nan_c(self):
        result = optimize_segment(
            {"time": "test", "lambda": 10, "mu": 5, "c": math.nan},
        )
        self.assertIn("Invalid", result.get("warning", ""))

    def test_compute_blended_rate_nan_hours(self):
        rate = compute_blended_rate(math.nan, 0, 0)
        self.assertIsNotNone(rate)

    def test_compute_blended_rate_negative_hours(self):
        rate = compute_blended_rate(-5, 2, -3)
        self.assertEqual(rate, 1.0)

    def test_compute_waiting_cost_nan_lambda(self):
        cost = _compute_waiting_cost(math.nan, 0.5, 100)
        self.assertTrue(math.isnan(cost))

    def test_compute_waiting_cost_inf_wq(self):
        cost = _compute_waiting_cost(10, math.inf, 100)
        self.assertTrue(math.isinf(cost))

    def test_summarize_optimization_nan_in_rows(self):
        rows = [
            {
                "cost_current": None,
                "cost_optimal": None,
                "rho_current": None,
                "rho_optimal": None,
                "Wq_current": None,
                "Wq_optimal": None,
                "waiting_cost_current": None,
                "waiting_cost_optimal": None,
                "abandonment_cost_current": None,
                "abandonment_cost_optimal": None,
                "delta_c": None,
            }
        ]
        summary = summarize_optimization(rows)
        self.assertEqual(summary["total_current_cost"], 0.0)


if __name__ == "__main__":
    unittest.main()
