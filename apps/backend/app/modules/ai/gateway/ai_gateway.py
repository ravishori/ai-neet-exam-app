import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.ai.gateway.base import AIProvider, AIResponse
from app.modules.ai.gateway.claude_provider import ClaudeProvider
from app.modules.ai.gateway.fallback_provider import FallbackProvider
from app.modules.ai.models import AIRequestLog

logger = get_logger("ai_gateway")
settings = get_settings()

# Approximate Claude Sonnet-class pricing (USD per token) — good enough for
# the cost *observability* ADR-0004 asks for, not billing-grade accuracy.
_PRICE_PER_INPUT_TOKEN = 3.0 / 1_000_000
_PRICE_PER_OUTPUT_TOKEN = 15.0 / 1_000_000


def _build_provider() -> AIProvider:
    if settings.anthropic_api_key:
        return ClaudeProvider(api_key=settings.anthropic_api_key, model=settings.ai_default_model)
    return FallbackProvider()


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return prompt_tokens * _PRICE_PER_INPUT_TOKEN + completion_tokens * _PRICE_PER_OUTPUT_TOKEN


class AIGateway:
    """The only way any agent talks to a model — logs cost/latency for every call."""

    def __init__(self, session: AsyncSession, provider: AIProvider | None = None):
        self.session = session
        self._provider = provider or _build_provider()

    async def generate(
        self,
        *,
        agent_type: str,
        system_prompt: str,
        user_prompt: str,
        user_id: uuid.UUID | None = None,
        max_tokens: int = 1024,
    ) -> AIResponse:
        started = time.perf_counter()
        try:
            response = await self._provider.generate(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens)
            success = True
            error_message = None
        except Exception as exc:  # noqa: BLE001 — logged below, always re-raised
            latency_ms = int((time.perf_counter() - started) * 1000)
            await self._log(agent_type, user_id, "error", 0, 0, 0.0, latency_ms, is_fallback=False, success=False, error_message=str(exc))
            logger.error("ai_request_failed", agent_type=agent_type, error=str(exc))
            raise

        latency_ms = int((time.perf_counter() - started) * 1000)
        response.cost_usd = _estimate_cost(response.prompt_tokens, response.completion_tokens)
        await self._log(
            agent_type,
            user_id,
            response.model,
            response.prompt_tokens,
            response.completion_tokens,
            response.cost_usd,
            latency_ms,
            is_fallback=response.is_fallback,
            success=success,
            error_message=error_message,
        )
        return response

    async def _log(
        self,
        agent_type: str,
        user_id: uuid.UUID | None,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        latency_ms: int,
        *,
        is_fallback: bool,
        success: bool,
        error_message: str | None,
    ) -> None:
        self.session.add(
            AIRequestLog(
                agent_type=agent_type,
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost_usd=cost,
                latency_ms=latency_ms,
                is_fallback=is_fallback,
                success=success,
                error_message=error_message,
            )
        )
        await self.session.commit()
        logger.info(
            "ai_request",
            agent_type=agent_type,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost, 6),
            latency_ms=latency_ms,
            is_fallback=is_fallback,
        )
