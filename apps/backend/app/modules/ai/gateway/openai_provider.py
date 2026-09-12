"""OpenAI Chat Completions via existing httpx."""

from __future__ import annotations

import httpx

from app.modules.ai.gateway.base import PROVIDER_INVALID_RESPONSE, AIProvider, AIResponse, GenerateRequest, ProviderError
from app.modules.ai.gateway.errors import classify_http_error, map_exception


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
        payload: dict = {
            "model": model,
            "max_tokens": request.max_tokens,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.require_json:
            payload["response_format"] = {"type": "json_object"}

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
            raise ProviderError(PROVIDER_INVALID_RESPONSE, "OpenAI returned no choices", provider=self.name)
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        return AIResponse(
            text=text,
            model=data.get("model") or model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            provider=self.name,
            finish_reason=choices[0].get("finish_reason"),
            provider_request_id=data.get("id"),
            is_fallback=False,
        )
