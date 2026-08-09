"""Unit tests for simulation engines (DES + Monte Carlo)."""

from __future__ import annotations

import math
import unittest

import pandas as pd

from backend.queueing_engine.simulation.simulation import (
    SegmentResult,
    _classify_status,
    mc_simulate_segment,
    mc_summarize_simulation,
    simulate_segment,
    simulate_segments,
    summarize_simulation,
    validate_with_simulation,
)


class ClassificationTests(unittest.TestCase):
    def test_classify_status_lean(self):
        self.assertEqual(_classify_status(0.3, 0, 20), "Lean")

    def test_classify_status_normal(self):
        self.assertEqual(_classify_status(0.7, 0, 20), "Normal")

    def test_classify_status_peak(self):
        self.assertEqual(_classify_status(0.85, 0, 20), "Peak")

    def test_classify_status_critical_by_utilization(self):
        self.assertEqual(_classify_status(0.95, 0, 20), "Critical")

    def test_classify_status_critical_by_queue_depth(self):
        self.assertEqual(_classify_status(0.3, 30, 20), "Critical")

    def test_classify_status_unstable(self):
        self.assertEqual(_classify_status(1.5, 0, 20), "Unstable")

    def test_classify_status_nan_rho(self):
        self.assertEqual(_classify_status(math.nan, 0, 20), "Lean")

    def test_classify_status_negative_rho(self):
        self.assertEqual(_classify_status(-1.0, 0, 20), "Lean")

    def test_classify_status_huge_rho(self):
        self.assertEqual(_classify_status(1e10, 0, 20), "Unstable")


class SimulationTests(unittest.TestCase):

    def test_simulate_segment_mm1_stable(self):
        result = simulate_segment(
            {"time": "test", "lambda": 2, "mu": 3, "c": 1},
            sim_hours=1.0,
            seed=42,
        )
        self.assertIsInstance(result, SegmentResult)
        self.assertIsNotNone(result.rho_sim)
        self.assertGreaterEqual(result.rho_sim, 0)
        self.assertGreater(result.served, 0)

    def test_simulate_segment_zero_arrivals(self):
        result = simulate_segment(
            {"time": "test", "lambda": 0, "mu": 3, "c": 1},
            sim_hours=1.0,
            seed=42,
        )
        self.assertEqual(result.rho_sim, 0.0)
        self.assertEqual(result.Lq_sim, 0.0)
        self.assertEqual(result.Wq_sim, 0.0)

    def test_simulate_segment_invalid(self):
        result = simulate_segment(
            {"time": "test", "mu": 3, "c": 1},
            sim_hours=1.0,
        )
        self.assertEqual(result.status, "ERROR")
        self.assertIsNotNone(result.error)

    def test_simulate_segments_empty(self):
        self.assertEqual(simulate_segments([]), [])

    def test_simulate_segments_none(self):
        self.assertEqual(simulate_segments(None), [])

    def test_summarize_simulation_empty(self):
        summary = summarize_simulation([])
        self.assertIsNone(summary["avg_rho"])

    def test_summarize_simulation_none(self):
        summary = summarize_simulation(None)
        self.assertIsNone(summary["avg_rho"])

    def test_mc_simulate_segment_stable(self):
        result = mc_simulate_segment(
            {"time": "test", "lambda": 2, "mu": 3, "c": 1},
            num_trials=100,
            seed=42,
        )
        self.assertIsNotNone(result["rho_mean"])
        self.assertIsNotNone(result["Wq_mean"])
        self.assertIsNotNone(result["failure_rate"])

    def test_mc_simulate_segment_invalid(self):
        result = mc_simulate_segment(
            {"time": "test", "mu": 3, "c": 1},
            num_trials=100,
        )
        self.assertEqual(result["status"], "ERROR")

    def test_mc_summarize_simulation_empty(self):
        summary = mc_summarize_simulation([])
        self.assertIsNone(summary["avg_rho"])

    def test_simulate_segment_nan_lambda(self):
        result = simulate_segment(
            {"time": "test", "lambda": math.nan, "mu": 3, "c": 1},
            sim_hours=1.0, seed=42,
        )
        self.assertEqual(result.status, "ERROR")

    def test_simulate_segment_inf_lambda(self):
        result = simulate_segment(
            {"time": "test", "lambda": math.inf, "mu": 3, "c": 1},
            sim_hours=1.0, seed=42,
        )
        self.assertEqual(result.status, "ERROR")

    def test_simulate_segment_nan_mu(self):
        result = simulate_segment(
            {"time": "test", "lambda": 2, "mu": math.nan, "c": 1},
            sim_hours=1.0, seed=42,
        )
        self.assertEqual(result.status, "ERROR")

    def test_simulate_segment_inf_mu(self):
        result = simulate_segment(
            {"time": "test", "lambda": 2, "mu": math.inf, "c": 1},
            sim_hours=1.0, seed=42,
        )
        self.assertEqual(result.status, "ERROR")

    def test_simulate_segment_negative_mu(self):
        result = simulate_segment(
            {"time": "test", "lambda": 2, "mu": -1, "c": 1},
            sim_hours=1.0, seed=42,
        )
        self.assertEqual(result.status, "ERROR")

    def test_mc_simulate_segment_nan_lambda(self):
        result = mc_simulate_segment(
            {"time": "test", "lambda": math.nan, "mu": 3, "c": 1},
            num_trials=10, seed=42,
        )
        self.assertEqual(result["status"], "ERROR")

    def test_mc_simulate_segment_inf_mu(self):
        result = mc_simulate_segment(
            {"time": "test", "lambda": 2, "mu": math.inf, "c": 1},
            num_trials=10, seed=42,
        )
        self.assertEqual(result["status"], "ERROR")

    def test_mc_simulate_segment_negative_mu(self):
        result = mc_simulate_segment(
            {"time": "test", "lambda": 2, "mu": -1, "c": 1},
            num_trials=10, seed=42,
        )
        self.assertEqual(result["status"], "ERROR")

    def test_validate_with_simulation_defaults_to_engine_failure_threshold(self):
        df = pd.DataFrame([
            {"time": "08:00", "lambda": 8.2, "mu": 10.0, "c_optimal": 1},
        ])
        result = validate_with_simulation(df, mc_trials=3000, seed=42)
        self.assertGreater(result.loc[0, "mc_failure_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
