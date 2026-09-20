"""Email/SMS OTP challenges — codes stored hashed, never returned in API bodies."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.identity.models.otp import OtpChallenge
from app.modules.identity.services.email_service import _send
from app.modules.identity.services.token_service import hash_opaque_token

logger = get_logger("otp")

OTP_TTL_MINUTES = 10
OTP_LENGTH = 6
RESEND_COOLDOWN_SECONDS = 60


def _generate_otp() -> str:
    # Cryptographically secure numeric OTP
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


class OtpService:
    def __init__(self, session: AsyncSession):
        self.session = session

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
        _send(
            to=email_norm,
            subject="Your Trinetra verification code",
            body=f"Your verification code is: {plaintext}\n\nIt expires in {OTP_TTL_MINUTES} minutes.\n",
            kind="otp",
        )
        logger.info("otp_requested", purpose=purpose, channel="email", destination=email_norm)

    async def verify_email_otp(self, *, email: str, purpose: str, code: str) -> bool:
        email_norm = email.lower().strip()
        code = code.strip()
        if not code.isdigit() or len(code) != OTP_LENGTH:
            raise AppError("Invalid verification code", code="OTP_INVALID", status_code=400)

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
            logger.info("otp_failed", reason="expired_or_missing", purpose=purpose)
            raise AppError("Invalid or expired verification code", code="OTP_INVALID", status_code=400)

        if challenge.attempts >= challenge.max_attempts:
            challenge.consumed_at = datetime.now(UTC)
            await self.session.commit()
            logger.info("otp_failed", reason="max_attempts", purpose=purpose)
            raise AppError("Too many invalid attempts", code="OTP_LOCKED", status_code=429)

        if not secrets.compare_digest(challenge.code_hash, hash_opaque_token(code)):
            challenge.attempts += 1
            await self.session.commit()
            logger.info("otp_failed", reason="mismatch", purpose=purpose, attempts=challenge.attempts)
            raise AppError("Invalid or expired verification code", code="OTP_INVALID", status_code=400)

        challenge.consumed_at = datetime.now(UTC)
        await self.session.commit()
        logger.info("otp_verified", purpose=purpose, channel="email")
        return True
