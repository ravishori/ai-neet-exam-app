"""Krutrim (Ola Krutrim AI Cloud) OpenAI-compatible Chat Completions provider.

Mirrors ``GroqProvider``/``OpenRouterProvider`` exactly (see
``groq_provider.py``, ``openrouter_provider.py``): a thin
``OpenAIProvider`` subclass that only overrides the class-level ``name``
so Krutrim's identity is never ambiguous on either call path (the
``ProviderRouter``, which always overwrites ``response.provider`` with
the registry key it looked the entry up under; AND the
directly-injected-provider path used by ``AIGateway.generate()``'s
``self._injected is not None`` branch, which reads
``getattr(self._provider, "name", ...)`` — a bare ``OpenAIProvider``
instance would report ``"openai"`` there, never ``"krutrim"``).

CONFIRMED real values (from the official ``ola-krutrim/krutrim-cloud-python``
GitHub repo source + Krutrim's own AI Studio billing docs — verified via
real web fetches in the top-level research task that specified this
change; NO live network call was made anywhere in the task that
introduced this file):

- Base URL: the client's default host is ``https://cloud.olakrutrim.com``
  and the chat-completions path is ``/v1/chat/completions``, so the
  OpenAI-compatible-style base_url (matching how Groq/OpenRouter are
  configured in this codebase) is ``https://cloud.olakrutrim.com/v1``.
- Auth: ``Authorization: Bearer <api_key>`` — genuinely OpenAI-compatible,
  same header style Groq/OpenRouter already use via ``OpenAIProvider``.
- Model id: ``Krutrim-spectre-v2`` is the REAL, confirmed API model id
  (found in the official Python client's ``api.md`` and
  ``resources/chat/completions.py`` docstrings). The literal string
  ``"Krutrim-2"`` is Krutrim's catalog/marketing display name — it does
  NOT appear as a valid API ``model`` field value anywhere in the
  official source and must never be sent as one.

This is a pure additive change: it reuses 100% of ``OpenAIProvider``'s
``generate_request`` implementation (request building, response parsing,
error classification) and adds zero new behavior beyond the base_url
default and the ``name`` class attribute. It is never enabled by default
(``settings.krutrim_enabled`` defaults to ``False``) and is treated as
"not configured" by ``registry.build_registry_from_settings`` /
``mcq_llm_provider.resolve_mcq_factory_stage_selection`` whenever
``settings.krutrim_model`` is empty — the same fail-closed-on-unconfigured-
model discipline already enforced for OpenRouter.
"""

from __future__ import annotations

from app.modules.ai.gateway.openai_provider import OpenAIProvider


class KrutrimProvider(OpenAIProvider):
    """Krutrim's OpenAI-compatible Chat Completions endpoint, with
    correct "krutrim" lineage on every call path (router AND direct
    injection) — mirrors ``GroqProvider``/``OpenRouterProvider`` exactly."""

    name = "krutrim"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://cloud.olakrutrim.com/v1",
        timeout: float = 60.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout)
