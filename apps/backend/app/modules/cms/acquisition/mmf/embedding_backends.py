"""Production embedding backends for MMF — implements existing EmbeddingBackend.

Uses Settings chat API keys for OpenAI Embeddings API only.
Never logs or returns secrets. Does not route through chat/completions.
"""

from __future__ import annotations

from typing import Any, Sequence

import httpx

from app.core.config import Settings, get_settings
from app.modules.cms.acquisition.mmf.semantic_dedupe import EmbeddingBackend

# Reproducible configuration (not secrets)
EMBEDDING_CONFIGURATION_VERSION = "mmf-embedding-config-v1"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_OPENAI_EMBEDDING_DIMENSION = 1536
OPENAI_EMBED_BATCH_SIZE = 64
OPENAI_EMBED_MAX_TEXTS = 919


class EmbeddingConfigurationError(RuntimeError):
    """Raised when no safe production embedding backend can be selected."""


def embedding_status_from_settings(settings: Settings | None = None) -> dict[str, Any]:
    """Boolean/config status only — never include secret values."""
    s = settings or get_settings()
    return {
        "embedding_configuration_version": EMBEDDING_CONFIGURATION_VERSION,
        "preferred_provider": "openai",
        "preferred_model": DEFAULT_OPENAI_EMBEDDING_MODEL,
        "preferred_dimension": DEFAULT_OPENAI_EMBEDDING_DIMENSION,
        "openai": {
            "api_key_configured": bool((s.openai_api_key or "").strip()),
            "enabled_flag": bool(s.openai_enabled),
            "chat_model": s.openai_model,
            "embedding_model": DEFAULT_OPENAI_EMBEDDING_MODEL,
            "embedding_dimension": DEFAULT_OPENAI_EMBEDDING_DIMENSION,
            "embeddings_endpoint": "https://api.openai.com/v1/embeddings",
        },
        "gemini": {
            "api_key_configured": bool((s.gemini_api_key or "").strip()),
            "enabled_flag": bool(s.gemini_enabled),
            "note": "Not selected as primary embedding backend for this calibration gate",
        },
        "anthropic": {
            "api_key_configured": bool((s.anthropic_api_key or "").strip()),
            "note": "No standard embeddings API in this stack",
        },
        "null_fallback_forbidden_for_executed_claim": True,
    }


def select_production_embedding_backend(
    settings: Settings | None = None,
) -> EmbeddingBackend:
    """Select a real backend or raise — never silently return NullEmbeddingBackend."""
    s = settings or get_settings()
    status = embedding_status_from_settings(s)
    if status["openai"]["api_key_configured"] and status["openai"]["enabled_flag"]:
        return OpenAIEmbeddingBackend(
            api_key=s.openai_api_key,
            model=DEFAULT_OPENAI_EMBEDDING_MODEL,
            dimensions=DEFAULT_OPENAI_EMBEDDING_DIMENSION,
        )
    missing = []
    if not status["openai"]["api_key_configured"]:
        missing.append("openai_api_key empty")
    if not status["openai"]["enabled_flag"]:
        missing.append("openai_enabled=false")
    raise EmbeddingConfigurationError(
        "No safe production embedding backend available. "
        f"Missing/blocked: {', '.join(missing) or 'unknown'}. "
        "Refusing NullEmbeddingBackend fallback for EXECUTED claims."
    )


class OpenAIEmbeddingBackend(EmbeddingBackend):
    """OpenAI /v1/embeddings — implements MMF EmbeddingBackend (provider-neutral boundary)."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
        dimensions: int = DEFAULT_OPENAI_EMBEDDING_DIMENSION,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
        batch_size: int = OPENAI_EMBED_BATCH_SIZE,
        max_texts: int = OPENAI_EMBED_MAX_TEXTS,
    ):
        if not (api_key or "").strip():
            raise EmbeddingConfigurationError("OpenAIEmbeddingBackend requires api_key")
        self._api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self.batch_size = batch_size
        self.max_texts = max_texts
        self.http_calls = 0
        self.tokens_estimated = 0

    def config_manifest(self) -> dict[str, Any]:
        return {
            "embedding_provider": self.name,
            "embedding_model": self.model,
            "embedding_dimension": self.dimensions,
            "embedding_configuration_version": EMBEDDING_CONFIGURATION_VERSION,
            "batch_size": self.batch_size,
            "max_texts": self.max_texts,
            "api_key_configured": True,
            # never include api_key
        }

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if len(texts) > self.max_texts:
            raise EmbeddingConfigurationError(
                f"refusing to embed {len(texts)} texts; max_texts={self.max_texts}"
            )
        if not texts:
            return []
        out: list[list[float]] = []
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for start in range(0, len(texts), self.batch_size):
                batch = list(texts[start : start + self.batch_size])
                payload = {
                    "model": self.model,
                    "input": batch,
                    "dimensions": self.dimensions,
                }
                self.http_calls += 1
                resp = await client.post(
                    f"{self._base_url}/embeddings",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code >= 400:
                    # Do not include response body if it might echo secrets
                    raise EmbeddingConfigurationError(
                        f"openai_embeddings_http_{resp.status_code}:{resp.text[:200]}"
                    )
                data = resp.json()
                usage = data.get("usage") or {}
                self.tokens_estimated += int(usage.get("total_tokens") or 0)
                items = data.get("data") or []
                # OpenAI may return out of order — sort by index
                items = sorted(items, key=lambda x: int(x.get("index", 0)))
                if len(items) != len(batch):
                    raise EmbeddingConfigurationError(
                        f"openai_embeddings_count_mismatch:{len(items)}!={len(batch)}"
                    )
                for item in items:
                    vec = item.get("embedding")
                    if not isinstance(vec, list) or len(vec) != self.dimensions:
                        raise EmbeddingConfigurationError(
                            f"openai_embeddings_bad_dimension:"
                            f"{len(vec) if isinstance(vec, list) else type(vec)}"
                        )
                    out.append([float(x) for x in vec])
        return out


__all__ = [
    "DEFAULT_OPENAI_EMBEDDING_DIMENSION",
    "DEFAULT_OPENAI_EMBEDDING_MODEL",
    "EMBEDDING_CONFIGURATION_VERSION",
    "EmbeddingConfigurationError",
    "OpenAIEmbeddingBackend",
    "embedding_status_from_settings",
    "select_production_embedding_backend",
]
