"""Route-level regression test for PR #39's mobile-based OTP rate limiting.

Unlike test_otp_rate_limit_by_mobile.py (which exercises rate_limit_by_mobile
in isolation against a bespoke app), this hits the actual application route —
POST /api/v1/auth/mobile/otp/verify — with its real MobileOtpVerifyRequest
model and both declared dependencies (the existing IP-based `rate_limit` and
the new `rate_limit_by_mobile`) stacked exactly as in auth_router.py. Twilio
is stubbed (TwilioVerifyStub), never called over the network; Redis is a
minimal in-memory fake, not bypassed, so the real counting logic runs.
"""

from __future__ import annotations

import itertools
import time
import uuid

import pytest

from app.core import rate_limit as rl
from app.main import app
from app.modules.identity.api.auth_router import get_twilio_verify
from app.modules.identity.services.twilio_verify_service import TwilioVerifyStub

pytestmark = pytest.mark.asyncio(loop_scope="session")


class FakeRedis:
    def __init__(self):
        self._counts: dict[str, int] = {}
        self._expiry: dict[str, float] = {}

    def _expired(self, key: str) -> bool:
        return key in self._expiry and time.monotonic() > self._expiry[key]

    async def incr(self, key: str) -> int:
        if self._expired(key):
            self._counts.pop(key, None)
            self._expiry.pop(key, None)
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self._expiry[key] = time.monotonic() + seconds

    async def ttl(self, key: str) -> int:
        return 60


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)
    return fake


@pytest.fixture
def rotating_client_ip(monkeypatch):
    """Simulates Railway's edge behavior that caused the original bug: every
    call to `_client_ip` returns a *different* address, reproducing the
    real-world scenario where the IP-based limiter alone cannot accumulate
    a count for one caller."""
    counter = itertools.count()
    monkeypatch.setattr(rl, "_client_ip", lambda request: f"100.64.0.{next(counter) % 250 + 1}")


@pytest.fixture
def twilio_stub():
    stub = TwilioVerifyStub(seeded_code="123456")
    app.dependency_overrides[get_twilio_verify] = lambda: stub
    yield stub
    app.dependency_overrides.pop(get_twilio_verify, None)


def _payload(email: str, mobile: str) -> dict:
    return {
        "email": email,
        "first_name": "Rl",
        "last_name": "Test",
        "mobile": mobile,
        "state_code": "KARNATAKA",
        "city": "Bangalore",
        "password": "RateLimitRoutePass!42",
    }


async def test_verify_route_blocks_same_mobile_after_ten_despite_rotating_ip(
    client, fake_redis, rotating_client_ip, twilio_stub
):
    email = f"rl-route-{uuid.uuid4().hex[:12]}@example.com"
    mobile = "9876500301"
    await client.post("/api/v1/auth/register", json=_payload(email, mobile))
    await client.post("/api/v1/auth/logout")

    for i in range(10):
        resp = await client.post(
            "/api/v1/auth/mobile/otp/verify", json={"mobile": mobile, "code": "000000"}
        )
        assert resp.status_code == 401, f"attempt {i + 1}: expected wrong-code 401, got {resp.status_code}"
        assert "access_token" not in resp.cookies

    calls_before_11th = len(twilio_stub.check_calls)

    eleventh = await client.post(
        "/api/v1/auth/mobile/otp/verify", json={"mobile": mobile, "code": "000000"}
    )
    assert eleventh.status_code == 429
    assert eleventh.json()["errors"][0]["code"] == "RATE_LIMITED"
    assert "access_token" not in eleventh.cookies

    # Twilio must not have been reached for the blocked 11th attempt.
    assert len(twilio_stub.check_calls) == calls_before_11th

    # No OTP or secret in the 429 body.
    body_text = eleventh.text
    assert "000000" not in body_text
    assert "twilio" not in body_text.lower()


async def test_verify_route_different_mobile_is_not_blocked_by_first_mobiles_bucket(
    client, fake_redis, rotating_client_ip, twilio_stub
):
    email_a = f"rl-route-a-{uuid.uuid4().hex[:12]}@example.com"
    email_b = f"rl-route-b-{uuid.uuid4().hex[:12]}@example.com"
    mobile_a = "9876500302"
    mobile_b = "9876500303"
    await client.post("/api/v1/auth/register", json=_payload(email_a, mobile_a))
    await client.post("/api/v1/auth/logout")
    await client.post("/api/v1/auth/register", json=_payload(email_b, mobile_b))
    await client.post("/api/v1/auth/logout")

    for _ in range(10):
        resp = await client.post(
            "/api/v1/auth/mobile/otp/verify", json={"mobile": mobile_a, "code": "000000"}
        )
        assert resp.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/mobile/otp/verify", json={"mobile": mobile_a, "code": "000000"}
    )
    assert blocked.status_code == 429

    # A different, unrelated mobile number is unaffected by mobile_a's bucket.
    unaffected = await client.post(
        "/api/v1/auth/mobile/otp/verify", json={"mobile": mobile_b, "code": "000000"}
    )
    assert unaffected.status_code == 401  # normal wrong-code rejection, not rate-limited
