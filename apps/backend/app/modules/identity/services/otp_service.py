"""Email/SMS OTP challenges — codes stored hashed, never returned in API bodies."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.identity.models.otp import OtpAbuseCounter, OtpChallenge
from app.modules.identity.services.email_service import send_email_verification_otp_email, send_login_otp_email
from app.modules.identity.services.token_service import hash_opaque_token

logger = get_logger("otp")

OTP_TTL_MINUTES = 5
OTP_LENGTH = 6
RESEND_COOLDOWN_SECONDS = 60
# Persistent, cross-challenge verification-attempt cap (see OtpAbuseCounter's
# own docstring) -- deliberately the same ceiling as a single challenge's
# max_attempts, since this counter is what actually governs abuse now; a
# fresh challenge's own `attempts` field still exists for per-code
# visibility/logging, but no longer gives an attacker a fresh 5-attempt
# budget just by requesting a new code.
MAX_ABUSE_ATTEMPTS = 5
# How long a period of failed attempts is remembered before resetting on
# its own -- prevents a few wrong attempts days apart from ever
# accumulating into a permanent lockout for a legitimate user who
# occasionally mistypes their code. A successful verification also resets
# this immediately, independent of the window.
ABUSE_WINDOW_MINUTES = 60

# email_login is the only purpose that establishes a session (see
# auth_router._LOGIN_OTP_PURPOSES) — it gets the LOGIN_OTP template/subject.
# Everything else (email_verify, login_stepup, sensitive_action) is "prove
# you control this mailbox for one action" and gets EMAIL_VERIFICATION_OTP.
_LOGIN_OTP_PURPOSES = frozenset({"email_login"})


def _generate_otp() -> str:
    # Cryptographically secure numeric OTP
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


class OtpService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_abuse_counter(self, *, destination: str, purpose: str) -> OtpAbuseCounter:
        """Fetch-or-create the persistent counter for this (destination,
        purpose) pair, resetting it first if its rolling window has
        expired. Never resets it just because a new OtpChallenge was
        requested -- only this window expiry or a successful verification
        (see verify_email_otp) ever clears it."""
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(OtpAbuseCounter).where(
                OtpAbuseCounter.destination == destination, OtpAbuseCounter.purpose == purpose
            )
        )
        counter = result.scalar_one_or_none()
        if counter is None:
            counter = OtpAbuseCounter(destination=destination, purpose=purpose, failed_attempts=0, window_started_at=now)
            self.session.add(counter)
            await self.session.flush()
        elif (now - counter.window_started_at).total_seconds() > ABUSE_WINDOW_MINUTES * 60:
            counter.failed_attempts = 0
            counter.window_started_at = now
        return counter

    async def request_email_otp(self, *, email: str, purpose: str) -> None:
        email_norm = email.lower().strip()
        # Invalidate prior unused challenges for same destination+purpose
        existing = await self.session.execute(
            select(OtpChallenge).where(
                OtpChallenge.destination == email_norm,
                OtpChallenge.purpose == purpose,
                OtpChallenge.consumed_at.is_(None),
            )
        )
        now = datetime.now(UTC)
        for row in existing.scalars().all():
            if row.created_at and (now - row.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
                raise AppError("Please wait before requesting another code.", code="OTP_COOLDOWN", status_code=429)
            row.consumed_at = now

        plaintext = _generate_otp()
        challenge = OtpChallenge(
            destination=email_norm,
            channel="email",
            purpose=purpose,
            code_hash=hash_opaque_token(plaintext),
            attempts=0,
            max_attempts=5,
            expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
        )
        self.session.add(challenge)
        await self.session.commit()

        # Never log plaintext OTP. Email body includes it only for delivery.
        if purpose in _LOGIN_OTP_PURPOSES:
            await send_login_otp_email(to=email_norm, code=plaintext)
        else:
            await send_email_verification_otp_email(to=email_norm, code=plaintext)
        logger.info("otp_requested", purpose=purpose, channel="email", destination=email_norm)

    async def verify_email_otp(self, *, email: str, purpose: str, code: str) -> bool:
        email_norm = email.lower().strip()
        code = code.strip()
        if not code.isdigit() or len(code) != OTP_LENGTH:
            raise AppError("Invalid verification code", code="OTP_INVALID", status_code=400)

        # Persistent, cross-challenge abuse ceiling -- checked BEFORE
        # looking at any individual challenge, so once it trips, no further
        # guesses are evaluated even against a brand-new code requested
        # after this point.
        counter = await self._get_abuse_counter(destination=email_norm, purpose=purpose)
        if counter.failed_attempts >= MAX_ABUSE_ATTEMPTS:
            await self.session.commit()  # persist any window-reset _get_abuse_counter already staged
            logger.info("otp_failed", reason="abuse_locked", purpose=purpose, failed_attempts=counter.failed_attempts)
            raise AppError("Too many invalid attempts", code="OTP_LOCKED", status_code=429)

        result = await self.session.execute(
            select(OtpChallenge)
            .where(
                OtpChallenge.destination == email_norm,
                OtpChallenge.purpose == purpose,
                OtpChallenge.consumed_at.is_(None),
            )
            .order_by(OtpChallenge.created_at.desc())
            .limit(1)
        )
        challenge = result.scalar_one_or_none()
        if not challenge or challenge.expires_at <= datetime.now(UTC):
            await self.session.commit()
            logger.info("otp_failed", reason="expired_or_missing", purpose=purpose)
            raise AppError("Invalid or expired verification code", code="OTP_INVALID", status_code=400)

        if challenge.attempts >= challenge.max_attempts:
            challenge.consumed_at = datetime.now(UTC)
            await self.session.commit()
            logger.info("otp_failed", reason="max_attempts", purpose=purpose)
            raise AppError("Too many invalid attempts", code="OTP_LOCKED", status_code=429)

        if not secrets.compare_digest(challenge.code_hash, hash_opaque_token(code)):
            challenge.attempts += 1
            counter.failed_attempts += 1
            await self.session.commit()
            logger.info(
                "otp_failed",
                reason="mismatch",
                purpose=purpose,
                attempts=challenge.attempts,
                abuse_attempts=counter.failed_attempts,
            )
            raise AppError("Invalid or expired verification code", code="OTP_INVALID", status_code=400)

        challenge.consumed_at = datetime.now(UTC)
        counter.failed_attempts = 0  # legitimate success clears the abuse window immediately
        await self.session.commit()
        logger.info("otp_verified", purpose=purpose, channel="email")
        return True
