"""Deterministic semantic input representation + disk cache for MMF embeddings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.modules.cms.acquisition.mmf.normalize import normalize_text

SEMANTIC_INPUT_VERSION = "mmf-semantic-input-v1"


def build_semantic_input(raw: dict[str, Any]) -> str:
    """Deterministic text for embedding: stem + options A-D + correct answer.

    Excludes explanation, provider metadata, timestamps.
    """
    opts = raw.get("options") or {}
    stem = normalize_text(str(raw.get("stem") or ""))
    a = normalize_text(str(opts.get("A") or ""))
    b = normalize_text(str(opts.get("B") or ""))
    c = normalize_text(str(opts.get("C") or ""))
    d = normalize_text(str(opts.get("D") or ""))
    ans = str(raw.get("correct_answer") or "").strip().upper()
    # Fixed field order for reproducibility
    return (
        f"{SEMANTIC_INPUT_VERSION}\n"
        f"STEM:{stem}\n"
        f"A:{a}\n"
        f"B:{b}\n"
        f"C:{c}\n"
        f"D:{d}\n"
        f"ANSWER:{ans}"
    )


def semantic_input_hash(raw: dict[str, Any]) -> str:
    blob = build_semantic_input(raw).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def cache_key_for_embedding(
    *,
    semantic_input_sha256: str,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_configuration_version: str,
) -> str:
    material = "|".join(
        [
            embedding_configuration_version,
            embedding_provider,
            embedding_model,
            str(embedding_dimension),
            semantic_input_sha256,
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class EmbeddingDiskCache:
    """Cache vectors by deterministic key. Never stores API credentials."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> list[float] | None:
        path = self._path(key)
        if not path.exists():
            self.misses += 1
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if "api_key" in data or "authorization" in data:
            raise RuntimeError("cache_file_contains_forbidden_secret_fields")
        vec = data.get("vector")
        if not isinstance(vec, list):
            self.misses += 1
            return None
        self.hits += 1
        return [float(x) for x in vec]

    def put(
        self,
        key: str,
        vector: list[float],
        *,
        candidate_id: str,
        semantic_input_sha256: str,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        payload = {
            "cache_key": key,
            "candidate_id": candidate_id,
            "semantic_input_sha256": semantic_input_sha256,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "embedding_dimension": embedding_dimension,
            "vector": vector,
        }
        self._path(key).write_text(json.dumps(payload), encoding="utf-8")


__all__ = [
    "EmbeddingDiskCache",
    "SEMANTIC_INPUT_VERSION",
    "build_semantic_input",
    "cache_key_for_embedding",
    "semantic_input_hash",
]
