"""Repository for whatsapp.link_codes. Mutations that must win a
concurrent race (consuming a code, incrementing an attempt) use a single
atomic ``UPDATE ... WHERE <still-valid> RETURNING`` statement rather than
read-then-write, so two simultaneous verification attempts for the same
code can never both succeed."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.whatsapp.models.whatsapp_link_code import WhatsAppLinkCode


class WhatsAppLinkCodeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, user_id: uuid.UUID, code_hash: str, expires_at: datetime, max_attempts: int) -> WhatsAppLinkCode:
        code = WhatsAppLinkCode(
            user_id=user_id,
            code_hash=code_hash,
            attempts=0,
            max_attempts=max_attempts,
            expires_at=expires_at,
        )
        self.session.add(code)
        await self.session.flush()
        return code

    async def invalidate_pending_for_user(self, user_id: uuid.UUID) -> None:
        """Consume (without linking anything) every still-pending code for
        this user — mirrors OtpService's "invalidate prior unused
        challenges" behavior so a new code request supersedes old ones
        rather than leaving multiple valid codes outstanding."""
        now = datetime.now(UTC)
        await self.session.execute(
            update(WhatsAppLinkCode)
            .where(WhatsAppLinkCode.user_id == user_id, WhatsAppLinkCode.consumed_at.is_(None))
            .values(consumed_at=now)
        )

    async def get_active_by_id(self, code_id: uuid.UUID) -> WhatsAppLinkCode | None:
        result = await self.session.execute(
            select(WhatsAppLinkCode).where(WhatsAppLinkCode.id == code_id, WhatsAppLinkCode.consumed_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def find_candidates_for_verification(self, *, now: datetime) -> list[WhatsAppLinkCode]:
        """Unconsumed, unexpired, not-yet-locked-out codes — the plaintext
        code carries no identifying reference back to a specific row, so
        verification must hash-compare against this candidate set rather
        than a single indexed lookup. Bounded by expiry/consumption/
        attempts, so this set stays small in practice."""
        result = await self.session.execute(
            select(WhatsAppLinkCode).where(
                WhatsAppLinkCode.consumed_at.is_(None),
                WhatsAppLinkCode.expires_at > now,
                WhatsAppLinkCode.attempts < WhatsAppLinkCode.max_attempts,
            )
        )
        return list(result.scalars().all())

    async def increment_attempts(self, code_id: uuid.UUID) -> None:
        await self.session.execute(
            update(WhatsAppLinkCode).where(WhatsAppLinkCode.id == code_id).values(attempts=WhatsAppLinkCode.attempts + 1)
        )

    async def try_consume(self, code_id: uuid.UUID, *, whatsapp_identity_id: uuid.UUID) -> bool:
        """Atomically marks the code consumed — the ``WHERE consumed_at IS
        NULL`` guard is what makes two concurrent verification attempts
        for the same code resolve to exactly one winner. Returns True iff
        this call was the one that consumed it."""
        now = datetime.now(UTC)
        result = await self.session.execute(
            update(WhatsAppLinkCode)
            .where(WhatsAppLinkCode.id == code_id, WhatsAppLinkCode.consumed_at.is_(None))
            .values(consumed_at=now, whatsapp_identity_id=whatsapp_identity_id)
            .returning(WhatsAppLinkCode.id)
        )
        return result.scalar_one_or_none() is not None
