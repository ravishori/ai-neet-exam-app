"""Provider-neutral candidate generation adapters (no ContentItem coupling)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.modules.cms.acquisition.mmf.config import ProviderConfigStatus, provider_status_from_settings
from app.modules.cms.acquisition.mmf.schemas import CandidateRecord


class LiveGenerationDisabledError(RuntimeError):
    """Raised when a live provider call is attempted without explicit authorization."""


@dataclass
class GenerationRequest:
    source_material: str
    source_document: str
    source_sha256: str
    generation_batch_id: str
    subject: str
    class_level: str
    chapter: str
    requested_count: int
    provider: str
    model: str
    prompt_version: str
    difficulty_targets: dict[str, float] = field(default_factory=dict)
    allow_live: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    candidates: list[CandidateRecord]
    provider: str
    model: str
    dry_run: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class CandidateProviderAdapter(ABC):
    """Provider adapter for MMF candidates. Must not call ContentWorkflowService."""

    name: str = "unknown"

    @abstractmethod
    async def generate_candidates(self, request: GenerationRequest) -> GenerationResult:
        ...

    def status(self) -> ProviderConfigStatus:
        for row in provider_status_from_settings():
            if row.provider == self.name:
                return row
        return ProviderConfigStatus(
            provider=self.name,
            enabled_flag=False,
            api_key_configured=False,
            model="",
            live_calls_allowed=False,
            detail="unknown",
        )


class DryRunAdapter(CandidateProviderAdapter):
    """Instantiable adapter that never performs network I/O."""

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

    async def generate_candidates(self, request: GenerationRequest) -> GenerationResult:
        if request.allow_live:
            raise LiveGenerationDisabledError(
                f"Live generation is not authorized in this milestone for provider={self.name}"
            )
        # Verify request is well-formed without inventing candidates
        if request.requested_count < 0:
            raise ValueError("requested_count must be >= 0")
        if request.source_sha256 != request.source_sha256.lower():
            raise ValueError("source_sha256 must be lowercase hex")
        return GenerationResult(
            candidates=[],
            provider=self.name,
            model=request.model or self.model,
            dry_run=True,
            metadata={
                "mode": "dry_run",
                "would_request": request.requested_count,
                "external_http_calls": 0,
                "content_workflow_calls": 0,
                "instantiated_at": datetime.now(UTC).isoformat(),
            },
        )


class GeminiCandidateAdapter(DryRunAdapter):
    def __init__(self, model: str | None = None):
        st = next((p for p in provider_status_from_settings() if p.provider == "gemini"), None)
        super().__init__("gemini", model or (st.model if st else "gemini-2.0-flash"))


class AnthropicCandidateAdapter(DryRunAdapter):
    def __init__(self, model: str | None = None):
        st = next((p for p in provider_status_from_settings() if p.provider == "anthropic"), None)
        super().__init__("anthropic", model or (st.model if st else "claude-sonnet-4-6"))


class OpenAICandidateAdapter(DryRunAdapter):
    def __init__(self, model: str | None = None):
        st = next((p for p in provider_status_from_settings() if p.provider == "openai"), None)
        super().__init__("openai", model or (st.model if st else "gpt-4o-mini"))


class ExtensibleCandidateAdapter(DryRunAdapter):
    """Third/future provider slot (e.g. mistral or custom)."""

    def __init__(self, name: str = "mistral", model: str | None = None):
        st = next((p for p in provider_status_from_settings() if p.provider == name), None)
        super().__init__(name, model or (st.model if st else name))


def build_adapters() -> dict[str, CandidateProviderAdapter]:
    return {
        "gemini": GeminiCandidateAdapter(),
        "anthropic": AnthropicCandidateAdapter(),
        "openai": OpenAICandidateAdapter(),
        "mistral": ExtensibleCandidateAdapter("mistral"),
    }
