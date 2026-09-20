"""MCQ-PROVIDER-ABSTRACTION-001 — Content-factory LLM provider façade.

Decouples MCQ generation from any single vendor SDK. Production generation
goes through this façade → AIGateway → AIProvider adapters (Anthropic,
Gemini, OpenAI, …). Cursor is never a generation provider.

Silent cross-provider fallback is forbidden unless the operator explicitly
sets FACTORY_PROVIDER_MODE=fallback_chain AND MCQ_ALLOW_FALLBACK_CHAIN=true.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.gateway.base import (
    PROVIDER_AUTH_FAILED,
    PROVIDER_BLOCKED,
    PROVIDER_RATE_LIMITED,
    PROVIDER_TIMEOUT,
    PROVIDER_UNAVAILABLE,
    AIProvider,
    AIResponse,
    ProviderError,
)
from app.modules.ai.gateway.errors import map_exception
from app.modules.ai.gateway.registry import build_registry_from_settings
from app.modules.ai.gateway.router import MODE_FALLBACK_CHAIN, MODE_FIXED, parse_routing_policy

# Content-layer classifications (not HTTP provider codes)
PARSE_ERROR = "PARSE_ERROR"
VALIDATION_ERROR = "VALIDATION_ERROR"
DUPLICATE = "DUPLICATE"
NETWORK_ERROR = "NETWORK_ERROR"
PROVIDER_INTERNAL_ERROR = "PROVIDER_INTERNAL_ERROR"
TIMEOUT = "TIMEOUT"
AUTH_ERROR = "AUTH_ERROR"
RATE_LIMIT = "RATE_LIMIT"

# Operator-facing aliases → registry names
_PROVIDER_ALIASES: dict[str, str] = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "google": "gemini",
    "gemini": "gemini",
    "openai": "openai",
    "local": "openai",  # OpenAI-compatible local endpoint via openai_base_url
    "mistral": "mistral",
    "sarvam": "sarvam",
}

# Providers exposed for MCQ factory configuration (must have adapters)
MCQ_SUPPORTED_PROVIDERS = ("anthropic", "gemini", "openai", "mistral", "sarvam")


@runtime_checkable
class McqLlmProvider(Protocol):
    """Factory-facing provider contract — no vendor SDK imports at call sites."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    async def generate_mcq(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1200,
        user_id: UUID | None = None,
        correlation_id: str | None = None,
        generation_run_id: str | None = None,
        blueprint_id: str | None = None,
        blueprint_version: int | None = None,
        prompt_version: str | None = None,
        agent_type: str = "CONTENT_FACTORY_MCQ",
    ) -> AIResponse: ...

    def health_check(self) -> dict[str, Any]: ...

    def classify_error(self, exc: BaseException) -> ProviderError: ...


@dataclass(frozen=True)
class McqProviderSelection:
    """Resolved, explicit MCQ provider selection (never silent)."""

    requested: str
    registry_name: str
    model: str
    mode: str
    routing_policy: str
    allow_fallback_chain: bool
    openai_base_url: str | None


def normalize_mcq_provider_name(raw: str) -> str:
    key = (raw or "").strip().lower()
    if not key:
        raise AppError("MCQ provider name is empty", code="MCQ_PROVIDER_UNSET", status_code=400)
    if key not in _PROVIDER_ALIASES:
        raise AppError(
            f"Unsupported MCQ provider '{raw}'. "
            f"Allowed: anthropic|google|gemini|openai|local|mistral|sarvam",
            code="MCQ_PROVIDER_UNSUPPORTED",
            status_code=400,
        )
    return _PROVIDER_ALIASES[key]


def resolve_mcq_provider_selection(settings: Settings | None = None) -> McqProviderSelection:
    """Resolve explicit MCQ provider from settings (MCQ_PROVIDER → FACTORY_PROVIDER)."""
    s = settings or get_settings()
    requested = (getattr(s, "mcq_provider", None) or s.factory_provider or s.ai_provider_default or "").strip()
    registry_name = normalize_mcq_provider_name(requested)
    mode = (s.factory_provider_mode or MODE_FIXED).strip().lower()
    allow_fb = bool(getattr(s, "mcq_allow_fallback_chain", False))

    if mode == MODE_FALLBACK_CHAIN and not allow_fb:
        raise AppError(
            "FACTORY_PROVIDER_MODE=fallback_chain is disabled for MCQ generation "
            "unless MCQ_ALLOW_FALLBACK_CHAIN=true (explicit operator opt-in). "
            "Silent provider switching is forbidden.",
            code="MCQ_SILENT_FALLBACK_FORBIDDEN",
            status_code=400,
        )

    if (requested or "").strip().lower() == "local":
        base = (getattr(s, "openai_base_url", None) or "").strip()
        if not base:
            raise AppError(
                "MCQ_PROVIDER=local requires OPENAI_BASE_URL (OpenAI-compatible endpoint)",
                code="MCQ_LOCAL_BASE_URL_REQUIRED",
                status_code=400,
            )

    model_map = {
        "anthropic": s.anthropic_model or s.ai_default_model,
        "gemini": s.gemini_model,
        "openai": s.openai_model,
        "mistral": s.mistral_model,
        "sarvam": s.sarvam_model,
    }
    model = model_map.get(registry_name, s.ai_default_model)

    primary = registry_name
    # Keep fixed / fixed_model; only fallback_chain requires opt-in (already validated above).
    policy = parse_routing_policy(
        mode=mode if mode in {"fixed", "fixed_model", "fallback_chain"} else MODE_FIXED,
        provider=primary,
        model=model if mode == "fixed_model" else None,
        fallback_chain=s.factory_provider_fallback_chain if allow_fb else "",
    )

    return McqProviderSelection(
        requested=requested,
        registry_name=registry_name,
        model=model,
        mode=policy.mode,
        routing_policy=policy.describe(),
        allow_fallback_chain=allow_fb and mode == MODE_FALLBACK_CHAIN,
        openai_base_url=(getattr(s, "openai_base_url", None) or "").strip() or None,
    )


def classify_mcq_error(exc: BaseException, *, provider: str | None = None) -> ProviderError:
    """Normalize exceptions into factory error taxonomy."""
    if isinstance(exc, ProviderError):
        return exc
    return map_exception(provider or "unknown", exc)


def content_error_code(kind: str) -> str:
    """Map content-pipeline failures to stable codes."""
    k = (kind or "").upper()
    if k in {PARSE_ERROR, "FAILED_PARSE"}:
        return PARSE_ERROR
    if k in {VALIDATION_ERROR, "REJECTED_VALIDATION"}:
        return VALIDATION_ERROR
    if k in {DUPLICATE, "REJECTED_DUPLICATE"}:
        return DUPLICATE
    return k


def report_error_alias(code: str) -> str:
    """Operator-facing alias for telemetry (stored code remains ProviderError.code)."""
    mapping = {
        PROVIDER_RATE_LIMITED: RATE_LIMIT,
        PROVIDER_AUTH_FAILED: AUTH_ERROR,
        PROVIDER_TIMEOUT: TIMEOUT,
        PROVIDER_UNAVAILABLE: NETWORK_ERROR,
        PROVIDER_BLOCKED: PROVIDER_BLOCKED,
        "PROVIDER_INVALID_RESPONSE": PROVIDER_INTERNAL_ERROR,
        "PROVIDER_ERROR": PROVIDER_INTERNAL_ERROR,
    }
    return mapping.get(code, code)


def is_retryable_provider_error(exc: ProviderError) -> bool:
    """RATE_LIMIT / timeout / unavailable may retry; BLOCKED / AUTH must stop."""
    if exc.code in {PROVIDER_BLOCKED, PROVIDER_AUTH_FAILED}:
        return False
    return bool(exc.retryable) or exc.code in {
        PROVIDER_RATE_LIMITED,
        PROVIDER_TIMEOUT,
        PROVIDER_UNAVAILABLE,
    }


def must_stop_run(exc: ProviderError) -> bool:
    return exc.code in {PROVIDER_BLOCKED, PROVIDER_AUTH_FAILED} or not is_retryable_provider_error(exc)


class GatewayMcqLlmProvider:
    """Production adapter: McqLlmProvider → AIGateway → vendor AIProvider."""

    def __init__(
        self,
        gateway: AIGateway,
        *,
        selection: McqProviderSelection,
        injected: AIProvider | None = None,
    ) -> None:
        self._gateway = gateway
        self._selection = selection
        self._injected = injected

    @property
    def provider_name(self) -> str:
        if self._injected is not None:
            return getattr(self._injected, "name", self._selection.registry_name)
        return self._selection.registry_name

    @property
    def model_name(self) -> str:
        return self._selection.model

    @property
    def selection(self) -> McqProviderSelection:
        return self._selection

    async def generate_mcq(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1200,
        user_id: UUID | None = None,
        correlation_id: str | None = None,
        generation_run_id: str | None = None,
        blueprint_id: str | None = None,
        blueprint_version: int | None = None,
        prompt_version: str | None = None,
        agent_type: str = "CONTENT_FACTORY_MCQ",
    ) -> AIResponse:
        try:
            return await self._gateway.generate(
                agent_type=agent_type,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                user_id=user_id,
                max_tokens=max_tokens,
                generation_run_id=generation_run_id,
                blueprint_id=blueprint_id,
                blueprint_version=blueprint_version,
                prompt_version=prompt_version,
                require_json=True,
                correlation_id=correlation_id,
                model=self._selection.model if self._selection.mode == "fixed_model" else None,
            )
        except ProviderError:
            raise
        # Let non-ProviderError propagate so the factory can soft-continue
        # (historical behavior for transient scripted/network failures).

    def health_check(self) -> dict[str, Any]:
        """Config-only health (no live credit burn)."""
        registry = build_registry_from_settings(get_settings())
        entry = registry.get(self.provider_name)
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "routing_policy": self._selection.routing_policy,
            "status": entry.status if entry else "UNKNOWN",
            "enabled": entry.enabled if entry else False,
            "configured": entry.configured if entry else False,
            "detail": entry.detail if entry else "not in registry",
            "live_ping": False,
            "note": "Config-only health_check — does not call provider APIs",
        }

    def classify_error(self, exc: BaseException) -> ProviderError:
        return classify_mcq_error(exc, provider=self.provider_name)


def build_mcq_llm_provider(
    session: Any,
    *,
    provider: AIProvider | None = None,
    settings: Settings | None = None,
) -> GatewayMcqLlmProvider:
    """Construct the factory MCQ provider façade."""
    s = settings or get_settings()
    selection = resolve_mcq_provider_selection(s)
    routing = parse_routing_policy(
        mode=selection.mode,
        provider=selection.registry_name,
        model=selection.model if selection.mode == "fixed_model" else None,
        fallback_chain=s.factory_provider_fallback_chain if selection.allow_fallback_chain else "",
    )
    gateway = AIGateway(session, provider=provider, routing_policy=routing)
    return GatewayMcqLlmProvider(gateway, selection=selection, injected=provider)


def list_implemented_mcq_providers(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Describe which MCQ providers are implemented and currently AVAILABLE."""
    s = settings or get_settings()
    registry = build_registry_from_settings(s)
    out = []
    for name in MCQ_SUPPORTED_PROVIDERS:
        entry = registry.get(name)
        out.append(
            {
                "registry_name": name,
                "aliases": [k for k, v in _PROVIDER_ALIASES.items() if v == name],
                "implemented": True,
                "status": entry.status if entry else "UNKNOWN",
                "model": entry.model if entry else None,
                "local_endpoint_supported": name == "openai",
                "openai_base_url_configured": bool((getattr(s, "openai_base_url", None) or "").strip())
                if name == "openai"
                else None,
            }
        )
    return out


def assert_provider_metadata_consistent(
    *,
    candidate_provider: str | None,
    expected_provider: str,
) -> None:
    """Guard: a candidate must never appear generated by a different provider."""
    if not candidate_provider:
        raise AppError(
            "Candidate missing provider metadata",
            code="MCQ_PROVIDER_METADATA_MISSING",
            status_code=500,
        )
    if candidate_provider != expected_provider:
        raise AppError(
            f"Provider metadata mismatch: candidate={candidate_provider} expected={expected_provider}",
            code="MCQ_PROVIDER_METADATA_MISMATCH",
            status_code=500,
        )
