from sqlalchemy.exc import OperationalError


def test_readiness_checks_database(client):
    assert client.get("/ready").status_code == 200


def test_readiness_fails_when_database_unavailable(client, db_engine, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OperationalError("connect", {}, Exception("unavailable"))
    monkeypatch.setattr(db_engine, "connect", unavailable)
    assert client.get("/ready").status_code == 503
