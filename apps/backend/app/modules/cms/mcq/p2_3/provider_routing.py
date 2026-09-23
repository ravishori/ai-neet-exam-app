"""P2.3 cross-provider validation routing — never same-provider 'independent' validation."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.modules.ai.gateway.base import AIProvider
from app.modules.ai.gateway.gemini_provider import GeminiProvider
from app.modules.ai.gateway.openai_provider import OpenAIProvider
from app.modules.ai.gateway.registry import build_registry_from_settings

# Anthropic excluded from generation rotation while billing unavailable (P2.3-R1).
GENERATION_PROVIDERS = ("gemini", "openai")

CROSS_VALIDATOR: dict[str, str] = {
    "gemini": "openai",
    "openai": "gemini",
    "anthropic": "openai",  # never route to anthropic when unavailable
}


def cross_validator_for(generator_provider: str) -> str | None:
    """Return required independent validator provider name, or None if unknown."""
    return CROSS_VALIDATOR.get((generator_provider or "").lower())


def is_same_provider_validation(generator_provider: str, validator_provider: str) -> bool:
    return (generator_provider or "").lower() == (validator_provider or "").lower()


def assert_cross_provider(generator_provider: str, validator_provider: str) -> None:
    if is_same_provider_validation(generator_provider, validator_provider):
        raise ValueError(
            f"Same-provider validation blocked: {generator_provider} → {validator_provider}"
        )


def resolve_generation_providers(*, include_anthropic: bool = False) -> dict[str, tuple[AIProvider, str]]:
    """Available generation providers; Anthropic disabled by default (P2.3-R1)."""
    settings = get_settings()
    registry = build_registry_from_settings(settings)
    names = ("gemini", "openai", "anthropic") if include_anthropic else GENERATION_PROVIDERS
    out: dict[str, tuple[AIProvider, str]] = {}
    for name in names:
        entry = registry.get(name)
        if not entry or entry.status != "AVAILABLE" or not entry.instance:
            continue
        model = entry.model
        if name == "openai" and model.startswith("gpt-5"):
            inst = OpenAIProvider(settings.openai_api_key, "gpt-4o-mini")
            model = "gpt-4o-mini"
        else:
            inst = entry.instance
        out[name] = (inst, model)
    return out


def resolve_validator_bundle(
    generator_provider: str,
    settings: Settings | None = None,
) -> tuple[AIProvider, str, str] | None:
    """Resolve independent validator for a generation provider (cross-provider only)."""
    settings = settings or get_settings()
    target = cross_validator_for(generator_provider)
    if not target:
        return None

    if target == "openai":
        if settings.openai_api_key and settings.openai_enabled:
            model = "gpt-4o-mini"
            return OpenAIProvider(settings.openai_api_key, model), "openai", model
        registry = build_registry_from_settings(settings)
        entry = registry.get("openai")
        if entry and entry.status == "AVAILABLE" and entry.instance:
            model = entry.model
            if model.startswith("gpt-5"):
                return OpenAIProvider(settings.openai_api_key, "gpt-4o-mini"), "openai", "gpt-4o-mini"
            return entry.instance, "openai", model

    if target == "gemini":
        if settings.gemini_api_key and settings.gemini_enabled:
            model = settings.gemini_model or "gemini-3.6-flash"
            return GeminiProvider(settings.gemini_api_key, model), "gemini", model
        registry = build_registry_from_settings(settings)
        entry = registry.get("gemini")
        if entry and entry.status == "AVAILABLE" and entry.instance:
            return entry.instance, "gemini", entry.model

    return None
