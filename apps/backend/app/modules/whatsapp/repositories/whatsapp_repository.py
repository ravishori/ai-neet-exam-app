"""Repository for whatsapp.identities / whatsapp.messages /
whatsapp.study_sessions. Follows the identity module's repository
pattern (plain class wrapping an AsyncSession — see
identity/repositories/geo_repository.py)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.whatsapp.models.whatsapp_identity import WhatsAppIdentity
from app.modules.whatsapp.models.whatsapp_message import WhatsAppMessage
from app.modules.whatsapp.models.whatsapp_study_session import WhatsAppStudySession


class WhatsAppRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- identities -----------------------------------------------------

    async def get_identity_by_provider_phone(self, provider: str, phone_e164: str) -> WhatsAppIdentity | None:
        result = await self.session.execute(
            select(WhatsAppIdentity).where(WhatsAppIdentity.provider == provider, WhatsAppIdentity.phone_e164 == phone_e164)
        )
        return result.scalar_one_or_none()

    async def get_or_create_identity(self, *, provider: str, phone_e164: str) -> WhatsAppIdentity:
        """Never auto-links to a user — user_id stays NULL until the (M2)
        linking flow explicitly sets it. Idempotent: a second call with
        the same (provider, phone_e164) returns the existing row."""
        existing = await self.get_identity_by_provider_phone(provider, phone_e164)
        if existing:
            return existing

        identity = WhatsAppIdentity(provider=provider, phone_e164=phone_e164, status="active")
        try:
            # SAVEPOINT, not a full session.rollback() — a concurrent-
            # duplicate race here must only undo this one insert, never
            # discard other work already pending in the caller's
            # transaction.
            async with self.session.begin_nested():
                self.session.add(identity)
                await self.session.flush()
        except IntegrityError:
            existing = await self.get_identity_by_provider_phone(provider, phone_e164)
            if existing:
                return existing
            raise
        return identity

    async def touch_last_seen(self, identity: WhatsAppIdentity) -> None:
        identity.last_seen_at = datetime.now(UTC)

    # --- messages ---------------------------------------------------------

    async def get_message_by_provider_id(self, provider: str, provider_message_id: str) -> WhatsAppMessage | None:
        result = await self.session.execute(
            select(WhatsAppMessage).where(
                WhatsAppMessage.provider == provider, WhatsAppMessage.provider_message_id == provider_message_id
            )
        )
        return result.scalar_one_or_none()

    async def persist_inbound_message(
        self,
        *,
        whatsapp_identity_id: uuid.UUID,
        provider: str,
        provider_message_id: str,
        message_type: str,
        text: str | None,
        provider_timestamp: datetime | None,
    ) -> tuple[WhatsAppMessage, bool]:
        """Returns (message, created). ``created=False`` means this exact
        (provider, provider_message_id) was already persisted — the
        durable idempotency guarantee from the UNIQUE(provider,
        provider_message_id) constraint, not just an in-process check."""
        existing = await self.get_message_by_provider_id(provider, provider_message_id)
        if existing:
            return existing, False

        message = WhatsAppMessage(
            whatsapp_identity_id=whatsapp_identity_id,
            provider=provider,
            provider_message_id=provider_message_id,
            direction="inbound",
            message_type=message_type,
            text=text,
            provider_timestamp=provider_timestamp,
            processing_status="received",
        )
        try:
            # SAVEPOINT — see get_or_create_identity's comment above.
            async with self.session.begin_nested():
                self.session.add(message)
                await self.session.flush()
        except IntegrityError:
            existing = await self.get_message_by_provider_id(provider, provider_message_id)
            if existing:
                return existing, False
            raise
        return message, True

    async def mark_message_status(self, message: WhatsAppMessage, *, status: str, error_code: str | None = None) -> None:
        message.processing_status = status
        message.error_code = error_code

    # --- study sessions -----------------------------------------------------

    async def create_study_session(self, *, whatsapp_identity_id: uuid.UUID, session_type: str) -> WhatsAppStudySession:
        """M1 persistence boundary only — no state machine on top of this
        yet (see model docstring)."""
        session_row = WhatsAppStudySession(
            whatsapp_identity_id=whatsapp_identity_id,
            session_type=session_type,
            status="active",
            started_at=datetime.now(UTC),
        )
        self.session.add(session_row)
        await self.session.flush()
        return session_row
