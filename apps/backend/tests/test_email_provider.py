"""Dedicated coverage for the HTTPS transactional-email provider
(email_service.py) that replaced raw SMTP in production — Railway blocks
outbound SMTP-class ports (confirmed via direct network diagnostics:
ENETUNREACH on 587/465/25, while HTTPS/443 succeeds).

Mocks httpx entirely — no real network calls, no real emails sent.
"""

from __future__ import annotations

import httpx
import pytest
import structlog

from app.core.config import Settings
from app.modules.identity.services import email_service

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _settings(**overrides) -> Settings:
    base = dict(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        jwt_secret="test-secret-not-real",
        encryption_key="uLCw_rsupBRTzp7bhuN_iuxiMiXgpxc6DujbFR_sXkM=",
        environment="production",
        email_provider="resend",
        email_api_key="fake-resend-api-key-for-tests-only",
        email_from="noreply@example.com",
        email_from_name="Trinetra",
    )
    base.update(overrides)
    return Settings(**base)


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeAsyncClient:
    """Minimal async context-manager stand-in for httpx.AsyncClient."""

    def __init__(self, *, status_code: int = 200, raise_exc: Exception | None = None, capture: dict | None = None):
        self._status_code = status_code
        self._raise_exc = raise_exc
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, *, headers, json):
        if self._capture is not None:
            self._capture["url"] = url
            self._capture["headers"] = headers
            self._capture["json"] = json
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeResponse(self._status_code)


# --------------------------------------------------------------------------- provider success


async def test_provider_success_sends_and_logs_without_secrets(monkeypatch):
    captured_request: dict = {}
    monkeypatch.setattr(
        email_service.httpx, "AsyncClient", lambda **_kw: _FakeAsyncClient(status_code=200, capture=captured_request)
    )
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())

    with structlog.testing.capture_logs() as logs:
        await email_service.send_password_reset_email(to="student@example.com", token="reset-token-abc")

    assert captured_request["url"] == "https://api.resend.com/emails"
    assert captured_request["headers"]["Authorization"] == "Bearer fake-resend-api-key-for-tests-only"
    assert captured_request["json"]["to"] == ["student@example.com"]

    log_text = " ".join(str(e) for e in logs)
    assert "fake-resend-api-key-for-tests-only" not in log_text
    assert any(e.get("event") == "email_sent" and e.get("provider") == "resend" for e in logs)


# --------------------------------------------------------------------------- provider failure modes


async def test_provider_timeout_is_caught_and_logged(monkeypatch):
    monkeypatch.setattr(
        email_service.httpx,
        "AsyncClient",
        lambda **_kw: _FakeAsyncClient(raise_exc=httpx.TimeoutException("simulated timeout")),
    )
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())

    with structlog.testing.capture_logs() as logs:
        # Must not raise — caller's generic response must be unaffected.
        await email_service.send_password_reset_email(to="student@example.com", token="reset-token-abc")

    assert any(e.get("event") == "email_send_failed" and e.get("provider") == "resend" for e in logs)


async def test_provider_http_failure_status_is_caught_and_logged(monkeypatch):
    monkeypatch.setattr(email_service.httpx, "AsyncClient", lambda **_kw: _FakeAsyncClient(status_code=500))
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())

    with structlog.testing.capture_logs() as logs:
        await email_service.send_password_reset_email(to="student@example.com", token="reset-token-abc")

    assert any(e.get("event") == "email_send_failed" for e in logs)


async def test_provider_authentication_failure_is_caught_and_logged(monkeypatch):
    """401 from the provider (bad/revoked API key) must fail the same safe
    way as any other provider error — never raised to the caller, never
    logs the key."""
    monkeypatch.setattr(email_service.httpx, "AsyncClient", lambda **_kw: _FakeAsyncClient(status_code=401))
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())

    with structlog.testing.capture_logs() as logs:
        await email_service.send_password_reset_email(to="student@example.com", token="reset-token-abc")

    log_text = " ".join(str(e) for e in logs)
    assert "fake-resend-api-key-for-tests-only" not in log_text
    assert any(e.get("event") == "email_send_failed" for e in logs)


async def test_unconfigured_provider_in_production_logs_without_attempting_smtp(monkeypatch):
    monkeypatch.setattr(
        email_service, "get_settings", lambda: _settings(email_provider="", email_api_key="", email_from="")
    )

    def _smtp_should_never_be_called(*_a, **_k):
        raise AssertionError("SMTP must never be attempted in production")

    monkeypatch.setattr(email_service.smtplib, "SMTP", _smtp_should_never_be_called)

    with structlog.testing.capture_logs() as logs:
        await email_service.send_password_reset_email(to="student@example.com", token="reset-token-abc")

    assert any(e.get("event") == "email_not_configured" for e in logs)


# --------------------------------------------------------------------------- admin-alert visibility (pre-merge review)


async def test_provider_failure_notifies_admin_alert_mechanism(monkeypatch):
    """An unexpected provider failure (e.g. Resend 500) must reach the
    existing admin incident-alert mechanism, not just structured logs."""
    monkeypatch.setattr(email_service.httpx, "AsyncClient", lambda **_kw: _FakeAsyncClient(status_code=500))
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())

    alert_calls: list[dict] = []

    async def fake_alert(**kwargs):
        alert_calls.append(kwargs)
        return True

    monkeypatch.setattr("app.core.alerts.maybe_send_critical_alert", fake_alert)

    with structlog.testing.capture_logs() as logs:
        await email_service.send_password_reset_email(to="student@example.com", token="reset-token-abc")

    assert any(e.get("event") == "email_send_failed" for e in logs)
    assert len(alert_calls) == 1
    assert alert_calls[0]["dedupe_key"] == "email_delivery_failure:password_reset"


async def test_unconfigured_provider_in_production_notifies_admin_alert_mechanism(monkeypatch):
    """Missing production email-provider configuration must not silently
    disappear — it must also reach the admin alert mechanism."""
    monkeypatch.setattr(
        email_service, "get_settings", lambda: _settings(email_provider="", email_api_key="", email_from="")
    )
    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()))

    alert_calls: list[dict] = []

    async def fake_alert(**kwargs):
        alert_calls.append(kwargs)
        return True

    monkeypatch.setattr("app.core.alerts.maybe_send_critical_alert", fake_alert)

    await email_service.send_password_reset_email(to="student@example.com", token="reset-token-abc")

    assert len(alert_calls) == 1
    assert alert_calls[0]["dedupe_key"] == "email_delivery_failure:password_reset"


async def test_client_still_receives_generic_response_on_provider_failure(monkeypatch):
    """The forgot-password route must still return its generic 200 envelope
    even when the email provider fails and the admin-alert path is exercised
    for real (no mock) against a fail-closed Redis stub."""
    from httpx import ASGITransport, AsyncClient

    from app.core import rate_limit as rl
    from app.main import app
    from app.modules.identity.services import auth_service as auth_service_mod

    monkeypatch.setattr(email_service.httpx, "AsyncClient", lambda **_kw: _FakeAsyncClient(status_code=500))
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())

    async def fake_request_password_reset(self, email):
        return "some-real-reset-token"

    monkeypatch.setattr(auth_service_mod.AuthService, "request_password_reset", fake_request_password_reset)

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/forgot-password", json={"email": "student@example.com"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "reset link has been sent" in body["data"]["message"]


async def test_security_alert_failure_does_not_recurse_into_another_alert(monkeypatch):
    """A failure while sending the alert email itself (kind == security_alert)
    must not trigger another call into the admin-alert mechanism — that would
    be infinite recursion through the same broken provider."""
    monkeypatch.setattr(email_service.httpx, "AsyncClient", lambda **_kw: _FakeAsyncClient(status_code=500))
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings(alert_email="ops@example.com"))

    alert_calls: list[dict] = []

    async def fake_alert(**kwargs):
        alert_calls.append(kwargs)
        return True

    monkeypatch.setattr("app.core.alerts.maybe_send_critical_alert", fake_alert)

    with structlog.testing.capture_logs() as logs:
        await email_service.send_security_alert_email(subject="s", body="b")

    assert any(e.get("event") == "email_send_failed" and e.get("kind") == "security_alert" for e in logs)
    assert alert_calls == []


async def test_normal_4xx_does_not_trigger_email_delivery_alert(monkeypatch):
    """A successful email send (or any non-provider-failure code path) must
    not call the admin-alert mechanism at all."""
    captured_request: dict = {}
    monkeypatch.setattr(
        email_service.httpx, "AsyncClient", lambda **_kw: _FakeAsyncClient(status_code=200, capture=captured_request)
    )
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())

    alert_calls: list[dict] = []

    async def fake_alert(**kwargs):
        alert_calls.append(kwargs)
        return True

    monkeypatch.setattr("app.core.alerts.maybe_send_critical_alert", fake_alert)

    await email_service.send_password_reset_email(to="student@example.com", token="reset-token-abc")

    assert alert_calls == []
