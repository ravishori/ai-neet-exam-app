"""Incident reporting + controlled failure path."""

from __future__ import annotations

import pytest

from app.core.alerts import build_incident_email_body, format_exception_stack, maybe_send_critical_alert

pytestmark = pytest.mark.asyncio(loop_scope="session")


def test_incident_email_body_contains_ops_fields_not_secrets():
    body = build_incident_email_body(
        incident_id="ABC123",
        request_id="REQ-1",
        method="POST",
        route="/api/v1/auth/login",
        status_code=500,
        error_type="RuntimeError",
        safe_message="Something went wrong. Please try again.",
        environment="development",
        stack_trace="RuntimeError: boom\n",
        context={"password": "should-be-dropped", "user_id": "u1"},
    )
    assert "Incident ID: ABC123" in body
    assert "Request ID: REQ-1" in body
    assert "RuntimeError: boom" in body
    assert "should-be-dropped" not in body
    assert "user_id" in body


def test_format_exception_stack_includes_type():
    try:
        raise ValueError("controlled")
    except ValueError as exc:
        text = format_exception_stack(exc)
    assert "ValueError" in text
    assert "controlled" in text


async def test_alert_skipped_when_reporting_disabled(monkeypatch):
    from app.core import alerts as alerts_mod
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "error_reporting_enabled", False)
    monkeypatch.setattr(settings, "alert_email", "ravishori@gmail.com")
    sent = []

    async def fake_send(**kwargs):
        sent.append(kwargs)

    monkeypatch.setattr(alerts_mod, "send_security_alert_email", fake_send)
    assert await maybe_send_critical_alert(subject="s", body="b", dedupe_key="disabled-key") is False
    assert sent == []


async def test_controlled_failure_returns_safe_envelope(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from app.core import alerts as alerts_mod
    from app.main import app

    captured: list[dict] = []

    def fake_schedule(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(alerts_mod, "schedule_unexpected_incident", fake_schedule)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/admin/diagnostics/controlled-failure?confirm=yes")
    assert resp.status_code == 500
    body = resp.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "INTERNAL_SERVER_ERROR"
    assert "Something went wrong" in body["errors"][0]["message"]
    assert "traceback" not in resp.text.lower()
    assert "CONTROLLED_FAILURE" not in resp.text
    assert "errorId" in body["meta"]
    assert body.get("traceId")
    assert captured and captured[0]["error_id"] == body["meta"]["errorId"]


async def test_controlled_failure_hidden_without_confirm(client):
    resp = await client.post("/api/v1/admin/diagnostics/controlled-failure")
    assert resp.status_code == 404
