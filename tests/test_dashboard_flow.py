"""Regression tests for dashboard data flow helpers."""

from __future__ import annotations

import unittest
from importlib.util import find_spec

import pandas as pd

from app_page_utils import sample_segments, to_segment_records, validate_and_normalize
from data_processing import compute_kpis, process_segments
from optimization import optimize_segments


class DashboardFlowTests(unittest.TestCase):
    def test_validate_and_normalize_accepts_current_schema(self):
        valid, message, normalized = validate_and_normalize(sample_segments())

        self.assertTrue(valid, message)
        self.assertEqual(["time", "lambda", "mu", "c", "variance", "K"], list(normalized.columns))
        self.assertTrue(pd.api.types.is_integer_dtype(normalized["c"]))

    def test_validate_and_normalize_rejects_missing_required_column(self):
        valid, message, _ = validate_and_normalize(pd.DataFrame({"time": ["08:00"], "lambda": [1], "mu": [2]}))

        self.assertFalse(valid)
        self.assertIn("c", message)

    def test_process_segments_and_kpis(self):
        valid, _, normalized = validate_and_normalize(sample_segments())
        self.assertTrue(valid)

        results = process_segments(to_segment_records(normalized))
        kpis = compute_kpis(results)

        self.assertEqual(len(results), len(normalized))
        self.assertIn("rho", results.columns)
        self.assertIn("avg_utilization", kpis)

    def test_optimization_produces_recommendation_rows(self):
        valid, _, normalized = validate_and_normalize(sample_segments())
        self.assertTrue(valid)

        comparison = pd.DataFrame(optimize_segments(to_segment_records(normalized), max_servers=10))

        self.assertEqual(len(comparison), len(normalized))
        self.assertIn("c_optimal", comparison.columns)
        self.assertTrue(comparison["recommendation"].notna().all())

    def test_simulation_produces_summary(self):
        if find_spec("simpy") is None:
            self.skipTest("simpy is not installed in this Python environment")

        from backend.queueing_engine.simulation import simulate_segments, summarize_simulation

        rows = [{"time": "08:00-09:00", "lambda": 2.0, "mu": 3.0, "c": 1}]

        results = simulate_segments(rows, sim_hours=1.0, seed=123)
        summary = summarize_simulation(results)

        self.assertEqual(len(results), 1)
        self.assertIn("rho_sim", results[0])
        self.assertIn("avg_rho", summary)


if __name__ == "__main__":
    unittest.main()
