"""WhatsApp message persistence/idempotency foundation. M1 scope only —
no intent resolution or learning-service dispatch here (that's the
orchestrator, a later milestone); this service's job ends at "the
inbound message is durably, idempotently persisted."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.modules.whatsapp.models.whatsapp_message import WhatsAppMessage
from app.modules.whatsapp.repositories.whatsapp_repository import WhatsAppRepository


class WhatsAppMessageService:
    def __init__(self, repository: WhatsAppRepository):
        self._repository = repository

    async def persist_inbound(
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
        provider message id was already processed — callers must not
        re-run any downstream action for it."""
        return await self._repository.persist_inbound_message(
            whatsapp_identity_id=whatsapp_identity_id,
            provider=provider,
            provider_message_id=provider_message_id,
            message_type=message_type,
            text=text,
            provider_timestamp=provider_timestamp,
        )
