"""Groq OpenAI-compatible Chat Completions provider.

MCQ-FACTORY-PROVIDER-AGNOSTIC-001 (follow-up to MCQ-FACTORY-GROQ-001).

``registry.py`` originally reused ``OpenAIProvider`` directly (no
subclass) for both the registry's single "groq" slot and the separate
verification-model instance built by
``registry.construct_groq_verification_provider``. That is fine on the
``ProviderRouter`` call path (``router.py`` always overwrites
``response.provider`` with the registry key it looked the entry up
under, regardless of the instance's own ``.name``), but it left a latent
attribution gap on any DIRECTLY-INJECTED call path — i.e.
``AIGateway.generate()``'s ``self._injected is not None`` branch, used by
``GatewayMcqVerificationProvider`` and the new
``mcq_llm_provider.build_mcq_factory_stage_caller``. That branch reads
``getattr(self._provider, "name", ...)``, which for a bare
``OpenAIProvider`` instance is always the class attribute ``"openai"`` —
never ``"groq"`` — so structlog's ``ai_request`` log line (and any future
code that trusts ``AIResponse.provider``/the injected instance's
``.name`` instead of a separately-threaded registry name) would silently
attribute a Groq call to "openai".

``SarvamProvider`` already solved exactly this for Sarvam with a thin
``OpenAIProvider`` subclass that only overrides the class-level ``name``
(see ``sarvam_provider.py``). ``GroqProvider`` mirrors that existing,
proven pattern so Groq's identity is never ambiguous on an injected call
path either — while still reusing 100% of ``OpenAIProvider``'s HTTP
logic (no new network client, no new wire format; Groq's Chat
Completions endpoint is OpenAI-wire-compatible, which is the whole reason
MCQ-FACTORY-GROQ-001 could reuse ``OpenAIProvider`` in the first place).

This is a pure additive fix: every existing call site that worked before
(``isinstance(entry.instance, OpenAIProvider)`` still holds for a
``GroqProvider`` instance since it is an ``OpenAIProvider`` subclass) is
unaffected; only the previously-wrong ``.name`` value changes from
``"openai"`` to the correct ``"groq"``.
"""

from __future__ import annotations

from app.modules.ai.gateway.openai_provider import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """Groq's OpenAI-compatible Chat Completions endpoint, with correct
    "groq" lineage on every call path (router AND direct-injection)."""

    name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout: float = 60.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout)
