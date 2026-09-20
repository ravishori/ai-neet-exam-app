from anthropic import AsyncAnthropic

from app.modules.ai.gateway.base import AIProvider, AIResponse, GenerateRequest
from app.modules.ai.gateway.errors import map_exception


class ClaudeProvider(AIProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        return await self.generate_request(
            GenerateRequest(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens, model=self._model)
        )

    async def generate_request(self, request: GenerateRequest) -> AIResponse:
        model = request.model or self._model
        try:
            kwargs = {
                "model": model,
                "max_tokens": request.max_tokens,
                "system": request.system_prompt,
                "messages": [{"role": "user", "content": request.user_prompt}],
            }
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            response = await self._client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise map_exception(self.name, exc) from exc

        text = "".join(block.text for block in response.content if block.type == "text")
        return AIResponse(
            text=text,
            model=model,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            provider=self.name,
            finish_reason=getattr(response, "stop_reason", None),
            provider_request_id=getattr(response, "id", None),
            is_fallback=False,
        )
