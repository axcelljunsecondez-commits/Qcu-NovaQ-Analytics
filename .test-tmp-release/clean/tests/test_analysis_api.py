"""Analysis endpoints: engine adapters for the six analytical models."""

from __future__ import annotations

import pytest

from tests.helpers import create_user, login

ANALYSIS_URL = "/analysis/{model}"


@pytest.mark.parametrize(
    ("model", "body", "key"),
    [
        ("mm1", {"lambda": 10, "mu": 20}, "rho"),
        ("mmc", {"lambda": 30, "mu": 12, "c": 3}, "rho"),
        ("mgc", {"lambda": 30, "mu": 12, "c": 3, "variance": 0.006}, "rho"),
        ("mmck", {"lambda": 30, "mu": 12, "c": 3, "K": 15}, "rho"),
        ("mgck", {"lambda": 30, "mu": 12, "c": 3, "variance": 0.006, "K": 15}, "rho"),
        ("erlang_a", {"lambda": 30, "mu": 12, "c": 3, "theta": 1.0}, "rho"),
    ],
)
def test_analysis_models_return_metrics(db_engine, client, model, body, key):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(ANALYSIS_URL.format(model=model), json=body)
    assert response.status_code == 200
    assert key in response.json()


def test_analysis_requires_auth(client):
    assert client.post("/analysis/mm1", json={"lambda": 10, "mu": 20}).status_code == 401


def test_analysis_unknown_model_404(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    assert client.post("/analysis/garbage", json={"lambda": 10, "mu": 20}).status_code == 404


def test_analysis_missing_required_param_422(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post("/analysis/mgc", json={"lambda": 30, "mu": 12, "c": 3})
    assert response.status_code == 422
    assert "variance" in response.json()["detail"]


def test_analysis_invalid_mu_422(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    assert client.post("/analysis/mm1", json={"lambda": 10, "mu": 0}).status_code == 422


def test_mm1_matches_engine(db_engine, client):
    from backend.queueing_engine.models.queue_models import mm1

    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    expected = mm1(10.0, 20.0)
    response = client.post("/analysis/mm1", json={"lambda": 10, "mu": 20})
    for key, value in expected.items():
        assert response.json().get(key) == pytest.approx(value) if isinstance(value, float) else True


def test_mmc_stable_flag(db_engine, client):
    from backend.queueing_engine.models.queue_models import mmc

    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    unstable = mmc(100.0, 12.0, 3)
    assert unstable["stable"] is False
    response = client.post("/analysis/mmc", json={"lambda": 100, "mu": 12, "c": 3})
    assert response.status_code == 200
    assert response.json()["stable"] is False
