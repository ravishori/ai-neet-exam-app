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
    "groq": "groq",  # MCQ-FACTORY-GROQ-001 — generation model only (see registry.py)
    "openrouter": "openrouter",  # MCQ-FACTORY-OPENROUTER-001 (see registry.py)
    "krutrim": "krutrim",  # MCQ-FACTORY-KRUTRIM-001 (see registry.py)
    "deepseek": "deepseek",  # MCQ-FACTORY-DEEPSEEK-001 (see registry.py)
}

# Providers exposed for MCQ factory configuration (must have adapters)
MCQ_SUPPORTED_PROVIDERS = (
    "anthropic",
    "gemini",
    "openai",
    "mistral",
    "sarvam",
    "groq",
    "openrouter",
    "krutrim",
    "deepseek",
)


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
            f"Allowed: anthropic|google|gemini|openai|local|mistral|sarvam|groq|openrouter|krutrim|deepseek",
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
        "groq": s.groq_generation_model,
        "openrouter": s.openrouter_model,
        "krutrim": s.krutrim_model,
        "deepseek": s.deepseek_model,
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


@dataclass(frozen=True)
class McqVerificationSelection:
    """Resolved VERIFICATION-model selection — always the Groq
    openai/gpt-oss-120b-class model, never the generation model. There is
    no multi-provider selection here (unlike ``McqProviderSelection``):
    verification is Groq-only by design (see registry.py's
    ``construct_groq_verification_provider``)."""

    registry_name: str  # always "groq"
    model: str
    enabled: bool
    configured: bool


VERIFICATION_AGENT_TYPE = "CONTENT_FACTORY_MCQ_VERIFY"  # must fit ai.ai_requests.agent_type VARCHAR(30)


def resolve_mcq_verification_selection(settings: Settings | None = None) -> McqVerificationSelection:
    """Resolve the independent VERIFICATION-model selection.

    Mirrors ``resolve_mcq_provider_selection``'s shape (so callers can
    reason about the two symmetrically) but is intentionally simpler: it
    is never routed, aliased, or fallback-chained — it is always Groq's
    ``settings.groq_verification_model``.
    """
    s = settings or get_settings()
    return McqVerificationSelection(
        registry_name="groq",
        model=s.groq_verification_model,
        enabled=bool(s.groq_enabled),
        configured=bool((s.groq_api_key or "").strip()),
    )


class GatewayMcqVerificationProvider:
    """Production adapter for the independent VERIFICATION call site.

    Deliberately a SEPARATE class from ``GatewayMcqLlmProvider`` (not a
    mode flag on it) — this is "the genuinely separate call site" the
    orchestrator (``app/modules/cms/mcq_factory_groq/orchestrator.py``)
    must use so a verification result can never be silently satisfied by
    re-using the generation call's own response. It still goes through
    the same ``AIGateway`` façade (same cost/latency logging contract,
    same ``AIRequestLog`` lineage) as generation — just with its own
    ``agent_type`` (``VERIFICATION_AGENT_TYPE``) and its own explicitly
    injected provider instance (never the router/registry's single
    ``groq`` slot, which only ever carries the generation model).
    """

    def __init__(self, gateway: AIGateway, *, selection: McqVerificationSelection) -> None:
        self._gateway = gateway
        self._selection = selection

    @property
    def provider_name(self) -> str:
        return self._selection.registry_name

    @property
    def model_name(self) -> str:
        return self._selection.model

    @property
    def selection(self) -> McqVerificationSelection:
        return self._selection

    async def verify_candidate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 700,
        user_id: UUID | None = None,
        correlation_id: str | None = None,
        generation_run_id: str | None = None,
    ) -> AIResponse:
        try:
            return await self._gateway.generate(
                agent_type=VERIFICATION_AGENT_TYPE,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                user_id=user_id,
                max_tokens=max_tokens,
                generation_run_id=generation_run_id,
                require_json=True,
                correlation_id=correlation_id,
                model=self._selection.model,
            )
        except ProviderError:
            raise

    def health_check(self) -> dict[str, Any]:
        if not self._selection.enabled:
            status, detail = "DISABLED", "Provider disabled"
        elif not self._selection.configured:
            status, detail = "BLOCKED", "API key missing"
        else:
            status, detail = "AVAILABLE", None
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "status": status,
            "enabled": self._selection.enabled,
            "configured": self._selection.configured,
            "detail": detail,
            "live_ping": False,
            "note": "Config-only health_check — does not call provider APIs",
        }

    def classify_error(self, exc: BaseException) -> ProviderError:
        return classify_mcq_error(exc, provider=self.provider_name)


def build_mcq_verification_provider(
    session: Any,
    *,
    provider: AIProvider | None = None,
    settings: Settings | None = None,
) -> GatewayMcqVerificationProvider | None:
    """Construct the VERIFICATION façade, or ``None`` when Groq
    verification is disabled/unconfigured.

    Mirrors ``build_mcq_llm_provider``'s construction pattern exactly
    (same ``AIGateway`` wrapping) but always resolves to the Groq
    verification model via ``registry.construct_groq_verification_provider``
    rather than the multi-provider router — the two are never conflated.
    A caller (the orchestrator) that receives ``None`` back MUST treat
    verification as unavailable for this run and fail closed (route to
    REVIEW_REQUIRED), never silently skip the reviewer gate.
    """
    from app.modules.ai.gateway.registry import construct_groq_verification_provider

    s = settings or get_settings()
    selection = resolve_mcq_verification_selection(s)
    if provider is None:
        provider = construct_groq_verification_provider(s)
        if provider is None:
            return None
    gateway = AIGateway(session, provider=provider)
    return GatewayMcqVerificationProvider(gateway, selection=selection)


@dataclass(frozen=True)
class McqFactoryStageSelection:
    """Resolved, explicit provider+model selection for ONE MCQ-factory
    orchestrator call site (``stage`` is ``"generation"`` or
    ``"verification"``) — MCQ-FACTORY-PROVIDER-AGNOSTIC-001.

    Generalizes ``McqVerificationSelection`` (which stayed hard-coded to
    Groq) to any ``MCQ_SUPPORTED_PROVIDERS`` entry, independently for each
    stage, each defaulting to Groq when
    ``settings.mcq_factory_<stage>_provider`` is left unset. Never a
    silent fallback to Groq for an explicitly unsupported/misspelled
    name — ``normalize_mcq_provider_name`` (reused, not reimplemented)
    raises ``AppError`` for that case.
    """

    stage: str
    requested: str
    registry_name: str
    model: str
    enabled: bool
    configured: bool


def _default_model_for_stage_provider(registry_name: str, stage: str, s: Settings) -> str:
    """Same model-per-registry-name convention already used by
    ``resolve_mcq_provider_selection``'s ``model_map`` above, duplicated
    narrowly here (rather than refactoring that function) so this
    additive stage-selection path never risks changing the existing
    generic MCQ-provider resolution's behavior."""
    if registry_name == "groq":
        return s.groq_generation_model if stage == "generation" else s.groq_verification_model
    model_map = {
        "anthropic": s.anthropic_model or s.ai_default_model,
        "gemini": s.gemini_model,
        "openai": s.openai_model,
        "mistral": s.mistral_model,
        "sarvam": s.sarvam_model,
        "openrouter": s.openrouter_model,
        "krutrim": s.krutrim_model,
        "deepseek": s.deepseek_model,
    }
    return model_map.get(registry_name, s.ai_default_model)


def resolve_mcq_factory_stage_selection(
    stage: str, *, settings: Settings | None = None
) -> McqFactoryStageSelection:
    """Resolve the independent provider+model for one MCQ-factory call
    site from ``settings.mcq_factory_<stage>_provider`` /
    ``_model``, defaulting to Groq when unset. Fails closed (``AppError``,
    via ``normalize_mcq_provider_name``) on a genuinely unsupported
    provider name — it never silently substitutes Groq for a typo.
    """
    if stage not in ("generation", "verification"):
        raise ValueError(f"Unknown MCQ factory stage: {stage!r}")
    s = settings or get_settings()
    raw_provider = (getattr(s, f"mcq_factory_{stage}_provider", "") or "").strip()
    requested = raw_provider or "groq"
    registry_name = normalize_mcq_provider_name(requested)

    raw_model = (getattr(s, f"mcq_factory_{stage}_model", "") or "").strip()
    model = raw_model or _default_model_for_stage_provider(registry_name, stage, s)

    if registry_name == "groq":
        enabled = bool(s.groq_enabled)
        configured = bool((s.groq_api_key or "").strip())
    else:
        enabled = bool(getattr(s, f"{registry_name}_enabled", False))
        key = (getattr(s, f"{registry_name}_api_key", "") or "").strip()
        base_url = (getattr(s, "openai_base_url", "") or "").strip()
        configured = bool(key) or (registry_name == "openai" and bool(base_url))
        if registry_name in ("openrouter", "krutrim", "deepseek"):
            # Fails closed on an empty/placeholder model — mirrors the
            # identical check in registry.build_registry_from_settings
            # (see openrouter_provider.py's / krutrim_provider.py's /
            # deepseek_provider.py's module docstrings). A key alone is
            # never enough: an unconfirmed model string must never
            # silently reach a live HTTP call.
            configured = configured and bool(model.strip())

    return McqFactoryStageSelection(
        stage=stage,
        requested=requested,
        registry_name=registry_name,
        model=model,
        enabled=enabled,
        configured=configured,
    )


def build_mcq_factory_stage_provider(
    stage: str, *, settings: Settings | None = None
) -> tuple[AIProvider | None, McqFactoryStageSelection]:
    """Construct (or fail closed to ``None``) the ``AIProvider`` instance
    for one MCQ-factory stage, reusing the EXISTING abstractions for
    every provider — never a bespoke HTTP client:

    - ``groq`` reuses ``registry.construct_groq_provider_for_model`` (the
      same ``GroqProvider``-over-``OpenAIProvider`` reuse the generation/
      verification call sites always used), bound to whatever model this
      stage resolved to (not necessarily ``groq_generation_model`` /
      ``groq_verification_model`` — an operator may override either via
      ``mcq_factory_<stage>_model``).
    - any other ``MCQ_SUPPORTED_PROVIDERS`` entry reuses the already-
      available instance from a freshly-built ``ProviderRegistry``
      (``registry.build_registry_from_settings``) — the SAME instance
      construction every other gateway caller uses. The stage's resolved
      ``model`` is passed per-call via ``AIGateway.generate(model=...)``
      (see ``build_mcq_factory_stage_caller`` below), not baked into the
      instance, since ``AIProvider.generate_request`` already supports an
      explicit per-call model override.

    Returns ``(None, selection)`` when the resolved provider is disabled
    or unconfigured — callers decide how to fail closed per stage (see
    ``build_mcq_factory_stage_caller``).
    """
    from app.modules.ai.gateway.registry import (
        AVAILABLE,
        build_registry_from_settings,
        construct_groq_provider_for_model,
    )
    from app.modules.ai.gateway.pricing import PriceRate

    s = settings or get_settings()
    selection = resolve_mcq_factory_stage_selection(stage, settings=s)
    if not selection.enabled or not selection.configured:
        return None, selection

    if selection.registry_name == "groq":
        # Same published-rate placeholders build_registry_from_settings /
        # construct_groq_verification_provider already use per stage —
        # verify before any live run (see those functions' docstrings).
        default_rate = PriceRate(0.10, 0.50) if stage == "generation" else PriceRate(0.40, 0.75)
        provider = construct_groq_provider_for_model(s, selection.model, default_rate=default_rate)
    else:
        reg = build_registry_from_settings(s)
        entry = reg.get(selection.registry_name)
        provider = entry.instance if entry and entry.status == AVAILABLE else None

    return provider, selection


def build_mcq_factory_stage_caller(
    session: Any, *, stage: str, settings: Settings | None = None
) -> Any:
    """Build a plain async caller (``system_prompt``/``user_prompt``/
    ``max_tokens`` -> ``AIResponse``) for one MCQ-factory stage, resolved
    independently via ``mcq_factory_<stage>_provider`` / ``_model``
    (defaulting to Groq). Matches the orchestrator's
    ``GenerationCaller``/``VerificationCaller`` protocol shape exactly
    (``app/modules/cms/mcq_factory_groq/orchestrator.py``) — drops in
    wherever ``build_groq_generation_caller``/``build_groq_verification_caller``
    do today; those two functions are left untouched for existing callers.

    Generation: raises ``AppError`` (fail closed) when the resolved
    provider is disabled/unconfigured — a batch cannot run without a
    generation caller.
    Verification: returns ``None`` (fail closed to ``REVIEW_REQUIRED``,
    exactly like ``build_mcq_verification_provider``'s existing contract)
    rather than raising, since a missing verifier is "optional but never
    silently skipped" by the orchestrator's routing rule.
    """
    s = settings or get_settings()
    provider, selection = build_mcq_factory_stage_provider(stage, settings=s)
    if provider is None:
        if stage == "generation":
            raise AppError(
                f"MCQ factory generation provider '{selection.registry_name}' is unavailable "
                f"(enabled={selection.enabled}, configured={selection.configured})",
                code="MCQ_FACTORY_GENERATION_PROVIDER_UNAVAILABLE",
                status_code=400,
            )
        return None

    gateway = AIGateway(session, provider=provider)
    agent_type = VERIFICATION_AGENT_TYPE if stage == "verification" else "CONTENT_FACTORY_MCQ"

    async def _caller(*, system_prompt: str, user_prompt: str, max_tokens: int) -> AIResponse:
        return await gateway.generate(
            agent_type=agent_type,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            model=selection.model,
            require_json=True,
        )

    return _caller


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
