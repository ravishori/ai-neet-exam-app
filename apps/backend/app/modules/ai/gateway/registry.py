"""Provider registry — enablement, keys, health (no live credit burns)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.modules.ai.gateway.base import AIProvider, PROVIDER_BLOCKED
from app.modules.ai.gateway.claude_provider import ClaudeProvider
from app.modules.ai.gateway.fallback_provider import FallbackProvider
from app.modules.ai.gateway.gemini_provider import GeminiProvider
from app.modules.ai.gateway.mistral_provider import MistralProvider
from app.modules.ai.gateway.openai_provider import OpenAIProvider
from app.modules.ai.gateway.pricing import PriceRate, register_rate

# Health states (config-only; no live model calls)
DISABLED = "DISABLED"
ENABLED = "ENABLED"
CONFIGURED = "CONFIGURED"
AVAILABLE = "AVAILABLE"
BLOCKED = "BLOCKED"

KNOWN_PROVIDERS = ("anthropic", "openai", "gemini", "mistral")


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
    ]

    for name, enabled, key, model, cls, default_rate in specs:
        configured = bool(key and str(key).strip())
        status, detail = _status(enabled=enabled, configured=configured)
        instance: AIProvider | None = None
        if status == AVAILABLE:
            _ensure_rate(name, model, default_rate)
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
