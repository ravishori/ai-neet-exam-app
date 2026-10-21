"""OpenRouter OpenAI-compatible Chat Completions provider.

MCQ-FACTORY-OPENROUTER-001 — wires OpenRouter (openrouter.ai) into the
existing MCQ Factory the same way MCQ-FACTORY-GROQ-001 wired Groq in, and
the same way MCQ-FACTORY-PROVIDER-AGNOSTIC-001 later gave Groq its own
``GroqProvider(OpenAIProvider)`` subclass (see ``groq_provider.py``,
``sarvam_provider.py``) instead of reusing a bare ``OpenAIProvider``
instance: a thin subclass that only overrides the class-level ``name`` so
OpenRouter's identity is never ambiguous on either call path (the
``ProviderRouter``, which always overwrites ``response.provider`` with
the registry key it looked the entry up under; AND the
directly-injected-provider path used by
``AIGateway.generate()``'s ``self._injected is not None`` branch, which
reads ``getattr(self._provider, "name", ...)`` — a bare ``OpenAIProvider``
instance would report ``"openai"`` there, never ``"openrouter"``).

OpenRouter's Chat Completions endpoint
(https://openrouter.ai/api/v1/chat/completions) is OpenAI-wire-compatible,
which is the whole reason this reuses ``OpenAIProvider``'s HTTP logic
unchanged (no new network client, no new wire format, no new SDK
dependency) rather than writing a bespoke client.

This is a pure additive change: it reuses 100% of ``OpenAIProvider``'s
``generate_request`` implementation (request building, response parsing,
error classification) and adds zero new behavior beyond the base_url
default and the ``name`` class attribute. It is never enabled by default
(``settings.openrouter_enabled`` defaults to ``False``) and is treated as
"not configured" by ``registry.build_registry_from_settings`` /
``mcq_llm_provider.resolve_mcq_factory_stage_selection`` whenever
``settings.openrouter_model`` is empty/placeholder — see those modules'
docstrings. No live network call was made anywhere in the task that
introduced this file.
"""

from __future__ import annotations

from app.modules.ai.gateway.openai_provider import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter's OpenAI-compatible Chat Completions endpoint, with
    correct "openrouter" lineage on every call path (router AND direct
    injection) — mirrors ``GroqProvider``/``SarvamProvider`` exactly."""

    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 60.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout)
