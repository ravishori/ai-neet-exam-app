"""WhatsApp identity foundation. M1 scope only: resolve/create an
identity record keyed on (provider, phone_e164) and track last_seen_at.
Never auto-links to a Trinetra user — user_id stays NULL until the (M2)
secure one-time-code linking flow explicitly sets it."""

from __future__ import annotations

from app.modules.whatsapp.models.whatsapp_identity import WhatsAppIdentity
from app.modules.whatsapp.repositories.whatsapp_repository import WhatsAppRepository


class WhatsAppIdentityService:
    def __init__(self, repository: WhatsAppRepository):
        self._repository = repository

    async def resolve_identity(self, *, provider: str, phone_e164: str) -> WhatsAppIdentity:
        identity = await self._repository.get_or_create_identity(provider=provider, phone_e164=phone_e164)
        await self._repository.touch_last_seen(identity)
        return identity
