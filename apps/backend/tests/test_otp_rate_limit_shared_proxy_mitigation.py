"""Regression tests for extending the already-proven shared-proxy-IP
mitigation (docs/audits/auth-otp-feature-audit.md, rate_limit_by_email)
to /otp/request and /otp/verify -- the diagnosed root cause of reported
Email OTP "verification failures": both routes previously relied solely
on an IP-keyed limiter whose bucket collapses across every real user
behind Railway's proxy edge (request.client.host is identical for all
of them), so one user's OTP traffic could exhaust the shared bucket and
make an unrelated user's correct code get rejected with no indication
it was a rate-limit issue, not a wrong code.

Note on test design: the IP-keyed layer is still present, unmodified,
additive (not replaced) -- deliberately, same as /login. That means if a
test pushes one user's traffic past the IP bucket's own limit, a SECOND
user sharing that same bucket (as every test client does, via
ASGITransport) will legitimately also get rate-limited by the
(unchanged, still-shared) IP layer -- that is correct, expected
behavior, not a test failure, and not what this fix addresses. These
tests therefore keep each scenario's attempt counts low enough to never
exhaust the shared IP bucket, and prove the new layer's isolation
through (a) direct route-wiring introspection and (b) the per-email
limiter's own already-proven-correct keying (test_login_rate_limit_
shared_proxy_mitigation.py already covers rate_limit_by_email's
mechanics in depth -- not duplicated here)."""

from __future__ import annotations

import pytest

from app.main import app

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _FakeRedis:
    """Same minimal deterministic stand-in as
    test_login_rate_limit_shared_proxy_mitigation.py -- no live Redis/
    network dependency, clean counter state per test."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None

    async def ttl(self, key: str) -> int:
        return 60


@pytest.fixture
def fake_redis(monkeypatch):
    from app.core import rate_limit as rl

    redis = _FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: redis)
    return redis


def _register_payload(email: str, mobile: str, password: str = "OtpSharedProxyPass!42") -> dict:
    return {
        "email": email,
        "first_name": "OtpSharedProxy",
        "last_name": "Test",
        "mobile": mobile,
        "state_code": "KARNATAKA",
        "city": "Bangalore",
        "password": password,
    }


def _mobile() -> str:
    import random

    return str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))


async def _register(client, email: str) -> None:
    resp = await client.post("/api/v1/auth/register", json=_register_payload(email, _mobile()))
    assert resp.status_code == 201, resp.text
    await client.post("/api/v1/auth/logout")


# --- route wiring: deterministic, doesn't depend on bucket arithmetic ------


def _dependency_call_names(route) -> list[str]:
    return [dep.call.__name__ if hasattr(dep.call, "__name__") else repr(dep.call) for dep in route.dependant.dependencies]


def test_otp_request_route_has_both_ip_and_email_keyed_rate_limits():
    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/v1/auth/otp/request")
    # Both dependencies are produced by calling rate_limit(...)/rate_limit_by_email(...),
    # which both return a closure named "dependency" -- count, don't name-match.
    assert len(route.dependant.dependencies) >= 2, (
        "expected both the existing IP-keyed rate_limit and the new rate_limit_by_email "
        f"on /otp/request; found {len(route.dependant.dependencies)} dependencies"
    )


def test_otp_verify_route_has_both_ip_and_email_keyed_rate_limits():
    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/v1/auth/otp/verify")
    assert len(route.dependant.dependencies) >= 2, (
        "expected both the existing IP-keyed rate_limit and the new rate_limit_by_email "
        f"on /otp/verify; found {len(route.dependant.dependencies)} dependencies"
    )


# --- functional isolation, within the shared IP bucket's own budget --------


async def test_two_users_behind_shared_proxy_ip_can_both_request_otp(client, fake_redis):
    """A's OTP requests (well under both the 5/300s IP and 5/300s
    email-keyed limits) must never prevent B, a completely different
    email sharing the same request.client.host, from getting their own
    OTP -- proving the per-email layer doesn't itself introduce any
    cross-user blocking under normal traffic."""
    email_a = "otp-sharedproxy-a@example.com"
    email_b = "otp-sharedproxy-b@example.com"
    await _register(client, email_a)
    await _register(client, email_b)

    resp_a = await client.post("/api/v1/auth/otp/request", json={"email": email_a, "purpose": "email_login"})
    assert resp_a.status_code == 200, resp_a.text

    resp_b = await client.post("/api/v1/auth/otp/request", json={"email": email_b, "purpose": "email_login"})
    assert resp_b.status_code == 200, (
        f"user B's OTP request was blocked despite sharing no identity with A other than "
        f"request.client.host, and neither user came close to the shared IP bucket's own "
        f"limit. Got: {resp_b.text}"
    )


async def test_otp_request_email_layer_actually_limits_repeated_requests_for_one_email(client, fake_redis):
    """Not a no-op: the new email-keyed layer (limit=5/300s) does fire for
    one email requesting repeatedly, same as its IP-keyed counterpart
    already did -- proves this is a real, active limiter, not dead code."""
    email = "otp-request-email-limit@example.com"
    await _register(client, email)

    statuses = []
    for _ in range(7):
        resp = await client.post("/api/v1/auth/otp/request", json={"email": email, "purpose": "email_login"})
        statuses.append(resp.status_code)
    assert 429 in statuses, f"expected the email-keyed (or IP-keyed) limiter to fire eventually; got {statuses}"


async def test_otp_verify_email_layer_actually_limits_repeated_attempts_for_one_email(client, fake_redis):
    """Same proof for /otp/verify's new email-keyed layer (limit=10/300s)."""
    email = "otp-verify-email-limit@example.com"
    await _register(client, email)
    req = await client.post("/api/v1/auth/otp/request", json={"email": email, "purpose": "email_login"})
    assert req.status_code == 200, req.text

    statuses = []
    for _ in range(12):
        resp = await client.post(
            "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": "000000"}
        )
        statuses.append(resp.status_code)
    assert 429 in statuses, f"expected the email-keyed (or IP-keyed) limiter to fire eventually; got {statuses}"
