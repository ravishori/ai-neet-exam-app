"""DeepSeek OpenAI-compatible Chat Completions provider.

Mirrors ``GroqProvider``/``OpenRouterProvider``/``KrutrimProvider`` exactly
(see ``groq_provider.py``, ``openrouter_provider.py``, ``krutrim_provider.py``):
a thin ``OpenAIProvider`` subclass that only overrides the class-level
``name`` so DeepSeek's identity is never ambiguous on either call path (the
``ProviderRouter``, which always overwrites ``response.provider`` with
the registry key it looked the entry up under; AND the
directly-injected-provider path used by ``AIGateway.generate()``'s
``self._injected is not None`` branch, which reads
``getattr(self._provider, "name", ...)`` — a bare ``OpenAIProvider``
instance would report ``"openai"`` there, never ``"deepseek"``).

CONFIRMED real values (from DeepSeek's official docs at
api-docs.deepseek.com, verified via real web fetches in the top-level
research task that specified this change; NO live network call was made
anywhere in the task that introduced this file):

- Base URL: DeepSeek's real, documented endpoint is
  ``https://api.deepseek.com/chat/completions`` — i.e. there is NO
  ``/v1`` path segment, UNLIKE Groq/OpenRouter/Krutrim above, whose
  base_urls all end in ``/v1`` (their real endpoints live under that
  path). ``OpenAIProvider.generate_request`` always builds the URL as
  ``f"{self._base_url}/chat/completions"`` (see openai_provider.py), so
  DeepSeek's ``base_url`` default here MUST be exactly
  ``https://api.deepseek.com`` — appending ``/v1`` would silently point
  at a URL DeepSeek does not serve. A future maintainer "fixing" this to
  match the other three providers' ``/v1``-suffixed pattern would BREAK
  DeepSeek — this is a deliberate, confirmed difference, not an
  oversight.
- Auth: ``Authorization: Bearer <api_key>`` — genuinely OpenAI-compatible,
  same header style Groq/OpenRouter/Krutrim already use via
  ``OpenAIProvider``.
- Model id: ``deepseek-flash`` is the REAL, current, confirmed API model
  id (DeepSeek-V4.1-Flash under the hood). The legacy aliases
  ``deepseek-v4-flash``/``deepseek-chat`` are deprecated/being phased out
  and must never be used as the default.

This is a pure additive change: it reuses 100% of ``OpenAIProvider``'s
``generate_request`` implementation (request building, response parsing,
error classification) and adds zero new behavior beyond the base_url
default and the ``name`` class attribute. It is never enabled by default
(``settings.deepseek_enabled`` defaults to ``False``) and is treated as
"not configured" by ``registry.build_registry_from_settings`` /
``mcq_llm_provider.resolve_mcq_factory_stage_selection`` whenever
``settings.deepseek_model`` is empty — the same fail-closed-on-unconfigured-
model discipline already enforced for OpenRouter/Krutrim.
"""

from __future__ import annotations

from app.modules.ai.gateway.openai_provider import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek's OpenAI-compatible Chat Completions endpoint, with
    correct "deepseek" lineage on every call path (router AND direct
    injection) — mirrors ``GroqProvider``/``OpenRouterProvider``/
    ``KrutrimProvider`` exactly.

    NOTE the base_url default below has NO ``/v1`` suffix, unlike the
    other three providers in this module family — see the module
    docstring above for why that is correct, confirmed, and
    intentional."""

    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://api.deepseek.com",
        timeout: float = 60.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout)
