"""Prompt B, session-time active-role selector: one account, one login
identity, can hold multiple roles (unchanged, already-supported many-to-
many user_roles) and choose which role to present as for a given session
via POST /switch-role, without ever changing what the account can
actually do (every authorization check still reads the full role_codes
set -- see app.modules.identity.role_priority's own docstring).

Covers:
1. A single-role account's active_role defaults to its only role, and
   /switch-role rejects a role it doesn't hold.
2. A multi-role account defaults to the highest-priority role
   (SUPER_ADMIN > ADMIN > CONTENT_MANAGER > TEACHER > SUPPORT > STUDENT)
   and can switch to another role it holds, reflected in /me.
3. Switching role is display-only: it never changes the underlying
   role_codes, and (implicitly, since no permission logic reads
   active_role at all) can't change what the account is authorized to
   do.
4. /switch-role requires CSRF and requires the caller to already hold
   the requested role.
5. The chosen active_role survives a silent /refresh (doesn't reset back
   to the default just because the access token expired first).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _mobile() -> str:
    import random

    return str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))


def _email(tag: str = "active-role") -> str:
    return f"{tag}-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client, email: str, password: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "ActiveRole",
            "last_name": "Test",
            "mobile": _mobile(),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": password,
        },
    )
    assert resp.status_code == 201, resp.text


async def _grant_roles(db_session, email: str, role_codes: list[str]) -> None:
    from app.modules.identity.models.role import Role, UserRole
    from app.modules.identity.models.user import User

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    for code in role_codes:
        role = (await db_session.execute(select(Role).where(Role.code == code))).scalar_one()
        db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. Single-role account
# ---------------------------------------------------------------------------


async def test_single_role_account_defaults_to_its_only_role(client):
    email = _email()
    password = "ActiveRoleStudentPass!42"
    await _register(client, email, password)

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    data = login.json()["data"]
    assert data["active_role"] == "STUDENT"
    assert data["available_roles"] == ["STUDENT"]


async def test_switch_role_rejects_a_role_the_account_does_not_hold(client):
    email = _email()
    password = "ActiveRoleRejectPass!42"
    await _register(client, email, password)
    csrf = (await client.post("/api/v1/auth/login", json={"email": email, "password": password})).cookies.get(
        "csrf_token"
    )

    resp = await client.post(
        "/api/v1/auth/switch-role", headers={"X-CSRF-Token": csrf}, json={"role": "SUPER_ADMIN"}
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["errors"][0]["code"] == "ROLE_NOT_ASSIGNED"


# ---------------------------------------------------------------------------
# 2. Multi-role account
# ---------------------------------------------------------------------------


async def test_multi_role_account_defaults_to_highest_priority_role(client, db_session):
    email = _email()
    password = "ActiveRoleMultiPass!42"
    await _register(client, email, password)
    # TEACHER + CONTENT_MANAGER granted in addition to the default STUDENT
    # role every self-registered account gets.
    await _grant_roles(db_session, email, ["TEACHER", "CONTENT_MANAGER"])

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    data = login.json()["data"]
    # CONTENT_MANAGER outranks TEACHER and STUDENT in ROLE_PRIORITY.
    assert data["active_role"] == "CONTENT_MANAGER"
    assert set(data["available_roles"]) == {"STUDENT", "TEACHER", "CONTENT_MANAGER"}


async def test_switch_role_changes_active_role_and_me_reflects_it(client, db_session):
    email = _email()
    password = "ActiveRoleSwitchPass!42"
    await _register(client, email, password)
    await _grant_roles(db_session, email, ["TEACHER", "CONTENT_MANAGER"])

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.json()["data"]["active_role"] == "CONTENT_MANAGER"
    csrf = login.cookies.get("csrf_token")

    switch = await client.post(
        "/api/v1/auth/switch-role", headers={"X-CSRF-Token": csrf}, json={"role": "TEACHER"}
    )
    assert switch.status_code == 200, switch.text
    assert switch.json()["data"]["active_role"] == "TEACHER"
    # The underlying role set is unchanged -- this is a display choice,
    # not a privilege drop.
    assert set(switch.json()["data"]["available_roles"]) == {"STUDENT", "TEACHER", "CONTENT_MANAGER"}

    new_csrf = switch.cookies.get("csrf_token") or csrf
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["active_role"] == "TEACHER"

    # Switching back works too, and still does not touch available_roles.
    switch_back = await client.post(
        "/api/v1/auth/switch-role", headers={"X-CSRF-Token": new_csrf}, json={"role": "CONTENT_MANAGER"}
    )
    assert switch_back.status_code == 200, switch_back.text
    assert switch_back.json()["data"]["active_role"] == "CONTENT_MANAGER"


async def test_switch_role_requires_csrf(client, db_session):
    email = _email()
    password = "ActiveRoleCsrfPass!42"
    await _register(client, email, password)
    await _grant_roles(db_session, email, ["TEACHER"])
    await client.post("/api/v1/auth/login", json={"email": email, "password": password})

    resp = await client.post("/api/v1/auth/switch-role", json={"role": "TEACHER"})
    assert resp.status_code == 403
    assert resp.json()["errors"][0]["code"] == "CSRF_INVALID"


# ---------------------------------------------------------------------------
# 3. Display-only: switching never changes actual authorization
# ---------------------------------------------------------------------------


async def test_switching_to_a_lower_role_does_not_reduce_actual_permissions(client, db_session):
    """SUPER_ADMIN presenting as STUDENT must still be able to do anything
    SUPER_ADMIN can -- active_role is cosmetic, authorization always reads
    the full, unchanged role_codes set (see require_permission, which
    never looks at active_role). GET /api/v1/users is gated on the real
    "users.manage" permission -- SUPER_ADMIN bypasses that check entirely
    regardless of which role is "active"."""
    email = _email()
    password = "ActiveRoleNoPrivDropPass!42"
    await _register(client, email, password)
    await _grant_roles(db_session, email, ["SUPER_ADMIN"])

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.json()["data"]["active_role"] == "SUPER_ADMIN"
    csrf = login.cookies.get("csrf_token")

    switch = await client.post(
        "/api/v1/auth/switch-role", headers={"X-CSRF-Token": csrf}, json={"role": "STUDENT"}
    )
    assert switch.json()["data"]["active_role"] == "STUDENT"

    still_privileged = await client.get("/api/v1/users")
    assert still_privileged.status_code == 200, (
        f"a SUPER_ADMIN presenting as STUDENT must still pass the real users.manage check -- "
        f"active_role must never gate authorization. Got: {still_privileged.text}"
    )


# ---------------------------------------------------------------------------
# 5. Survives a silent refresh
# ---------------------------------------------------------------------------


async def test_active_role_survives_a_silent_refresh(client, db_session):
    email = _email()
    password = "ActiveRoleRefreshPass!42"
    await _register(client, email, password)
    await _grant_roles(db_session, email, ["TEACHER", "CONTENT_MANAGER"])

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    csrf = login.cookies.get("csrf_token")
    switch = await client.post(
        "/api/v1/auth/switch-role", headers={"X-CSRF-Token": csrf}, json={"role": "TEACHER"}
    )
    assert switch.json()["data"]["active_role"] == "TEACHER"

    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["data"]["active_role"] == "TEACHER", (
        "a silent token refresh must not reset the chosen active_role back to the default"
    )
