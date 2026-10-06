"""The ``novaq`` loggers must emit their INFO ``event=`` lines (G8 production finding, 2026-10-06).

Under uvicorn's default logging configuration nothing configured the ``novaq`` loggers, so they
inherited the root WARNING level and every INFO ``event=`` line (request log, security events) was
dropped. ``docs/operations.md`` requires API logs with timestamp, severity, event, request ID,
method, query-free path, status, duration and safe user ID.
"""

from __future__ import annotations

import io
import logging
import re

import pytest
from fastapi.testclient import TestClient

from backend.api.email_delivery import FakeEmailSender
from backend.api.main import _EventLogHandler, configure_event_logging, create_app
from backend.api.settings import Settings

NOVAQ = logging.getLogger("novaq")
LINE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z INFO novaq\.api event=probe value=1$")


@pytest.fixture(autouse=True)
def isolated_novaq_logger():
    """Start each test from an unconfigured ``novaq`` logger and restore the original afterwards."""
    level, handlers = NOVAQ.level, list(NOVAQ.handlers)
    NOVAQ.setLevel(logging.NOTSET)
    for handler in handlers:
        NOVAQ.removeHandler(handler)
    yield
    for handler in list(NOVAQ.handlers):
        NOVAQ.removeHandler(handler)
    for handler in handlers:
        NOVAQ.addHandler(handler)
    NOVAQ.setLevel(level)


def _event_handlers() -> list[_EventLogHandler]:
    return [h for h in NOVAQ.handlers if isinstance(h, _EventLogHandler)]


def test_app_request_emits_info_event_line(db_engine, caplog):
    app = create_app(engine=db_engine, settings=Settings(), email_sender=FakeEmailSender())
    TestClient(app).get("/health", headers={"X-Request-ID": "probe-123"})
    events = [r.getMessage() for r in caplog.records if r.name == "novaq.api" and r.levelno == logging.INFO]
    assert any("event=http_request request_id=probe-123 method=GET path=/health status=200" in m for m in events)


def test_security_event_is_emitted_at_info(db_engine, caplog):
    app = create_app(engine=db_engine, settings=Settings(), email_sender=FakeEmailSender())
    TestClient(app).post("/auth/forgot-password", json={"email": "nobody@example.com"})
    messages = [r.getMessage() for r in caplog.records if r.name == "novaq.api"]
    assert any(m.startswith("event=password_reset_request ") and "outcome=accepted" in m for m in messages)


def test_stream_handler_added_once_when_root_has_no_handler(monkeypatch):
    # Uvicorn's default configuration leaves the root logger without handlers.
    monkeypatch.setattr(logging.getLogger(), "handlers", [])
    configure_event_logging()
    configure_event_logging()
    handlers = _event_handlers()
    assert len(handlers) == 1
    assert NOVAQ.getEffectiveLevel() == logging.INFO
    stream = io.StringIO()
    handlers[0].setStream(stream)
    logging.getLogger("novaq.api").info("event=probe value=%s", 1)
    logging.getLogger("novaq.api").debug("event=debug_hidden")
    assert LINE.match(stream.getvalue().rstrip("\n")), stream.getvalue()


def test_existing_root_handler_receives_records_without_a_second_handler(monkeypatch):
    stream = io.StringIO()
    root_handler = logging.StreamHandler(stream)
    monkeypatch.setattr(logging.getLogger(), "handlers", [root_handler])
    configure_event_logging()
    assert _event_handlers() == []
    logging.getLogger("novaq.api").info("event=probe value=%s", 1)
    assert stream.getvalue() == "event=probe value=1\n"


def test_explicit_novaq_level_is_kept(monkeypatch):
    monkeypatch.setattr(logging.getLogger(), "handlers", [])
    NOVAQ.setLevel(logging.WARNING)
    configure_event_logging()
    assert NOVAQ.level == logging.WARNING
