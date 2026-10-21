"""Provider registry — enablement, keys, health (no live credit burns)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.modules.ai.gateway.base import PROVIDER_BLOCKED, AIProvider
from app.modules.ai.gateway.claude_provider import ClaudeProvider
from app.modules.ai.gateway.deepseek_provider import DeepSeekProvider
from app.modules.ai.gateway.fallback_provider import FallbackProvider
from app.modules.ai.gateway.gemini_provider import GeminiProvider
from app.modules.ai.gateway.groq_provider import GroqProvider
from app.modules.ai.gateway.krutrim_provider import KrutrimProvider
from app.modules.ai.gateway.mistral_provider import MistralProvider
from app.modules.ai.gateway.openai_provider import OpenAIProvider
from app.modules.ai.gateway.openrouter_provider import OpenRouterProvider
from app.modules.ai.gateway.pricing import PriceRate, register_rate
from app.modules.ai.gateway.sarvam_provider import SarvamProvider

# Health states (config-only; no live model calls)
DISABLED = "DISABLED"
ENABLED = "ENABLED"
CONFIGURED = "CONFIGURED"
AVAILABLE = "AVAILABLE"
BLOCKED = "BLOCKED"

KNOWN_PROVIDERS = ("anthropic", "openai", "gemini", "mistral", "sarvam", "groq", "openrouter", "krutrim", "deepseek")


@dataclass
class ProviderHealth:
    provider: str
    enabled: bool
    configured: bool  # has API key
    status: str
    model: str | None
    detail: str | None = None


@dataclass
class RegisteredProvider:
    name: str
    enabled: bool
    configured: bool
    model: str
    instance: AIProvider | None
    status: str
    detail: str | None = None


class ProviderRegistry:
    """Discovers providers from settings. Duplicate names rejected. Unknown names rejected."""

    def __init__(self) -> None:
        self._providers: dict[str, RegisteredProvider] = {}

    def register(self, entry: RegisteredProvider) -> None:
        if entry.name in self._providers:
            raise ValueError(f"Duplicate provider registration: {entry.name}")
        if entry.name not in KNOWN_PROVIDERS and entry.name != "fallback":
            raise ValueError(f"Unknown provider: {entry.name}")
        self._providers[entry.name] = entry

    def get(self, name: str) -> RegisteredProvider | None:
        return self._providers.get(name)

    def require_available(self, name: str) -> RegisteredProvider:
        entry = self._providers.get(name)
        if entry is None:
            raise ValueError(f"Unknown provider: {name}")
        if entry.status != AVAILABLE or entry.instance is None:
            from app.modules.ai.gateway.base import ProviderError

            raise ProviderError(
                PROVIDER_BLOCKED,
                f"Provider {name} is not available ({entry.status})",
                provider=name,
                retryable=False,
            )
        return entry

    def list_available(self) -> list[RegisteredProvider]:
        return [p for p in self._providers.values() if p.status == AVAILABLE]

    def health(self) -> list[ProviderHealth]:
        return [
            ProviderHealth(
                provider=p.name,
                enabled=p.enabled,
                configured=p.configured,
                status=p.status,
                model=p.model if p.configured else None,
                detail=p.detail,
            )
            for p in self._providers.values()
            if p.name != "fallback"
        ]

    def as_dict(self) -> dict[str, Any]:
        return {
            h.provider: {
                "enabled": h.enabled,
                "configured": h.configured,
                "status": h.status,
                "model": h.model,
                "detail": h.detail,
            }
            for h in self.health()
        }


def _status(*, enabled: bool, configured: bool, detail: str | None = None) -> tuple[str, str | None]:
    if not enabled:
        return DISABLED, detail or "Provider disabled"
    if not configured:
        return BLOCKED, detail or "API key missing"
    return AVAILABLE, None


def _ensure_rate(provider: str, model: str, default: PriceRate) -> None:
    from app.modules.ai.gateway.pricing import estimate_cost

    est = estimate_cost(provider, model, 1, 1)
    if est.cost_status == "UNAVAILABLE":
        register_rate(provider, model, default)


def build_registry_from_settings(settings: Settings) -> ProviderRegistry:
    """Build registry from environment. Does not call provider APIs."""
    registry = ProviderRegistry()

    specs: list[tuple[str, bool, str, str, type[AIProvider], PriceRate]] = [
        (
            "anthropic",
            settings.anthropic_enabled,
            settings.anthropic_api_key,
            settings.anthropic_model or settings.ai_default_model,
            ClaudeProvider,
            PriceRate(3.0, 15.0),
        ),
        (
            "openai",
            settings.openai_enabled,
            settings.openai_api_key,
            settings.openai_model,
            OpenAIProvider,
            PriceRate(0.15, 0.60),
        ),
        (
            "gemini",
            settings.gemini_enabled,
            settings.gemini_api_key,
            settings.gemini_model,
            GeminiProvider,
            PriceRate(0.10, 0.40),
        ),
        (
            "mistral",
            settings.mistral_enabled,
            settings.mistral_api_key,
            settings.mistral_model,
            MistralProvider,
            PriceRate(0.10, 0.30),
        ),
        (
            "sarvam",
            settings.sarvam_enabled,
            settings.sarvam_api_key,
            settings.sarvam_model,
            SarvamProvider,
            # Sarvam public INR rates converted with the project's ₹83/USD
            # observability rate; estimates are not billing-grade.
            PriceRate(29.28 / 83.0, 73.20 / 83.0),
        ),
        (
            # MCQ-FACTORY-GROQ-001: Groq's Chat Completions endpoint is
            # OpenAI-wire-compatible, so this reuses OpenAIProvider's HTTP
            # logic (via the GroqProvider subclass — see groq_provider.py,
            # MCQ-FACTORY-PROVIDER-AGNOSTIC-001) pointed at groq_base_url
            # instead of writing a bespoke HTTP client. This registry entry
            # only ever carries the GENERATION model (openai/gpt-oss-20b
            # default) — the separate, larger VERIFICATION model
            # (openai/gpt-oss-120b default) is never routed through this
            # single-model registry slot; callers that need it construct a
            # second GroqProvider explicitly with settings.groq_verification_model
            # (see mcq_factory_groq_controls.py and
            # construct_groq_verification_provider below) so the two are
            # never conflated.
            "groq",
            settings.groq_enabled,
            settings.groq_api_key,
            settings.groq_generation_model,
            GroqProvider,
            # Groq's published per-token price for openai/gpt-oss-20b
            # (console.groq.com/docs/model) at time of writing. Verify
            # before any live run — this is an estimate, not billing-grade.
            PriceRate(0.10, 0.50),
        ),
        (
            # MCQ-FACTORY-OPENROUTER-001: same OpenAI-wire-compatible reuse
            # as Groq, via the OpenRouterProvider subclass (see
            # openrouter_provider.py) pointed at openrouter_base_url. This
            # entry additionally requires a non-empty settings.openrouter_model
            # to ever reach AVAILABLE — see the `configured` computation
            # below, which treats an empty/placeholder model as "not
            # configured" (fails closed) rather than letting a bogus model
            # string reach a live HTTP call. No real OpenRouter rate was
            # confirmed for this change (no network access) — this
            # placeholder rate is a rough proxy only and MUST be verified
            # against the actual model's published OpenRouter price before
            # any live run; it is not used for anything except keeping
            # estimate_cost() from reporting UNAVAILABLE.
            "openrouter",
            settings.openrouter_enabled,
            settings.openrouter_api_key,
            settings.openrouter_model,
            OpenRouterProvider,
            PriceRate(0.0, 0.0),
        ),
        (
            # MCQ-FACTORY-KRUTRIM-001: same OpenAI-wire-compatible reuse as
            # Groq/OpenRouter, via the KrutrimProvider subclass (see
            # krutrim_provider.py) pointed at krutrim_base_url. Same
            # fail-closed-on-empty-model discipline as OpenRouter — see the
            # `configured` computation below. Krutrim's real, confirmed
            # published rate is ₹6.6 per 1,000,000 tokens (input AND
            # output — Krutrim AI Studio billing docs), converted to USD
            # at the project's existing ₹83/USD observability rate (same
            # rate already used for Sarvam above and for
            # settings.p2_3_usd_inr) — this is an observability estimate,
            # not billing-grade.
            "krutrim",
            settings.krutrim_enabled,
            settings.krutrim_api_key,
            settings.krutrim_model,
            KrutrimProvider,
            PriceRate(6.6 / 83.0, 6.6 / 83.0),
        ),
        (
            # MCQ-FACTORY-DEEPSEEK-001: same OpenAI-wire-compatible reuse as
            # Groq/OpenRouter/Krutrim, via the DeepSeekProvider subclass
            # (see deepseek_provider.py) pointed at deepseek_base_url (NO
            # "/v1" suffix — see that module's docstring). Same
            # fail-closed-on-empty-model discipline as OpenRouter/Krutrim —
            # see the `configured` computation below. DeepSeek's real,
            # confirmed published rate (api-docs.deepseek.com) is
            # time-of-day dependent (peak 01:00-04:00 and 06:00-10:00 UTC
            # Mon-Fri); PriceRate has no time-of-day axis, so the PEAK
            # (higher, more conservative) cache-miss rate is used here as
            # the safe default: $0.30/1M input, $1.20/1M output. Off-peak
            # is cheaper ($0.15/$0.60); this estimate is not billing-grade.
            "deepseek",
            settings.deepseek_enabled,
            settings.deepseek_api_key,
            settings.deepseek_model,
            DeepSeekProvider,
            PriceRate(0.30, 1.20),
        ),
    ]

    for name, enabled, key, model, cls, default_rate in specs:
        base_url = ""
        if name == "openai":
            base_url = (getattr(settings, "openai_base_url", None) or "").strip()
        elif name == "groq":
            base_url = (getattr(settings, "groq_base_url", None) or "").strip() or "https://api.groq.com/openai/v1"
        elif name == "openrouter":
            base_url = (
                getattr(settings, "openrouter_base_url", None) or ""
            ).strip() or "https://openrouter.ai/api/v1"
        elif name == "krutrim":
            base_url = (
                getattr(settings, "krutrim_base_url", None) or ""
            ).strip() or "https://cloud.olakrutrim.com/v1"
        elif name == "deepseek":
            # NO "/v1" suffix — see deepseek_provider.py's module docstring
            # for why that is correct/confirmed for DeepSeek specifically.
            base_url = (getattr(settings, "deepseek_base_url", None) or "").strip() or "https://api.deepseek.com"
        # Groq always needs a real key (unlike the "local" OpenAI-compatible
        # override, which may run keyless against a dev endpoint) — a
        # base_url alone never marks it configured.
        configured = bool(key and str(key).strip()) or (name == "openai" and bool(base_url))
        detail_override: str | None = None
        if name == "openrouter":
            # A key alone is not enough: an empty/placeholder model must
            # never silently reach a live HTTP call (see the task's
            # "fails closed on an unconfirmed/empty model" requirement —
            # mirrors how every other provider here already requires a
            # non-empty `model` default; openrouter_model's default is
            # deliberately empty until an operator confirms a real id).
            has_model = bool(str(model or "").strip())
            if configured and not has_model:
                configured = False
                detail_override = (
                    "OPENROUTER_MODEL is empty/placeholder — confirm a real model id against "
                    "OpenRouter's live /models listing before enabling"
                )
        elif name == "krutrim":
            # Same fail-closed-on-empty-model discipline as OpenRouter —
            # krutrim_model's default is deliberately empty until an
            # operator explicitly opts into "Krutrim-spectre-v2" (or
            # another confirmed real Krutrim model id).
            has_model = bool(str(model or "").strip())
            if configured and not has_model:
                configured = False
                detail_override = "KRUTRIM_MODEL is empty/placeholder — set a confirmed real model id before enabling"
        elif name == "deepseek":
            # Same fail-closed-on-empty-model discipline as OpenRouter/
            # Krutrim — deepseek_model's default is deliberately empty
            # until an operator explicitly opts into "deepseek-flash" (or
            # another confirmed real DeepSeek model id).
            has_model = bool(str(model or "").strip())
            if configured and not has_model:
                configured = False
                detail_override = (
                    "DEEPSEEK_MODEL is empty/placeholder — set a confirmed real model id before enabling"
                )
        status, detail = _status(enabled=enabled, configured=configured, detail=detail_override)
        instance: AIProvider | None = None
        if status == AVAILABLE:
            _ensure_rate(name, model, default_rate)
            if name == "openai" and base_url:
                instance = cls(api_key=(key or "local"), model=model, base_url=base_url)
            elif name in ("groq", "openrouter", "krutrim", "deepseek"):
                instance = cls(api_key=key, model=model, base_url=base_url)
            else:
                instance = cls(api_key=key, model=model)
        registry.register(
            RegisteredProvider(
                name=name,
                enabled=enabled,
                configured=configured,
                model=model,
                instance=instance,
                status=status,
                detail=detail,
            )
        )

    # Legacy stub — never AVAILABLE for factory routing
    registry.register(
        RegisteredProvider(
            name="fallback",
            enabled=True,
            configured=True,
            model="fallback",
            instance=FallbackProvider(),
            status=ENABLED,
            detail="Stub only — not a live provider; Content Factory rejects is_fallback",
        )
    )
    return registry


def groq_verification_status(settings: Settings) -> tuple[str, str | None]:
    """Enablement/config status for the VERIFICATION model
    (``settings.groq_verification_model``, default openai/gpt-oss-120b).

    Mirrors ``_status`` exactly as the main ``groq`` registry entry uses it
    (same enabled/configured semantics, same DISABLED/BLOCKED/AVAILABLE
    vocabulary) so a caller can treat verification availability with the
    identical fail-closed discipline as generation — but this is
    deliberately NOT a second ``ProviderRegistry`` entry (``register``
    forbids duplicate provider names); see ``construct_groq_verification_provider``.
    """
    configured = bool((settings.groq_api_key or "").strip())
    return _status(enabled=settings.groq_enabled, configured=configured)


def construct_groq_provider_for_model(
    settings: Settings, model: str, *, default_rate: PriceRate | None = None
) -> AIProvider | None:
    """Construct a Groq provider instance bound to an EXPLICIT model
    string (generation model, verification model, or — for
    MCQ-FACTORY-PROVIDER-AGNOSTIC-001's independent per-stage provider
    selection, see ``mcq_llm_provider.build_mcq_factory_stage_provider`` —
    any other Groq model an operator configures for either stage).

    Generalizes what ``construct_groq_verification_provider`` always did
    for the verification model specifically (same enabled/key/base_url
    checks, same fail-closed ``None`` on missing config, same
    ``GroqProvider``-over-``OpenAIProvider`` reuse) so any caller that
    needs "a Groq instance bound to model X" gets the identical
    construction discipline, regardless of which stage asked for it. This
    does not call the network and does not mutate the ``groq`` registry
    entry built by ``build_registry_from_settings`` — each call returns a
    fresh, independent provider object.
    """
    if not settings.groq_enabled:
        return None
    key = (settings.groq_api_key or "").strip()
    if not key:
        return None
    base_url = (settings.groq_base_url or "").strip() or "https://api.groq.com/openai/v1"
    if default_rate is not None:
        _ensure_rate("groq", model, default_rate)
    return GroqProvider(api_key=key, model=model, base_url=base_url)


def construct_groq_verification_provider(settings: Settings) -> AIProvider | None:
    """Construct the independent VERIFICATION-model provider instance.

    Exact same construction pattern as the ``groq`` registry entry above
    (Groq's OpenAI-compatible HTTP client, same base_url/key checks) but
    ALWAYS bound to ``settings.groq_verification_model`` (openai/gpt-oss-
    120b by default) — NEVER ``groq_generation_model``. Returns ``None``
    (never half-configured) when Groq is disabled or unconfigured;
    callers (``mcq_llm_provider.build_mcq_verification_provider``,
    ``mcq_factory_groq/orchestrator.py``) MUST treat ``None`` as
    "verification unavailable" and fail closed (never silently skip the
    reviewer gate — see ``mcq_factory_groq/validators.gate_reviewer``,
    which already treats a missing verification result as YELLOW/
    human-review-eligible, never GREEN).

    Kept as its own named function (unchanged signature/behavior) for
    backward compatibility — it is now a thin wrapper over
    ``construct_groq_provider_for_model`` with the verification model's
    own published rate, identical to the number this function always used.
    """
    # Groq's published per-token price for openai/gpt-oss-120b
    # (console.groq.com/docs/model) at time of writing. Verify before any
    # live run — this is an estimate, not billing-grade, same caveat as
    # the generation-model rate registered in build_registry_from_settings.
    return construct_groq_provider_for_model(
        settings, settings.groq_verification_model, default_rate=PriceRate(0.40, 0.75)
    )


def resolve_default_provider(registry: ProviderRegistry, settings: Settings) -> AIProvider:
    """Pick default live provider for non-routed gateway callers (tutor, etc.)."""
    preferred = (settings.ai_provider_default or "anthropic").strip().lower()
    entry = registry.get(preferred)
    if entry and entry.status == AVAILABLE and entry.instance is not None:
        return entry.instance
    available = registry.list_available()
    if available:
        return available[0].instance  # type: ignore[return-value]
    return FallbackProvider()
