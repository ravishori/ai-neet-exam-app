"""Legacy stub when no live provider is configured.

FACTORY-P3.1: FallbackProvider is NOT the multi-provider router.
Content Factory pilot continues to reject is_fallback=True outputs.
"""

from app.modules.ai.gateway.base import AIProvider, AIResponse


class FallbackProvider(AIProvider):
    name = "fallback"

    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        return AIResponse(
            text=(
                "[Fallback mode — no live AI provider configured] "
                "Set a provider API key and enable the provider to generate content."
            ),
            model="fallback",
            prompt_tokens=0,
            completion_tokens=0,
            is_fallback=True,
            provider="fallback",
            cost_status="UNAVAILABLE",
        )
