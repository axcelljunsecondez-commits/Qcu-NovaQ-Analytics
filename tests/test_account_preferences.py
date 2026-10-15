"""B1: optional preferences saved without touching onboarding (spec 2026-10-09 §11, D2)."""

from __future__ import annotations

from sqlalchemy import select

from backend.api.main import CsrfDoubleSubmitMiddleware
from backend.db.models import User
from tests.helpers import clear_cookies, create_user, csrf_header, login, make_sessionmaker

FULL = {
    "operation_type": "retail",
    "preferred_terminology": {
        "service_point": "other",
        "service_point_label": "Pay points",
        "service_point_label_singular": "Pay point",
        "customer": "customers",
    },
}


def _stored(engine, email: str) -> User:
    with make_sessionmaker(engine)() as db:
        return db.execute(select(User).where(User.email == email)).scalar_one()


def _signed_in(db_engine, client, email: str = "pref@example.com") -> None:
    create_user(db_engine, email, "s3cret-pass")
    assert login(client, email, "s3cret-pass") == 200


def test_preferences_require_a_session(client):
    assert client.get("/account/preferences").status_code == 401
    assert client.put("/account/preferences", json=FULL).status_code == 401


def test_put_requires_the_csrf_header(db_engine, client):
    _signed_in(db_engine, client)
    response = client.put("/account/preferences", json=FULL)
    assert response.status_code == 403
    assert _stored(db_engine, "pref@example.com").operation_type is None


def test_preferences_are_not_csrf_exempt():
    assert not any(
        "/account/preferences" == family or "/account/preferences".startswith(family + "/")
        for family in CsrfDoubleSubmitMiddleware.EXEMPT_FAMILIES
    )


def test_never_saved_preferences_are_empty(db_engine, client):
    _signed_in(db_engine, client)
    response = client.get("/account/preferences")
    assert response.status_code == 200
    assert response.json() == {"operation_type": None, "preferred_terminology": {}}


def test_put_saves_exactly_what_was_sent_and_leaves_onboarding_alone(db_engine, client):
    _signed_in(db_engine, client)
    response = client.put("/account/preferences", json=FULL, headers=csrf_header(client))
    assert response.status_code == 200
    assert response.json() == FULL
    assert client.get("/account/preferences").json() == FULL
    stored = _stored(db_engine, "pref@example.com")
    assert stored.operation_type == "retail"
    assert stored.preferred_terminology == FULL["preferred_terminology"]
    assert stored.onboarding_completed is False


def test_put_does_not_unset_a_completed_onboarding(db_engine, client):
    _signed_in(db_engine, client)
    with make_sessionmaker(db_engine)() as db:
        user = db.execute(select(User).where(User.email == "pref@example.com")).scalar_one()
        user.onboarding_completed = True
        db.commit()
    assert client.put("/account/preferences", json=FULL, headers=csrf_header(client)).status_code == 200
    assert _stored(db_engine, "pref@example.com").onboarding_completed is True


def test_put_with_empty_values_clears_and_fills_nothing_in(db_engine, client):
    _signed_in(db_engine, client)
    client.put("/account/preferences", json=FULL, headers=csrf_header(client))
    response = client.put("/account/preferences", json={}, headers=csrf_header(client))
    assert response.status_code == 200
    assert response.json() == {"operation_type": None, "preferred_terminology": {}}
    stored = _stored(db_engine, "pref@example.com")
    assert stored.operation_type is None
    assert stored.preferred_terminology == {}


def test_values_are_trimmed(db_engine, client):
    _signed_in(db_engine, client)
    body = {"operation_type": "  retail ", "preferred_terminology": {"customer_label": " Guests "}}
    response = client.put("/account/preferences", json=body, headers=csrf_header(client))
    assert response.json() == {"operation_type": "retail", "preferred_terminology": {"customer_label": "Guests"}}


def test_length_and_type_are_validated(db_engine, client):
    _signed_in(db_engine, client)
    headers = csrf_header(client)
    rejected = [
        {"operation_type": "x" * 51},
        {"operation_type": "   "},
        {"operation_type": 5},
        {"preferred_terminology": {"customer_label": "y" * 51}},
        {"preferred_terminology": {"customer_label": ""}},
        {"preferred_terminology": {"customer_label": ["list"]}},
        {"preferred_terminology": {"unknown_key": "value"}},
        {"preferred_terminology": "not an object"},
        {"onboarding_completed": True},
    ]
    for body in rejected:
        assert client.put("/account/preferences", json=body, headers=headers).status_code == 422, body
    stored = _stored(db_engine, "pref@example.com")
    assert stored.operation_type is None
    assert stored.preferred_terminology in ({}, None)
    assert stored.onboarding_completed is False
    accepted = {"operation_type": "x" * 50, "preferred_terminology": {"customer_label": "y" * 50}}
    assert client.put("/account/preferences", json=accepted, headers=headers).status_code == 200


def test_each_user_sees_and_changes_only_their_own_preferences(db_engine, client):
    _signed_in(db_engine, client, "first@example.com")
    client.put("/account/preferences", json=FULL, headers=csrf_header(client))
    clear_cookies(client)
    _signed_in(db_engine, client, "second@example.com")
    assert client.get("/account/preferences").json() == {"operation_type": None, "preferred_terminology": {}}
    other = {"operation_type": "healthcare", "preferred_terminology": {"customer": "patients"}}
    client.put("/account/preferences", json=other, headers=csrf_header(client))
    assert _stored(db_engine, "first@example.com").operation_type == "retail"
    assert _stored(db_engine, "first@example.com").preferred_terminology == FULL["preferred_terminology"]
    assert _stored(db_engine, "second@example.com").operation_type == "healthcare"


def test_existing_onboarding_values_are_returned_as_stored(db_engine, client):
    _signed_in(db_engine, client)
    with make_sessionmaker(db_engine)() as db:
        user = db.execute(select(User).where(User.email == "pref@example.com")).scalar_one()
        user.operation_type = "financial"
        user.preferred_terminology = {"service_point": "tellers", "customer": "clients"}
        db.commit()
    assert client.get("/account/preferences").json() == {
        "operation_type": "financial",
        "preferred_terminology": {"service_point": "tellers", "customer": "clients"},
    }
