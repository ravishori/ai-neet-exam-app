"""Provider-neutral canonical message shapes. Only these cross the
providers/<name>/ boundary into services/repositories/models — no
provider-specific field name (Twilio's MessageSid, `whatsapp:`-prefixed
numbers, Meta's wa_id) ever appears outside providers/twilio/ (or a
future providers/<other>/). See
docs/decisions/ADR-WHATSAPP-PROVIDER-ABSTRACTION.md."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CanonicalInboundMessage(BaseModel):
    """What a provider adapter's ``parse_inbound`` produces."""

    provider: str
    provider_message_id: str = Field(min_length=1, max_length=120)
    from_phone: str = Field(min_length=1, max_length=20, description="Sender's WhatsApp number, E.164, no provider prefix")
    to_phone: str = Field(min_length=1, max_length=20, description="Destination (our) WhatsApp number, E.164")
    message_type: str = "text"
    text: str | None = None
    provider_timestamp: datetime | None = None


class ProviderSendResult(BaseModel):
    """What ``send_text`` returns — provider-agnostic; callers never see
    a provider's own response shape."""

    success: bool
    provider: str
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
