"""Focused coverage for confirmed audit gaps (finding not previously tested):

- MFA login via recovery code, and recovery-code single-use rejection
- MFA disable flow
- CSRF rejection when the header is missing/wrong on a CSRF-protected route
- Negative alert test: normal 4xx (wrong password, invalid OTP, validation,
  401/403/404/429) must NOT trigger the admin incident-alert path

Reuses existing fixtures/conventions (client, db_session, csrf_headers,
the established rate-limit-bypass monkeypatch, pyotp already used by
test_security_wave_c.py) rather than new test infrastructure.
"""

from __future__ import annotations

import uuid

import pyotp
import pytest

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    from app.core import rate_limit as rl

    async def no_limit(key: str, *, limit: int, window_seconds: int, fail_closed: bool, log_key: str | None = None) -> None:
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


def _mobile() -> str:
    import random

    return str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))


async def _register_and_enable_totp(client, email: str, password: str) -> tuple[str, list[str]]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "Mfa",
            "last_name": "Test",
            "mobile": _mobile(),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": password,
        },
    )
    assert resp.status_code == 201, resp.text

    setup = await client.post("/api/v1/auth/totp/setup", headers=csrf_headers(client))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["data"]["secret"]

    confirm = await client.post(
        "/api/v1/auth/totp/confirm", headers=csrf_headers(client), json={"code": pyotp.TOTP(secret).now()}
    )
    assert confirm.status_code == 200, confirm.text
    recovery_codes = confirm.json()["data"]["recoveryCodes"]
    return secret, recovery_codes


# --------------------------------------------------------------------------- MFA recovery


async def test_mfa_login_with_recovery_code_succeeds(client):
    email = f"mfa-recovery-{uuid.uuid4().hex[:12]}@example.com"
    password = "MfaRecoveryPass!5"
    _secret, recovery_codes = await _register_and_enable_totp(client, email, password)
    await client.post("/api/v1/auth/logout")

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    mfa_token = login.json()["data"]["mfaToken"]

    verify = await client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "code": recovery_codes[0]}
    )
    assert verify.status_code == 200, verify.text

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200


async def test_used_recovery_code_cannot_be_reused(client):
    email = f"mfa-recovery-reuse-{uuid.uuid4().hex[:12]}@example.com"
    password = "MfaRecoveryReusePass!5"
    _secret, recovery_codes = await _register_and_enable_totp(client, email, password)
    await client.post("/api/v1/auth/logout")

    first_login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    first_verify = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": first_login.json()["data"]["mfaToken"], "code": recovery_codes[0]},
    )
    assert first_verify.status_code == 200
    await client.post("/api/v1/auth/logout")

    second_login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    second_verify = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": second_login.json()["data"]["mfaToken"], "code": recovery_codes[0]},
    )
    assert second_verify.status_code == 401, "an already-used recovery code must not authenticate a second time"


async def test_mfa_disable_requires_valid_code_and_removes_requirement(client):
    email = f"mfa-disable-{uuid.uuid4().hex[:12]}@example.com"
    password = "MfaDisablePass!5"
    secret, _recovery_codes = await _register_and_enable_totp(client, email, password)

    wrong = await client.post(
        "/api/v1/auth/totp/disable", headers=csrf_headers(client), json={"code": "000000"}
    )
    assert wrong.status_code == 400

    disable = await client.post(
        "/api/v1/auth/totp/disable", headers=csrf_headers(client), json={"code": pyotp.TOTP(secret).now()}
    )
    assert disable.status_code == 200
    assert disable.json()["data"]["enabled"] is False

    await client.post("/api/v1/auth/logout")
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert "mfaRequired" not in login.json()["data"], "MFA must no longer be required after disable"


# --------------------------------------------------------------------------- CSRF


async def test_csrf_protected_route_rejects_missing_header(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"csrf-{uuid.uuid4().hex[:12]}@example.com",
            "first_name": "Csrf",
            "last_name": "Test",
            "mobile": _mobile(),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": "CsrfTestPass!42",
        },
    )
    assert resp.status_code == 201

    # /totp/setup is CSRF-protected (verify_csrf dependency). Omit the header.
    no_header = await client.post("/api/v1/auth/totp/setup")
    assert no_header.status_code == 403
    assert no_header.json()["errors"][0]["code"] == "CSRF_INVALID"

    wrong_header = await client.post("/api/v1/auth/totp/setup", headers={"X-CSRF-Token": "not-the-real-token"})
    assert wrong_header.status_code == 403
    assert wrong_header.json()["errors"][0]["code"] == "CSRF_INVALID"


# --------------------------------------------------------------------------- negative alert cases


async def test_normal_auth_failures_do_not_trigger_admin_alert(client, monkeypatch):
    """Wrong password, invalid OTP-shaped input, validation error, 401/403/404
    all route through app_error_handler / http_exception_handler /
    validation_exception_handler — none of which call schedule_unexpected_incident.
    This asserts that end-to-end: no alert email attempt is made for any of them."""
    from app.core import alerts as alerts_mod
    from app.main import app
    from app.modules.identity.api.auth_router import get_twilio_verify
    from app.modules.identity.services.twilio_verify_service import TwilioVerifyStub

    # Stub Twilio so the wrong-OTP case below exercises the normal
    # "wrong code" 401 path rather than the unrelated (and correctly
    # separately-alerting) TWILIO_VERIFY_NOT_CONFIGURED 503 fail-closed
    # path — this test's own dev/CI environment has no real Twilio config.
    app.dependency_overrides[get_twilio_verify] = lambda: TwilioVerifyStub(seeded_code="123456")

    alert_calls: list[str] = []

    async def _track(*args, **kwargs):
        alert_calls.append(kwargs.get("dedupe_key", "unknown"))
        return True

    monkeypatch.setattr(alerts_mod, "maybe_send_critical_alert", _track)

    email = f"no-alert-{uuid.uuid4().hex[:12]}@example.com"
    password = "NoAlertTestPass!5"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "NoAlert",
            "last_name": "Test",
            "mobile": _mobile(),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": password,
        },
    )
    assert reg.status_code == 201
    await client.post("/api/v1/auth/logout")

    # wrong password -> 401
    wrong_pw = await client.post("/api/v1/auth/login", json={"email": email, "password": "WrongOne!123456"})
    assert wrong_pw.status_code == 401

    # validation error -> 422
    bad_body = await client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert bad_body.status_code == 422

    # 404
    not_found = await client.get("/api/v1/auth/does-not-exist")
    assert not_found.status_code == 404

    # invalid mobile OTP verify -> 401
    try:
        bad_otp = await client.post(
            "/api/v1/auth/mobile/otp/verify", json={"mobile": "+919876500999", "code": "000000"}
        )
        assert bad_otp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_twilio_verify, None)

    # forbidden (CSRF) -> 403
    forbidden = await client.post("/api/v1/auth/totp/setup")
    assert forbidden.status_code in (401, 403)

    assert alert_calls == [], f"normal 4xx failures must never trigger an admin alert, but got: {alert_calls}"
