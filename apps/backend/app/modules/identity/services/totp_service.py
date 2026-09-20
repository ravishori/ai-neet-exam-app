"""Optional TOTP MFA (authenticator apps) + recovery codes."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

import pyotp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.identity.models.otp import TotpRecoveryCode
from app.modules.identity.models.user import User
from app.modules.identity.services.token_service import hash_opaque_token

logger = get_logger("totp")

RECOVERY_CODE_COUNT = 8


class TotpService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def begin_enrollment(self, user: User) -> dict:
        if user.totp_enabled:
            raise AppError("Two-factor authentication is already enabled", code="TOTP_ALREADY_ENABLED", status_code=400)
        secret = pyotp.random_base32()
        user.totp_secret_encrypted = encrypt_secret(secret)
        user.totp_enabled = False
        user.totp_confirmed_at = None
        await self.session.commit()
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Trinetra TALOS")
        return {"secret": secret, "otpauth_url": uri}

    async def confirm_enrollment(self, user: User, code: str) -> list[str]:
        if not user.totp_secret_encrypted:
            raise AppError("Start enrollment first", code="TOTP_NOT_STARTED", status_code=400)
        secret = decrypt_secret(user.totp_secret_encrypted)
        if not pyotp.TOTP(secret).verify(code.strip(), valid_window=1):
            raise AppError("Invalid authenticator code", code="TOTP_INVALID", status_code=400)
        user.totp_enabled = True
        user.totp_confirmed_at = datetime.now(UTC)

        # Replace recovery codes
        existing = await self.session.execute(select(TotpRecoveryCode).where(TotpRecoveryCode.user_id == user.id))
        for row in existing.scalars().all():
            await self.session.delete(row)

        plain_codes: list[str] = []
        for _ in range(RECOVERY_CODE_COUNT):
            code_plain = secrets.token_hex(4)
            plain_codes.append(code_plain)
            self.session.add(TotpRecoveryCode(user_id=user.id, code_hash=hash_opaque_token(code_plain)))
        await self.session.commit()
        logger.info("totp_enabled", user_id=str(user.id))
        return plain_codes

    async def disable(self, user: User, code: str) -> None:
        if not user.totp_enabled:
            raise AppError("Two-factor authentication is not enabled", code="TOTP_NOT_ENABLED", status_code=400)
        if not await self.verify(user, code):
            raise AppError("Invalid authenticator code", code="TOTP_INVALID", status_code=400)
        user.totp_enabled = False
        user.totp_secret_encrypted = None
        user.totp_confirmed_at = None
        existing = await self.session.execute(select(TotpRecoveryCode).where(TotpRecoveryCode.user_id == user.id))
        for row in existing.scalars().all():
            await self.session.delete(row)
        await self.session.commit()
        logger.info("totp_disabled", user_id=str(user.id))

    async def verify(self, user: User, code: str) -> bool:
        code = code.strip()
        if user.totp_enabled and user.totp_secret_encrypted:
            secret = decrypt_secret(user.totp_secret_encrypted)
            if pyotp.TOTP(secret).verify(code, valid_window=1):
                return True
        # Recovery codes
        result = await self.session.execute(
            select(TotpRecoveryCode).where(
                TotpRecoveryCode.user_id == user.id,
                TotpRecoveryCode.used_at.is_(None),
            )
        )
        for row in result.scalars().all():
            if secrets.compare_digest(row.code_hash, hash_opaque_token(code)):
                row.used_at = datetime.now(UTC)
                await self.session.commit()
                logger.info("totp_recovery_used", user_id=str(user.id))
                return True
        return False
