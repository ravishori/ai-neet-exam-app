"""Step 4 of the auth/OTP audit: mandatory TOTP MFA enforcement for
SUPER_ADMIN/ADMIN accounts (docs/authentication.md "MFA enforcement for
privileged accounts", step 4 of its migration path).

Covers:
1. Default (ENFORCE_MFA_FOR_PRIVILEGED_ROLES=False): a privileged account
   without TOTP logs in exactly as before -- this flag is OFF in
   production right now (zero admin accounts have TOTP confirmed per the
   doc), so a regression here would lock out every real admin.
2. Enforcement ON: a privileged account without TOTP is blocked at
   password login with 403/MFA_SETUP_REQUIRED + a setup token, instead of
   getting a session.
3. The same gate fires on the email-OTP login path and the mobile-OTP
   login path (both of which can also issue a full session).
4. A non-privileged account is never gated, regardless of the flag.
5. A privileged account that has ALREADY enrolled in TOTP is never routed
   through the setup gate -- it goes through the existing, unaffected
   mfaRequired challenge instead (no double-gating).
6. The /mfa-setup/begin + /mfa-setup/confirm flow: completes enrollment
   using only the setup token (no session cookie ever existed), and winds
   up with a real session + recovery codes.
7. An invalid/expired/wrong-type setup token is rejected by both
   /mfa-setup/* routes.
"""

from __future__ import annotations

import uuid

import pyotp
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    from app.core import rate_limit as rl

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


@pytest.fixture
def _enforce_mfa(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "enforce_mfa_for_privileged_roles", True)


@pytest.fixture
def _mobile_otp_enabled(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "mobile_otp_login_enabled", True)


def _mobile() -> str:
    import random

    return str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))


def _email(tag: str = "mfa-enforce") -> str:
    return f"{tag}-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client, email: str, password: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "MfaEnforce",
            "last_name": "Test",
            "mobile": _mobile(),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": password,
        },
    )
    assert resp.status_code == 201, resp.text
    await client.post("/api/v1/auth/logout")


async def _make_admin(db_session, email: str) -> None:
    """Grant the ADMIN role to the just-registered user, directly via the
    DB -- there is no public self-service "become admin" endpoint, and
    this test's own role-assignment mechanics aren't what's under test."""
    from sqlalchemy import select

    from app.modules.identity.models.role import Role, UserRole
    from app.modules.identity.models.user import User

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    role = (await db_session.execute(select(Role).where(Role.code == "ADMIN"))).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. Default: flag off, no behavior change
# ---------------------------------------------------------------------------


async def test_default_flag_off_privileged_account_without_totp_logs_in_normally(client, db_session):
    email = _email()
    password = "MfaEnforceOffPass!42"
    await _register(client, email, password)
    await _make_admin(db_session, email)

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    assert "mfaSetupToken" not in login.json().get("data", {})

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["mfa_setup_required"] is True  # soft-gate signal still present


# ---------------------------------------------------------------------------
# 2. Enforcement on: password login blocked
# ---------------------------------------------------------------------------


async def test_enforcement_on_blocks_password_login_for_privileged_account_without_totp(
    client, db_session, _enforce_mfa
):
    email = _email()
    password = "MfaEnforceOnPass!42"
    await _register(client, email, password)
    await _make_admin(db_session, email)

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 403, login.text
    body = login.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "MFA_SETUP_REQUIRED"
    assert body["data"]["mfaSetupToken"]
    assert body["data"]["email"] == email
    assert "access_token" not in login.cookies
    assert "refresh_token" not in login.cookies


async def test_enforcement_on_does_not_block_non_privileged_account(client, _enforce_mfa):
    email = _email()
    password = "MfaEnforceStudentPass!42"
    await _register(client, email, password)

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    assert "mfaSetupToken" not in login.json().get("data", {})


async def test_already_enrolled_admin_gets_mfa_required_not_setup_required(client, db_session, monkeypatch):
    """A privileged account that already completed TOTP enrollment must go
    through the existing mfaRequired challenge exactly as before -- the
    Step 4 gate is for accounts that have NOT enrolled, not a second
    factor on top of an already-satisfied one."""
    from app.core.config import get_settings

    email = _email()
    password = "MfaEnforceEnrolled2Pass!42"
    await _register(client, email, password)
    await _make_admin(db_session, email)

    # Enroll while enforcement is off so the normal login+totp/setup flow
    # is available (a separate test already proves the blocked path).
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text

    csrf_cookie = login.cookies.get("csrf_token")
    setup = await client.post("/api/v1/auth/totp/setup", headers={"X-CSRF-Token": csrf_cookie})
    assert setup.status_code == 200, setup.text
    secret = setup.json()["data"]["secret"]
    confirm = await client.post(
        "/api/v1/auth/totp/confirm", headers={"X-CSRF-Token": csrf_cookie}, json={"code": pyotp.TOTP(secret).now()}
    )
    assert confirm.status_code == 200, confirm.text
    await client.post("/api/v1/auth/logout")

    # Now turn enforcement on and log in again -- must get the ORDINARY
    # mfaRequired challenge, not MFA_SETUP_REQUIRED.
    monkeypatch.setattr(get_settings(), "enforce_mfa_for_privileged_roles", True)
    second_login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert second_login.status_code == 200, second_login.text
    assert second_login.json()["data"].get("mfaRequired") is True
    assert "mfaSetupToken" not in second_login.json().get("data", {})


# ---------------------------------------------------------------------------
# 3. Same gate on email-OTP and mobile-OTP login paths
# ---------------------------------------------------------------------------


async def test_enforcement_on_blocks_email_otp_login_for_privileged_account_without_totp(
    client, db_session, monkeypatch, _enforce_mfa
):
    email = _email()
    password = "MfaEnforceEmailOtpPass!42"
    await _register(client, email, password)
    await _make_admin(db_session, email)

    captured: dict[str, str] = {}

    async def capture_send(*, to, code):
        captured["code"] = code

    monkeypatch.setattr("app.modules.identity.services.otp_service.send_login_otp_email", capture_send)
    req = await client.post("/api/v1/auth/otp/request", json={"email": email, "purpose": "email_login"})
    assert req.status_code == 200, req.text

    verify = await client.post(
        "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": captured["code"]}
    )
    assert verify.status_code == 403, verify.text
    assert verify.json()["errors"][0]["code"] == "MFA_SETUP_REQUIRED"
    assert verify.json()["data"]["mfaSetupToken"]


async def test_enforcement_on_blocks_mobile_otp_login_for_privileged_account_without_totp(
    client, db_session, _enforce_mfa, _mobile_otp_enabled
):
    from app.main import app
    from app.modules.identity.api.auth_router import get_twilio_verify
    from app.modules.identity.services.twilio_verify_service import TwilioVerifyStub

    email = _email()
    password = "MfaEnforceMobileOtpPass!42"
    mobile = _mobile()
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "MfaEnforce",
            "last_name": "Mobile",
            "mobile": mobile,
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": password,
        },
    )
    assert resp.status_code == 201, resp.text
    await client.post("/api/v1/auth/logout")
    await _make_admin(db_session, email)

    from app.modules.identity.services.profile_validation import normalize_indian_mobile

    stub = TwilioVerifyStub()
    stub.seed(normalize_indian_mobile(mobile), "123456")
    app.dependency_overrides[get_twilio_verify] = lambda: stub
    try:
        verify = await client.post("/api/v1/auth/mobile/otp/verify", json={"mobile": mobile, "code": "123456"})
        assert verify.status_code == 403, verify.text
        assert verify.json()["errors"][0]["code"] == "MFA_SETUP_REQUIRED"
        assert verify.json()["data"]["mfaSetupToken"]
    finally:
        app.dependency_overrides.pop(get_twilio_verify, None)


# ---------------------------------------------------------------------------
# 6/7. The /mfa-setup/* flow itself
# ---------------------------------------------------------------------------


async def test_mfa_setup_flow_completes_enrollment_and_issues_a_session(client, db_session, _enforce_mfa):
    email = _email()
    password = "MfaSetupFlowPass!42"
    await _register(client, email, password)
    await _make_admin(db_session, email)

    blocked = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert blocked.status_code == 403, blocked.text
    setup_token = blocked.json()["data"]["mfaSetupToken"]

    begin = await client.post("/api/v1/auth/mfa-setup/begin", json={"setup_token": setup_token})
    assert begin.status_code == 200, begin.text
    secret = begin.json()["data"]["secret"]

    confirm = await client.post(
        "/api/v1/auth/mfa-setup/confirm",
        json={"setup_token": setup_token, "code": pyotp.TOTP(secret).now()},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["data"]["recoveryCodes"]
    assert "access_token" in confirm.cookies

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["totp_enabled"] is True
    assert me.json()["data"]["mfa_setup_required"] is False


async def test_mfa_setup_begin_rejects_invalid_token(client, _enforce_mfa):
    resp = await client.post("/api/v1/auth/mfa-setup/begin", json={"setup_token": "not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "MFA_SETUP_TOKEN_INVALID"


async def test_mfa_setup_confirm_rejects_an_ordinary_mfa_pending_token(client, db_session, _enforce_mfa):
    """An mfa_pending token (from the existing, unrelated TOTP-challenge
    flow) must not work here -- the two token types are deliberately
    distinct (see decode_mfa_setup_pending_token's own type check)."""
    from app.modules.identity.services.token_service import create_mfa_pending_token

    email = _email()
    password = "MfaSetupWrongTokenPass!42"
    await _register(client, email, password)
    await _make_admin(db_session, email)
    from sqlalchemy import select

    from app.modules.identity.models.user import User

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    wrong_type_token = create_mfa_pending_token(user_id=user.id)

    resp = await client.post(
        "/api/v1/auth/mfa-setup/confirm", json={"setup_token": wrong_type_token, "code": "000000"}
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "MFA_SETUP_TOKEN_INVALID"


# ---------------------------------------------------------------------------
# Route wiring
# ---------------------------------------------------------------------------


def test_mfa_setup_routes_are_registered():
    from app.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/v1/auth/mfa-setup/begin" in paths
    assert "/api/v1/auth/mfa-setup/confirm" in paths
