"""DB failure + email safety gates for resilience verification."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app.core.alerts import maybe_send_critical_alert, report_unexpected_incident
from app.core.exceptions import sqlalchemy_exception_handler
from starlette.requests import Request

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _request(path: str = "/api/v1/test-db") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
        "state": {"trace_id": "REQ-DBFAILTEST1"},
    }
    return Request(scope)


async def test_operational_error_returns_safe_student_body(monkeypatch):
    from app.core import alerts as alerts_mod

    scheduled = []

    def fake_schedule(**kwargs):
        scheduled.append(kwargs)

    monkeypatch.setattr(alerts_mod, "schedule_unexpected_incident", fake_schedule)

    exc = OperationalError("SELECT 1", {}, Exception("could not connect to server"))
    response = await sqlalchemy_exception_handler(_request(), exc)
    assert response.status_code == 503
    body = response.body.decode()
    assert "SERVICE_UNAVAILABLE" in body or "preparation data" in body.lower()
    assert "could not connect" not in body.lower()
    assert "postgresql" not in body.lower()
    assert "password" not in body.lower()
    assert "REQ-DBFAILTEST1" in body
    assert scheduled and scheduled[0]["request_id"] == "REQ-DBFAILTEST1"


async def test_email_failure_does_not_raise(monkeypatch):
    from app.core import alerts as alerts_mod
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "error_reporting_enabled", True)
    monkeypatch.setattr(settings, "alert_email", "ravishori@gmail.com")
    monkeypatch.setattr(alerts_mod, "get_redis", lambda: None)

    def boom(**kwargs):
        raise RuntimeError("SMTP down")

    monkeypatch.setattr(alerts_mod, "send_security_alert_email", boom)

    # maybe_send catches and returns False
    ok = await maybe_send_critical_alert(subject="s", body="b", dedupe_key="email-fail-safety")
    assert ok is False

    # report_unexpected_incident also must not raise
    await report_unexpected_incident(
        method="POST",
        route="/api/v1/x",
        status_code=500,
        exc=RuntimeError("app boom"),
        request_id="REQ-EMAILFAIL1",
        error_id="E1",
        safe_message="safe",
    )


async def test_alert_dedupe_limits_flood(monkeypatch):
    from app.core import alerts as alerts_mod
    from app.core.config import get_settings
    from unittest.mock import AsyncMock, MagicMock

    settings = get_settings()
    monkeypatch.setattr(settings, "error_reporting_enabled", True)
    monkeypatch.setattr(settings, "alert_email", "ravishori@gmail.com")

    sent = []

    def fake_send(*, subject, body):
        sent.append(subject)

    redis = MagicMock()
    # first True (send), then False for subsequent (deduped)
    redis.set = AsyncMock(side_effect=[True, False, False, False, False])
    monkeypatch.setattr(alerts_mod, "get_redis", lambda: redis)
    monkeypatch.setattr(alerts_mod, "send_security_alert_email", fake_send)

    results = []
    for i in range(5):
        results.append(
            await maybe_send_critical_alert(subject=f"s{i}", body="b", dedupe_key="flood-key")
        )
    assert results[0] is True
    assert results[1:] == [False, False, False, False]
    assert len(sent) == 1
