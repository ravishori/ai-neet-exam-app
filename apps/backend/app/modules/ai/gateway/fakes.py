"""Offline fake providers for contract tests — no network."""

from __future__ import annotations

from app.modules.ai.gateway.base import (
    PROVIDER_AUTH_FAILED,
    PROVIDER_INVALID_RESPONSE,
    PROVIDER_RATE_LIMITED,
    PROVIDER_TIMEOUT,
    PROVIDER_UNAVAILABLE,
    AIProvider,
    AIResponse,
    GenerateRequest,
    ProviderError,
)


class _ScriptedFake(AIProvider):
    def __init__(self, name: str, model: str, *, behavior: str = "success"):
        self.name = name
        self._model = model
        self.behavior = behavior
        self.calls = 0

    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        return await self.generate_request(
            GenerateRequest(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens, model=self._model)
        )

    async def generate_request(self, request: GenerateRequest) -> AIResponse:
        self.calls += 1
        if self.behavior == "auth":
            raise ProviderError(PROVIDER_AUTH_FAILED, "auth failed", provider=self.name)
        if self.behavior == "rate_limit":
            raise ProviderError(PROVIDER_RATE_LIMITED, "rate limited", provider=self.name, retryable=True)
        if self.behavior == "timeout":
            raise ProviderError(PROVIDER_TIMEOUT, "timeout", provider=self.name, retryable=True)
        if self.behavior == "unavailable":
            raise ProviderError(PROVIDER_UNAVAILABLE, "unavailable", provider=self.name, retryable=True)
        if self.behavior == "malformed":
            raise ProviderError(PROVIDER_INVALID_RESPONSE, "malformed", provider=self.name)
        model = request.model or self._model
        return AIResponse(
            text='{"stem":"ok","options":[{"label":"A","text":"a"},{"label":"B","text":"b"},{"label":"C","text":"c"},{"label":"D","text":"d"}],"correct_option":"A","explanation":"because","difficulty":"medium"}',
            model=model,
            prompt_tokens=11,
            completion_tokens=22,
            provider=self.name,
            provider_request_id=f"{self.name}-req-1",
            finish_reason="stop",
            is_fallback=False,
        )


class FakeAnthropicProvider(_ScriptedFake):
    def __init__(self, *, behavior: str = "success", model: str = "claude-sonnet-4-6"):
        super().__init__("anthropic", model, behavior=behavior)


class FakeOpenAIProvider(_ScriptedFake):
    def __init__(self, *, behavior: str = "success", model: str = "gpt-4o-mini"):
        super().__init__("openai", model, behavior=behavior)


class FakeGeminiProvider(_ScriptedFake):
    def __init__(self, *, behavior: str = "success", model: str = "gemini-2.0-flash"):
        super().__init__("gemini", model, behavior=behavior)


class FakeMistralProvider(_ScriptedFake):
    def __init__(self, *, behavior: str = "success", model: str = "mistral-small-latest"):
        super().__init__("mistral", model, behavior=behavior)


class FakeSarvamProvider(_ScriptedFake):
    def __init__(self, *, behavior: str = "success", model: str = "sarvam-105b"):
        super().__init__("sarvam", model, behavior=behavior)
