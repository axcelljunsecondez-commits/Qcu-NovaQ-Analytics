"""Unit tests for optimization engine."""

from __future__ import annotations

import math
import unittest

from backend.queueing_engine.services.optimization import (
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
        self.assertAlmostEqual(rate, 87.0)

    def test_compute_waiting_cost_stable(self):
        cost = _compute_waiting_cost(10, 0.5, 100)
        self.assertEqual(cost, 500.0)

    def test_compute_waiting_cost_unstable(self):
        cost = _compute_waiting_cost(10, None, 100)
        self.assertIsNone(cost)

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

    def test_ternary_search_feasible_region_beyond_inf_band(self):
        def fn(c):
            return float("inf") if c < 31 else float(c)

        result = _ternary_search_c(fn, 1, 40)
        self.assertEqual(result, 31)

    def test_optimize_segment_finds_stable_plan_above_inf_band(self):
        result = optimize_segment(
            {"time": "t", "lambda": 30, "mu": 1, "c": 1},
            max_servers=50,
        )
        self.assertIsNotNone(result["c_optimal"])
        self.assertGreaterEqual(result["c_optimal"], 31)
        self.assertNotIn("Unable to find a stable staffing plan", result["recommendation"])

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

    def test_summarize_optimization_empty_branch_has_full_key_set(self):
        summary = summarize_optimization([])
        for key in [
            "total_waiting_cost_current",
            "total_waiting_cost_optimal",
            "total_abandonment_cost_current",
            "total_abandonment_cost_optimal",
        ]:
            self.assertIn(key, summary)
            self.assertEqual(summary[key], None if key.endswith("optimal") else 0.0)

    def test_build_recommendations_no_changes(self):
        rows = [
            {
                "time": "08:00",
                "recommendation": "Maintain current staffing at 08:00.",
                "current_stable": True, "optimized_stable": True, "c_optimal": 2,
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
        self.assertEqual(rate, 87.0)

    def test_compute_waiting_cost_nan_lambda(self):
        cost = _compute_waiting_cost(math.nan, 0.5, 100)
        self.assertIsNone(cost)

    def test_compute_waiting_cost_inf_wq(self):
        cost = _compute_waiting_cost(10, math.inf, 100)
        self.assertIsNone(cost)

    def test_stable_baseline_behavior_remains_feasible(self):
        result = optimize_segment(
            {"time": "stable", "lambda": 15, "mu": 10, "c": 2},
            target_utilization=0.7,
            max_servers=5,
        )
        self.assertTrue(result["current_stable"])
        self.assertEqual(result["feasibility_status"], "FEASIBLE")
        self.assertIsNotNone(result["cost_current"])
        self.assertLessEqual(result["rho_optimal"], 0.7)

    def test_unstable_baseline_continues_to_feasible_candidate(self):
        result = optimize_segment(
            {"time": "overload", "lambda": 20.214, "mu": 10, "c": 2},
            target_utilization=0.7,
            max_servers=5,
        )
        self.assertEqual(result["c_current"], 2)
        self.assertAlmostEqual(result["rho_current"], 1.0107)
        self.assertFalse(result["current_stable"])
        self.assertEqual(result["feasibility_status"], "FEASIBLE")
        self.assertEqual(result["c_optimal"], 3)
        self.assertTrue(result["optimized_stable"])
        self.assertLessEqual(result["rho_optimal"], 0.7)

    def test_unstable_baseline_without_feasible_candidate_is_explicit(self):
        result = optimize_segment(
            {"time": "overload", "lambda": 20.214, "mu": 10, "c": 2},
            target_utilization=0.7,
            max_servers=2,
        )
        self.assertFalse(result["current_stable"])
        self.assertEqual(result["feasibility_status"], "NO_FEASIBLE_CONFIGURATION")
        self.assertIsNone(result["c_optimal"])
        self.assertIn("model_stability", result["violated_constraints"])

    def test_configured_utilization_target_changes_recommendation(self):
        segment = {"time": "target", "lambda": 20, "mu": 10, "c": 2}
        at_seventy = optimize_segment(segment, target_utilization=0.7, max_servers=6)
        at_fifty = optimize_segment(segment, target_utilization=0.5, max_servers=6)
        self.assertEqual(at_seventy["c_optimal"], 3)
        self.assertEqual(at_fifty["c_optimal"], 4)
        self.assertEqual(at_fifty["effective_constraints"]["target_utilization"], 0.5)
        self.assertLessEqual(at_fifty["rho_optimal"], 0.5)

    def test_unstable_baseline_does_not_fabricate_wait_or_finance(self):
        result = optimize_segment(
            {"time": "overload", "lambda": 20.214, "mu": 10, "c": 2},
            target_utilization=0.7,
            max_servers=5,
        )
        self.assertIsNone(result["Wq_current"])
        self.assertIsNone(result["Lq_current"])
        self.assertIsNone(result["waiting_cost_current"])
        self.assertIsNone(result["cost_current"])
        self.assertIsNone(result["delta_cost"])
        self.assertIsNotNone(result["Wq_optimal"])
        self.assertIsNotNone(result["cost_optimal"])

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
        self.assertIsNone(summary["total_current_cost"])

    def test_optimize_segment_theta_uses_erlang_a(self):
        result = optimize_segment(
            {"time": "t", "lambda": 9, "mu": 10, "c": 1, "theta": 0.5},
            max_servers=5,
        )
        result_no_theta = optimize_segment(
            {"time": "t", "lambda": 9, "mu": 10, "c": 1},
            max_servers=5,
        )
        self.assertIsNotNone(result["Wq_current"])
        self.assertIsNotNone(result_no_theta["Wq_current"])
        self.assertLess(result["Wq_current"], result_no_theta["Wq_current"])

    def test_optimize_segment_theta_zero_falls_back_to_mm1(self):
        result = optimize_segment(
            {"time": "t", "lambda": 2, "mu": 5, "c": 1, "theta": 0},
            max_servers=5,
        )
        result_no_theta = optimize_segment(
            {"time": "t", "lambda": 2, "mu": 5, "c": 1},
            max_servers=5,
        )
        self.assertEqual(result["Wq_current"], result_no_theta["Wq_current"])

    def test_queue_metrics_theta_dispatches_to_erlang_a(self):
        from backend.queueing_engine.services.optimization import _queue_metrics

        with_theta = _queue_metrics(9, 10, 1, theta=0.5)
        without_theta = _queue_metrics(9, 10, 1)
        self.assertLess(with_theta["Wq"], without_theta["Wq"])
        self.assertIn("theta", with_theta)

    def test_queue_metrics_theta_precedes_variance(self):
        from backend.queueing_engine.services.optimization import _queue_metrics

        result = _queue_metrics(9, 10, 1, variance=0.1, theta=0.5)
        self.assertIn("theta", result)

    def test_queue_metrics_theta_precedes_capacity(self):
        from backend.queueing_engine.services.optimization import _queue_metrics

        result = _queue_metrics(9, 10, 1, K=5, theta=0.5)
        self.assertIn("theta", result)

    def test_queue_metrics_theta_zero_falls_through(self):
        from backend.queueing_engine.services.optimization import _queue_metrics

        result = _queue_metrics(2, 5, 1, variance=0.1, theta=0)
        self.assertNotIn("theta", result)

    def test_waste_reduction_skipped_when_savings_negative(self):
        result = optimize_segment(
            {"time": "t", "lambda": 2, "mu": 5, "c": 2},
            max_servers=5,
            default_server_cost=87.0,
            customer_waiting_cost=2000.0,
        )
        self.assertEqual(result["c_optimal"], 2)
        self.assertNotIn("Remove 1 server", result["recommendation"])
        self.assertNotIn("save", result["recommendation"])

    def test_waste_reduction_applies_when_savings_positive(self):
        result = optimize_segment(
            {"time": "t", "lambda": 2, "mu": 5, "c": 2},
            max_servers=5,
            default_server_cost=87.0,
            customer_waiting_cost=100.0,
        )
        self.assertEqual(result["c_optimal"], 1)
        self.assertIn("Remove 1 server", result["recommendation"])
        self.assertLess(result["cost_optimal"], result["cost_current"])


if __name__ == "__main__":
    unittest.main()
