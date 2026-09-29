"""AI Gateway — single entrypoint; multi-provider routing is explicit only."""

from __future__ import annotations

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.ai.gateway.base import AIProvider, AIResponse, GenerateRequest, ProviderError
from app.modules.ai.gateway.fallback_provider import FallbackProvider
from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.ai.gateway.registry import ProviderRegistry, build_registry_from_settings, resolve_default_provider
from app.modules.ai.gateway.router import ProviderRouter, RoutingPolicy, parse_routing_policy
from app.modules.ai.models import AIRequestLog

logger = get_logger("ai_gateway")


class AIGateway:
    """The only way any agent talks to a model — logs cost/latency for every call.

    Inject ``provider`` for tests / factory mocks (bypasses router).
    Otherwise uses ProviderRegistry + explicit RoutingPolicy from settings.
    """

    def __init__(
        self,
        session: AsyncSession,
        provider: AIProvider | None = None,
        *,
        registry: ProviderRegistry | None = None,
        routing_policy: RoutingPolicy | None = None,
    ):
        self.session = session
        settings = get_settings()
        self._injected = provider
        self._registry = registry if registry is not None else build_registry_from_settings(settings)
        if routing_policy is not None:
            self._policy = routing_policy
        else:
            try:
                self._policy = parse_routing_policy(
                    mode=settings.factory_provider_mode,
                    provider=settings.factory_provider or settings.ai_provider_default,
                    model=None,
                    fallback_chain=settings.factory_provider_fallback_chain,
                )
            except ValueError:
                self._policy = parse_routing_policy(
                    mode="fixed",
                    provider=settings.ai_provider_default or "anthropic",
                )
        # Legacy single-provider path when injected or when callers expect one adapter
        self._provider = provider or resolve_default_provider(self._registry, settings)

    @property
    def registry(self) -> ProviderRegistry:
        return self._registry

    @property
    def routing_policy(self) -> RoutingPolicy:
        return self._policy

    def provider_health(self) -> list[dict]:
        return [
            {
                "provider": h.provider,
                "enabled": h.enabled,
                "configured": h.configured,
                "status": h.status,
                "model": h.model,
                "detail": h.detail,
            }
            for h in self._registry.health()
        ]

    async def generate(
        self,
        *,
        agent_type: str,
        system_prompt: str,
        user_prompt: str,
        user_id: uuid.UUID | None = None,
        max_tokens: int = 1024,
        model: str | None = None,
        temperature: float | None = None,
        correlation_id: str | None = None,
        generation_run_id: str | None = None,
        blueprint_id: str | None = None,
        blueprint_version: int | None = None,
        prompt_version: str | None = None,
        require_json: bool = False,
        use_router: bool = True,
    ) -> AIResponse:
        request = GenerateRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            model=model,
            temperature=temperature,
            correlation_id=correlation_id,
            generation_run_id=generation_run_id,
            blueprint_id=blueprint_id,
            blueprint_version=blueprint_version,
            prompt_version=prompt_version,
            require_json=require_json,
        )
        started = time.perf_counter()
        try:
            if self._injected is not None or not use_router:
                response = await self._provider.generate_request(request)
                latency_ms = int((time.perf_counter() - started) * 1000)
                provider_name = getattr(self._provider, "name", response.provider or "unknown")
                cost = estimate_cost(provider_name, response.model, response.prompt_tokens, response.completion_tokens)
                if response.is_fallback:
                    response.cost_status = "UNAVAILABLE"
                    response.cost_usd = 0.0
                elif cost.cost_status == "ESTIMATED":
                    response.cost_usd = cost.cost_usd
                    response.cost_status = "ESTIMATED"
                elif self._injected is not None:
                    # Test/injected adapters may use fake model ids — do not fail-closed
                    response.cost_status = "ESTIMATED"
                    response.cost_usd = float(response.cost_usd or 0.0)
                else:
                    response.cost_usd = 0.0
                    response.cost_status = "UNAVAILABLE"
                response.provider = provider_name
                response.total_tokens = cost.total_tokens
                response.latency_ms = latency_ms
                response.routing_policy = response.routing_policy or "injected"
                response.provider_attempt_no = response.provider_attempt_no or 1
                attempts_meta = [{"attempt_no": 1, "provider": provider_name, "status": "SUCCESS"}]
            elif not self._registry.list_available():
                # Legacy: no live providers → FallbackProvider stub (not multi-provider routing)
                response = await FallbackProvider().generate_request(request)
                latency_ms = int((time.perf_counter() - started) * 1000)
                response.latency_ms = latency_ms
                response.routing_policy = "legacy_fallback_stub"
                attempts_meta = [{"attempt_no": 1, "provider": "fallback", "status": "SUCCESS"}]
            else:
                router = ProviderRouter(self._registry, self._policy)
                result = await router.execute(request)
                latency_ms = int((time.perf_counter() - started) * 1000)
                if result.response is None:
                    err = result.error or ProviderError("PROVIDER_BLOCKED", "Provider blocked")
                    await self._log(
                        agent_type,
                        user_id,
                        "error",
                        0,
                        0,
                        0.0,
                        latency_ms,
                        is_fallback=False,
                        success=False,
                        error_message=f"{err.code}: {err}",
                        provider=getattr(err, "provider", None),
                    )
                    # Attach attempts for callers that inspect exception args
                    err.attempts = [a.to_dict() for a in result.attempts]  # type: ignore[attr-defined]
                    err.routing_policy = result.routing_policy  # type: ignore[attr-defined]
                    raise err
                response = result.response
                attempts_meta = [a.to_dict() for a in result.attempts]

            await self._log(
                agent_type,
                user_id,
                response.model,
                response.prompt_tokens,
                response.completion_tokens,
                response.cost_usd,
                response.latency_ms or latency_ms,
                is_fallback=response.is_fallback,
                success=True,
                error_message=None,
                provider=response.provider,
            )
            response.safe_metadata = {
                **(response.safe_metadata or {}),
                "provider_attempts": attempts_meta,
                "routing_policy": response.routing_policy,
            }
            return response
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - started) * 1000)
            await self._log(
                agent_type,
                user_id,
                "error",
                0,
                0,
                0.0,
                latency_ms,
                is_fallback=False,
                success=False,
                error_message=str(exc)[:500],
            )
            logger.error("ai_request_failed", agent_type=agent_type, error=str(exc)[:200])
            raise

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
        provider: str | None = None,
    ) -> None:
        # Never log API keys. Provider name is safe metadata.
        self.session.add(
            AIRequestLog(
                agent_type=agent_type,
                user_id=user_id,
                model=(model or "unknown")[:50],
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost_usd=cost,
                latency_ms=latency_ms,
                is_fallback=is_fallback,
                success=success,
                error_message=error_message,
            )
        )
        # Batch ECAEP / importers set session.info["defer_commit"]=True so AI
        # usage logs flush into the caller's open transaction instead of
        # committing early and breaking atomic rollback.
        if self.session.info.get("defer_commit"):
            await self.session.flush()
        else:
            await self.session.commit()
        logger.info(
            "ai_request",
            agent_type=agent_type,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(float(cost or 0), 6),
            latency_ms=latency_ms,
            is_fallback=is_fallback,
            success=success,
        )
