"""Sarvam OpenAI-compatible Chat Completions provider."""

from __future__ import annotations

from app.modules.ai.gateway.openai_provider import OpenAIProvider


class SarvamProvider(OpenAIProvider):
    """Use Sarvam's OpenAI-compatible v1 endpoint with Sarvam lineage."""

    name = "sarvam"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://api.sarvam.ai/v1",
        timeout: float = 60.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout)
