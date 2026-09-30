"""Twilio-specific webhook payload shape. Confined to providers/twilio/ —
never imported by services/, repositories/, models/, or api/. Twilio
delivers inbound WhatsApp messages as application/x-www-form-urlencoded
POST parameters (not JSON)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TwilioInboundForm(BaseModel):
    """Subset of Twilio's inbound WhatsApp webhook form fields actually
    used by this M1 foundation. Twilio sends many more fields (NumMedia,
    ProfileName, WaId, etc.) — only what's needed is modeled here;
    unmodeled fields are ignored, not an error.

    F-03: MessageSid/From/To are required for correctness (idempotency
    key, identity key) — min_length=1 rejects an empty string, which
    plain ``str`` alone would accept. Matches this codebase's existing
    Field(min_length=...) convention (see identity/schemas/auth.py's
    RegisterRequest) rather than inventing new validation/normalization;
    whitespace-only values are not separately stripped or rejected here,
    same as that existing convention.
    """

    MessageSid: str = Field(min_length=1)
    From: str = Field(min_length=1)  # "whatsapp:+91XXXXXXXXXX"
    To: str = Field(min_length=1)  # "whatsapp:+91XXXXXXXXXX"
    Body: str | None = None
    NumMedia: str | None = None


WHATSAPP_PREFIX = "whatsapp:"


def strip_whatsapp_prefix(value: str) -> str:
    """ "whatsapp:+91XXXXXXXXXX" -> "+91XXXXXXXXXX". Returns the input
    unchanged if the prefix isn't present (defensive; Twilio always sends
    it for WhatsApp channel messages)."""
    if value.startswith(WHATSAPP_PREFIX):
        return value[len(WHATSAPP_PREFIX) :]
    return value


def add_whatsapp_prefix(phone_e164: str) -> str:
    """ "+91XXXXXXXXXX" -> "whatsapp:+91XXXXXXXXXX", for outbound sends."""
    if phone_e164.startswith(WHATSAPP_PREFIX):
        return phone_e164
    return f"{WHATSAPP_PREFIX}{phone_e164}"
