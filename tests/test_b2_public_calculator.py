"""B2: the guest Quick calculator endpoint.

Spec: docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md §7.12, §11 B2 (owner decision D1).
The signed-IP bucket in pages_signed mode is covered with the other buckets in tests/test_proxy_assertion.py.

Data: SYNTHETIC (rates made for the test; the §7.12 board example λ 40/h, μ 15/h).
"""

from __future__ import annotations

import pytest

from tests.helpers import create_user, csrf_header, login

CASES = {
    "mm1": {"lambda": 10.0, "mu": 15.0},
    "mmc": {"lambda": 40.0, "mu": 15.0, "c": 3},
    "mgc": {"lambda": 40.0, "mu": 15.0, "c": 3, "variance": 0.0025},
    "mmck": {"lambda": 40.0, "mu": 15.0, "c": 2, "K": 6},
    "mgck": {"lambda": 40.0, "mu": 15.0, "c": 2, "variance": 0.0025, "K": 6},
    "erlang_a": {"lambda": 40.0, "mu": 15.0, "c": 2, "theta": 6.0},
}


@pytest.mark.parametrize("model", sorted(CASES))
def test_a_guest_gets_exactly_the_signed_in_numbers(db_engine, client, model):
    guest = client.post(f"/public/calculator/{model}", json=CASES[model])
    assert guest.status_code == 200, guest.text
    assert "set-cookie" not in {key.lower() for key in guest.headers}  # no session is created
    create_user(db_engine, "owner@example.com", "pw")
    login(client, "owner@example.com", "pw")
    signed_in = client.post(f"/analysis/{model}", headers=csrf_header(client), json=CASES[model])
    assert signed_in.status_code == 200, signed_in.text
    assert guest.json() == signed_in.json()


def test_the_board_example_of_the_spec(client):
    """§7.12: λ 40/h, μ 15/h. 2 counters cannot keep up; 3 wait 9.57 min; 4 wait 1.14 min."""
    two, three, four = (client.post("/public/calculator/mmc", json={"lambda": 40, "mu": 15, "c": c}).json()
                        for c in (2, 3, 4))
    assert two["stable"] is False and two["Wq"] is None
    assert three["rho"] == pytest.approx(0.8889, abs=1e-4)
    assert three["Lq"] == pytest.approx(6.3801, abs=1e-4)
    assert three["Wq"] * 60 == pytest.approx(9.57, abs=0.01)
    assert four["rho"] == pytest.approx(0.6667, abs=1e-4)
    assert four["Wq"] * 60 == pytest.approx(1.14, abs=0.01)


def test_unknown_models_and_missing_inputs_are_refused(client):
    assert client.post("/public/calculator/mm9", json={"lambda": 1, "mu": 2}).status_code == 404
    missing = client.post("/public/calculator/mmc", json={"lambda": 1, "mu": 2})
    assert missing.status_code == 422
    assert "requires parameters: c" in missing.text
    assert client.post("/public/calculator/mmc", json={"lambda": -1, "mu": 2, "c": 1}).status_code == 422


def test_guests_have_their_own_limit_and_get_a_retry_time(db_engine, client, app):
    app.state.settings.rate_limit_guest_compute = 3
    body = {"lambda": 40, "mu": 15, "c": 3}
    assert [client.post("/public/calculator/mmc", json=body).status_code for _ in range(3)] == [200, 200, 200]
    refused = client.post("/public/calculator/mmc", json=body)
    assert refused.status_code == 429
    assert refused.json()["detail"] == "Too many requests. Try again later."
    assert int(refused.headers["Retry-After"]) >= 1
    # The guest bucket is separate: signed-in compute still runs.
    create_user(db_engine, "owner@example.com", "pw")
    login(client, "owner@example.com", "pw")
    assert client.post("/analysis/mmc", headers=csrf_header(client), json=body).status_code == 200


def test_the_default_guest_limit_allows_ten_calculations_of_three_calls():
    from backend.api.settings import Settings

    assert Settings().rate_limit_guest_compute == 30
