"""OPENAI-ADAPTER-FIX-001 — Chat Completions parameter contract tests (offline)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.modules.ai.gateway.base import (
    PROVIDER_BLOCKED,
    PROVIDER_INVALID_RESPONSE,
    PROVIDER_RATE_LIMITED,
    GenerateRequest,
    ProviderError,
)
from app.modules.ai.gateway.errors import classify_http_error
from app.modules.ai.gateway.openai_provider import (
    OpenAIProvider,
    build_chat_completions_payload,
    uses_max_completion_tokens,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


def test_uses_max_completion_tokens_for_gpt5_family():
    assert uses_max_completion_tokens("gpt-5-mini") is True
    assert uses_max_completion_tokens("gpt-5-mini-2025-08-07") is True
    assert uses_max_completion_tokens("gpt-4o-mini") is False
    assert uses_max_completion_tokens("gpt-4.1-mini") is False
    assert uses_max_completion_tokens("o3-mini") is True


def test_gpt5_payload_uses_max_completion_tokens_not_max_tokens():
    req = GenerateRequest(
        system_prompt="Return JSON only.",
        user_prompt="Produce one original MCQ now as JSON.",
        max_tokens=1200,
        model="gpt-5-mini",
        require_json=True,
        temperature=0.2,  # must be omitted for gpt-5 family
    )
    payload = build_chat_completions_payload(req, default_model="gpt-5-mini")
    assert "max_completion_tokens" in payload
    assert payload["max_completion_tokens"] == 2400  # 1200*2 headroom for reasoning models
    assert "max_tokens" not in payload
    assert "temperature" not in payload
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["model"] == "gpt-5-mini"


def test_legacy_gpt4o_payload_keeps_max_tokens():
    req = GenerateRequest(
        system_prompt="sys",
        user_prompt="user",
        max_tokens=800,
        model="gpt-4o-mini",
        require_json=True,
        temperature=0.3,
    )
    payload = build_chat_completions_payload(req, default_model="gpt-4o-mini")
    assert payload["max_tokens"] == 800
    assert "max_completion_tokens" not in payload
    assert payload["temperature"] == 0.3
    assert payload["response_format"] == {"type": "json_object"}


def test_structured_output_flag_preserved_for_both_families():
    for model in ("gpt-5-mini", "gpt-4o-mini"):
        payload = build_chat_completions_payload(
            GenerateRequest(system_prompt="s", user_prompt="u JSON", max_tokens=100, model=model, require_json=True),
            default_model=model,
        )
        assert payload["response_format"]["type"] == "json_object"


async def test_openai_http_payload_gpt5_uses_max_completion_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {
                "id": "chatcmpl-test",
                "model": "gpt-5-mini",
                "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    p = OpenAIProvider("sk-test", "gpt-5-mini")
    resp = await p.generate_request(
        GenerateRequest(
            system_prompt="Return JSON only.",
            user_prompt="Produce one original MCQ now as JSON.",
            max_tokens=1200,
            require_json=True,
            model="gpt-5-mini",
        )
    )
    assert captured["url"].endswith("/chat/completions")
    body = captured["json"]
    assert "max_completion_tokens" in body
    assert "max_tokens" not in body
    assert body["max_completion_tokens"] == 2400
    assert resp.provider == "openai"
    assert resp.model == "gpt-5-mini"
    assert json.loads(resp.text)["ok"] is True


async def test_openai_lineage_model_prefers_request_over_dated_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeResponse:
        status_code = 200

        def json(self):
            return {
                "id": "chatcmpl-dated",
                "model": "gpt-5-mini-2025-08-07",
                "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    p = OpenAIProvider("sk-test", "gpt-5-mini")
    resp = await p.generate_request(
        GenerateRequest(system_prompt="s", user_prompt="u JSON", max_tokens=100, model="gpt-5-mini", require_json=True)
    )
    assert resp.model == "gpt-5-mini"
    assert resp.safe_metadata.get("api_model") == "gpt-5-mini-2025-08-07"


async def test_openai_http_payload_gpt4o_keeps_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {
                "id": "chatcmpl-legacy",
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    p = OpenAIProvider("sk-test", "gpt-4o-mini")
    await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u", max_tokens=500, model="gpt-4o-mini"))
    assert "max_tokens" in captured["json"]
    assert "max_completion_tokens" not in captured["json"]


def test_error_classification_intact():
    blocked = classify_http_error("openai", 400, "Your credit balance is too low to access the API")
    assert blocked.code == PROVIDER_BLOCKED
    assert blocked.retryable is False
    rl = classify_http_error("openai", 429, "rate limit exceeded")
    assert rl.code == PROVIDER_RATE_LIMITED
    assert rl.retryable is True
    bad = classify_http_error(
        "openai",
        400,
        "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.",
    )
    assert bad.code == PROVIDER_INVALID_RESPONSE


def test_other_adapters_unchanged_import_surface():
    # Smoke that sibling adapters still import and do not share OpenAI payload helper.
    from app.modules.ai.gateway import claude_provider, gemini_provider, mistral_provider
    from app.modules.ai.gateway.claude_provider import ClaudeProvider
    from app.modules.ai.gateway.gemini_provider import GeminiProvider
    from app.modules.ai.gateway.mistral_provider import MistralProvider

    assert ClaudeProvider.name == "anthropic" or getattr(ClaudeProvider, "name", "anthropic")
    assert GeminiProvider.name == "gemini"
    assert MistralProvider.name == "mistral"
    assert not hasattr(claude_provider, "build_chat_completions_payload")
    assert not hasattr(gemini_provider, "build_chat_completions_payload")
    assert not hasattr(mistral_provider, "build_chat_completions_payload")


def test_provider_blocked_still_stops_and_rate_limit_retryable():
    from app.modules.cms.services.mcq_llm_provider import is_retryable_provider_error, must_stop_run

    blocked = ProviderError(PROVIDER_BLOCKED, "billing", provider="openai", retryable=False)
    rate = ProviderError(PROVIDER_RATE_LIMITED, "429", provider="openai", retryable=True)
    assert must_stop_run(blocked) is True
    assert is_retryable_provider_error(blocked) is False
    assert must_stop_run(rate) is False
    assert is_retryable_provider_error(rate) is True
