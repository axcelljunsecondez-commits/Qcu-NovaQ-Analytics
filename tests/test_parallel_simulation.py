"""Focused Parallel M/G/1 DES regressions."""

from __future__ import annotations

from backend.queueing_engine.simulation.simulation import (
    simulate_segments,
    simulate_segments_with_trace,
    summarize_simulation,
)

SETUP = {
    "queue_structure": "separate_queues",
    "queue_ids": ["queue_a", "queue_b"],
    "staffing_varies_by_period": False,
    "separate_queue_closure_policy": "drain_existing",
    "segments": [{"id": "s1", "start_time": "07:00:00", "end_time": "08:00:00"}],
}


def records(lambda_a=4.0, lambda_b=2.0):
    return [
        {
            "segment_id": "s1",
            "time": "s1",
            "queue_id": "queue_a",
            "queue_structure": "separate_queues",
            "model_id": "parallel_mg1",
            "lambda": lambda_a,
            "mu": 4.0,
            "c": 1,
            "service_time_source": "empirical",
            "service_samples_hours": [0.2, 0.3],
        },
        {
            "segment_id": "s1",
            "time": "s1",
            "queue_id": "queue_b",
            "queue_structure": "separate_queues",
            "model_id": "parallel_mg1",
            "lambda": lambda_b,
            "mu": 8.0,
            "c": 1,
            "service_time_source": "empirical",
            "service_samples_hours": [0.1, 0.15],
        },
    ]


def test_parallel_des_is_seed_reproducible_and_uses_empirical_support():
    first = simulate_segments_with_trace(records(), seed=7, queue_setup=SETUP, max_events=1000)
    second = simulate_segments_with_trace(records(), seed=7, queue_setup=SETUP, max_events=1000)
    assert first == second
    service_events = [event for event in first["trace"] if event["type"] == "service_end"]
    assert service_events
    assert all(
        event["service_time_hours"] in ({0.2, 0.3} if event["queue_id"] == "queue_a" else {0.1, 0.15})
        for event in service_events
    )


def test_parallel_des_keeps_queues_and_servers_independent():
    result = simulate_segments(records(), seed=7, queue_setup=SETUP)
    assert {row["queue_id"] for row in result} == {"queue_a", "queue_b"}
    assert {row["server_id"] for row in result} == {"server:queue_a", "server:queue_b"}
    assert all(row["queue_structure"] == "separate" for row in result)
    assert all(row["customer_conservation"] for row in result)


def test_parallel_des_runs_overloaded_finite_horizon_without_rejection():
    result = simulate_segments(records(lambda_a=100.0, lambda_b=0.0), seed=11, queue_setup=SETUP)
    queue_a = next(row for row in result if row["queue_id"] == "queue_a")
    assert queue_a["simulation_supported"] is True
    assert queue_a["arrivals"] > queue_a["served"]
    assert queue_a["waiting"] + queue_a["in_service"] > 0


def test_parallel_des_requires_empirical_samples():
    missing = [dict(records()[0], service_time_source="aggregate_statistics", service_samples_hours=None)]
    result = simulate_segments(missing, seed=3, queue_setup=SETUP)
    assert result[0]["simulation_supported"] is False
    assert "empirical" in result[0]["error"]


def test_parallel_des_rejects_missing_structured_schedule():
    result = simulate_segments(records(), seed=3, queue_setup=None)
    assert result[0]["simulation_supported"] is False
    assert "QueueSetup schedule" in result[0]["error"]


def test_parallel_des_system_summary_is_weighted_and_conservative():
    result = simulate_segments(records(), seed=7, queue_setup=SETUP)
    summary = summarize_simulation(result)
    assert summary["customer_conservation"] is True
    assert summary["total_arrivals"] == sum(row["arrivals"] for row in result)
    assert set(summary["per_queue"]) == {"queue_a", "queue_b"}
    assert 0.0 <= summary["avg_rho"] <= 1.0


def test_parallel_des_long_stable_case_matches_pollaczek_khinchine():
    lambda_value = 2.0
    samples = [0.1, 0.2]
    mean_service = sum(samples) / len(samples)
    second_moment = sum(sample**2 for sample in samples) / len(samples)
    rho = lambda_value * mean_service
    analytical_wq = lambda_value * second_moment / (2.0 * (1.0 - rho))
    setup = {
        "queue_structure": "separate_queues",
        "queue_ids": ["queue_a"],
        "staffing_varies_by_period": False,
        "separate_queue_closure_policy": "drain_existing",
        "segments": [{"id": "long", "start_time": "00:00:00", "end_time": "23:59:00"}],
    }
    row = {
        "segment_id": "long",
        "time": "long",
        "queue_id": "queue_a",
        "queue_structure": "separate_queues",
        "model_id": "parallel_mg1",
        "lambda": lambda_value,
        "mu": 1.0 / mean_service,
        "c": 1,
        "service_time_source": "empirical",
        "service_samples_hours": samples,
    }
    simulated_wq = []
    for seed in range(20):
        result = simulate_segments([row], seed=seed, queue_setup=setup)[0]
        simulated_wq.append(result["Wq_sim"])
    mean_simulated_wq = sum(simulated_wq) / len(simulated_wq)
    assert rho < 1.0
    assert analytical_wq == 0.03571428571428571
    assert abs(mean_simulated_wq - analytical_wq) < 0.02


def test_parallel_des_preserves_fifo_within_each_queue():
    trace = simulate_segments_with_trace(
        records(lambda_a=60.0, lambda_b=0.0), seed=2, queue_setup=SETUP, max_events=1000
    )
    starts = [
        event["customer_id"]
        for event in trace["trace"]
        if event["type"] == "service_start" and event["queue_id"] == "queue_a"
    ]
    arrivals = [
        event["customer_id"]
        for event in trace["trace"]
        if event["type"] == "arrival" and event["queue_id"] == "queue_a"
    ]
    assert starts == sorted(starts, key=arrivals.index)


def test_parallel_des_uses_mixed_structured_durations_as_one_horizon():
    setup = {
        **SETUP,
        "queue_ids": ["queue_a"],
        "segments": [
            {"id": "h1", "start_time": "05:00:00", "end_time": "06:00:00"},
            {"id": "q1", "start_time": "06:00:00", "end_time": "06:15:00"},
            {"id": "h2", "start_time": "06:15:00", "end_time": "06:45:00"},
            {"id": "h3", "start_time": "06:45:00", "end_time": "07:45:00"},
        ],
    }
    rows = [dict(records()[0], segment_id=segment_id) for segment_id in ("h1", "q1", "h2", "h3")]
    trace = simulate_segments_with_trace(rows, seed=5, queue_setup=setup, max_events=1000)
    assert trace["total_hours"] == 2.75
    assert {event["segment_id"] for event in trace["trace"]} <= {"h1", "q1", "h2", "h3"}


def test_parallel_des_draining_queue_keeps_backlog_and_stops_new_arrivals():
    setup = {
        "queue_structure": "separate_queues",
        "queue_ids": ["queue_a", "queue_b"],
        "staffing_varies_by_period": True,
        "separate_queue_closure_policy": "drain_existing",
        "segments": [
            {"id": "open", "start_time": "07:00:00", "end_time": "07:15:00", "active_queue_ids": ["queue_a", "queue_b"]},
            {"id": "closed", "start_time": "07:15:00", "end_time": "07:30:00", "active_queue_ids": ["queue_b"]},
        ],
    }
    rows = [
        {**records()[0], "segment_id": "open", "lambda": 60.0},
        {**records()[1], "segment_id": "open", "lambda": 0.0},
        {**records()[1], "segment_id": "closed", "lambda": 0.0},
    ]
    trace = simulate_segments_with_trace(rows, seed=4, queue_setup=setup, max_events=10000)
    queue_a_arrivals = [event for event in trace["trace"] if event.get("queue_id") == "queue_a" and event["type"] == "arrival"]
    assert queue_a_arrivals
    assert all(event["t"] < 0.25 for event in queue_a_arrivals)


def test_parallel_des_missing_next_segment_record_drains_queue_without_disappearing():
    setup = {
        "queue_structure": "separate_queues",
        "queue_ids": ["queue_a", "queue_b"],
        "staffing_varies_by_period": True,
        "separate_queue_closure_policy": "drain_existing",
        "segments": [
            {"id": "open", "start_time": "07:00:00", "end_time": "07:15:00", "active_queue_ids": ["queue_a", "queue_b"]},
            {"id": "closed", "start_time": "07:15:00", "end_time": "07:30:00", "active_queue_ids": ["queue_a"]},
        ],
    }
    rows = [
        {**records()[0], "segment_id": "open", "lambda": 30.0},
        {**records()[1], "segment_id": "open", "lambda": 30.0},
        {**records()[0], "segment_id": "closed", "lambda": 0.0},
    ]
    trace = simulate_segments_with_trace(rows, seed=3, queue_setup=setup, max_events=10000)
    queue_b_events = [event for event in trace["trace"] if event.get("queue_id") == "queue_b"]
    assert queue_b_events
    assert max(event["t"] for event in queue_b_events if event["type"] == "arrival") < 0.25


def test_parallel_des_allows_fully_drained_queue_to_reactivate():
    setup = {
        "queue_structure": "separate_queues",
        "queue_ids": ["queue_a"],
        "staffing_varies_by_period": True,
        "separate_queue_closure_policy": "drain_existing",
        "segments": [
            {"id": "open", "start_time": "07:00:00", "end_time": "07:15:00", "active_queue_ids": ["queue_a"]},
            {"id": "off", "start_time": "07:15:00", "end_time": "07:30:00", "active_queue_ids": []},
            {"id": "reopen", "start_time": "07:30:00", "end_time": "07:45:00", "active_queue_ids": ["queue_a"]},
        ],
    }
    rows = [{**records()[0], "segment_id": segment_id, "lambda": 0.0} for segment_id in ("open", "reopen")]
    result = simulate_segments(rows, seed=4, queue_setup=setup)
    assert all(row["simulation_supported"] for row in result)


def test_parallel_des_gates_reactivation_while_queue_is_still_draining():
    setup = {
        "queue_structure": "separate_queues",
        "queue_ids": ["queue_a"],
        "staffing_varies_by_period": True,
        "separate_queue_closure_policy": "drain_existing",
        "segments": [
            {"id": "open", "start_time": "07:00:00", "end_time": "07:15:00", "active_queue_ids": ["queue_a"]},
            {"id": "off", "start_time": "07:15:00", "end_time": "07:30:00", "active_queue_ids": []},
            {"id": "reopen", "start_time": "07:30:00", "end_time": "07:45:00", "active_queue_ids": ["queue_a"]},
        ],
    }
    rows = [
        {**records()[0], "segment_id": "open", "lambda": 60.0},
        {**records()[0], "segment_id": "reopen", "lambda": 0.0},
    ]
    result = simulate_segments(rows, seed=4, queue_setup=setup)
    assert result[0]["simulation_supported"] is False
    assert "draining" in result[0]["error"]
