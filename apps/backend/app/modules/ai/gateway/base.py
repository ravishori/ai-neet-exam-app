"""FACTORY-P3.1 AI Gateway provider contract.

Backward-compatible with existing AIProvider.generate(system_prompt, user_prompt, max_tokens).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# Normalized provider error codes (factory + gateway)
PROVIDER_BLOCKED = "PROVIDER_BLOCKED"
PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
PROVIDER_INVALID_RESPONSE = "PROVIDER_INVALID_RESPONSE"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
PROVIDER_ERROR = "PROVIDER_ERROR"
PROVIDER_COST_UNKNOWN = "PROVIDER_COST_UNKNOWN"
# Raised by a provider's own constructor when its feature flag is off (e.g.
# GeminiProvider when settings.gemini_enabled is False) — a fail-closed
# guard independent of which code path tried to construct it (CLI script,
# admin endpoint, scheduled worker, or the shared AIGateway router).
PROVIDER_DISABLED = "PROVIDER_DISABLED"


class ProviderError(Exception):
    """Normalized provider failure — never embeds secrets.

    ``http_status``/``provider_detail`` retain the real HTTP status code and
    a short, already-redacted excerpt of the provider's own response body
    (never the request, so never the Authorization header/API key) — this
    is diagnostic-only and must never be set from request data. Without
    these, every unrecognized HTTP error collapses to the same generic
    "Provider error" string, which made a real 2026-10-13 Krutrim 404
    ("Cannot POST /v1/chat/completions") indistinguishable from any other
    failure until someone bypassed this layer entirely to inspect the raw
    response.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        provider: str | None = None,
        retryable: bool = False,
        http_status: int | None = None,
        provider_detail: str | None = None,
    ):
        self.code = code
        self.provider = provider
        self.retryable = retryable
        self.http_status = http_status
        self.provider_detail = provider_detail
        if http_status is not None or provider_detail:
            message = f"{message} (http_status={http_status}, detail={provider_detail!r})"
        super().__init__(message)


@dataclass
class GenerateRequest:
    system_prompt: str
    user_prompt: str
    max_tokens: int = 1024
    model: str | None = None
    temperature: float | None = None
    correlation_id: str | None = None
    generation_run_id: str | None = None
    blueprint_id: str | None = None
    blueprint_version: int | None = None
    prompt_version: str | None = None
    require_json: bool = False


@dataclass
class AIResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    is_fallback: bool = False
    cost_usd: float = 0.0
    # FACTORY-P3.1 lineage
    provider: str = "unknown"
    total_tokens: int = 0
    cost_status: str = "ESTIMATED"  # ESTIMATED | UNAVAILABLE | EXACT
    finish_reason: str | None = None
    provider_request_id: str | None = None
    latency_ms: int = 0
    routing_policy: str | None = None
    provider_attempt_no: int = 1
    safe_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.total_tokens:
            self.total_tokens = int(self.prompt_tokens or 0) + int(self.completion_tokens or 0)


class AIProvider(ABC):
    """Every live/fake provider implements this. Content Factory must not branch on provider SDKs."""

    name: str = "unknown"

    @abstractmethod
    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        ...

    async def generate_request(self, request: GenerateRequest) -> AIResponse:
        """Optional richer entrypoint; default delegates to generate()."""
        return await self.generate(
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
            max_tokens=request.max_tokens,
        )
