"""Smoke test for the integration-test fixtures themselves (ADR-0020)."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_health_check_does_not_need_auth(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


async def test_register_then_me_reflects_new_user(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "smoke-test@example.com", "password": "SmokeTest!234", "first_name": "Smoke"},
    )
    assert resp.status_code == 201, resp.text

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "smoke-test@example.com"
    assert me.json()["data"]["roles"] == ["STUDENT"]


async def test_register_user_fixture_grants_requested_role(client, db_session, register_user):
    user = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    assert user["email"]

    me = await client.get("/api/v1/auth/me")
    assert "ADMIN" in me.json()["data"]["roles"]
