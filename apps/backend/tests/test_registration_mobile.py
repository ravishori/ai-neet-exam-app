"""Registration flow with mobile / state / city + must_change_password."""

import uuid

import pytest
from sqlalchemy import select

from app.modules.identity.models.user import User
from app.modules.identity.services.auth_service import INITIAL_DEFAULT_PASSWORD

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _email() -> str:
    return f"reg-{uuid.uuid4().hex[:12]}@example.com"


def _mobile10(prefix: str = "98765") -> str:
    """Deterministic-per-call mobile that fits ``[6-9]\\d{9}``. Callers avoid
    collisions by seeding a unique 5-digit tail themselves."""
    return prefix + uuid.uuid4().hex[:5].translate(str.maketrans("abcdef", "012345"))


def _payload(email: str, mobile10: str, state: str = "KARNATAKA", city: str = "Bangalore") -> dict:
    return {
        "email": email,
        "first_name": "Reg",
        "last_name": "Tester",
        "mobile": mobile10,
        "state_code": state,
        "city": city,
    }


async def test_register_stores_must_change_password_and_mobile_e164(client, db_session):
    email = _email()
    mobile = "9876500001"
    resp = await client.post("/api/v1/auth/register", json=_payload(email, mobile))
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["email"] == email
    assert body["mobile_e164"] == "+91" + mobile
    assert body["state_code"] == "KARNATAKA"
    assert body["city_name"] == "Bangalore"
    assert body["must_change_password"] is True

    # And the row in the DB matches — no client-supplied password field was
    # required; the hash is stored, not the plaintext.
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    assert user.mobile_e164 == "+91" + mobile
    assert user.state_code == "KARNATAKA"
    assert user.city_name == "Bangalore"
    assert user.must_change_password is True
    assert user.password_hash and user.password_hash != INITIAL_DEFAULT_PASSWORD
    # Master-data FKs point at the resolved state/city rows.
    assert user.state_id is not None
    assert user.city_id is not None


async def test_register_login_with_initial_password_then_change_clears_flag(client):
    email = _email()
    mobile = "9876500002"
    await client.post("/api/v1/auth/register", json=_payload(email, mobile))
    # Log out the auto-issued session so we can prove the initial credential works.
    await client.post("/api/v1/auth/logout")

    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": INITIAL_DEFAULT_PASSWORD}
    )
    assert login.status_code == 200
    assert login.json()["data"]["must_change_password"] is True

    from conftest import csrf_headers

    change = await client.post(
        "/api/v1/auth/change-password",
        headers=csrf_headers(client),
        json={"current_password": INITIAL_DEFAULT_PASSWORD, "new_password": "N3wStrongPass!42"},
    )
    assert change.status_code == 200, change.text

    login2 = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "N3wStrongPass!42"}
    )
    assert login2.status_code == 200
    assert login2.json()["data"]["must_change_password"] is False


async def test_register_rejects_missing_required_fields(client):
    for missing in ("first_name", "last_name", "mobile", "state_code", "city"):
        payload = _payload(_email(), "9876500003")
        payload.pop(missing)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in (400, 422), (missing, resp.status_code, resp.text)


async def test_register_rejects_invalid_mobile(client):
    payload = _payload(_email(), "5876543210")  # starts with 5 → invalid
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["code"] == "MOBILE_INVALID"


async def test_register_rejects_invalid_state(client):
    payload = _payload(_email(), "9876500004", state="ZZ", city="Nowhere")
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["code"] == "STATE_INVALID"


async def test_register_rejects_city_that_does_not_belong_to_state(client):
    payload = _payload(_email(), "9876500005", state="TAMIL_NADU", city="Bangalore")
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["code"] == "CITY_INVALID_FOR_STATE"


async def test_register_rejects_duplicate_email(client):
    email = _email()
    a = await client.post("/api/v1/auth/register", json=_payload(email, "9876500006"))
    assert a.status_code == 201
    b = await client.post("/api/v1/auth/register", json=_payload(email, "9876500007"))
    assert b.status_code == 409
    assert b.json()["errors"][0]["code"] == "EMAIL_TAKEN"


async def test_register_rejects_duplicate_mobile(client):
    a = await client.post("/api/v1/auth/register", json=_payload(_email(), "9876500008"))
    assert a.status_code == 201
    b = await client.post("/api/v1/auth/register", json=_payload(_email(), "9876500008"))
    assert b.status_code == 409
    assert b.json()["errors"][0]["code"] == "MOBILE_TAKEN"


async def test_register_response_does_not_leak_initial_password(client):
    resp = await client.post("/api/v1/auth/register", json=_payload(_email(), "9876500009"))
    body_text = resp.text.lower()
    assert "password123" not in body_text
    assert "password_hash" not in resp.json()["data"]
