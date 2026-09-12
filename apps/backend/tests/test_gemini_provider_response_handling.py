"""Gemini provider response-handling hardening — mocked HTTP only (no live API)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.modules.ai.gateway.base import PROVIDER_INVALID_RESPONSE, GenerateRequest, ProviderError
from app.modules.ai.gateway.gemini_provider import GeminiProvider
from app.modules.cms.services.factory_candidate_validation import parse_mcq_json

pytestmark = pytest.mark.asyncio(loop_scope="session")

_VALID_MCQ = {
    "stem": "What is Ohm's law?",
    "options": [
        {"label": "A", "text": "V = IR"},
        {"label": "B", "text": "F = ma"},
        {"label": "C", "text": "E = mc^2"},
        {"label": "D", "text": "P = IV only"},
    ],
    "correct_option": "A",
    "explanation": "Ohm's law states that voltage equals current times resistance for ohmic conductors.",
    "difficulty": "medium",
}


def _gemini_body(
    *,
    text: str | None = None,
    parts: list[dict[str, Any]] | None = None,
    finish_reason: str | None = "STOP",
    candidates: list | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    thoughts_tokens: int | None = 5,
) -> dict[str, Any]:
    if candidates is not None:
        body: dict[str, Any] = {"candidates": candidates}
    elif parts is not None:
        body = {
            "candidates": [
                {
                    "finishReason": finish_reason,
                    "content": {"parts": parts},
                }
            ]
        }
    else:
        body = {
            "candidates": [
                {
                    "finishReason": finish_reason,
                    "content": {"parts": [{"text": text if text is not None else json.dumps(_VALID_MCQ)}]},
                }
            ]
        }
    body["usageMetadata"] = {
        "promptTokenCount": prompt_tokens,
        "candidatesTokenCount": completion_tokens,
    }
    if thoughts_tokens is not None:
        body["usageMetadata"]["thoughtsTokenCount"] = thoughts_tokens
    return body


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient — captures POST JSON body."""

    last_request: dict[str, Any] = {}

    def __init__(self, response: _FakeResponse, *, timeout: float | None = None):
        self._response = response
        self.timeout = timeout

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, json: dict | None = None, **kwargs: object) -> _FakeResponse:
        _FakeAsyncClient.last_request = {"url": url, "json": json or {}}
        return self._response


def _patch_httpx(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any], status: int = 200) -> None:
    response = _FakeResponse(status, payload)

    def _factory(*args: object, **kwargs: object) -> _FakeAsyncClient:
        return _FakeAsyncClient(response, timeout=kwargs.get("timeout"))  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


async def test_valid_gemini_json_stop_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(monkeypatch, _gemini_body(finish_reason="STOP", thoughts_tokens=12))
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    resp = await p.generate_request(
        GenerateRequest(system_prompt="sys", user_prompt="user", max_tokens=1200, require_json=True, model="gemini-3.6-flash")
    )
    assert resp.provider == "gemini"
    assert resp.model == "gemini-3.6-flash"
    assert resp.finish_reason == "STOP"
    assert resp.text
    parsed = parse_mcq_json(resp.text)
    assert parsed["correct_option"] == "A"
    assert resp.safe_metadata.get("finish_reason") == "STOP"
    assert resp.safe_metadata.get("response_char_count") == len(resp.text)
    assert resp.safe_metadata.get("thoughts_token_count") == 12
    # Never assert or echo API keys
    assert "test-key" not in json.dumps(resp.safe_metadata)


async def test_multipart_text_concatenated(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = json.dumps(_VALID_MCQ)
    mid = len(raw) // 2
    _patch_httpx(
        monkeypatch,
        _gemini_body(
            parts=[{"text": raw[:mid]}, {"text": raw[mid:]}],
            finish_reason="STOP",
        ),
    )
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    resp = await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u", max_tokens=1200))
    assert resp.text == raw
    assert parse_mcq_json(resp.text)["stem"]


async def test_max_tokens_incomplete_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(
        monkeypatch,
        _gemini_body(text='{"stem": "truncated', finish_reason="MAX_TOKENS", completion_tokens=48),
    )
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    with pytest.raises(ProviderError) as ei:
        await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u", max_tokens=1200))
    assert ei.value.code == PROVIDER_INVALID_RESPONSE
    assert ei.value.provider == "gemini"
    assert ei.value.retryable is True
    assert "MAX_TOKENS" in str(ei.value)


async def test_safety_finish_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(
        monkeypatch,
        {
            "candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 0},
        },
    )
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    with pytest.raises(ProviderError) as ei:
        await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert ei.value.code == PROVIDER_INVALID_RESPONSE
    assert "SAFETY" in str(ei.value)
    assert ei.value.retryable is False


async def test_safety_with_partial_text_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(monkeypatch, _gemini_body(text='{"stem":"x"}', finish_reason="SAFETY"))
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    with pytest.raises(ProviderError) as ei:
        await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert ei.value.code == PROVIDER_INVALID_RESPONSE
    assert "SAFETY" in str(ei.value)


async def test_empty_candidates_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(monkeypatch, {"candidates": [], "usageMetadata": {}})
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    with pytest.raises(ProviderError) as ei:
        await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert ei.value.code == PROVIDER_INVALID_RESPONSE


async def test_empty_parts_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(
        monkeypatch,
        {
            "candidates": [{"finishReason": "STOP", "content": {"parts": []}}],
            "usageMetadata": {},
        },
    )
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    with pytest.raises(ProviderError) as ei:
        await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert ei.value.code == PROVIDER_INVALID_RESPONSE


async def test_missing_content_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(
        monkeypatch,
        {"candidates": [{"finishReason": "STOP"}], "usageMetadata": {}},
    )
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    with pytest.raises(ProviderError) as ei:
        await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert ei.value.code == PROVIDER_INVALID_RESPONSE


async def test_recitation_and_other_finish_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    for reason in ("RECITATION", "OTHER"):
        _patch_httpx(monkeypatch, _gemini_body(text='{"a":1}', finish_reason=reason))
        with pytest.raises(ProviderError) as ei:
            await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u"))
        assert ei.value.code == PROVIDER_INVALID_RESPONSE
        assert reason in str(ei.value)


async def test_truncated_json_factory_parser_rejects() -> None:
    """STOP-path truncated JSON still fails factory parse (adapter may pass text through)."""
    with pytest.raises(json.JSONDecodeError):
        parse_mcq_json('{"stem": "unterminated')


async def test_require_json_sets_response_mime_type(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeAsyncClient.last_request = {}
    _patch_httpx(monkeypatch, _gemini_body(finish_reason="STOP"))
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    await p.generate_request(
        GenerateRequest(system_prompt="sys", user_prompt="user", max_tokens=1200, require_json=True)
    )
    gen = _FakeAsyncClient.last_request["json"]["generationConfig"]
    assert gen["responseMimeType"] == "application/json"
    assert gen["maxOutputTokens"] == 1200
    assert gen["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}


async def test_max_tokens_1200_mapped(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeAsyncClient.last_request = {}
    _patch_httpx(monkeypatch, _gemini_body(finish_reason="STOP"))
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u", max_tokens=1200))
    gen = _FakeAsyncClient.last_request["json"]["generationConfig"]
    assert gen["maxOutputTokens"] == 1200
    assert "responseMimeType" not in gen
    assert gen["thinkingConfig"]["thinkingLevel"] == "MINIMAL"


async def test_thinking_config_minimal_always_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """TEST A — Content Factory JSON path requests lowest supported thinking level."""
    _FakeAsyncClient.last_request = {}
    _patch_httpx(monkeypatch, _gemini_body(finish_reason="STOP"))
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    await p.generate_request(
        GenerateRequest(
            system_prompt="sys",
            user_prompt="user",
            max_tokens=1200,
            require_json=True,
            model="gemini-3.6-flash",
        )
    )
    body = _FakeAsyncClient.last_request["json"]
    gen = body["generationConfig"]
    assert gen["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
    assert gen["maxOutputTokens"] == 1200
    assert gen["responseMimeType"] == "application/json"
    assert body["systemInstruction"]["parts"][0]["text"] == "sys"
    assert body["contents"][0]["parts"][0]["text"] == "user"
    assert "gemini-3.6-flash" in _FakeAsyncClient.last_request["url"]
    # Sanitized: never assert secret values beyond placeholder absence in metadata paths
    assert "AIza" not in json.dumps(body)


async def test_system_instruction_and_contents_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeAsyncClient.last_request = {}
    _patch_httpx(monkeypatch, _gemini_body(finish_reason="STOP"))
    p = GeminiProvider(api_key="test-key", model="gemini-3.6-flash")
    await p.generate_request(
        GenerateRequest(system_prompt="SYSTEM_RULES", user_prompt="USER_PROMPT", max_tokens=1200, require_json=True)
    )
    body = _FakeAsyncClient.last_request["json"]
    assert body["systemInstruction"]["parts"][0]["text"] == "SYSTEM_RULES"
    assert body["contents"][0]["parts"][0]["text"] == "USER_PROMPT"
    assert body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "MINIMAL"
    # URL contains query key placeholder from constructor — ensure we do not print it in asserts
    assert "models/gemini-3.6-flash:generateContent" in _FakeAsyncClient.last_request["url"]
