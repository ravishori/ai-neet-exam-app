"""Step 2 of the auth/OTP audit: 5-minute expiry, single-use verification,
immediate invalidation of previous codes after resend, and a persistent
(cross-challenge, non-resetting) verification-abuse counter."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.modules.identity.models.otp import OtpAbuseCounter, OtpChallenge
from app.modules.identity.services.otp_service import (
    MAX_ABUSE_ATTEMPTS,
    OTP_TTL_MINUTES,
    OtpService,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    from app.core import rate_limit as rl

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


def _email() -> str:
    return f"otp-expiry-{uuid.uuid4().hex[:12]}@example.com"


def _mobile() -> str:
    import random

    return str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))


async def _register(client, email: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "OtpExpiry",
            "last_name": "Test",
            "mobile": _mobile(),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": "OtpExpiryPass!42",
        },
    )
    assert resp.status_code == 201, resp.text


async def _capture_code(client, email: str, monkeypatch, purpose: str = "email_login") -> str:
    captured: dict[str, str] = {}

    async def capture_send(*, to, code):
        captured["code"] = code

    monkeypatch.setattr("app.modules.identity.services.otp_service.send_login_otp_email", capture_send)
    monkeypatch.setattr("app.modules.identity.services.otp_service.send_email_verification_otp_email", capture_send)

    resp = await client.post("/api/v1/auth/otp/request", json={"email": email, "purpose": purpose})
    assert resp.status_code == 200, resp.text
    return captured["code"]


# ---------------------------------------------------------------------------
# 5-minute expiry
# ---------------------------------------------------------------------------


def test_otp_ttl_constant_is_five_minutes():
    assert OTP_TTL_MINUTES == 5


async def test_expired_otp_is_rejected(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)
    code = await _capture_code(client, email, monkeypatch)

    # Force the just-issued challenge into the past, past its own TTL.
    challenge = (
        await db_session.execute(
            select(OtpChallenge).where(OtpChallenge.destination == email, OtpChallenge.consumed_at.is_(None))
        )
    ).scalar_one()
    assert challenge.expires_at - challenge.created_at <= timedelta(minutes=OTP_TTL_MINUTES, seconds=5)
    challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.add(challenge)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": code})
    assert resp.status_code == 400, resp.text
    assert resp.json()["errors"][0]["code"] == "OTP_INVALID"


# ---------------------------------------------------------------------------
# Single-use
# ---------------------------------------------------------------------------


async def test_otp_code_cannot_be_reused_after_successful_verification(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)
    await client.post("/api/v1/auth/logout")
    code = await _capture_code(client, email, monkeypatch)

    first = await client.post("/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": code})
    assert first.status_code == 200, first.text

    await client.post("/api/v1/auth/logout")
    second = await client.post("/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": code})
    assert second.status_code == 400, second.text
    assert "access_token" not in second.cookies


# ---------------------------------------------------------------------------
# Resend invalidates the previous code immediately
# ---------------------------------------------------------------------------


async def test_resend_immediately_invalidates_the_previous_code(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)
    old_code = await _capture_code(client, email, monkeypatch)

    # Move the old challenge's created_at into the past so the 60s resend
    # cooldown doesn't block the second request.
    old_challenge = (
        await db_session.execute(
            select(OtpChallenge).where(OtpChallenge.destination == email, OtpChallenge.consumed_at.is_(None))
        )
    ).scalar_one()
    old_challenge.created_at = datetime.now(UTC) - timedelta(seconds=61)
    db_session.add(old_challenge)
    await db_session.commit()

    new_code = await _capture_code(client, email, monkeypatch)
    assert new_code != old_code

    # The old code must no longer work, even though it hasn't expired on
    # its own TTL yet.
    old_attempt = await client.post(
        "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": old_code}
    )
    assert old_attempt.status_code == 400, old_attempt.text

    # The new code still works.
    new_attempt = await client.post(
        "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": new_code}
    )
    assert new_attempt.status_code == 200, new_attempt.text


# ---------------------------------------------------------------------------
# Persistent, non-resetting abuse counter
# ---------------------------------------------------------------------------


async def test_per_challenge_attempts_cap_is_still_five(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)
    await _capture_code(client, email, monkeypatch)

    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": "000000"}
        )
        assert resp.status_code == 400

    locked = await client.post(
        "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": "000000"}
    )
    assert locked.status_code == 429, locked.text
    assert locked.json()["errors"][0]["code"] == "OTP_LOCKED"


async def test_requesting_a_new_code_does_not_reset_the_abuse_counter(client, db_session, monkeypatch):
    """The actual gap this step closes: exhausting one challenge's 5
    attempts, then requesting a brand-new code, must NOT hand the caller a
    fresh 5-attempt budget -- the persistent OtpAbuseCounter must already
    be at the cap and block the new challenge's very first guess too."""
    email = _email()
    await _register(client, email)
    first_code = await _capture_code(client, email, monkeypatch)
    assert first_code  # the actual value is irrelevant -- every guess below is wrong on purpose

    for _ in range(MAX_ABUSE_ATTEMPTS):
        resp = await client.post(
            "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": "000000"}
        )
        assert resp.status_code == 400

    counter = (
        await db_session.execute(
            select(OtpAbuseCounter).where(OtpAbuseCounter.destination == email, OtpAbuseCounter.purpose == "email_login")
        )
    ).scalar_one()
    assert counter.failed_attempts == MAX_ABUSE_ATTEMPTS

    # Move the exhausted challenge's created_at back so resend isn't
    # blocked by its own 60s cooldown, then request a genuinely new code.
    exhausted = (
        await db_session.execute(
            select(OtpChallenge).where(OtpChallenge.destination == email, OtpChallenge.consumed_at.is_(None))
        )
    ).scalar_one()
    exhausted.created_at = datetime.now(UTC) - timedelta(seconds=61)
    db_session.add(exhausted)
    await db_session.commit()

    new_code = await _capture_code(client, email, monkeypatch)
    assert new_code  # a real new code WAS issued -- the lockout doesn't block *requesting*, only verifying

    blocked = await client.post(
        "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": new_code}
    )
    assert blocked.status_code == 429, (
        f"a brand-new OTP code must still be blocked by the persistent abuse counter from the "
        f"PREVIOUS challenge's failed attempts -- got {blocked.text}"
    )
    assert blocked.json()["errors"][0]["code"] == "OTP_LOCKED"


async def test_successful_verification_clears_the_abuse_counter(client, db_session, monkeypatch):
    """The counter isn't a permanent lock -- a few wrong guesses followed
    by the actual correct code must clear it, not carry a lingering
    partial count into the user's next, unrelated login."""
    email = _email()
    await _register(client, email)
    code = await _capture_code(client, email, monkeypatch)

    for _ in range(3):
        resp = await client.post(
            "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": "000000"}
        )
        assert resp.status_code == 400

    success = await client.post(
        "/api/v1/auth/otp/verify", json={"email": email, "purpose": "email_login", "code": code}
    )
    assert success.status_code == 200, success.text

    counter = (
        await db_session.execute(
            select(OtpAbuseCounter).where(OtpAbuseCounter.destination == email, OtpAbuseCounter.purpose == "email_login")
        )
    ).scalar_one()
    assert counter.failed_attempts == 0


async def test_abuse_counter_is_isolated_per_destination(client, db_session, monkeypatch):
    """Flooding one user's OTP challenge must never lock out an unrelated
    user -- the counter is keyed per (destination, purpose), not global."""
    email_a = _email()
    email_b = _email()
    await _register(client, email_a)
    await _register(client, email_b)

    await _capture_code(client, email_a, monkeypatch)
    for _ in range(MAX_ABUSE_ATTEMPTS):
        await client.post("/api/v1/auth/otp/verify", json={"email": email_a, "purpose": "email_login", "code": "000000"})

    code_b = await _capture_code(client, email_b, monkeypatch)
    resp_b = await client.post(
        "/api/v1/auth/otp/verify", json={"email": email_b, "purpose": "email_login", "code": code_b}
    )
    assert resp_b.status_code == 200, (
        f"user A's exhausted abuse counter must never affect user B's own OTP verification. Got: {resp_b.text}"
    )


async def test_abuse_counter_resets_after_its_rolling_window_expires(db_session):
    """A stale pattern of failed attempts from long ago must not permanently
    lock a legitimate user out -- the rolling window (ABUSE_WINDOW_MINUTES)
    resets the counter on its own once enough time has passed. Exercises
    OtpService._get_abuse_counter directly (DB-level, not an HTTP round
    trip) since the window is 60 minutes -- not practical to wait for in a
    real request/response cycle."""
    from app.modules.identity.services.otp_service import ABUSE_WINDOW_MINUTES

    email = _email()
    service = OtpService(db_session)
    counter = await service._get_abuse_counter(destination=email, purpose="email_login")
    counter.failed_attempts = MAX_ABUSE_ATTEMPTS
    counter.window_started_at = datetime.now(UTC) - timedelta(minutes=ABUSE_WINDOW_MINUTES + 1)
    await db_session.commit()

    refetched = await service._get_abuse_counter(destination=email, purpose="email_login")
    assert refetched.failed_attempts == 0, "a stale, expired abuse window must reset on next access"
