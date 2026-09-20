"""Explicit provider routing — never silent cross-provider fallback."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.modules.ai.gateway.base import (
    PROVIDER_BLOCKED,
    PROVIDER_ERROR,
    AIResponse,
    GenerateRequest,
    ProviderError,
)
from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.ai.gateway.registry import ProviderRegistry


MODE_FIXED = "fixed"
MODE_FIXED_MODEL = "fixed_model"
MODE_FALLBACK_CHAIN = "fallback_chain"

VALID_MODES = {MODE_FIXED, MODE_FIXED_MODEL, MODE_FALLBACK_CHAIN}


@dataclass
class ProviderAttempt:
    attempt_no: int
    provider: str
    model: str | None
    status: str  # SUCCESS | code
    latency_ms: int = 0
    error_code: str | None = None
    error_message: str | None = None
    provider_request_id: str | None = None
    cost_usd: float | None = None
    cost_status: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_no": self.attempt_no,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "provider_request_id": self.provider_request_id,
            "cost_usd": self.cost_usd,
            "cost_status": self.cost_status,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }


@dataclass
class RoutingResult:
    response: AIResponse | None
    attempts: list[ProviderAttempt] = field(default_factory=list)
    routing_policy: str = MODE_FIXED
    error: ProviderError | None = None


@dataclass
class RoutingPolicy:
    mode: str
    primary: str
    model: str | None = None
    chain: list[str] = field(default_factory=list)

    def describe(self) -> str:
        if self.mode == MODE_FALLBACK_CHAIN:
            return f"fallback_chain:{'→'.join(self.chain)}"
        if self.mode == MODE_FIXED_MODEL:
            return f"fixed_model:{self.primary}:{self.model or 'configured'}"
        return f"fixed:{self.primary}"


def parse_routing_policy(
    *,
    mode: str,
    provider: str,
    model: str | None = None,
    fallback_chain: str = "",
) -> RoutingPolicy:
    m = (mode or MODE_FIXED).strip().lower()
    if m not in VALID_MODES:
        raise ValueError(f"Invalid routing mode: {mode}")
    primary = (provider or "").strip().lower()
    if not primary:
        raise ValueError("factory_provider / ai provider is required for routing")
    chain: list[str] = []
    if m == MODE_FALLBACK_CHAIN:
        raw = [p.strip().lower() for p in (fallback_chain or "").split(",") if p.strip()]
        chain = raw if raw else [primary]
        if primary not in chain:
            chain = [primary, *chain]
    else:
        chain = [primary]
    return RoutingPolicy(mode=m, primary=primary, model=model, chain=chain)


class ProviderRouter:
    """Executes GenerateRequest against explicitly configured providers only."""

    def __init__(self, registry: ProviderRegistry, policy: RoutingPolicy):
        self.registry = registry
        self.policy = policy

    async def execute(self, request: GenerateRequest) -> RoutingResult:
        attempts: list[ProviderAttempt] = []
        last_error: ProviderError | None = None
        providers = self.policy.chain if self.policy.mode == MODE_FALLBACK_CHAIN else [self.policy.primary]

        for idx, name in enumerate(providers, start=1):
            entry = self.registry.get(name)
            if entry is None:
                att = ProviderAttempt(
                    attempt_no=idx,
                    provider=name,
                    model=None,
                    status=PROVIDER_BLOCKED,
                    error_code=PROVIDER_BLOCKED,
                    error_message="Unknown provider",
                )
                attempts.append(att)
                last_error = ProviderError(PROVIDER_BLOCKED, f"Unknown provider: {name}", provider=name)
                if self.policy.mode != MODE_FALLBACK_CHAIN:
                    break
                continue

            if entry.status != "AVAILABLE" or entry.instance is None:
                att = ProviderAttempt(
                    attempt_no=idx,
                    provider=name,
                    model=entry.model,
                    status=PROVIDER_BLOCKED,
                    error_code=PROVIDER_BLOCKED,
                    error_message=entry.detail or entry.status,
                )
                attempts.append(att)
                last_error = ProviderError(
                    PROVIDER_BLOCKED,
                    f"Provider {name} blocked ({entry.status})",
                    provider=name,
                )
                if self.policy.mode != MODE_FALLBACK_CHAIN:
                    break
                continue

            model = request.model or self.policy.model or entry.model
            req = GenerateRequest(
                system_prompt=request.system_prompt,
                user_prompt=request.user_prompt,
                max_tokens=request.max_tokens,
                model=model,
                temperature=request.temperature,
                correlation_id=request.correlation_id,
                generation_run_id=request.generation_run_id,
                blueprint_id=request.blueprint_id,
                blueprint_version=request.blueprint_version,
                prompt_version=request.prompt_version,
                require_json=request.require_json,
            )
            started = time.perf_counter()
            try:
                response = await entry.instance.generate_request(req)
                latency_ms = int((time.perf_counter() - started) * 1000)
                cost = estimate_cost(name, response.model, response.prompt_tokens, response.completion_tokens)
                response.provider = name
                response.cost_usd = cost.cost_usd
                response.cost_status = cost.cost_status
                response.total_tokens = cost.total_tokens
                response.latency_ms = latency_ms
                response.routing_policy = self.policy.describe()
                response.provider_attempt_no = idx
                attempts.append(
                    ProviderAttempt(
                        attempt_no=idx,
                        provider=name,
                        model=response.model,
                        status="SUCCESS",
                        latency_ms=latency_ms,
                        provider_request_id=response.provider_request_id,
                        cost_usd=cost.cost_usd,
                        cost_status=cost.cost_status,
                        prompt_tokens=response.prompt_tokens,
                        completion_tokens=response.completion_tokens,
                    )
                )
                response.safe_metadata = {"provider_attempts": [a.to_dict() for a in attempts]}
                return RoutingResult(response=response, attempts=attempts, routing_policy=self.policy.describe())
            except ProviderError as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                attempts.append(
                    ProviderAttempt(
                        attempt_no=idx,
                        provider=name,
                        model=model,
                        status=exc.code,
                        latency_ms=latency_ms,
                        error_code=exc.code,
                        error_message=str(exc)[:300],
                    )
                )
                last_error = exc
                if self.policy.mode != MODE_FALLBACK_CHAIN:
                    break
                continue
            except Exception as exc:  # noqa: BLE001
                latency_ms = int((time.perf_counter() - started) * 1000)
                err = ProviderError(PROVIDER_ERROR, str(exc)[:300], provider=name)
                attempts.append(
                    ProviderAttempt(
                        attempt_no=idx,
                        provider=name,
                        model=model,
                        status=PROVIDER_ERROR,
                        latency_ms=latency_ms,
                        error_code=PROVIDER_ERROR,
                        error_message=str(exc)[:300],
                    )
                )
                last_error = err
                if self.policy.mode != MODE_FALLBACK_CHAIN:
                    break
                continue

        return RoutingResult(
            response=None,
            attempts=attempts,
            routing_policy=self.policy.describe(),
            error=last_error
            or ProviderError(PROVIDER_BLOCKED, "No provider available", provider=self.policy.primary),
        )
