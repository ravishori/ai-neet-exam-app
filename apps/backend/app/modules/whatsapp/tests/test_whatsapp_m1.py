"""M1 foundation tests: provider interface/portability, Twilio adapter
(signature validation, inbound parsing, outbound send), repository
idempotency, and the webhook API. No real Twilio call is ever made —
httpx.MockTransport stands in for the network per the existing
twilio_verify_service.py test convention (TwilioVerifyStubTransport)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
import pydantic
import pytest
import structlog
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.rate_limit import RateLimitExceeded
from app.modules.whatsapp.providers.twilio import client as twilio_client_module
from app.modules.whatsapp.providers.twilio.client import TwilioWhatsAppProvider
from app.modules.whatsapp.providers.twilio.schemas import TwilioInboundForm, add_whatsapp_prefix, strip_whatsapp_prefix
from app.modules.whatsapp.providers.twilio.webhook import (
    _canonical_request_url,
    compute_twilio_signature,
    validate_twilio_signature,
)
from app.modules.whatsapp.repositories.whatsapp_repository import WhatsAppRepository
from app.modules.whatsapp.schemas.webhook import CanonicalInboundMessage, ProviderSendResult
from app.modules.whatsapp.services.whatsapp_sender import WhatsAppSender
from app.modules.whatsapp.services.whatsapp_webhook_service import WebhookValidationError, WhatsAppWebhookService

pytestmark = pytest.mark.asyncio(loop_scope="session")

_AUTH_TOKEN = "test-twilio-auth-token-1234567890"
_WEBHOOK_URL = "http://test/api/v1/whatsapp/webhook"


def _set_twilio_env(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TWILIO_ACCOUNT_SID", "ACtest0000000000000000000000000000")
    monkeypatch.setenv("WHATSAPP_TWILIO_AUTH_TOKEN", _AUTH_TOKEN)
    monkeypatch.setenv("WHATSAPP_TWILIO_WHATSAPP_FROM", "+15550001111")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
    get_settings.cache_clear()


def _clear_settings_cache():
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Fake provider — provider portability
# ---------------------------------------------------------------------------


class FakeWhatsAppProvider:
    """Implements the same structural interface as TwilioWhatsAppProvider
    (providers.base.WhatsAppProvider) without importing anything
    Twilio-specific. Used to prove the webhook service can process a
    canonical message through a completely different provider
    implementation with zero code changes to the service layer."""

    def __init__(self, *, valid: bool = True, message_id: str = "fake-msg-1"):
        self._valid = valid
        self._message_id = message_id
        self.sent: list[tuple[str, str]] = []

    async def validate_webhook(self, request, raw_body: bytes) -> bool:
        return self._valid

    async def parse_inbound(self, request, raw_body: bytes) -> CanonicalInboundMessage:
        return CanonicalInboundMessage(
            provider="fake",
            provider_message_id=self._message_id,
            from_phone="+919999999999",
            to_phone="+911111111111",
            message_type="text",
            text="hi",
            provider_timestamp=datetime.now(UTC),
        )

    async def send_text(self, to_phone: str, body: str) -> ProviderSendResult:
        self.sent.append((to_phone, body))
        return ProviderSendResult(success=True, provider="fake", provider_message_id="fake-sent-1")


class _FakeRequest:
    """Minimal stand-in for starlette.requests.Request — the fake provider
    above never actually inspects it, but the interface requires passing
    something request-shaped."""


async def test_webhook_service_processes_a_fake_provider_with_no_twilio_import(db_session):
    """Provider portability: WhatsAppWebhookService works against a
    provider that has never heard of Twilio."""
    fake = FakeWhatsAppProvider()
    repository = WhatsAppRepository(db_session)
    service = WhatsAppWebhookService(provider=fake, repository=repository)

    result = await service.handle_inbound(_FakeRequest(), b"")

    assert result.accepted is True
    assert result.duplicate is False

    identity = await repository.get_identity_by_provider_phone("fake", "+919999999999")
    assert identity is not None
    message = await repository.get_message_by_provider_id("fake", "fake-msg-1")
    assert message is not None
    assert message.text == "hi"


async def test_webhook_service_rejects_invalid_signature_regardless_of_provider(db_session):
    fake = FakeWhatsAppProvider(valid=False)
    repository = WhatsAppRepository(db_session)
    service = WhatsAppWebhookService(provider=fake, repository=repository)

    with pytest.raises(WebhookValidationError):
        await service.handle_inbound(_FakeRequest(), b"")


async def test_webhook_service_idempotent_for_duplicate_provider_message_id(db_session):
    fake = FakeWhatsAppProvider(message_id="dup-1")
    repository = WhatsAppRepository(db_session)
    service = WhatsAppWebhookService(provider=fake, repository=repository)

    first = await service.handle_inbound(_FakeRequest(), b"")
    second = await service.handle_inbound(_FakeRequest(), b"")

    assert first.duplicate is False
    assert second.duplicate is True

    # Exactly one row for this provider_message_id — not two.
    from sqlalchemy import func, select

    from app.modules.whatsapp.models.whatsapp_message import WhatsAppMessage

    count = (
        await db_session.execute(
            select(func.count()).where(WhatsAppMessage.provider == "fake", WhatsAppMessage.provider_message_id == "dup-1")
        )
    ).scalar_one()
    assert count == 1


# ---------------------------------------------------------------------------
# Twilio adapter — schemas (prefix helpers)
# ---------------------------------------------------------------------------


def test_strip_whatsapp_prefix():
    assert strip_whatsapp_prefix("whatsapp:+919999999999") == "+919999999999"
    assert strip_whatsapp_prefix("+919999999999") == "+919999999999"


def test_add_whatsapp_prefix():
    assert add_whatsapp_prefix("+919999999999") == "whatsapp:+919999999999"
    assert add_whatsapp_prefix("whatsapp:+919999999999") == "whatsapp:+919999999999"


# ---------------------------------------------------------------------------
# Twilio adapter — schemas (F-03: required-field validation)
# ---------------------------------------------------------------------------

_VALID_FORM = {
    "MessageSid": "SM123",
    "From": "whatsapp:+919999999999",
    "To": "whatsapp:+911111111111",
    "Body": "hi",
}


def test_twilio_inbound_form_accepts_valid_values():
    parsed = TwilioInboundForm.model_validate(_VALID_FORM)
    assert parsed.MessageSid == "SM123"
    assert parsed.From == "whatsapp:+919999999999"
    assert parsed.To == "whatsapp:+911111111111"


def test_twilio_inbound_form_rejects_empty_message_sid():
    with pytest.raises(pydantic.ValidationError):
        TwilioInboundForm.model_validate({**_VALID_FORM, "MessageSid": ""})


def test_twilio_inbound_form_rejects_empty_from():
    with pytest.raises(pydantic.ValidationError):
        TwilioInboundForm.model_validate({**_VALID_FORM, "From": ""})


def test_twilio_inbound_form_rejects_empty_to():
    with pytest.raises(pydantic.ValidationError):
        TwilioInboundForm.model_validate({**_VALID_FORM, "To": ""})


async def test_post_webhook_empty_message_sid_rejected_safely_via_malformed_payload_path(client: AsyncClient, monkeypatch):
    """F-03's empty-field rejection must flow through the same existing
    safe malformed-payload path as a genuinely missing field (both are
    pydantic.ValidationError, caught identically in parse_inbound)."""
    _set_twilio_env(monkeypatch)
    form = {**_VALID_FORM, "MessageSid": ""}
    sig = await compute_twilio_signature(_WEBHOOK_URL, form, _AUTH_TOKEN)
    resp = await client.post("/api/v1/whatsapp/webhook", data=form, headers={"X-Twilio-Signature": sig})

    assert resp.status_code >= 400
    assert "Traceback" not in resp.text
    assert _AUTH_TOKEN not in resp.text
    _clear_settings_cache()


# ---------------------------------------------------------------------------
# Twilio adapter — signature validation
# ---------------------------------------------------------------------------


async def test_compute_twilio_signature_is_deterministic_and_key_sensitive():
    """No external "known vector" is asserted here — this environment has
    no verified reference value from Twilio's own docs to check against.
    Instead: the algorithm must be deterministic (same inputs -> same
    signature) and sensitive to every input that's supposed to matter
    (URL, each param, and the auth token) — exactly the properties that
    make it usable as a real signature scheme."""
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    params = {"Digits": "1234"}
    token = "12345"

    sig = await compute_twilio_signature(url, params, token)
    assert await compute_twilio_signature(url, params, token) == sig  # deterministic

    assert await compute_twilio_signature(url + "x", params, token) != sig
    assert await compute_twilio_signature(url, {"Digits": "5678"}, token) != sig
    assert await compute_twilio_signature(url, params, token + "x") != sig


async def test_compute_twilio_signature_sorts_params_by_key():
    """Twilio's algorithm sorts params by key before concatenating —
    verify param insertion order doesn't affect the result."""
    url = "https://mycompany.com/myapp.php"
    token = "12345"
    sig_a = await compute_twilio_signature(url, {"b": "2", "a": "1"}, token)
    sig_b = await compute_twilio_signature(url, {"a": "1", "b": "2"}, token)
    assert sig_a == sig_b


class _SignedRequest:
    """Minimal Starlette-Request-shaped stub for validate_twilio_signature,
    which only calls .headers.get(...), .url, and .form()."""

    def __init__(self, url: str, form: dict[str, str], signature: str | None):
        self.url = url
        self._form = form
        self.headers = {"X-Twilio-Signature": signature} if signature else {}

    async def form(self):
        class _Form:
            def __init__(self, data):
                self._data = data

            def multi_items(self):
                return list(self._data.items())

        return _Form(self._form)


async def test_validate_twilio_signature_accepts_valid_signature():
    url = "http://test/api/v1/whatsapp/webhook"
    form = {"MessageSid": "SM123", "From": "whatsapp:+919999999999", "To": "whatsapp:+911111111111", "Body": "hi"}
    sig = await compute_twilio_signature(url, form, _AUTH_TOKEN)
    request = _SignedRequest(url, form, sig)
    assert await validate_twilio_signature(request, auth_token=_AUTH_TOKEN) is True


async def test_validate_twilio_signature_rejects_invalid_signature():
    url = "http://test/api/v1/whatsapp/webhook"
    form = {"MessageSid": "SM123", "From": "whatsapp:+919999999999", "To": "whatsapp:+911111111111", "Body": "hi"}
    request = _SignedRequest(url, form, "not-a-real-signature")
    assert await validate_twilio_signature(request, auth_token=_AUTH_TOKEN) is False


async def test_validate_twilio_signature_rejects_missing_signature():
    url = "http://test/api/v1/whatsapp/webhook"
    form = {"MessageSid": "SM123"}
    request = _SignedRequest(url, form, None)
    assert await validate_twilio_signature(request, auth_token=_AUTH_TOKEN) is False


async def test_validate_twilio_signature_fails_closed_when_unconfigured():
    url = "http://test/api/v1/whatsapp/webhook"
    form = {"MessageSid": "SM123"}
    request = _SignedRequest(url, form, "some-signature")
    assert await validate_twilio_signature(request, auth_token="") is False


async def test_validate_twilio_signature_rejects_malformed_form(monkeypatch):
    class _BrokenFormRequest:
        url = "http://test/api/v1/whatsapp/webhook"
        headers = {"X-Twilio-Signature": "whatever"}

        async def form(self):
            raise ValueError("malformed body")

    assert await validate_twilio_signature(_BrokenFormRequest(), auth_token=_AUTH_TOKEN) is False


# ---------------------------------------------------------------------------
# Twilio adapter — F-01: reverse-proxy scheme/host canonicalization
# ---------------------------------------------------------------------------


class _ForwardedRequest:
    """Like _SignedRequest, but with a Starlette-URL-shaped ``url`` (has
    .path/.query, like the real thing behind a proxy) and support for
    X-Forwarded-Proto/X-Forwarded-Host headers."""

    class _Url:
        def __init__(self, raw: str):
            self._raw = raw
            parts = urlsplit(raw)
            self.path = parts.path
            self.query = parts.query

        def __str__(self):
            return self._raw

    def __init__(self, url: str, form: dict[str, str], signature: str | None, headers: dict[str, str] | None = None):
        self.url = self._Url(url)
        self._form = form
        self.headers = {**(headers or {})}
        if signature:
            self.headers["X-Twilio-Signature"] = signature

    async def form(self):
        class _Form:
            def __init__(self, data):
                self._data = data

            def multi_items(self):
                return list(self._data.items())

        return _Form(self._form)


_EXTERNAL_URL = "https://api.neet.trinetralab.net/api/v1/whatsapp/webhook"
_INTERNAL_URL = "http://internal-service/api/v1/whatsapp/webhook"
_FORM = {"MessageSid": "SM123", "From": "whatsapp:+919999999999", "To": "whatsapp:+911111111111", "Body": "hi"}


async def test_canonical_request_url_uses_request_url_when_no_forwarded_headers():
    """Direct HTTPS, no proxy in front — identical to pre-fix behavior."""
    request = _ForwardedRequest(_EXTERNAL_URL, _FORM, None)
    assert _canonical_request_url(request) == "https://api.neet.trinetralab.net/api/v1/whatsapp/webhook"


async def test_canonical_request_url_prefers_forwarded_headers():
    """Reverse-proxy case: request.url reports internal HTTP, but
    X-Forwarded-Proto/Host carry what Twilio actually called."""
    request = _ForwardedRequest(
        _INTERNAL_URL,
        _FORM,
        None,
        headers={"x-forwarded-proto": "https", "x-forwarded-host": "api.neet.trinetralab.net"},
    )
    assert _canonical_request_url(request) == "https://api.neet.trinetralab.net/api/v1/whatsapp/webhook"


async def test_validate_twilio_signature_accepts_valid_signature_behind_reverse_proxy():
    """The signature Twilio computed against the externally-visible HTTPS
    URL must validate even though request.url itself is internal HTTP —
    this is the exact scenario F-01 flagged as broken."""
    sig = await compute_twilio_signature(_EXTERNAL_URL, _FORM, _AUTH_TOKEN)
    request = _ForwardedRequest(
        _INTERNAL_URL,
        _FORM,
        sig,
        headers={"x-forwarded-proto": "https", "x-forwarded-host": "api.neet.trinetralab.net"},
    )
    assert await validate_twilio_signature(request, auth_token=_AUTH_TOKEN) is True


async def test_validate_twilio_signature_rejects_signature_for_wrong_external_url():
    """A signature computed against a different (attacker-claimed) external
    URL must not validate just because forwarded headers are present."""
    sig = await compute_twilio_signature("https://evil.example.com/api/v1/whatsapp/webhook", _FORM, _AUTH_TOKEN)
    request = _ForwardedRequest(
        _INTERNAL_URL,
        _FORM,
        sig,
        headers={"x-forwarded-proto": "https", "x-forwarded-host": "api.neet.trinetralab.net"},
    )
    assert await validate_twilio_signature(request, auth_token=_AUTH_TOKEN) is False


async def test_validate_twilio_signature_direct_https_still_rejects_missing_signature():
    request = _ForwardedRequest(_EXTERNAL_URL, _FORM, None)
    assert await validate_twilio_signature(request, auth_token=_AUTH_TOKEN) is False


# ---------------------------------------------------------------------------
# Twilio adapter — outbound send (mocked transport, no real network call)
# ---------------------------------------------------------------------------


async def test_twilio_send_text_success(monkeypatch):
    _set_twilio_env(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"sid": "SM_sent_1", "status": "queued"})

    provider = TwilioWhatsAppProvider(transport=httpx.MockTransport(handler))
    result = await provider.send_text("+919999999999", "Hello from Trinetra")

    assert result.success is True
    assert result.provider == "twilio"
    assert result.provider_message_id == "SM_sent_1"
    _clear_settings_cache()


async def test_twilio_send_text_provider_4xx_maps_to_safe_error(monkeypatch):
    _set_twilio_env(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": 21211, "message": "Invalid 'To' Phone Number: whatsapp:+1"})

    provider = TwilioWhatsAppProvider(transport=httpx.MockTransport(handler))
    result = await provider.send_text("+1", "Hello")

    assert result.success is False
    assert result.provider == "twilio"
    assert result.error_code == "WHATSAPP_PROVIDER_SEND_FAILED"
    # The raw Twilio error message must never be forwarded.
    assert result.error_message is None
    _clear_settings_cache()


async def test_twilio_send_text_malformed_2xx_response_does_not_raise(monkeypatch):
    """F-02: a 2xx response with a non-JSON body must degrade to a safe
    ProviderSendResult(success=False, ...), never a raw JSONDecodeError —
    per providers/base.py's send_text contract."""
    _set_twilio_env(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all", headers={"content-type": "text/plain"})

    provider = TwilioWhatsAppProvider(transport=httpx.MockTransport(handler))
    result = await provider.send_text("+919999999999", "Hello")  # must not raise

    assert result.success is False
    assert result.provider == "twilio"
    assert result.error_code == "WHATSAPP_PROVIDER_INVALID_RESPONSE"
    _clear_settings_cache()


async def test_twilio_send_text_empty_2xx_body_does_not_raise(monkeypatch):
    """Same contract, empty-body variant of the malformed-2xx case."""
    _set_twilio_env(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    provider = TwilioWhatsAppProvider(transport=httpx.MockTransport(handler))
    result = await provider.send_text("+919999999999", "Hello")  # must not raise

    assert result.success is False
    assert result.error_code == "WHATSAPP_PROVIDER_INVALID_RESPONSE"
    _clear_settings_cache()


async def test_twilio_send_text_network_failure(monkeypatch):
    _set_twilio_env(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = TwilioWhatsAppProvider(transport=httpx.MockTransport(handler))
    result = await provider.send_text("+919999999999", "Hello")

    assert result.success is False
    assert result.error_code == "WHATSAPP_PROVIDER_UNAVAILABLE"
    _clear_settings_cache()


async def test_twilio_send_text_unconfigured_returns_safe_error(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TWILIO_ACCOUNT_SID", "")
    monkeypatch.setenv("WHATSAPP_TWILIO_AUTH_TOKEN", "")
    monkeypatch.setenv("WHATSAPP_TWILIO_WHATSAPP_FROM", "")
    get_settings.cache_clear()

    provider = TwilioWhatsAppProvider()
    result = await provider.send_text("+919999999999", "Hello")

    assert result.success is False
    assert result.error_code == "WHATSAPP_PROVIDER_NOT_CONFIGURED"
    get_settings.cache_clear()


async def test_whatsapp_sender_logs_and_returns_failure(monkeypatch):
    class _AlwaysFailProvider:
        async def send_text(self, to_phone, body):
            return ProviderSendResult(success=False, provider="fake", error_code="BOOM")

    sender = WhatsAppSender(provider=_AlwaysFailProvider())
    result = await sender.send_text("+919999999999", "hi")
    assert result.success is False
    assert result.error_code == "BOOM"


# ---------------------------------------------------------------------------
# Repository — idempotency / persistence / transaction behavior
# ---------------------------------------------------------------------------


async def test_get_or_create_identity_creates_and_is_idempotent(db_session):
    repo = WhatsAppRepository(db_session)
    first = await repo.get_or_create_identity(provider="twilio", phone_e164="+919999999999")
    second = await repo.get_or_create_identity(provider="twilio", phone_e164="+919999999999")
    assert first.id == second.id
    assert first.user_id is None  # never auto-linked


async def test_persist_inbound_message_unique_provider_message_id(db_session):
    repo = WhatsAppRepository(db_session)
    identity = await repo.get_or_create_identity(provider="twilio", phone_e164="+919999999999")

    message, created = await repo.persist_inbound_message(
        whatsapp_identity_id=identity.id,
        provider="twilio",
        provider_message_id="SM_unique_1",
        message_type="text",
        text="hello",
        provider_timestamp=None,
    )
    assert created is True

    duplicate, created_again = await repo.persist_inbound_message(
        whatsapp_identity_id=identity.id,
        provider="twilio",
        provider_message_id="SM_unique_1",
        message_type="text",
        text="hello again — should be ignored",
        provider_timestamp=None,
    )
    assert created_again is False
    assert duplicate.id == message.id
    assert duplicate.text == "hello"  # the original row, not overwritten


async def test_create_study_session_persistence_boundary(db_session):
    repo = WhatsAppRepository(db_session)
    identity = await repo.get_or_create_identity(provider="twilio", phone_e164="+919999999999")
    session_row = await repo.create_study_session(whatsapp_identity_id=identity.id, session_type="quiz")
    assert session_row.id is not None
    assert session_row.status == "active"
    assert session_row.assessment_id is None
    assert session_row.attempt_id is None


# ---------------------------------------------------------------------------
# API — GET/POST webhook
# ---------------------------------------------------------------------------


async def test_get_webhook_returns_200(client: AsyncClient):
    resp = await client.get("/api/v1/whatsapp/webhook")
    assert resp.status_code == 200


async def test_post_webhook_valid_signature_persists_message(client: AsyncClient, monkeypatch):
    _set_twilio_env(monkeypatch)
    form = {
        "MessageSid": "SM_api_valid_1",
        "From": "whatsapp:+919999999999",
        "To": "whatsapp:+911111111111",
        "Body": "Hi",
    }
    sig = await compute_twilio_signature(_WEBHOOK_URL, form, _AUTH_TOKEN)

    resp = await client.post(
        "/api/v1/whatsapp/webhook",
        data=form,
        headers={"X-Twilio-Signature": sig},
    )
    assert resp.status_code == 200
    # Twilio's messaging webhook logs error 12300 ("Invalid Content-Type")
    # for any 2xx response it can't parse as TwiML — an empty <Response/>
    # is TwiML's documented no-reply acknowledgment, matching M1's
    # intentional no-auto-reply design.
    assert resp.headers["content-type"].startswith("text/xml")
    assert resp.text == '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    _clear_settings_cache()


async def test_post_webhook_invalid_signature_rejected(client: AsyncClient, monkeypatch):
    _set_twilio_env(monkeypatch)
    form = {
        "MessageSid": "SM_api_invalid_1",
        "From": "whatsapp:+919999999999",
        "To": "whatsapp:+911111111111",
        "Body": "Hi",
    }
    resp = await client.post(
        "/api/v1/whatsapp/webhook",
        data=form,
        headers={"X-Twilio-Signature": "totally-wrong"},
    )
    assert resp.status_code == 403
    assert "invalid_signature" in resp.text
    _clear_settings_cache()


async def test_post_webhook_missing_signature_rejected(client: AsyncClient, monkeypatch):
    _set_twilio_env(monkeypatch)
    form = {"MessageSid": "SM_api_missing_sig", "From": "whatsapp:+919999999999", "To": "whatsapp:+911111111111"}
    resp = await client.post("/api/v1/whatsapp/webhook", data=form)
    assert resp.status_code == 403
    _clear_settings_cache()


async def test_post_webhook_malformed_payload_rejected_safely(client: AsyncClient, monkeypatch):
    _set_twilio_env(monkeypatch)
    # Valid signature over a payload missing the required MessageSid field
    # — signature validation passes, but canonical parsing must fail
    # safely (500 handled by the app's existing centralized exception
    # handler), never leaking a stack trace.
    form = {"From": "whatsapp:+919999999999", "To": "whatsapp:+911111111111", "Body": "hi"}
    sig = await compute_twilio_signature(_WEBHOOK_URL, form, _AUTH_TOKEN)
    resp = await client.post("/api/v1/whatsapp/webhook", data=form, headers={"X-Twilio-Signature": sig})

    assert resp.status_code >= 400
    assert "Traceback" not in resp.text
    assert _AUTH_TOKEN not in resp.text
    _clear_settings_cache()


async def test_post_webhook_duplicate_delivery_is_idempotent(client: AsyncClient, db_session, monkeypatch):
    _set_twilio_env(monkeypatch)
    form = {
        "MessageSid": "SM_api_dup_1",
        "From": "whatsapp:+919999999999",
        "To": "whatsapp:+911111111111",
        "Body": "Hi",
    }
    sig = await compute_twilio_signature(_WEBHOOK_URL, form, _AUTH_TOKEN)

    first = await client.post("/api/v1/whatsapp/webhook", data=form, headers={"X-Twilio-Signature": sig})
    second = await client.post("/api/v1/whatsapp/webhook", data=form, headers={"X-Twilio-Signature": sig})

    # Both deliveries get the identical safe TwiML acknowledgment — the
    # duplicate is silently absorbed, never surfaced as an error to Twilio.
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.text == second.text == '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

    from sqlalchemy import func, select

    from app.modules.whatsapp.models.whatsapp_message import WhatsAppMessage

    count = (
        await db_session.execute(
            select(func.count()).where(
                WhatsAppMessage.provider == "twilio", WhatsAppMessage.provider_message_id == "SM_api_dup_1"
            )
        )
    ).scalar_one()
    assert count == 1
    _clear_settings_cache()


async def test_post_webhook_unconfigured_provider_fails_safely(client: AsyncClient, monkeypatch):
    monkeypatch.setenv("WHATSAPP_PROVIDER", "unknown_provider")
    get_settings.cache_clear()

    resp = await client.post("/api/v1/whatsapp/webhook", data={"MessageSid": "x"})
    assert resp.status_code >= 400
    assert "Traceback" not in resp.text
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


async def test_webhook_rate_limit_allows_when_redis_unavailable_and_fail_open(monkeypatch):
    """This test process has no live Redis connection (get_redis() returns
    None — nothing in this suite calls init_redis()). fail_closed=False is
    the documented fail-open behavior for that case: proceed, don't raise
    — matching the webhook service's own choice not to block message
    receipt on a Redis blip."""
    from app.core import rate_limit as rl

    monkeypatch.setattr(rl, "get_redis", lambda: None)
    await rl.check_rate_limit(f"ratelimit:whatsapp_inbound_test:{uuid.uuid4()}", limit=5, window_seconds=60, fail_closed=False)


async def test_webhook_rate_limit_blocks_when_redis_unavailable_and_fail_closed(monkeypatch):
    """Same no-Redis condition, but fail_closed=True — matches this
    codebase's own established convention for testing the limiter without
    a live Redis (see tests/test_security_wave_a.py::
    test_forgot_password_is_rate_limited)."""
    from app.core import rate_limit as rl

    monkeypatch.setattr(rl, "get_redis", lambda: None)
    with pytest.raises(RateLimitExceeded):
        await rl.check_rate_limit(f"ratelimit:whatsapp_inbound_test:{uuid.uuid4()}", limit=5, window_seconds=60, fail_closed=True)


# ---------------------------------------------------------------------------
# Secret-safe logging
# ---------------------------------------------------------------------------


async def test_send_failure_log_never_contains_auth_token(monkeypatch):
    """F-05: providers/twilio/client.py now uses app.core.logging.get_logger
    (structlog), the same mechanism structlog.testing.capture_logs()
    actually intercepts — verified genuinely observes this module's
    logger by test_capture_logs_observes_the_twilio_provider_logger
    below. ``assert len(logs) > 0`` is load-bearing: it fails loudly if
    capture ever silently stops observing this logger again (the exact
    way the original stdlib-logger version of this test went vacuous)."""
    _set_twilio_env(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "internal Twilio error"})

    provider = TwilioWhatsAppProvider(transport=httpx.MockTransport(handler))
    with structlog.testing.capture_logs() as logs:
        sender = WhatsAppSender(provider=provider)
        result = await sender.send_text("+919999999999", "hi")

    assert result.success is False
    assert len(logs) > 0, "capture_logs() observed nothing — this test would be vacuous"
    for entry in logs:
        assert _AUTH_TOKEN not in str(entry)


async def test_capture_logs_observes_the_twilio_provider_logger():
    """Meta-test: proves the assertion in the test above is not vacuous.
    Emits a log line through the exact same logger object
    providers/twilio/client.py uses (no production code touched here —
    this only calls the existing module-level ``logger``) and confirms
    structlog.testing.capture_logs() actually sees it. If the Twilio
    adapter's logger were ever reverted to plain stdlib logging.getLogger
    (the original F-05 defect), this test starts failing because the
    marker below would no longer be captured."""
    marker = "leaked-secret-marker-for-test-only"
    with structlog.testing.capture_logs() as logs:
        twilio_client_module.logger.warning("test_only_probe_event", probe_value=marker)

    assert len(logs) == 1
    assert any(marker in str(entry) for entry in logs), "capture_logs() did not observe the provider's logger"
    _clear_settings_cache()
