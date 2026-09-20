"""PATCH /users/me — mobile/state/city validation, duplicate mobile guard."""

import uuid

import pytest

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _payload(email: str, mobile: str) -> dict:
    return {
        "email": email,
        "first_name": "Prof",
        "last_name": "Test",
        "mobile": mobile,
        "state_code": "KARNATAKA",
        "city": "Bangalore",
    }


async def test_profile_patch_updates_state_and_city_together(client):
    email = f"prof-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json=_payload(email, "9876500201"))

    resp = await client.patch(
        "/api/v1/users/me",
        headers=csrf_headers(client),
        json={"state_code": "TAMIL_NADU", "city": "Chennai"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["state_code"] == "TAMIL_NADU"
    assert body["city_name"] == "Chennai"


async def test_profile_patch_rejects_city_from_wrong_state(client):
    email = f"prof-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json=_payload(email, "9876500202"))

    resp = await client.patch(
        "/api/v1/users/me",
        headers=csrf_headers(client),
        json={"state_code": "TAMIL_NADU", "city": "Bangalore"},
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["code"] == "CITY_INVALID_FOR_STATE"


async def test_profile_patch_normalizes_mobile(client):
    email = f"prof-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json=_payload(email, "9876500203"))

    resp = await client.patch(
        "/api/v1/users/me",
        headers=csrf_headers(client),
        json={"mobile": "+91 98765-11111"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["mobile_e164"] == "+919876511111"


async def test_profile_patch_rejects_mobile_owned_by_another_user(client):
    email_a = f"prof-{uuid.uuid4().hex[:12]}@example.com"
    email_b = f"prof-{uuid.uuid4().hex[:12]}@example.com"
    # A registers with a mobile.
    await client.post("/api/v1/auth/register", json=_payload(email_a, "9876500204"))
    # Log A out so B's registration is not conflated with A's cookies.
    await client.post("/api/v1/auth/logout")
    # B registers with a different mobile, is logged in as B.
    await client.post("/api/v1/auth/register", json=_payload(email_b, "9876500205"))

    # As B, try to steal A's mobile.
    resp = await client.patch(
        "/api/v1/users/me",
        headers=csrf_headers(client),
        json={"mobile": "9876500204"},
    )
    assert resp.status_code == 409
    assert resp.json()["errors"][0]["code"] == "MOBILE_TAKEN"


async def test_profile_patch_requires_authentication(client):
    # New anonymous client — no cookies.
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        resp = await anon.patch(
            "/api/v1/users/me",
            json={"state_code": "KARNATAKA", "city": "Bangalore"},
        )
        # Either 401 (no cookie) or 403 (no CSRF). Both are correct rejections
        # of an unauthenticated write.
        assert resp.status_code in (401, 403)
