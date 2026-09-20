"""Registration flow with mobile / state / city + user-chosen password."""

import uuid

import pytest
from sqlalchemy import select

from app.modules.identity.models.user import User
from app.modules.identity.services.password_service import (
    PASSWORD_MAX_AGE_DAYS,
    verify_password,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


PASSWORD = "RegTesterPass!42"


def _email() -> str:
    return f"reg-{uuid.uuid4().hex[:12]}@example.com"


def _mobile10(prefix: str = "98765") -> str:
    """Deterministic-per-call mobile that fits ``[6-9]\\d{9}``. Callers avoid
    collisions by seeding a unique 5-digit tail themselves."""
    return prefix + uuid.uuid4().hex[:5].translate(str.maketrans("abcdef", "012345"))


def _payload(
    email: str,
    mobile10: str,
    state: str = "KARNATAKA",
    city: str = "Bangalore",
    password: str = PASSWORD,
) -> dict:
    return {
        "email": email,
        "first_name": "Reg",
        "last_name": "Tester",
        "mobile": mobile10,
        "state_code": state,
        "city": city,
        "password": password,
    }


async def test_register_stores_user_password_and_mobile_e164(client, db_session):
    email = _email()
    mobile = "9876500001"
    resp = await client.post("/api/v1/auth/register", json=_payload(email, mobile))
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["email"] == email
    assert body["mobile_e164"] == "+91" + mobile
    assert body["state_code"] == "KARNATAKA"
    assert body["city_name"] == "Bangalore"
    # Public registration no longer forces a password change.
    assert body["must_change_password"] is False

    # DB row: hash stored, plaintext not stored, and hash verifies the
    # client-supplied password.
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    assert user.mobile_e164 == "+91" + mobile
    assert user.state_code == "KARNATAKA"
    assert user.city_name == "Bangalore"
    assert user.must_change_password is False
    assert user.password_hash and user.password_hash != PASSWORD
    assert verify_password(PASSWORD, user.password_hash)
    # Password timestamp stamped at register — drives the 90-day reminder.
    assert user.password_changed_at is not None
    # Master-data FKs point at the resolved state/city rows.
    assert user.state_id is not None
    assert user.city_id is not None


async def test_register_login_with_user_password_no_forced_change(client):
    email = _email()
    mobile = "9876500002"
    await client.post("/api/v1/auth/register", json=_payload(email, mobile))
    # Log out the auto-issued session so we can prove the user-chosen password works.
    await client.post("/api/v1/auth/logout")

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    data = login.json()["data"]
    assert data["must_change_password"] is False
    # Fresh account → age 0 days, not due yet.
    assert data["password_age_days"] == 0
    assert data["password_reminder_due"] is False
    assert data.get("password_hash") is None  # never leaks the hash


async def test_change_password_updates_timestamp(client, db_session):
    email = _email()
    mobile = "9876500010"
    await client.post("/api/v1/auth/register", json=_payload(email, mobile))
    from conftest import csrf_headers

    result = await db_session.execute(select(User).where(User.email == email))
    user_before = result.scalar_one()
    before_ts = user_before.password_changed_at
    assert before_ts is not None

    change = await client.post(
        "/api/v1/auth/change-password",
        headers=csrf_headers(client),
        json={"current_password": PASSWORD, "new_password": "N3wStrongPass!42"},
    )
    assert change.status_code == 200, change.text

    await db_session.refresh(user_before)
    assert user_before.password_changed_at is not None
    assert user_before.password_changed_at >= before_ts

    login2 = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "N3wStrongPass!42"}
    )
    assert login2.status_code == 200
    assert login2.json()["data"]["must_change_password"] is False


async def test_register_rejects_missing_required_fields(client):
    for missing in ("first_name", "last_name", "mobile", "state_code", "city", "password"):
        payload = _payload(_email(), "9876500003")
        payload.pop(missing)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in (400, 422), (missing, resp.status_code, resp.text)


async def test_register_rejects_weak_password(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json=_payload(_email(), "9876500011", password="short"),
    )
    assert resp.status_code in (400, 422)


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


async def test_register_response_does_not_leak_password(client):
    resp = await client.post("/api/v1/auth/register", json=_payload(_email(), "9876500009"))
    body_json = resp.json()["data"]
    # Neither the plaintext password nor the hash may appear in the API response.
    assert PASSWORD not in resp.text
    assert "password_hash" not in body_json
    assert "password" not in body_json


async def test_password_reminder_flags_ninety_day_old_account(client, db_session):
    """Simulate a 91-day-old password by rewinding password_changed_at in the
    DB. The reminder MUST fire and login MUST still succeed (non-blocking).
    """
    from datetime import UTC, datetime, timedelta

    email = _email()
    mobile = "9876500012"
    await client.post("/api/v1/auth/register", json=_payload(email, mobile))
    await client.post("/api/v1/auth/logout")

    # Age the password directly in the DB.
    row = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    row.password_changed_at = datetime.now(UTC) - timedelta(days=PASSWORD_MAX_AGE_DAYS + 1)
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text  # non-blocking
    data = login.json()["data"]
    assert data["password_age_days"] >= PASSWORD_MAX_AGE_DAYS
    assert data["password_reminder_due"] is True


async def test_password_reminder_absent_for_legacy_null_timestamp(client, db_session):
    """Legacy rows with password_changed_at IS NULL must not receive a
    reminder — we don't have data, so we don't nag."""
    email = _email()
    mobile = "9876500013"
    await client.post("/api/v1/auth/register", json=_payload(email, mobile))
    await client.post("/api/v1/auth/logout")

    row = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    row.password_changed_at = None
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    data = login.json()["data"]
    assert data["password_age_days"] is None
    assert data["password_reminder_due"] is False
