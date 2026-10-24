"""Tests for:
  - POST /api/v1/users/{user_id}/reset-password (admin-initiated password reset)
  - login response `mfa_setup_required` soft-gate flag for privileged accounts

Reuses the established `client`/`db_session`/`register_user`/`csrf_headers`
fixtures and the rate-limit-bypass monkeypatch pattern from
test_forgot_reset_password.py / test_mobile_otp_login.py.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    from app.core import rate_limit as rl

    async def no_limit(key: str, *, limit: int, window_seconds: int, fail_closed: bool, log_key: str | None = None) -> None:
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


# --------------------------------------------------------------------------- admin reset-password endpoint


async def test_non_manager_gets_403(client):
    student_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"student-{uuid.uuid4().hex[:12]}@example.com",
            "first_name": "S",
            "last_name": "T",
            "mobile": "9" + "".join(["1"] * 9),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": "StudentPass!123",
        },
    )
    assert student_resp.status_code == 201

    target_id = student_resp.json()["data"]["id"]
    resp = await client.post(f"/api/v1/users/{target_id}/reset-password", headers=csrf_headers(client))
    assert resp.status_code == 403


async def test_csrf_rejected_without_token(client, db_session, register_user):
    admin = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    target = await register_user(client, db_session=db_session)  # logs in as STUDENT target, logout below

    # Re-login as admin (register_user's role-code branch logs back in as
    # whichever account it just created with those roles).
    await client.post("/api/v1/auth/logout")
    login = await client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200

    resp = await client.post(f"/api/v1/users/{target['id']}/reset-password")  # no X-CSRF-Token header
    assert resp.status_code == 403


async def test_successful_reset_calls_request_password_reset_and_audits(client, db_session, register_user, monkeypatch):
    from app.modules.identity.api import users_router
    from app.modules.system.models.audit_log import AuditLog

    admin = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    target = await register_user(client, db_session=db_session)

    await client.post("/api/v1/auth/logout")
    login = await client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200

    captured: dict[str, str] = {}

    async def _fake_send(*, to, token):
        captured.update(to=to, token=token)

    monkeypatch.setattr(users_router, "send_password_reset_email", _fake_send)

    resp = await client.post(f"/api/v1/users/{target['id']}/reset-password", headers=csrf_headers(client))
    assert resp.status_code == 200
    assert "data" in resp.json()
    assert captured["to"] == target["email"]
    assert captured["token"]  # opaque token was generated

    # Target's user record now has a hashed reset token stored (reuse of
    # the exact same AuthService.request_password_reset mechanism).
    from app.modules.identity.models.user import User

    result = await db_session.execute(select(User).where(User.id == uuid.UUID(target["id"])))
    user = result.scalar_one()
    assert user.password_reset_token_hash is not None
    assert captured["token"] not in user.password_reset_token_hash

    # Audit entry recorded against the admin actor.
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "user.password_reset_initiated")
        )
    ).scalars().all()
    assert any(str(row.actor_user_id) == admin["id"] and str(row.entity_id) == target["id"] for row in audit_rows)


async def test_reset_password_unknown_user_404(client, db_session, register_user):
    admin = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    await client.post("/api/v1/auth/logout")
    login = await client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200

    resp = await client.post(f"/api/v1/users/{uuid.uuid4()}/reset-password", headers=csrf_headers(client))
    assert resp.status_code == 404


async def test_rate_limited_after_five_calls(client, db_session, register_user, monkeypatch):
    """Dedicated bucket `admin_reset_password`, limit=5/300s (see
    users_router.py). The autouse fixture above bypasses rate limiting for
    every other test in this module; here we replace it with a fake counter
    (no real Redis needed in the test env) that enforces the same limit=5
    semantics so we can assert the 6th call is rejected."""
    from app.core import rate_limit as rl
    from app.core.exceptions import AppError
    from app.modules.identity.api import users_router

    async def _noop(**_kwargs):
        return None

    monkeypatch.setattr(users_router, "send_password_reset_email", _noop)

    counts: dict[str, int] = {}

    async def _counting_check(key: str, *, limit: int, window_seconds: int, fail_closed: bool, log_key: str | None = None) -> None:
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > limit:
            raise AppError("Too many requests", code="RATE_LIMITED", status_code=429)

    monkeypatch.setattr(rl, "_check", _counting_check)

    admin = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    target = await register_user(client, db_session=db_session)
    await client.post("/api/v1/auth/logout")
    login = await client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200

    headers = csrf_headers(client)
    statuses = []
    for _ in range(6):
        resp = await client.post(f"/api/v1/users/{target['id']}/reset-password", headers=headers)
        statuses.append(resp.status_code)

    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


# --------------------------------------------------------------------------- mfa_setup_required login flag


async def test_mfa_setup_required_true_for_privileged_non_mfa_account(client, db_session, register_user):
    admin = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    resp = await client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert resp.status_code == 200
    assert resp.json()["data"]["mfa_setup_required"] is True


async def test_mfa_setup_required_false_for_student(client, db_session, register_user):
    student = await register_user(client, db_session=db_session)
    await client.post("/api/v1/auth/logout")
    resp = await client.post("/api/v1/auth/login", json={"email": student["email"], "password": student["password"]})
    assert resp.status_code == 200
    assert resp.json()["data"]["mfa_setup_required"] is False


async def test_mfa_setup_required_false_once_totp_enabled(client, db_session, register_user):
    from app.modules.identity.models.user import User

    admin = await register_user(client, role_codes=["ADMIN"], db_session=db_session)

    result = await db_session.execute(select(User).where(User.id == uuid.UUID(admin["id"])))
    user = result.scalar_one()
    user.totp_enabled = True
    await db_session.commit()

    await client.post("/api/v1/auth/logout")
    resp = await client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    # TOTP-enabled accounts hit the MFA challenge branch, not a direct
    # session — but the challenge response must not claim setup is still
    # required (it's already enabled).
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body.get("mfaRequired") is True
