"""Forgot/reset password E2E — dedicated coverage (audit finding #8).

Reuses the existing `client`/`db_session` fixtures and the established
rate-limit-bypass monkeypatch pattern from test_mobile_otp_login.py /
test_security_wave_c.py, rather than building new test infrastructure.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    from app.core import rate_limit as rl

    async def no_limit(key: str, *, limit: int, window_seconds: int, fail_closed: bool, log_key: str | None = None) -> None:
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


def _payload(email: str, mobile: str) -> dict:
    return {
        "email": email,
        "first_name": "Reset",
        "last_name": "Test",
        "mobile": mobile,
        "state_code": "KARNATAKA",
        "city": "Bangalore",
        "password": "ResetTestPass!42",
    }


def _email() -> str:
    return f"reset-{uuid.uuid4().hex[:12]}@example.com"


def _mobile() -> str:
    import random

    return str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))


async def _register(client, email: str | None = None) -> str:
    email = email or _email()
    resp = await client.post("/api/v1/auth/register", json=_payload(email, _mobile()))
    assert resp.status_code == 201, resp.text
    await client.post("/api/v1/auth/logout")
    return email


# --------------------------------------------------------------------------- non-enumeration


async def test_forgot_password_known_email_returns_generic_success(client):
    email = await _register(client)
    resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    assert "success" in resp.json()["data"]["message"].lower() or "sent" in resp.json()["data"]["message"].lower()


async def test_forgot_password_unknown_email_returns_identical_response(client):
    known = await _register(client)
    known_resp = await client.post("/api/v1/auth/forgot-password", json={"email": known})

    unknown_resp = await client.post(
        "/api/v1/auth/forgot-password", json={"email": f"definitely-not-registered-{uuid.uuid4().hex[:8]}@example.com"}
    )

    assert known_resp.status_code == unknown_resp.status_code == 200
    # Non-enumeration: identical message regardless of whether the account exists.
    assert known_resp.json()["data"]["message"] == unknown_resp.json()["data"]["message"]


# --------------------------------------------------------------------------- token generation/storage


async def test_reset_token_is_stored_hashed_not_plaintext(client, db_session):
    from app.modules.identity.models.user import User
    from app.modules.identity.services.auth_service import AuthService

    email = await _register(client)
    service = AuthService(db_session)
    plaintext_token = await service.request_password_reset(email)

    assert plaintext_token is not None
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    assert user.password_reset_token_hash is not None
    assert user.password_reset_token_hash != plaintext_token
    assert plaintext_token not in user.password_reset_token_hash


async def test_reset_token_expires_correctly(client, db_session):
    from datetime import UTC, datetime, timedelta

    from app.modules.identity.models.user import User
    from app.modules.identity.services.auth_service import AuthService

    email = await _register(client)
    service = AuthService(db_session)
    plaintext_token = await service.request_password_reset(email)

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.password_reset_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/reset-password", json={"token": plaintext_token, "new_password": "NewResetPass!99"}
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "INVALID_RESET_TOKEN"


async def test_reset_token_is_single_use(client, db_session):
    from app.modules.identity.services.auth_service import AuthService

    email = await _register(client)
    service = AuthService(db_session)
    plaintext_token = await service.request_password_reset(email)
    await db_session.commit()

    first = await client.post(
        "/api/v1/auth/reset-password", json={"token": plaintext_token, "new_password": "FirstResetPass!42"}
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/reset-password", json={"token": plaintext_token, "new_password": "SecondResetPass!42"}
    )
    assert second.status_code == 400
    assert second.json()["errors"][0]["code"] == "INVALID_RESET_TOKEN"


async def test_reset_password_rejects_invalid_token(client):
    resp = await client.post(
        "/api/v1/auth/reset-password", json={"token": "not-a-real-token", "new_password": "SomePass!123456"}
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "INVALID_RESET_TOKEN"


# --------------------------------------------------------------------------- reset semantics


async def test_successful_reset_revokes_all_refresh_tokens(client, db_session):
    from app.modules.identity.models.refresh_token import RefreshToken
    from app.modules.identity.models.user import User
    from app.modules.identity.services.auth_service import AuthService

    email = await _register(client)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "ResetTestPass!42"})
    assert login.status_code == 200

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()

    service = AuthService(db_session)
    plaintext_token = await service.request_password_reset(email)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/reset-password", json={"token": plaintext_token, "new_password": "PostResetPass!77"}
    )
    assert resp.status_code == 200

    rows = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    ).scalars().all()
    assert rows, "expected at least one refresh token row for this user"
    assert all(r.revoked_at is not None for r in rows), "reset must revoke every existing refresh token"


async def test_reset_password_does_not_auto_login(client, db_session):
    from app.modules.identity.services.auth_service import AuthService

    email = await _register(client)
    service = AuthService(db_session)
    plaintext_token = await service.request_password_reset(email)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/reset-password", json={"token": plaintext_token, "new_password": "NoAutoLoginPass!5"}
    )
    assert resp.status_code == 200
    assert "access_token" not in resp.cookies

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


async def test_new_password_works_old_password_rejected(client, db_session):
    from app.modules.identity.services.auth_service import AuthService

    email = await _register(client)
    login_old = await client.post("/api/v1/auth/login", json={"email": email, "password": "ResetTestPass!42"})
    assert login_old.status_code == 200
    await client.post("/api/v1/auth/logout")

    service = AuthService(db_session)
    plaintext_token = await service.request_password_reset(email)
    await db_session.commit()

    reset = await client.post(
        "/api/v1/auth/reset-password", json={"token": plaintext_token, "new_password": "BrandNewPass!88"}
    )
    assert reset.status_code == 200

    old_login = await client.post("/api/v1/auth/login", json={"email": email, "password": "ResetTestPass!42"})
    assert old_login.status_code == 401

    new_login = await client.post("/api/v1/auth/login", json={"email": email, "password": "BrandNewPass!88"})
    assert new_login.status_code == 200


async def test_reset_url_uses_configured_web_app_url(monkeypatch):
    from app.core.config import get_settings
    from app.modules.identity.services import email_service

    get_settings.cache_clear()
    monkeypatch.setenv("WEB_APP_URL", "https://neet.trinetralab.net")
    get_settings.cache_clear()

    captured: dict[str, str] = {}

    async def _fake_send(*, to, subject, body, kind):
        captured.update(to=to, subject=subject, body=body, kind=kind)

    monkeypatch.setattr(email_service, "_send", _fake_send)

    await email_service.send_password_reset_email(to="someone@example.com", token="abc123")

    assert "https://neet.trinetralab.net/reset-password?token=abc123" in captured["body"]
    assert "localhost" not in captured["body"]
    get_settings.cache_clear()


# --------------------------------------------------------------------------- email delivery failure handling


async def test_email_provider_failure_does_not_break_forgot_password_response(client, monkeypatch):
    from app.modules.identity.services import email_service

    async def _boom(**_kwargs):
        raise ConnectionError("simulated provider outage")

    monkeypatch.setattr(email_service, "send_password_reset_email", _boom)

    email = await _register(client)
    resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})

    assert resp.status_code == 200
    assert "sent" in resp.json()["data"]["message"].lower() or "exists" in resp.json()["data"]["message"].lower()


async def test_production_email_failure_is_logged_safely_no_credentials_leaked(monkeypatch):
    """Production never attempts SMTP (see email_service.py) — this exercises
    the HTTPS provider failure path, which is what production actually uses."""
    import structlog

    from app.core.config import Settings
    from app.modules.identity.services import email_service

    fake_settings = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        jwt_secret="test-secret-not-real",
        encryption_key="uLCw_rsupBRTzp7bhuN_iuxiMiXgpxc6DujbFR_sXkM=",
        environment="production",
        email_provider="resend",
        email_api_key="super-secret-resend-api-key",
        email_from="noreply@example.com",
    )
    monkeypatch.setattr(email_service, "get_settings", lambda: fake_settings)

    async def _boom(*, to, subject, body, settings):
        raise ConnectionError("simulated provider connection failure")

    monkeypatch.setattr(email_service, "_send_via_resend", _boom)

    with structlog.testing.capture_logs() as captured:
        await email_service.send_password_reset_email(to="user@example.com", token="sometoken123")

    log_text = " ".join(str(event) for event in captured)
    assert "super-secret-resend-api-key" not in log_text
    assert any(event.get("event") == "email_send_failed" for event in captured)


async def test_production_never_attempts_smtp_even_if_smtp_vars_are_set(monkeypatch):
    """The whole point of this change: even if SMTP_* env vars are still
    present on production, they must never be used there — only the HTTPS
    provider (or the safe no-op) is attempted."""
    from app.core.config import Settings
    from app.modules.identity.services import email_service

    fake_settings = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        jwt_secret="test-secret-not-real",
        encryption_key="uLCw_rsupBRTzp7bhuN_iuxiMiXgpxc6DujbFR_sXkM=",
        environment="production",
        smtp_host="smtp.gmail.com",
        smtp_from="noreply@example.com",
        # email_provider intentionally unset -> should hit the safe
        # "email_not_configured" branch, never smtplib.
    )
    monkeypatch.setattr(email_service, "get_settings", lambda: fake_settings)

    def _smtp_should_never_be_called(*_a, **_k):
        raise AssertionError("SMTP must never be attempted in production")

    monkeypatch.setattr(email_service.smtplib, "SMTP", _smtp_should_never_be_called)

    # Must return promptly (no 8s SMTP-connect hang) and not raise.
    await email_service.send_password_reset_email(to="user@example.com", token="sometoken123")
