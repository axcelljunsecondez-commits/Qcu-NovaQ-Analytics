"""Tests for the shared model-selection dispatch."""

import pytest

from backend.queueing_engine.models import mg1, mm1
from backend.queueing_engine.services.data_processing import process_segments
from backend.queueing_engine.services.model_selection import select_model
from backend.queueing_engine.services.optimization import optimize_segment
from backend.queueing_engine.simulation.simulation import simulation_coverage


@pytest.mark.parametrize(
    ("kwargs", "expected_name", "expected_servers"),
    [
        ({"theta": 0.5}, "M/M/c+M (Erlang-A)", 1),
        ({"variance": 0.1, "K": 5, "theta": 0.5}, "M/M/c+M (Erlang-A)", 1),
        ({"variance": 0.1, "K": 5}, "M/G/c/K", 1),
        ({"K": 5}, "M/M/c/K", 1),
        ({"variance": 0.1}, "M/G/c", 1),
        ({}, "M/M/1", 1),
        ({"c": 2}, "M/M/c", 2),
    ],
)
def test_select_model_dispatch(kwargs, expected_name, expected_servers):
    selection = select_model(9, 10, kwargs.pop("c", 1), **kwargs)
    assert selection["name"] == expected_name
    assert selection["servers"] == expected_servers
    assert selection["metrics"] is not None


def test_select_model_theta_zero_falls_through_to_variance():
    selection = select_model(2, 5, 1, variance=0.1, theta=0)
    assert selection["name"] == "M/G/c"


def test_select_model_theta_zero_falls_through_to_mmc():
    selection = select_model(2, 5, 2, theta=0)
    assert selection["name"] == "M/M/c"


def test_select_model_non_numeric_values_treated_as_absent():
    selection = select_model(2, 5, 1, variance="0.1", K="5", theta="0.5")
    assert selection["name"] == "M/M/1"


def test_select_model_nan_values_treated_as_absent():
    selection = select_model(2, 5, 1, variance=float("nan"), K=float("nan"), theta=float("nan"))
    assert selection["name"] == "M/M/1"


def test_select_model_inf_theta_treated_as_absent():
    selection = select_model(2, 5, 1, theta=float("inf"))
    assert selection["name"] == "M/M/1"


def test_mg1_matches_pollaczek_khinchine_formula():
    result = mg1(2.0, 4.0, 0.03125)
    service_mean = 0.25
    second_moment = 0.03125 + service_mean**2
    rho = 0.5
    Wq = 2.0 * second_moment / (2.0 * (1.0 - rho))
    W = Wq + service_mean
    assert result["stable"] is True
    assert result["rho"] == pytest.approx(rho)
    assert result["Wq"] == pytest.approx(Wq)
    assert result["W"] == pytest.approx(W)
    assert result["Lq"] == pytest.approx(2.0 * Wq)
    assert result["L"] == pytest.approx(2.0 * W)
    assert result["service_second_moment"] == pytest.approx(second_moment)


def test_mg1_exponential_service_matches_mm1():
    lambda_ = 2.0
    mu = 5.0
    result = mg1(lambda_, mu, 1.0 / mu**2)
    assert result["Wq"] == pytest.approx(mm1(lambda_, mu)["Wq"])
    assert result["Lq"] == pytest.approx(mm1(lambda_, mu)["Lq"])
    assert result["W"] == pytest.approx(mm1(lambda_, mu)["W"])


def test_mg1_low_variability_differs_from_mm1():
    lambda_ = 2.0
    mu = 5.0
    deterministic_like = mg1(lambda_, mu, 0.0)
    exponential = mm1(lambda_, mu)
    assert deterministic_like["Wq"] < exponential["Wq"]


@pytest.mark.parametrize("lambda_", [5.0, 6.0])
def test_mg1_reports_unstable_without_finite_steady_state(lambda_):
    result = mg1(lambda_, 5.0, 0.01)
    assert result["stable"] is False
    assert result["Wq"] is None
    assert result["Lq"] is None
    assert "Unstable" in result["error"]


def test_separate_dispatch_requires_variance_and_uses_mg1():
    unsupported = select_model(2.0, 5.0, 1, queue_structure="separate_queues")
    selected = select_model(2.0, 5.0, 1, variance=0.01, queue_structure="separate_queues")
    assert unsupported["name"] == "Separate FIFO Queues (unsupported)"
    assert selected["name"] == "Parallel M/G/1"
    assert selected["model_id"] == "parallel_mg1"
    assert selected["metrics"] == mg1(2.0, 5.0, 0.01)


def test_parallel_queues_are_grouped_and_calculated_independently():
    frame = process_segments(
        [
            {"time": "08:00-09:00", "queue_id": "a", "queue_structure": "separate_queues", "lambda": 2.0, "mu": 5.0, "c": 1, "variance": 0.01},
            {"time": "08:00-09:00", "queue_id": "b", "queue_structure": "separate_queues", "lambda": 1.0, "mu": 4.0, "c": 1, "variance": 0.02},
        ]
    )
    rows = {row["queue_id"]: row for row in frame.to_dict("records")}
    assert set(rows) == {"a", "b"}
    assert rows["a"]["model_id"] == "parallel_mg1"
    assert rows["b"]["model_id"] == "parallel_mg1"
    assert rows["a"]["rho"] == pytest.approx(2.0 / 5.0)
    assert rows["b"]["rho"] == pytest.approx(1.0 / 4.0)
    assert rows["a"]["Wq"] != rows["b"]["Wq"]


def test_duplicate_queue_rows_pool_first_and_second_moments():
    frame = process_segments(
        [
            {"time": "08:00-09:00", "queue_id": "a", "queue_structure": "separate_queues", "lambda": 2.0, "mu": 5.0, "c": 1, "variance": 0.01},
            {"time": "08:00-09:00", "queue_id": "a", "queue_structure": "separate_queues", "lambda": 1.0, "mu": 4.0, "c": 1, "variance": 0.02},
        ]
    )
    row = frame.iloc[0]
    expected_mean = (2.0 * 0.2 + 1.0 * 0.25) / 3.0
    expected_second_moment = (2.0 * (0.01 + 0.2**2) + 1.0 * (0.02 + 0.25**2)) / 3.0
    expected_variance = expected_second_moment - expected_mean**2
    expected = mg1(3.0, 1.0 / expected_mean, expected_variance)
    assert row["lambda"] == pytest.approx(3.0)
    assert row["mu"] == pytest.approx(1.0 / expected_mean)
    assert row["rho"] == pytest.approx(expected["rho"])
    assert row["Wq"] == pytest.approx(expected["Wq"])


@pytest.mark.parametrize("time_label", ["08:00-08:15", "08:00-08:30", "08:00-09:00"])
def test_parallel_rates_remain_per_hour_across_segment_labels(time_label):
    frame = process_segments(
        [{"time": time_label, "queue_id": "a", "queue_structure": "separate_queues", "lambda": 2.0, "mu": 5.0, "c": 1, "variance": 0.01}]
    )
    assert frame.iloc[0]["rho"] == pytest.approx(0.4)
    assert frame.iloc[0]["Wq"] == pytest.approx(mg1(2.0, 5.0, 0.01)["Wq"])


def test_parallel_downstream_paths_are_gated():
    result = optimize_segment(
        {"time": "a", "queue_structure": "separate_queues", "model_id": "parallel_mg1", "lambda": 2.0, "mu": 5.0, "c": 1, "variance": 0.01}
    )
    selected, error = simulation_coverage(
        {"time": "a", "queue_structure": "separate_queues", "lambda": 2.0, "mu": 5.0, "c": 1, "variance": 0.01}
    )
    assert result["feasibility_status"] == "INVALID_INPUT"
    assert "not supported" in result["warning"]
    assert selected == "Parallel M/G/1"
    assert error is None
    # Unsupported separate rows still fail closed at the coverage gate.
    bad, bad_error = simulation_coverage(
        {"time": "a", "queue_structure": "separate_queues", "lambda": 2.0, "mu": 5.0, "c": 1}
    )
    assert bad_error is not None and "Unsupported simulation model" in bad_error


def test_select_model_matches_optimization_queue_metrics():
    from backend.queueing_engine.services.optimization import _queue_metrics

    for kwargs in ({"theta": 0.5}, {"variance": 0.1, "K": 5}, {"K": 5}, {"variance": 0.1}, {}):
        selection = select_model(9, 10, 2, **kwargs)
        metrics = _queue_metrics(9, 10, 2, **kwargs)
        assert selection["metrics"] == metrics
