"""Tests for the shared model-selection dispatch."""

import pytest

from backend.queueing_engine.services.model_selection import select_model


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


def test_select_model_matches_optimization_queue_metrics():
    from backend.queueing_engine.services.optimization import _queue_metrics

    for kwargs in ({"theta": 0.5}, {"variance": 0.1, "K": 5}, {"K": 5}, {"variance": 0.1}, {}):
        selection = select_model(9, 10, 2, **kwargs)
        metrics = _queue_metrics(9, 10, 2, **kwargs)
        assert selection["metrics"] == metrics
