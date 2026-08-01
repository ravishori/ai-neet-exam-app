"""Integration tests: auth flows + permission boundaries (ADR-0020)."""

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")

EMAIL = "auth-test@example.com"
PASSWORD = "AuthTest!2345"


async def _register(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "first_name": "Auth"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_login_with_correct_password_succeeds(client):
    await _register(client)
    await client.post("/api/v1/auth/logout")

    resp = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == EMAIL


async def test_login_with_wrong_password_is_rejected(client):
    await _register(client)
    await client.post("/api/v1/auth/logout")

    resp = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "WrongPassword!1"})
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "INVALID_CREDENTIALS"


async def test_suspended_user_cannot_log_in(client, db_session):
    """Regression test for the Sprint 9 bug: authenticate() checked
    locked_until but never checked status, so a suspended account could
    still log in and receive a fresh token."""
    from app.modules.identity.models.user import User

    user_data = await _register(client)
    await client.post("/api/v1/auth/logout")

    result = await db_session.execute(select(User).where(User.id == user_data["id"]))
    user = result.scalar_one()
    user.status = "suspended"
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "ACCOUNT_SUSPENDED"


async def test_reactivated_user_can_log_in_again(client, db_session):
    from app.modules.identity.models.user import User

    user_data = await _register(client)
    await client.post("/api/v1/auth/logout")

    result = await db_session.execute(select(User).where(User.id == user_data["id"]))
    user = result.scalar_one()
    user.status = "suspended"
    await db_session.commit()
    user.status = "active"
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200


async def test_refresh_rotates_token_and_keeps_session_valid(client):
    await _register(client)

    old_refresh_cookie = client.cookies.get("refresh_token")
    assert old_refresh_cookie

    resp = await client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert resp.status_code == 200

    new_refresh_cookie = client.cookies.get("refresh_token")
    assert new_refresh_cookie != old_refresh_cookie

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200


async def test_logout_ends_the_session(client):
    await _register(client)

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


async def test_student_is_blocked_from_admin_only_users_list(client, db_session, register_user):
    await register_user(client, role_codes=None, db_session=db_session)

    resp = await client.get("/api/v1/users")
    assert resp.status_code == 403
    assert resp.json()["errors"][0]["code"] == "PERMISSION_DENIED"


async def test_admin_can_list_users(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)

    resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)
