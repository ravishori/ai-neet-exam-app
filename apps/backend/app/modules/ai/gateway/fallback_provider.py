from app.modules.ai.gateway.base import AIProvider, AIResponse

FALLBACK_NOTICE = (
    "AI Gateway is running in fallback mode — no ANTHROPIC_API_KEY is configured, "
    "so this is a deterministic placeholder, not a real model response. "
    "Set ANTHROPIC_API_KEY in apps/backend/.env to get live answers."
)


class FallbackProvider(AIProvider):
    """No API key configured — every agent still runs end to end, clearly labeled as fake.

    Matches the pattern already used elsewhere in this workspace
    (e.g. NEETExamPrepAPP's ai_service.py graceful degradation).
    """

    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        return AIResponse(
            text=FALLBACK_NOTICE,
            model="fallback",
            prompt_tokens=0,
            completion_tokens=0,
            is_fallback=True,
        )
