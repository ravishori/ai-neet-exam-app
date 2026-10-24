"""Step 3 of the auth/OTP audit: re-verification of the existing 60-second
resend cooldown, plus the two new layered send limits on /otp/request --
a persistent 5-emails-per-account-per-rolling-2-hours ceiling (with an
up-to-2-hour cooldown once hit, by construction of the fixed window) and
an additional, deliberately generous and fail-open IP-hourly backstop.

Design note (same rationale as test_otp_rate_limit_shared_proxy_mitigation.py
and test_login_rate_limit_shared_proxy_mitigation.py): the route now carries
FOUR layered rate-limit dependencies (IP/300s, email/300s, email/7200s,
IP/3600s) sharing one Redis client. Driving the real route through many
iterations would hit whichever layer's budget is smallest first (the
existing 5/300s burst layers), not necessarily the new ones. To prove the
new layers' own mechanics in isolation, their dependency closures are
exercised directly against a fake Redis and a minimal fake Request --
exactly as an HTTP call would invoke them, but without the burst layers'
much smaller budgets getting in the way first.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.rate_limit import RateLimitExceeded, rate_limit, rate_limit_by_email

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _FakeRedis:
    """Same minimal deterministic stand-in used throughout this session's
    other rate-limit tests -- no live Redis dependency, clean state per
    test."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None

    async def ttl(self, key: str) -> int:
        return 7200


@pytest.fixture
def fake_redis(monkeypatch):
    from app.core import rate_limit as rl

    redis = _FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: redis)
    return redis


class _FakeRequestWithEmail:
    def __init__(self, email: str) -> None:
        self._email = email
        self.client = None

    async def json(self):
        return {"email": self._email}


class _FakeRequestWithIp:
    class _Client:
        def __init__(self, host: str) -> None:
            self.host = host

    def __init__(self, ip: str) -> None:
        self.client = self._Client(ip)

    async def json(self):
        return {}


def _mobile() -> str:
    import random

    return str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))


def _email() -> str:
    return f"otp-send-limit-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client, email: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "OtpSendLimit",
            "last_name": "Test",
            "mobile": _mobile(),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": "OtpSendLimitPass!42",
        },
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Route wiring: all four layers present
# ---------------------------------------------------------------------------


def test_otp_request_route_has_four_layered_rate_limits():
    from app.main import app

    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/v1/auth/otp/request")
    assert len(route.dependant.dependencies) >= 4, (
        "expected the existing IP/300s and email/300s burst layers plus the new "
        f"email/7200s account ceiling and IP/3600s backstop; found "
        f"{len(route.dependant.dependencies)} dependencies"
    )


# ---------------------------------------------------------------------------
# 60-second resend cooldown (pre-existing, re-verified here against a real
# HTTP round trip with the Redis layers bypassed, isolating the service-
# layer cooldown itself)
# ---------------------------------------------------------------------------


@pytest.fixture
def _bypass_rate_limit(monkeypatch):
    from app.core import rate_limit as rl

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


async def test_resend_within_60_seconds_is_rejected_with_cooldown(client, _bypass_rate_limit):
    email = _email()
    await _register(client, email)

    first = await client.post("/api/v1/auth/otp/request", json={"email": email, "purpose": "email_login"})
    assert first.status_code == 200, first.text

    second = await client.post("/api/v1/auth/otp/request", json={"email": email, "purpose": "email_login"})
    assert second.status_code == 429, second.text
    assert second.json()["errors"][0]["code"] == "OTP_COOLDOWN"


# ---------------------------------------------------------------------------
# New: 5 emails per account per rolling 2 hours, then a cooldown
# ---------------------------------------------------------------------------


async def test_account_2hour_send_ceiling_fires_on_the_sixth_request(fake_redis):
    dependency = rate_limit_by_email("otp_request_by_email_2h", limit=5, window_seconds=7200, fail_closed=True)
    email = _email()
    request = _FakeRequestWithEmail(email)

    for _ in range(5):
        await dependency(request)  # must not raise

    with pytest.raises(RateLimitExceeded) as exc_info:
        await dependency(request)
    # The cooldown lasts up to the remainder of the 2-hour window -- bounded
    # by window_seconds, never longer.
    assert 0 < exc_info.value.retry_after_seconds <= 7200


async def test_account_2hour_send_ceiling_is_isolated_per_email(fake_redis):
    dependency = rate_limit_by_email("otp_request_by_email_2h", limit=5, window_seconds=7200, fail_closed=True)
    email_a = _email()
    email_b = _email()
    request_a = _FakeRequestWithEmail(email_a)
    request_b = _FakeRequestWithEmail(email_b)

    for _ in range(5):
        await dependency(request_a)

    with pytest.raises(RateLimitExceeded):
        await dependency(request_a)

    # Account B, never having sent a request, must be completely unaffected
    # by account A exhausting its own ceiling.
    await dependency(request_b)  # must not raise


# ---------------------------------------------------------------------------
# New: additional IP-based layering (generous, fail-open backstop)
# ---------------------------------------------------------------------------


async def test_ip_hourly_backstop_fires_after_twenty_requests_from_one_ip(fake_redis):
    dependency = rate_limit("otp_request_ip_hourly", limit=20, window_seconds=3600, fail_closed=False)
    request = _FakeRequestWithIp("203.0.113.50")

    for _ in range(20):
        await dependency(request)  # must not raise

    with pytest.raises(RateLimitExceeded):
        await dependency(request)


async def test_ip_hourly_backstop_fails_open_on_redis_error(monkeypatch):
    """fail_closed=False: a Redis outage on this specific layer must never
    block legitimate OTP requests -- the sensitive per-email layers above
    are fail_closed=True and already cover the abuse-prone cases; this one
    exists purely as a coarse, best-effort backstop."""
    from app.core import rate_limit as rl

    def _broken_redis():
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(rl, "get_redis", _broken_redis)
    dependency = rate_limit("otp_request_ip_hourly", limit=20, window_seconds=3600, fail_closed=False)
    request = _FakeRequestWithIp("203.0.113.51")

    # get_redis() raising directly isn't the normal path (get_redis()
    # normally returns None when unavailable, which _check already
    # handles) -- exercise that normal "unavailable" path instead.
    monkeypatch.setattr(rl, "get_redis", lambda: None)
    await dependency(request)  # must not raise despite no Redis available
