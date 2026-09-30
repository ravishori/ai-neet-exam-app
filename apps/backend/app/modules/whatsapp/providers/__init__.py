"""Provider resolver — the one place that knows how to turn
``settings.whatsapp_provider`` into a concrete WhatsAppProvider instance.
Adding a new provider means adding one branch here (or, at larger scale,
a registry dict) and a new providers/<name>/ package — never touching
services/, repositories/, models/, or the router."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.modules.whatsapp.providers.base import WhatsAppProvider
from app.modules.whatsapp.providers.twilio.client import TwilioWhatsAppProvider


class UnknownWhatsAppProviderError(AppError):
    def __init__(self, provider_name: str):
        super().__init__(
            f"Unknown WhatsApp provider: {provider_name}",
            code="WHATSAPP_PROVIDER_NOT_CONFIGURED",
            status_code=503,
        )


def get_whatsapp_provider() -> WhatsAppProvider:
    provider_name = (get_settings().whatsapp_provider or "").strip().lower()
    if provider_name == "twilio":
        return TwilioWhatsAppProvider()
    raise UnknownWhatsAppProviderError(provider_name or "(unset)")
