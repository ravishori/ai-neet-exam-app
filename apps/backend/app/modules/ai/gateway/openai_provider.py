"""OpenAI Chat Completions via existing httpx (no OpenAI Python SDK)."""

from __future__ import annotations

import httpx

from app.modules.ai.gateway.base import PROVIDER_INVALID_RESPONSE, AIProvider, AIResponse, GenerateRequest, ProviderError
from app.modules.ai.gateway.errors import classify_http_error, map_exception

# Chat Completions models that reject legacy `max_tokens` and require
# `max_completion_tokens` (OpenAI GPT-5 / reasoning families).
_MAX_COMPLETION_TOKEN_PREFIXES = (
    "gpt-5",
    # GPT-5.6 family (Luna, Terra, Sol, …) — same reasoning-family contract:
    # Chat Completions rejects legacy `max_tokens`. If a future 5.6-family
    # model turns out to accept classic max_tokens, drop this prefix.
    "gpt-5.6",
    "o1",
    "o3",
    "o4",
)


def uses_max_completion_tokens(model: str) -> bool:
    """Return True when Chat Completions must use max_completion_tokens."""
    m = (model or "").strip().lower()
    if not m:
        return False
    return any(m == p or m.startswith(f"{p}-") or m.startswith(f"{p}_") for p in _MAX_COMPLETION_TOKEN_PREFIXES)


def build_chat_completions_payload(request: GenerateRequest, *, default_model: str) -> dict:
    """Build Chat Completions JSON body with the correct output-token parameter.

    Internal GenerateRequest.max_tokens remains the façade budget; the HTTP
    field name is selected per model contract.
    """
    model = request.model or default_model
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ],
    }
    if uses_max_completion_tokens(model):
        # Hidden reasoning tokens count against max_completion_tokens. Factory MCQ
        # budgets (~1200) otherwise truncate to empty visible content (finish=length).
        budget = int(request.max_tokens)
        budget = min(max(budget * 2, budget + 1024), 8192)
        payload["max_completion_tokens"] = budget
        # GPT-5 family rejects non-default temperature (only default 1).
        # Omit temperature entirely unless caller explicitly requests 1.
        if request.temperature is not None and float(request.temperature) == 1.0:
            payload["temperature"] = 1.0
    else:
        payload["max_tokens"] = int(request.max_tokens)
        if request.temperature is not None:
            payload["temperature"] = request.temperature

    if request.require_json:
        payload["response_format"] = {"type": "json_object"}
    return payload


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, *, base_url: str = "https://api.openai.com/v1", timeout: float = 60.0):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        return await self.generate_request(
            GenerateRequest(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens, model=self._model)
        )

    async def generate_request(self, request: GenerateRequest) -> AIResponse:
        model = request.model or self._model
        payload = build_chat_completions_payload(request, default_model=self._model)

        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/chat/completions", json=payload, headers=headers)
            if resp.status_code >= 400:
                raise classify_http_error(self.name, resp.status_code, resp.text[:500])
            data = resp.json()
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise map_exception(self.name, exc) from exc

        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(
                PROVIDER_INVALID_RESPONSE,
                f"{self.name} returned no choices",
                provider=self.name,
            )
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        api_model = data.get("model") or model
        # Chat Completions may return a dated snapshot id (e.g. gpt-5-mini-2025-08-07).
        # Keep the configured/request model for pricing + factory lineage; stash API id in metadata.
        return AIResponse(
            text=text,
            model=model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            provider=self.name,
            finish_reason=choices[0].get("finish_reason"),
            provider_request_id=data.get("id"),
            is_fallback=False,
            safe_metadata={"api_model": api_model} if api_model != model else {},
        )
