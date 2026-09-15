"""Mobile OTP login via Twilio Verify — stub the network, not the router."""

import uuid

import pytest

from app.main import app
from app.modules.identity.api.auth_router import get_twilio_verify
from app.modules.identity.services.twilio_verify_service import TwilioVerifyStub

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    """ASGITransport does not run FastAPI's lifespan, so init_redis() never
    fires and every fail_closed=True endpoint would return 429. Existing
    test_security_wave_c uses the same pattern to no-op the check."""
    from app.core import rate_limit as rl

    async def no_limit(key: str, *, limit: int, window_seconds: int, fail_closed: bool) -> None:
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


def _payload(email: str, mobile: str = "9876500101") -> dict:
    return {
        "email": email,
        "first_name": "Mob",
        "last_name": "OTP",
        "mobile": mobile,
        "state_code": "KARNATAKA",
        "city": "Bangalore",
    }


@pytest.fixture
def twilio_stub():
    stub = TwilioVerifyStub(seeded_code="123456")
    app.dependency_overrides[get_twilio_verify] = lambda: stub
    yield stub
    app.dependency_overrides.pop(get_twilio_verify, None)


async def test_otp_send_returns_uniform_message_for_registered_user(client, twilio_stub):
    email = f"otp-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json=_payload(email, "9876500110"))

    resp = await client.post("/api/v1/auth/mobile/otp/send", json={"mobile": "9876500110"})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "otp" not in body
    assert body["channel"] == "sms"
    assert twilio_stub.send_calls == [("+919876500110", "sms")]


async def test_otp_send_uniform_message_for_unknown_mobile_no_twilio_call(client, twilio_stub):
    # Register a decoy so there IS a registered user in the DB; probe a
    # different unregistered number.
    email = f"otp-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json=_payload(email, "9876500120"))

    resp = await client.post("/api/v1/auth/mobile/otp/send", json={"mobile": "9876500999"})
    assert resp.status_code == 200
    # Same message — no enumeration signal.
    assert resp.json()["data"]["channel"] == "sms"
    # Twilio was NOT called for the unregistered number.
    assert ("+919876500999", "sms") not in twilio_stub.send_calls


async def test_otp_send_uniform_message_for_invalid_mobile_format(client, twilio_stub):
    resp = await client.post("/api/v1/auth/mobile/otp/send", json={"mobile": "5876543210"})
    assert resp.status_code == 200
    # No stack trace, no MOBILE_INVALID leak, no Twilio call.
    assert resp.json()["data"]["channel"] == "sms"
    assert twilio_stub.send_calls == []


async def test_otp_verify_happy_path_authenticates_user(client, twilio_stub):
    email = f"otp-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json=_payload(email, "9876500130"))
    # Log out the auto-session from registration so we can prove OTP verify issues a fresh one.
    await client.post("/api/v1/auth/logout")

    await client.post("/api/v1/auth/mobile/otp/send", json={"mobile": "9876500130"})

    resp = await client.post(
        "/api/v1/auth/mobile/otp/verify",
        json={"mobile": "9876500130", "code": "123456"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["email"] == email
    # Cookies set on the response
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies


async def test_otp_verify_wrong_code_returns_generic_401(client, twilio_stub):
    email = f"otp-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json=_payload(email, "9876500140"))
    await client.post("/api/v1/auth/mobile/otp/send", json={"mobile": "9876500140"})

    resp = await client.post(
        "/api/v1/auth/mobile/otp/verify",
        json={"mobile": "9876500140", "code": "000000"},
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "MOBILE_OTP_INVALID"


async def test_otp_verify_unknown_mobile_returns_same_generic_401(client, twilio_stub):
    # Stub approves the "correct" code even for a number nobody sent to,
    # simulating an attacker guessing 123456 for a random number.
    twilio_stub.seed("+919876500999", "123456")
    resp = await client.post(
        "/api/v1/auth/mobile/otp/verify",
        json={"mobile": "9876500999", "code": "123456"},
    )
    # Non-enumeration: same 401 whether the number is unknown or the code is wrong.
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "MOBILE_OTP_INVALID"


async def test_otp_verify_expired_returns_generic_401(client, twilio_stub):
    email = f"otp-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json=_payload(email, "9876500150"))
    # No prior /send → stub says "expired" for this destination.
    resp = await client.post(
        "/api/v1/auth/mobile/otp/verify",
        json={"mobile": "9876500150", "code": "123456"},
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "MOBILE_OTP_INVALID"


async def test_no_endpoint_ever_returns_an_otp_code(client, twilio_stub):
    email = f"otp-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json=_payload(email, "9876500160"))

    send = await client.post("/api/v1/auth/mobile/otp/send", json={"mobile": "9876500160"})
    assert "123456" not in send.text
    verify = await client.post(
        "/api/v1/auth/mobile/otp/verify",
        json={"mobile": "9876500160", "code": "123456"},
    )
    assert "123456" not in verify.text
