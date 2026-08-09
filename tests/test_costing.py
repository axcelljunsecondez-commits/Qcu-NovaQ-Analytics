"""Unit tests for cost calculation engine."""

from __future__ import annotations

import math
import unittest

import pandas as pd

from config import UNSTABLE_FIXED_COST
from costing import (
    compute_all_costs,
    compute_cost_summary,
    compute_segment_costs,
)


class CostingTests(unittest.TestCase):
    def test_compute_segment_costs_basic(self):
        costs = compute_segment_costs(
            servers=3,
            arrival_rate=10,
            wq=0.5,
            cost_per_server_hr=87,
            cost_per_wait_hr=100,
            cost_per_abandonment=60,
            abandonment_rate=0.1,
            hours_per_interval=1,
        )
        self.assertIsNotNone(costs["server_cost"])
        self.assertIsNotNone(costs["wait_cost"])
        self.assertIsNotNone(costs["total_cost"])
        self.assertAlmostEqual(costs["server_cost"], 261.0)
        self.assertAlmostEqual(costs["wait_cost"], 500.0)
        self.assertAlmostEqual(costs["abandonment_cost"], 60.0)

    def test_compute_segment_costs_none_inputs(self):
        costs = compute_segment_costs(
            servers=None,
            arrival_rate=10,
            wq=0.5,
        )
        self.assertIsNone(costs["server_cost"])
        self.assertIsNone(costs["total_cost"])

    def test_compute_segment_costs_infinite_wq(self):
        costs = compute_segment_costs(
            servers=2,
            arrival_rate=10,
            wq=float("inf"),
            cost_per_server_hr=87,
            cost_per_wait_hr=100,
            hours_per_interval=1,
        )
        self.assertEqual(costs["server_cost"], 174.0)
        self.assertGreater(costs["wait_cost"], 0)

    def test_compute_all_costs_empty(self):
        result = compute_all_costs(pd.DataFrame())
        self.assertTrue(result.empty)

    def test_compute_all_costs_none(self):
        result = compute_all_costs(None)
        self.assertTrue(result.empty)

    def test_compute_all_costs_with_data(self):
        df = pd.DataFrame({
            "time": ["08:00"],
            "c": [3],
            "lambda": [10],
            "Wq": [0.5],
        })
        result = compute_all_costs(df)
        self.assertIn("server_cost", result.columns)
        self.assertIn("total_cost", result.columns)

    def test_compute_cost_summary_empty(self):
        summary = compute_cost_summary(pd.DataFrame())
        self.assertEqual(summary["total_cost"], 0.0)

    def test_compute_cost_summary_with_data(self):
        df = pd.DataFrame({
            "time": ["08:00", "09:00"],
            "c": [3, 4],
            "lambda": [10, 15],
            "Wq": [0.5, 0.3],
        })
        summary = compute_cost_summary(df)
        self.assertGreater(summary["total_cost"], 0)
        self.assertGreater(summary["total_server_cost"], 0)

    def test_compute_segment_costs_nan_servers(self):
        costs = compute_segment_costs(
            servers=float("nan"),
            arrival_rate=10,
            wq=0.5,
        )
        self.assertIsNone(costs["server_cost"])

    def test_compute_segment_costs_negative_arrival_rate(self):
        costs = compute_segment_costs(
            servers=2,
            arrival_rate=-10,
            wq=0.5,
            cost_per_server_hr=87,
            cost_per_wait_hr=100,
            hours_per_interval=1,
        )
        self.assertIsNotNone(costs["server_cost"])

    def test_compute_all_costs_with_nan(self):
        df = pd.DataFrame({
            "time": ["08:00"],
            "c": [3],
            "lambda": [float("nan")],
            "Wq": [0.5],
        })
        result = compute_all_costs(df)
        self.assertFalse(result.empty)

    def test_compute_cost_summary_all_none(self):
        df = pd.DataFrame({
            "time": ["08:00"],
            "c": [None],
            "lambda": [None],
            "Wq": [None],
        })
        summary = compute_cost_summary(df)
        self.assertEqual(summary["total_cost"], 0.0)

    def test_compute_segment_costs_infinite_wq_uses_fixed_penalty(self):
        costs = compute_segment_costs(
            servers=2,
            arrival_rate=10,
            wq=float("inf"),
            cost_per_server_hr=87,
            cost_per_wait_hr=100,
            hours_per_interval=1,
        )
        self.assertEqual(costs["wait_cost"], UNSTABLE_FIXED_COST)
        self.assertAlmostEqual(costs["total_cost"], 174.0 + UNSTABLE_FIXED_COST)

    def test_compute_segment_costs_nan_wq_uses_fixed_penalty(self):
        costs = compute_segment_costs(
            servers=2,
            arrival_rate=10,
            wq=float("nan"),
            cost_per_server_hr=87,
            cost_per_wait_hr=100,
            hours_per_interval=1,
        )
        self.assertEqual(costs["wait_cost"], UNSTABLE_FIXED_COST)
        self.assertAlmostEqual(costs["total_cost"], 174.0 + UNSTABLE_FIXED_COST)

    def test_compute_all_costs_unstable_row_gets_penalty(self):
        df = pd.DataFrame({
            "time": ["08:00"],
            "c": [2],
            "lambda": [10],
            "Wq": [float("nan")],
        })
        result = compute_all_costs(
            df,
            cost_per_server_hr=87,
            cost_per_wait_hr=100,
            cost_per_abandonment=60,
            abandonment_rate=0.1,
            hours_per_interval=1,
        )
        self.assertEqual(result.loc[0, "wait_cost"], UNSTABLE_FIXED_COST)
        self.assertAlmostEqual(result.loc[0, "total_cost"], 174.0 + UNSTABLE_FIXED_COST + 60.0)

    def test_costing_matches_optimization_for_unstable_segment(self):
        from optimization import optimize_segment

        opt = optimize_segment({"time": "t", "lambda": 30, "mu": 10, "c": 1})
        costs = compute_segment_costs(
            servers=1,
            arrival_rate=30,
            wq=float("nan"),
            cost_per_server_hr=1.0,
            cost_per_wait_hr=100,
            cost_per_abandonment=0,
            abandonment_rate=0,
            hours_per_interval=1,
        )
        self.assertAlmostEqual(opt["cost_current"], costs["total_cost"], places=2)

    def test_costing_matches_optimization_for_stable_segment(self):
        from optimization import optimize_segment

        opt = optimize_segment({"time": "t", "lambda": 2, "mu": 5, "c": 1})
        costs = compute_segment_costs(
            servers=1,
            arrival_rate=2,
            wq=opt["Wq_current"],
            cost_per_server_hr=1.0,
            cost_per_wait_hr=100,
            cost_per_abandonment=0,
            abandonment_rate=0,
            hours_per_interval=1,
        )
        self.assertAlmostEqual(opt["cost_current"], costs["total_cost"], places=2)


if __name__ == "__main__":
    unittest.main()
