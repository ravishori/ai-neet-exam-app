"""Regression tests for the Gemini API key exposure incident.

Root cause: the key was sent as a `?key=...` URL query parameter. httpx logs
every outbound request at INFO level via the stdlib `logging` module ("HTTP
Request: {method} {url} ...") — a log path that bypasses this app's structlog
redaction pipeline entirely (redact_event_dict only inspects event-dict keys,
never the contents of httpx's own log records). Any secret placed in a URL
is therefore logged in plaintext regardless of how careful application-level
`logger.*` calls are.

Fix has three independent layers, each covered below:
  1. The key moves to the `x-goog-api-key` header — it is structurally never
     part of any URL httpx logs (see test_gemini_provider_response_handling.py
     and test_gemini_batch_credential_redaction below).
  2. httpx's/httpcore's own stdlib loggers are raised to WARNING so routine
     request lines are not emitted at all, regardless of what future code
     puts in a URL.
  3. `sanitize_error_text` scrubs credential-shaped query params / auth
     headers from any raw `str(exc)` before it is logged or persisted,
     covering the generic (non-ProviderError) exception paths in
     ai_gateway.py and router.py that are not normalized by a provider's own
     error handling.
"""

from __future__ import annotations

import json
import logging

import httpx
import pytest
import structlog

from app.core.logging import REDACTED, sanitize_error_text
from app.modules.ai.gateway.base import AIResponse, GenerateRequest
from app.modules.ai.gateway.registry import AVAILABLE, ProviderRegistry, RegisteredProvider
from app.modules.ai.gateway.router import ProviderRouter, RoutingPolicy

_async = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Layer 1 — gemini_batch.py (submit_batch / get_batch_status) no longer puts
# the key in the URL. gemini_provider.py's own coverage lives in
# test_gemini_provider_response_handling.py.
# ---------------------------------------------------------------------------


class _FakeBatchResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class _FakeBatchClient:
    last_request: dict = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _FakeBatchClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, json: dict | None = None, **kwargs: object) -> _FakeBatchResponse:
        _FakeBatchClient.last_request = {"url": url, "headers": kwargs.get("headers") or {}}
        return _FakeBatchResponse(200, {"name": "batches/abc123"})

    async def get(self, url: str, **kwargs: object) -> _FakeBatchResponse:
        _FakeBatchClient.last_request = {"url": url, "headers": kwargs.get("headers") or {}}
        return _FakeBatchResponse(200, {"metadata": {"state": "BATCH_STATE_SUCCEEDED"}, "response": {}})


@_async
async def test_batch_submit_key_never_in_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.ai.gateway import gemini_batch

    monkeypatch.setattr(httpx, "AsyncClient", _FakeBatchClient)
    secret = "AIzaSy-super-secret-batch-key-FAKE"
    _FakeBatchClient.last_request = {}
    await gemini_batch.submit_batch(
        api_key=secret,
        model="gemini-3.6-flash",
        items=[gemini_batch.BatchRequestItem(custom_id="1", system_prompt="s", user_prompt="u")],
        display_name="test",
    )
    assert secret not in _FakeBatchClient.last_request["url"]
    assert "key=" not in _FakeBatchClient.last_request["url"]
    assert _FakeBatchClient.last_request["headers"].get("x-goog-api-key") == secret


@_async
async def test_batch_poll_key_never_in_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.ai.gateway import gemini_batch

    monkeypatch.setattr(httpx, "AsyncClient", _FakeBatchClient)
    secret = "AIzaSy-super-secret-batch-key-FAKE"
    _FakeBatchClient.last_request = {}
    await gemini_batch.get_batch_status(api_key=secret, batch_name="batches/abc123")
    assert secret not in _FakeBatchClient.last_request["url"]
    assert "key=" not in _FakeBatchClient.last_request["url"]
    assert _FakeBatchClient.last_request["headers"].get("x-goog-api-key") == secret


# ---------------------------------------------------------------------------
# Layer 2 — httpx/httpcore stdlib loggers are silenced to WARNING by
# configure_logging(), so routine request lines never reach the root handler.
# ---------------------------------------------------------------------------


def test_configure_logging_silences_httpx_request_logging() -> None:
    """configure_logging() mutates *global* structlog/stdlib logging state
    (structlog.configure(..., cache_logger_on_first_use=True) has no scoping
    mechanism). Calling it for real from a test and not restoring the prior
    config leaks into every test collected afterwards in the same session —
    this previously broke structlog.testing.capture_logs() assertions in
    unrelated files (test_email_provider.py, test_forgot_reset_password.py)
    whenever they ran after this one. Snapshot and restore everything
    configure_logging() touches so this test's own side effects don't
    outlive it."""
    from app.core.logging import configure_logging

    prior_structlog_config = structlog.get_config()
    prior_httpx_level = logging.getLogger("httpx").level
    prior_httpcore_level = logging.getLogger("httpcore").level
    try:
        configure_logging("production")
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
    finally:
        structlog.configure(**prior_structlog_config)
        logging.getLogger("httpx").setLevel(prior_httpx_level)
        logging.getLogger("httpcore").setLevel(prior_httpcore_level)


# ---------------------------------------------------------------------------
# Layer 3 — sanitize_error_text scrubs credential-shaped text.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,secret",
    [
        ("Client error for url 'https://x.test/v1?key=AIzaSy12345secret'", "AIzaSy12345secret"),
        ("request to .../batchGenerateContent?key=super-secret-value failed", "super-secret-value"),
        ("auth header: Authorization: Bearer sk-live-abcdef123456", "sk-live-abcdef123456"),
        ("...&access_token=ya29.a0ARsecretvalue&foo=bar", "ya29.a0ARsecretvalue"),
    ],
)
def test_sanitize_error_text_redacts_credentials(raw: str, secret: str) -> None:
    cleaned = sanitize_error_text(raw)
    assert secret not in cleaned
    assert REDACTED in cleaned


@pytest.mark.parametrize(
    "raw,secret",
    [
        # Case variants
        ("x-goog-api-key: AIzaSyFAKE123", "AIzaSyFAKE123"),
        ("X-GOOG-API-KEY: AIzaSyFAKE123", "AIzaSyFAKE123"),
        ("X-Goog-Api-Key: AIzaSyFAKE123", "AIzaSyFAKE123"),
        # Delimiter variants: colon vs equals
        ("x-goog-api-key=AIzaSyFAKE123", "AIzaSyFAKE123"),
        ("x-goog-api-key:AIzaSyFAKE123", "AIzaSyFAKE123"),
        # Whitespace variants around the delimiter
        ("x-goog-api-key  :   AIzaSyFAKE123", "AIzaSyFAKE123"),
        ("x-goog-api-key : AIzaSyFAKE123", "AIzaSyFAKE123"),
        # dict/repr-style quoted header name AND quoted value (e.g. a
        # stringified httpx.Headers / request-headers dict)
        ("headers={'x-goog-api-key': 'AIzaSyFAKE123', 'content-type': 'json'}", "AIzaSyFAKE123"),
        ('headers={"x-goog-api-key": "AIzaSyFAKE123"}', "AIzaSyFAKE123"),
        # Multiline exception text
        ("Request failed:\nheaders:\n  x-goog-api-key: AIzaSyFAKE123\nstatus: 500", "AIzaSyFAKE123"),
    ],
)
def test_sanitize_error_text_redacts_goog_api_key_header(raw: str, secret: str) -> None:
    cleaned = sanitize_error_text(raw)
    assert secret not in cleaned
    assert REDACTED in cleaned


def test_sanitize_error_text_goog_api_key_preserves_surrounding_text() -> None:
    """Redaction must not swallow unrelated trailing/surrounding diagnostic
    content — only the credential value itself is replaced."""
    cleaned = sanitize_error_text("x-goog-api-key=AIzaSyFAKE123,model=gemini-3.6-flash,status=500")
    assert "AIzaSyFAKE123" not in cleaned
    assert "model=gemini-3.6-flash" in cleaned
    assert "status=500" in cleaned

    cleaned2 = sanitize_error_text(
        "headers={'x-goog-api-key': 'AIzaSyFAKE123', 'content-type': 'json'}"
    )
    assert "AIzaSyFAKE123" not in cleaned2
    assert "content-type" in cleaned2
    assert "json" in cleaned2


def test_sanitize_error_text_preserves_non_sensitive_text() -> None:
    cleaned = sanitize_error_text("Gemini returned no candidates (finishReason=SAFETY)")
    assert cleaned == "Gemini returned no candidates (finishReason=SAFETY)"


def test_sanitize_error_text_handles_none_and_truncates() -> None:
    assert sanitize_error_text(None) is None
    assert len(sanitize_error_text("x" * 1000, limit=50)) == 50


# ---------------------------------------------------------------------------
# Layer 3, end-to-end — a raw (non-ProviderError) exception thrown by a
# provider's generate_request propagates through ProviderRouter.execute()
# and must not leak a credential-shaped string into ProviderAttempt /
# AIRequestLog.error_message.
# ---------------------------------------------------------------------------


class _LeakyProvider:
    name = "gemini"

    async def generate_request(self, request: GenerateRequest) -> AIResponse:
        # Simulates an unwrapped httpx exception whose str() embeds the
        # full request URL, as httpx.HTTPStatusError/RequestError do.
        raise RuntimeError(
            "Server error '500' for url "
            "'https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key=AIzaSyLEAKEDSECRET'"
        )


@_async
async def test_router_sanitizes_unwrapped_exception_before_storing(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ProviderRegistry()
    registry.register(
        RegisteredProvider(
            name="gemini",
            enabled=True,
            configured=True,
            model="gemini-3.6-flash",
            instance=_LeakyProvider(),
            status=AVAILABLE,
        )
    )
    policy = RoutingPolicy(mode="fixed", primary="gemini")
    router = ProviderRouter(registry, policy)
    result = await router.execute(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert result.response is None
    assert len(result.attempts) == 1
    stored_message = result.attempts[0].error_message
    assert "AIzaSyLEAKEDSECRET" not in stored_message
    assert REDACTED in stored_message
    assert result.error is not None
    assert "AIzaSyLEAKEDSECRET" not in str(result.error)
