"""Email-OTP login — verifying the `email_login` purpose issues a real
session (cookies), unlike the informational purposes (email_verify,
sensitive_action, login_stepup) which only return {"verified": true}."""

import uuid
from unittest.mock import AsyncMock

import pyotp
import pytest
from sqlalchemy import select

from app.modules.identity.models.otp import OtpChallenge
from app.modules.identity.services.token_service import hash_opaque_token
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    from app.core import rate_limit as rl

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


def _email() -> str:
    return f"email-otp-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client, email: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "Email",
            "last_name": "Otp",
            "mobile": "9876500201",
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": "EmailOtpPass!42",
        },
    )
    assert resp.status_code == 201, resp.text


async def _capture_code(client, email: str, monkeypatch, purpose: str) -> str:
    """otp_service picks send_login_otp_email vs send_email_verification_otp_email
    based on purpose (see OtpService._LOGIN_OTP_PURPOSES) — patch both so this
    helper works regardless of which purpose the caller passes."""
    captured: dict[str, str] = {}

    async def capture_send(*, to, code):
        captured["code"] = code

    monkeypatch.setattr("app.modules.identity.services.otp_service.send_login_otp_email", capture_send)
    monkeypatch.setattr("app.modules.identity.services.otp_service.send_email_verification_otp_email", capture_send)

    resp = await client.post("/api/v1/auth/otp/request", json={"email": email, "purpose": purpose})
    assert resp.status_code == 200, resp.text
    return captured["code"]


async def test_otp_request_actually_awaits_send(client, db_session, monkeypatch):
    """Regression test: OtpService.request_email_otp must `await` the
    outbound send. A bare (un-awaited) call to an async `_send` silently
    creates and discards a coroutine — the function body never runs, no
    email is ever sent, and no error surfaces anywhere, while the API still
    returns 200. AsyncMock distinguishes "called" from "awaited": call_count
    increments even for a bare, non-awaited call, but await_count only
    increments if the coroutine was actually awaited — which is exactly the
    distinction this bug hides from a plain synchronous mock."""
    email = _email()
    mock_send = AsyncMock()
    monkeypatch.setattr("app.modules.identity.services.otp_service.send_login_otp_email", mock_send)

    resp = await client.post("/api/v1/auth/otp/request", json={"email": email, "purpose": "email_login"})
    assert resp.status_code == 200, resp.text

    assert mock_send.call_count == 1
    assert mock_send.await_count == 1, (
        "_send was called but never awaited — the OTP email would never "
        "actually be sent in production despite the API reporting success."
    )


async def test_email_otp_login_issues_session(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)
    await client.post("/api/v1/auth/logout")

    code = await _capture_code(client, email, monkeypatch, "email_login")

    resp = await client.post("/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": code})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["email"] == email
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["email"] == email


async def test_email_otp_login_wrong_code_no_session(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)
    await client.post("/api/v1/auth/logout")

    await _capture_code(client, email, monkeypatch, "email_login")

    resp = await client.post("/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": "000000"})
    assert resp.status_code == 400
    assert "access_token" not in resp.cookies


async def test_email_verify_purpose_still_returns_verified_flag_not_session(client, db_session, monkeypatch):
    """Non-login purposes must keep their old, non-session behavior."""
    email = _email()
    await _register(client, email)
    await client.post("/api/v1/auth/logout")

    code = await _capture_code(client, email, monkeypatch, "email_verify")

    resp = await client.post("/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_verify", "code": code})
    assert resp.status_code == 200
    assert resp.json()["data"] == {"verified": True}
    assert "access_token" not in resp.cookies


async def test_email_otp_login_unknown_email_generic_error(client, db_session, monkeypatch):
    """An OTP challenge can exist for an email with no account (e.g. request
    raced with account deletion) — verify must fail generically, never 500,
    and never establish a session."""
    email = _email()
    captured: dict[str, str] = {}

    async def capture_send(*, to, code):
        captured["code"] = code

    monkeypatch.setattr("app.modules.identity.services.otp_service.send_login_otp_email", capture_send)
    from app.core import rate_limit as rl

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)

    resp = await client.post("/api/v1/auth/otp/request", json={"email": email, "purpose": "email_login"})
    assert resp.status_code == 200
    code = captured["code"]

    verify = await client.post("/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": code})
    assert verify.status_code == 400
    assert "access_token" not in verify.cookies


async def test_email_otp_login_with_totp_enabled_requires_mfa_step_up(client, db_session, monkeypatch):
    """A user who has voluntarily enabled TOTP must not be able to skip their
    second factor by using Email-OTP instead of password login."""
    email = _email()
    await _register(client, email)

    from app.core import rate_limit as rl

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)

    setup = await client.post("/api/v1/auth/totp/setup", headers=csrf_headers(client))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["data"]["secret"]

    confirm = await client.post(
        "/api/v1/auth/totp/confirm",
        headers=csrf_headers(client),
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert confirm.status_code == 200, confirm.text

    await client.post("/api/v1/auth/logout")

    code = await _capture_code(client, email, monkeypatch, "email_login")
    resp = await client.post("/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": code})
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body.get("mfaRequired") is True
    assert "mfaToken" in body
    assert "access_token" not in resp.cookies

    me_before = await client.get("/api/v1/auth/me")
    assert me_before.status_code == 401

    bad_mfa = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": body["mfaToken"], "code": "000000"},
    )
    assert bad_mfa.status_code in (400, 401)
    assert "access_token" not in bad_mfa.cookies

    good_mfa = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": body["mfaToken"], "code": pyotp.TOTP(secret).now()},
    )
    assert good_mfa.status_code == 200, good_mfa.text
    assert "access_token" in good_mfa.cookies

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["email"] == email
