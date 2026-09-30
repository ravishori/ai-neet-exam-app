"""Provider-independent sender. Callers never touch a provider adapter
directly or see a provider-specific error — only ProviderSendResult."""

from __future__ import annotations

from app.core.logging import get_logger
from app.modules.whatsapp.providers import get_whatsapp_provider
from app.modules.whatsapp.providers.base import WhatsAppProvider
from app.modules.whatsapp.schemas.webhook import ProviderSendResult

logger = get_logger("whatsapp.sender")


class WhatsAppSender:
    def __init__(self, *, provider: WhatsAppProvider | None = None):
        # ``provider`` is injectable for tests (a fake provider); production
        # resolves it from settings on each call via get_whatsapp_provider().
        self._provider_override = provider

    def _provider(self) -> WhatsAppProvider:
        return self._provider_override or get_whatsapp_provider()

    async def send_text(self, to_phone: str, body: str) -> ProviderSendResult:
        result = await self._provider().send_text(to_phone, body)
        if not result.success:
            logger.warning(
                "whatsapp_send_failed",
                provider=result.provider,
                error_code=result.error_code,
            )
        return result
