"""Wave C: OTP hashing, TOTP MFA step-up, change-password, alert dedupe."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pyotp
import pytest
from sqlalchemy import select

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.logging import REDACTED, redact_event_dict
from app.modules.identity.models.otp import OtpChallenge
from app.modules.identity.services.token_service import hash_opaque_token
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _email() -> str:
    return f"wave-c-{uuid.uuid4().hex[:12]}@example.com"


# User-chosen password submitted at registration and validated against
# validate_password_policy. Becomes the "current password" for the first
# change-password call in this suite.
PASSWORD = "WaveCTestPass!7"


async def _register(client, email: str):
    # Unique 10-digit Indian mobile per registration to avoid the partial
    # unique index on identity.users(lower(mobile_e164)).
    import random

    mobile10 = str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "WaveC",
            "last_name": "Test",
            "mobile": mobile10,
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": PASSWORD,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def test_encrypt_decrypt_roundtrip():
    ct = encrypt_secret("BASE32SECRETTESTVALUE")
    assert ct != "BASE32SECRETTESTVALUE"
    assert decrypt_secret(ct) == "BASE32SECRETTESTVALUE"


def test_otp_never_appears_in_redacted_logs():
    event = redact_event_dict(None, "info", {"event": "otp_requested", "otp": "654321", "code": "654321"})
    assert event["otp"] == REDACTED


async def test_change_password_rejects_wrong_current(client):
    email = _email()
    await _register(client, email)
    resp = await client.post(
        "/api/v1/auth/change-password",
        headers=csrf_headers(client),
        json={"current_password": "WrongCurrent!1", "new_password": "BrandNewPass!99"},
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "INVALID_PASSWORD"


async def test_change_password_success_clears_cookies(client):
    email = _email()
    await _register(client, email)
    resp = await client.post(
        "/api/v1/auth/change-password",
        headers=csrf_headers(client),
        json={"current_password": PASSWORD, "new_password": "BrandNewPass!99"},
    )
    assert resp.status_code == 200, resp.text
    # After change, cookies cleared — me should fail
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


async def test_otp_request_and_verify(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)
    await client.post("/api/v1/auth/logout")

    captured: dict[str, str] = {}

    def capture_send(*, to, subject, body, kind):
        captured["body"] = body
        captured["to"] = to
        captured["kind"] = kind

    monkeypatch.setattr("app.modules.identity.services.otp_service._send", capture_send)

    from app.core import rate_limit as rl

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)

    resp = await client.post(
        "/api/v1/auth/otp/request",
        json={"email": email, "purpose": "email_verify"},
    )
    assert resp.status_code == 200, resp.text
    assert "code" not in resp.json()["data"]
    assert captured.get("kind") == "otp"
    import re

    match = re.search(r"\b(\d{6})\b", captured["body"])
    assert match
    code = match.group(1)

    row = (
        await db_session.execute(
            select(OtpChallenge).where(OtpChallenge.destination == email.lower()).order_by(OtpChallenge.created_at.desc())
        )
    ).scalar_one()
    assert row.code_hash == hash_opaque_token(code)
    assert row.code_hash != code

    bad = await client.post(
        "/api/v1/auth/otp/verify",
        json={"email": email, "purpose": "email_verify", "code": "000000"},
    )
    assert bad.status_code == 400

    ok = await client.post(
        "/api/v1/auth/otp/verify",
        json={"email": email, "purpose": "email_verify", "code": code},
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["verified"] is True


async def test_totp_enroll_and_mfa_login(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)

    from app.core import rate_limit as rl

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)

    setup = await client.post("/api/v1/auth/totp/setup", headers=csrf_headers(client))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["data"]["secret"]
    assert "otpauth_url" in setup.json()["data"]

    code = pyotp.TOTP(secret).now()
    confirm = await client.post(
        "/api/v1/auth/totp/confirm",
        headers=csrf_headers(client),
        json={"code": code},
    )
    assert confirm.status_code == 200, confirm.text
    recovery = confirm.json()["data"]["recoveryCodes"]
    assert len(recovery) == 8

    await client.post("/api/v1/auth/logout")

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    body = login.json()["data"]
    assert body.get("mfaRequired") is True
    assert "mfaToken" in body
    me_before = await client.get("/api/v1/auth/me")
    assert me_before.status_code == 401

    mfa_code = pyotp.TOTP(secret).now()
    mfa = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": body["mfaToken"], "code": mfa_code},
    )
    assert mfa.status_code == 200, mfa.text
    assert mfa.json()["data"]["totp_enabled"] is True
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200


async def test_alert_dedupe_skips_second_send(monkeypatch):
    from app.core import alerts as alerts_mod
    from app.core.config import get_settings

    sent: list[str] = []

    def fake_send(*, subject, body):
        sent.append(subject)

    redis = MagicMock()
    redis.set = AsyncMock(side_effect=[True, False])

    settings = get_settings()
    monkeypatch.setattr(settings, "error_reporting_enabled", True)
    monkeypatch.setattr(settings, "alert_email", "ravishori@gmail.com")
    monkeypatch.setattr(alerts_mod, "get_redis", lambda: redis)
    monkeypatch.setattr(alerts_mod, "send_security_alert_email", fake_send)

    assert await alerts_mod.maybe_send_critical_alert(subject="s1", body="b", dedupe_key="k1") is True
    assert await alerts_mod.maybe_send_critical_alert(subject="s2", body="b", dedupe_key="k1") is False
    assert len(sent) == 1
    assert "password" not in sent[0].lower()
