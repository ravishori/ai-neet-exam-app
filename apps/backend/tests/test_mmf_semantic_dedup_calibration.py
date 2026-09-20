"""Tests for MMF semantic embedding input, cache, calibration clustering."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.modules.cms.acquisition.mmf.config import (
    CH04_FIXTURE_SHA,
    DEFAULT_POC_BATCH_ID,
    redact_secrets,
)
from app.modules.cms.acquisition.mmf.embedding_backends import (
    DEFAULT_OPENAI_EMBEDDING_DIMENSION,
    EmbeddingConfigurationError,
    embedding_status_from_settings,
)
from app.modules.cms.acquisition.mmf.semantic_calibration import (
    classify_pair,
    clusters_at_threshold,
    compute_pairwise_scores,
    cross_provider_stats,
    representative_score,
)
from app.modules.cms.acquisition.mmf.semantic_dedupe import SemanticDedupConfig, cosine_similarity
from app.modules.cms.acquisition.mmf.semantic_input import (
    EmbeddingDiskCache,
    build_semantic_input,
    cache_key_for_embedding,
    semantic_input_hash,
)

SHA = CH04_FIXTURE_SHA
BATCH = DEFAULT_POC_BATCH_ID


def _raw(**overrides):
    base = {
        "candidate_id": f"{BATCH}-SD-1",
        "provider": "gemini",
        "stem": "Sponges exhibit which level of organisation?",
        "options": {"A": "Cellular", "B": "Tissue", "C": "Organ", "D": "Organ system"},
        "correct_answer": "A",
        "explanation": "should not appear in semantic input",
        "generated_at": datetime.now(UTC).isoformat(),
        "provider_metadata": {"slot": 1},
    }
    base.update(overrides)
    return base


def test_deterministic_semantic_input_excludes_explanation_and_metadata():
    a = build_semantic_input(_raw())
    b = build_semantic_input(
        _raw(
            explanation="different explanation",
            generated_at="2099-01-01T00:00:00Z",
            provider_metadata={"slot": 99, "foo": "bar"},
        )
    )
    assert a == b
    assert "should not appear" not in a
    assert "explanation" not in a.lower()
    assert "STEM:" in a and "ANSWER:A" in a
    assert semantic_input_hash(_raw()) == semantic_input_hash(_raw(explanation="x"))


def test_embedding_cache_key_stable_and_no_secrets(tmp_path: Path):
    h = semantic_input_hash(_raw())
    k1 = cache_key_for_embedding(
        semantic_input_sha256=h,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        embedding_configuration_version="mmf-embedding-config-v1",
    )
    k2 = cache_key_for_embedding(
        semantic_input_sha256=h,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        embedding_configuration_version="mmf-embedding-config-v1",
    )
    assert k1 == k2
    assert "sk-" not in k1

    cache = EmbeddingDiskCache(tmp_path)
    cache.put(
        k1,
        [0.1] * 8,
        candidate_id="c1",
        semantic_input_sha256=h,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=8,
    )
    got = cache.get(k1)
    assert got == [0.1] * 8
    assert cache.hits == 1
    blob = (tmp_path / f"{k1}.json").read_text(encoding="utf-8")
    assert "api_key" not in blob


def test_embedding_dimension_validation_in_status():
    st = embedding_status_from_settings()
    assert st["preferred_dimension"] == DEFAULT_OPENAI_EMBEDDING_DIMENSION
    assert st["null_fallback_forbidden_for_executed_claim"] is True
    red = redact_secrets({"api_key": "secret", "ok": 1})
    assert red["api_key"] == "***REDACTED***"


def test_similarity_and_threshold_config():
    assert abs(cosine_similarity([1, 0], [1, 0]) - 1.0) < 1e-9
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    cfg = SemanticDedupConfig(similarity_threshold=0.92, calibrated=False)
    assert cfg.calibrated is False
    with pytest.raises(ValueError):
        SemanticDedupConfig(similarity_threshold=0.0)


def test_cluster_construction_and_cross_provider():
    ids = ["a", "b", "c"]
    providers = ["gemini", "anthropic", "openai"]
    vectors = [[1.0, 0.0], [0.99, 0.01], [0.0, 1.0]]
    fps = ["fp1", "fp2", "fp3"]
    pairs = compute_pairwise_scores(
        candidate_ids=ids, providers=providers, vectors=vectors, fingerprints=fps, min_score_to_keep=0.5
    )
    assert pairs
    clusters = clusters_at_threshold(pairs, threshold=0.90, all_ids=ids)
    assert any(p.similarity_score >= 0.9 for p in pairs) or clusters
    xp = cross_provider_stats(pairs, threshold=0.90)
    assert "gemini_anthropic" in xp
    assert classify_pair(0.99, threshold=0.92, exact=False) == "SEMANTIC_DUPLICATE"
    assert classify_pair(1.0, threshold=0.92, exact=True) == "EXACT_DUPLICATE"


def test_representative_proposal_scoring():
    sc, reasons = representative_score(
        candidate_id="x",
        grounding_hint="DIRECT",
        structural_codes=[],
        type_mismatch=False,
        difficulty_disagree=False,
        concept_unresolved=False,
        explanation_fail=False,
    )
    assert sc > 1.0
    assert reasons
    sc2, _ = representative_score(
        candidate_id="y",
        grounding_hint="WEAK/UNCLEAR",
        structural_codes=["DUPLICATE_OPTIONS"],
        type_mismatch=True,
        difficulty_disagree=True,
        concept_unresolved=True,
        explanation_fail=True,
    )
    assert sc2 < sc


def test_no_source_artifact_mutation(tmp_path: Path):
    src = tmp_path / "candidates_normalized.jsonl"
    row = {
        "candidate_id": "x",
        "stem": "Q?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "correct_answer": "A",
    }
    src.write_text(json.dumps(row) + "\n", encoding="utf-8")
    before = src.read_bytes()
    _ = build_semantic_input(row)
    _ = semantic_input_hash(row)
    assert src.read_bytes() == before


def test_select_backend_refuses_without_key():
    from app.modules.cms.acquisition.mmf import embedding_backends as eb

    class FakeSettings:
        openai_api_key = ""
        openai_enabled = True
        openai_model = "x"
        gemini_api_key = ""
        gemini_enabled = False
        anthropic_api_key = ""

    with pytest.raises(EmbeddingConfigurationError):
        eb.select_production_embedding_backend(FakeSettings())  # type: ignore[arg-type]
