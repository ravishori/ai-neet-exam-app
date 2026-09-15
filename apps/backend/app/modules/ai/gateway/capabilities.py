"""Provider model capability registry — configuration-driven, not scattered hard-codes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderModelCapability:
    provider: str
    model: str
    supports_structured_output: bool = False
    supports_system_prompt: bool = True
    supports_temperature: bool = True
    max_context: int = 128_000
    max_output: int = 8_192
    enabled: bool = True


_CAPABILITIES: dict[tuple[str, str], ProviderModelCapability] = {}


def _reg(cap: ProviderModelCapability) -> None:
    _CAPABILITIES[(cap.provider, cap.model)] = cap


_reg(ProviderModelCapability("anthropic", "claude-sonnet-4-6", supports_structured_output=False, max_output=8192))
_reg(ProviderModelCapability("anthropic", "claude-3-5-sonnet-latest", supports_structured_output=False))
_reg(ProviderModelCapability("openai", "gpt-4o-mini", supports_structured_output=True))
_reg(ProviderModelCapability("openai", "gpt-4o", supports_structured_output=True))
_reg(
    ProviderModelCapability(
        "openai",
        "gpt-5-mini",
        supports_structured_output=True,
        max_context=400_000,
        max_output=8192,
    )
)
# GPT-5.6 Luna — added for the 100-MCQ pilot per operator-confirmed OpenAI
# documentation. Chat Completions + Structured outputs supported. Rates in
# pricing.py: input $0.20 / MTok, output $1.20 / MTok, cached input $0.02 / MTok.
_reg(
    ProviderModelCapability(
        "openai",
        "gpt-5.6-luna",
        supports_structured_output=True,
        max_output=8192,
    )
)
_reg(ProviderModelCapability("gemini", "gemini-2.0-flash", supports_structured_output=True, max_output=8192))
_reg(ProviderModelCapability("gemini", "gemini-1.5-flash", supports_structured_output=True))
_reg(
    ProviderModelCapability(
        "gemini",
        "gemini-2.5-flash",
        supports_structured_output=True,
        max_output=8192,
        max_context=1_048_576,
    )
)
_reg(
    ProviderModelCapability(
        "gemini",
        "gemini-3.6-flash",
        supports_structured_output=True,
        supports_system_prompt=True,
        max_context=1_048_576,
        max_output=65_536,
        enabled=True,
    )
)
_reg(ProviderModelCapability("mistral", "mistral-small-latest", supports_structured_output=True))
_reg(ProviderModelCapability("mistral", "mistral-large-latest", supports_structured_output=True))
_reg(
    ProviderModelCapability(
        "mistral",
        "mistral-small-2603",
        supports_structured_output=True,
        max_context=262_144,
        max_output=8192,
    )
)
_reg(
    ProviderModelCapability(
        "sarvam",
        "sarvam-105b",
        supports_structured_output=True,
        max_context=128_000,
        max_output=16_384,
    )
)
_reg(
    ProviderModelCapability(
        "sarvam",
        "sarvam-105b-conversations",
        supports_structured_output=True,
        max_context=32_000,
        max_output=16_384,
    )
)
_reg(
    ProviderModelCapability(
        "fallback", "fallback", supports_structured_output=False, supports_temperature=False, enabled=True
    )
)


def get_capability(provider: str, model: str) -> ProviderModelCapability | None:
    return _CAPABILITIES.get((provider, model))


def list_capabilities(provider: str | None = None) -> list[ProviderModelCapability]:
    caps = list(_CAPABILITIES.values())
    if provider:
        caps = [c for c in caps if c.provider == provider]
    return caps


def register_capability(cap: ProviderModelCapability) -> None:
    _reg(cap)
