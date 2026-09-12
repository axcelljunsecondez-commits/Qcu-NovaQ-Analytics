"""Unit tests for simulation engines (DES + Monte Carlo)."""

from __future__ import annotations

import math
import unittest

import pandas as pd

from backend.queueing_engine.simulation.simulation import (
    MC_DEFAULT_TRIALS,
    SegmentResult,
    _classify_status,
    mc_simulate_segment,
    mc_summarize_simulation,
    simulate_segment,
    simulate_segments,
    summarize_simulation,
    trace_simulate_segments,
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

    def test_trace_is_seeded_and_contains_ordered_events(self):
        segments = [{"time": "test", "lambda": 6, "mu": 8, "c": 2}]
        first = trace_simulate_segments(segments, trace_hours=1, seed=42)
        second = trace_simulate_segments(segments, trace_hours=1, seed=42)
        self.assertEqual(first, second)
        self.assertGreater(first["event_count"], 0)
        self.assertEqual(first["event_count"], len(first["trace"]))
        self.assertEqual(
            {event["type"] for event in first["trace"]},
            {"arrival", "service_start", "service_end"},
        )
        self.assertEqual(
            [event["t"] for event in first["trace"]],
            sorted(event["t"] for event in first["trace"]),
        )
        for event in first["trace"]:
            self.assertEqual(
                set(event),
                {"t", "type", "segment_id", "customer_id", "server_id", "queue_len_after"},
            )
            self.assertGreater(event["customer_id"], 0)
            self.assertGreaterEqual(event["queue_len_after"], 0)

    def test_trace_customer_lifecycle_and_accounting(self):
        result = trace_simulate_segments(
            [{"time": "test", "lambda": 12, "mu": 8, "c": 2}],
            trace_hours=1,
            seed=17,
        )
        events_by_customer: dict[int, list[dict]] = {}
        for event in result["trace"]:
            events_by_customer.setdefault(event["customer_id"], []).append(event)

        for events in events_by_customer.values():
            types = [event["type"] for event in events]
            self.assertEqual(types[0], "arrival")
            self.assertEqual(types.count("arrival"), 1)
            if "service_end" in types:
                self.assertIn("service_start", types)
                self.assertLess(types.index("service_start"), types.index("service_end"))

        arrived = set(events_by_customer)
        started = {
            event["customer_id"] for event in result["trace"]
            if event["type"] == "service_start"
        }
        served = {
            event["customer_id"] for event in result["trace"]
            if event["type"] == "service_end"
        }
        waiting = arrived - started
        serving = started - served
        self.assertEqual(len(arrived), len(waiting) + len(serving) + len(served))
        self.assertFalse(result["abandonment_supported"])
        self.assertEqual(result["segments"][0]["queue_structure"], "shared")

    def test_trace_uses_configured_server_count_for_one_three_and_five_servers(self):
        for server_count in (1, 3, 5):
            with self.subTest(server_count=server_count):
                result = trace_simulate_segments(
                    [{"time": "test", "lambda": 40, "mu": 10, "c": server_count}],
                    trace_hours=0.5,
                    seed=23,
                )
                self.assertEqual(result["segments"][0]["c"], server_count)
                server_ids = {
                    event["server_id"] for event in result["trace"]
                    if event["server_id"] is not None
                }
                self.assertTrue(server_ids)
                self.assertTrue(all(0 <= server_id < server_count for server_id in server_ids))

    def test_trace_respects_event_cap(self):
        result = trace_simulate_segments(
            [{"time": "test", "lambda": 20, "mu": 8, "c": 2}],
            trace_hours=2,
            max_events=3,
            seed=42,
        )
        self.assertEqual(result["event_count"], 3)
        self.assertTrue(result["truncated"])

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
        self.assertIn("failure_rate_ci_lower", result)
        self.assertIn("failure_rate_ci_upper", result)
        self.assertIn("failure_rate_ci_half_width", result)
        self.assertIn("failure_rate_precision", result)
        self.assertIn("failure_rate_adequate", result)

    def test_mc_simulate_segment_failure_rate_ci_bounds(self):
        result = mc_simulate_segment(
            {"time": "test", "lambda": 2, "mu": 3, "c": 1},
            num_trials=500,
            seed=42,
        )
        lo = result["failure_rate_ci_lower"]
        hi = result["failure_rate_ci_upper"]
        hw = result["failure_rate_ci_half_width"]
        p = result["failure_rate"]
        self.assertIsNotNone(lo)
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)
        self.assertLessEqual(lo, p)
        self.assertGreaterEqual(hi, p)
        self.assertAlmostEqual(hw, (hi - lo) / 2, places=4)
        self.assertEqual(result["failure_rate_adequate"], hw <= 0.05)
        self.assertIn(result["failure_rate_precision"], {"high", "moderate", "low"})

    def test_mc_simulate_segment_zero_failures_ci_lower_zero(self):
        result = mc_simulate_segment(
            {"time": "test", "lambda": 0, "mu": 3, "c": 1},
            num_trials=200,
            seed=42,
        )
        self.assertEqual(result["failure_rate"], 0.0)
        self.assertEqual(result["failure_rate_ci_lower"], 0.0)
        self.assertIsNotNone(result["failure_rate_ci_upper"])

    def test_mc_simulate_segment_error_ci_fields_none(self):
        result = mc_simulate_segment(
            {"time": "test", "mu": 3, "c": 1},
            num_trials=100,
        )
        self.assertEqual(result["status"], "ERROR")
        self.assertIsNone(result["failure_rate_ci_lower"])
        self.assertIsNone(result["failure_rate_ci_upper"])
        self.assertIsNone(result["failure_rate_ci_half_width"])
        self.assertIsNone(result["failure_rate_precision"])
        self.assertFalse(result["failure_rate_adequate"])

    def test_mc_default_trials_is_two_thousand(self):
        self.assertEqual(MC_DEFAULT_TRIALS, 2000)

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

    def test_validate_with_simulation_exposes_failure_rate_ci_columns(self):
        df = pd.DataFrame([
            {"time": "08:00", "lambda": 8.2, "mu": 10.0, "c_optimal": 1},
        ])
        result = validate_with_simulation(df, mc_trials=2000, seed=42)
        for col in [
            "mc_failure_rate_ci_lower",
            "mc_failure_rate_ci_upper",
            "mc_failure_rate_ci_half_width",
            "mc_failure_rate_precision",
            "mc_failure_rate_adequate",
        ]:
            self.assertIn(col, result.columns)
        lo = result.loc[0, "mc_failure_rate_ci_lower"]
        hi = result.loc[0, "mc_failure_rate_ci_upper"]
        self.assertLessEqual(lo, hi)
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)

    def test_validate_with_simulation_empty_result_has_ci_columns(self):
        df = pd.DataFrame([
            {"time": "08:00", "lambda": 8.2, "mu": 10.0, "c_optimal": None},
        ])
        result = validate_with_simulation(df, mc_trials=2000, seed=42)
        for col in [
            "mc_failure_rate_ci_lower",
            "mc_failure_rate_ci_upper",
            "mc_failure_rate_ci_half_width",
            "mc_failure_rate_precision",
            "mc_failure_rate_adequate",
        ]:
            self.assertIn(col, result.columns)
        self.assertTrue(result.loc[0, "mc_failure_rate_ci_lower"] is None)


if __name__ == "__main__":
    unittest.main()
