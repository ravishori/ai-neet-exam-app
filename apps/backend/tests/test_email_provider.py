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
