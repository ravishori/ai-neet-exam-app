"""Focused tests for Multi-Model Question Candidate Factory infrastructure."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.modules.cms.acquisition.mmf.adapters import (
    AnthropicCandidateAdapter,
    GeminiCandidateAdapter,
    GenerationRequest,
    LiveGenerationDisabledError,
    OpenAICandidateAdapter,
    build_adapters,
)
from app.modules.cms.acquisition.mmf.config import (
    CH04_FIXTURE_SHA,
    DEFAULT_POC_BATCH_ID,
    build_planned_batch,
    load_allocation_config,
    provider_status_from_settings,
    redact_secrets,
)
from app.modules.cms.acquisition.mmf.guards import GuardError, assert_source_sha
from app.modules.cms.acquisition.mmf.normalize import (
    apply_exact_deduplication,
    candidate_fingerprint,
    normalize_text,
)
from app.modules.cms.acquisition.mmf.pipeline import run_dry_run
from app.modules.cms.acquisition.mmf.schemas import CandidateRecord, DifficultyTargets, GenerationBatch
from app.modules.cms.acquisition.mmf.semantic_dedupe import (
    StubSemanticDuplicateDetector,
    mark_valid_variants,
)
from app.modules.cms.acquisition.mmf.validation import validate_candidate_dict, validate_candidate_list

SHA = CH04_FIXTURE_SHA
BATCH = DEFAULT_POC_BATCH_ID


def _cand(**overrides):
    base = {
        "candidate_id": f"{BATCH}-T-0001",
        "generation_batch_id": BATCH,
        "provider": "gemini",
        "model": "test-model",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_document": "ncert-ch4.pdf",
        "source_sha256": SHA,
        "subject": "Biology",
        "class": "11",
        "chapter": "Animal Kingdom",
        "topic": "Porifera",
        "concept": "ak-porifera-characters",
        "question_type": "factual",
        "difficulty": "easy",
        "stem": "Sponges exhibit which level of organisation?",
        "options": {"A": "Cellular", "B": "Tissue", "C": "Organ", "D": "Organ system"},
        "correct_answer": "A",
        "explanation": "Sponges show cellular level.",
        "source_evidence": "sponges exhibit cellular level of organisation",
        "prompt_version": "mmf-poc-prompt-v1",
        "provenance": {
            "provider": "gemini",
            "model": "test-model",
            "prompt_version": "mmf-poc-prompt-v1",
            "batch_id": BATCH,
        },
        "status": "GENERATED",
    }
    base.update(overrides)
    if "provenance" in overrides and isinstance(overrides["provenance"], dict):
        prov = {
            "provider": base["provider"],
            "model": base["model"],
            "prompt_version": base["prompt_version"],
            "batch_id": base["generation_batch_id"],
        }
        prov.update(overrides["provenance"])
        base["provenance"] = prov
    return base


def test_candidate_schema_validation():
    cand = CandidateRecord.model_validate(_cand())
    assert cand.schema_version == "mmf_candidate_v1"
    assert cand.class_level == "11"
    assert cand.correct_answer == "A"


def test_exactly_four_options_and_one_answer():
    cand = CandidateRecord.model_validate(_cand())
    assert set(cand.options.model_dump()) == {"A", "B", "C", "D"}
    with pytest.raises(ValidationError):
        CandidateRecord.model_validate(_cand(options={"A": "x", "B": "y", "C": "z"}))


def test_malformed_candidate_rejection():
    _, errs = validate_candidate_dict(_cand(options={"A": "only"}), expected_source_sha=SHA)
    assert errs
    bad = validate_candidate_list(
        [_cand(candidate_id=f"{BATCH}-DUP"), _cand(candidate_id=f"{BATCH}-DUP")],
        expected_source_sha=SHA,
    )
    assert bad["duplicate_candidate_ids"]


def test_source_sha_validation(tmp_path: Path):
    p = tmp_path / "f.jsonl"
    p.write_bytes(b"abc")
    with pytest.raises(GuardError) as ei:
        assert_source_sha(p, SHA)
    assert ei.value.code == "SOURCE_SHA_MISMATCH"


def test_provenance_preservation():
    cand = CandidateRecord.model_validate(_cand())
    assert cand.provenance.batch_id == BATCH
    assert cand.provenance.provider == "gemini"
    with pytest.raises(ValidationError):
        CandidateRecord.model_validate(
            _cand(
                provenance={
                    "batch_id": "OTHER",
                    "provider": "gemini",
                    "model": "test-model",
                    "prompt_version": "mmf-poc-prompt-v1",
                }
            )
        )


def test_deterministic_normalization_and_exact_dedupe():
    a = CandidateRecord.model_validate(_cand(candidate_id=f"{BATCH}-A1"))
    b = CandidateRecord.model_validate(
        _cand(candidate_id=f"{BATCH}-A2", stem="  Sponges exhibit which level of organisation?  ")
    )
    assert candidate_fingerprint(
        stem=a.stem, options=a.options.model_dump(), correct_answer=a.correct_answer
    ) == candidate_fingerprint(
        stem=b.stem, options=b.options.model_dump(), correct_answer=b.correct_answer
    )
    out = apply_exact_deduplication([a, b])
    assert out[0].status.value == "VALID"
    assert out[1].status.value == "EXACT_DUPLICATE"
    assert out[1].duplicate_of == out[0].candidate_id
    assert normalize_text("  Foo\u00a0Bar  ") == normalize_text("foo bar")


@pytest.mark.asyncio
async def test_semantic_dedupe_interface_and_valid_variant():
    a = CandidateRecord.model_validate(_cand(candidate_id=f"{BATCH}-S1"))
    b = CandidateRecord.model_validate(
        _cand(
            candidate_id=f"{BATCH}-S2",
            stem="Which animals show cellular organisation?",
            options={"A": "Sponges", "B": "Insects", "C": "Birds", "D": "Frogs"},
        )
    )
    deduped = apply_exact_deduplication([a, b])
    sem = await StubSemanticDuplicateDetector().detect(deduped)
    assert sem.metadata["external_embedding_calls"] == 0
    variants = mark_valid_variants(deduped, shared_concept="ak-porifera-characters")
    assert all(v.concept == "ak-porifera-characters" for v in variants)


@pytest.mark.asyncio
async def test_provider_adapters_dry_run_and_missing_live():
    adapters = build_adapters()
    assert set(adapters) >= {"gemini", "anthropic", "openai", "mistral"}
    for name, adapter in adapters.items():
        req = GenerationRequest(
            source_material="x",
            source_document="doc",
            source_sha256=SHA,
            generation_batch_id=BATCH,
            subject="Biology",
            class_level="11",
            chapter="Animal Kingdom",
            requested_count=10,
            provider=name,
            model="m",
            prompt_version="mmf-poc-prompt-v1",
            allow_live=False,
        )
        res = await adapter.generate_candidates(req)
        assert res.dry_run is True
        assert res.candidates == []
        assert res.metadata["external_http_calls"] == 0
    with pytest.raises(LiveGenerationDisabledError):
        await GeminiCandidateAdapter().generate_candidates(
            GenerationRequest(
                source_material="x",
                source_document="doc",
                source_sha256=SHA,
                generation_batch_id=BATCH,
                subject="Biology",
                class_level="11",
                chapter="Animal Kingdom",
                requested_count=1,
                provider="gemini",
                model="m",
                prompt_version="mmf-poc-prompt-v1",
                allow_live=True,
            )
        )
    assert isinstance(AnthropicCandidateAdapter(), AnthropicCandidateAdapter)
    assert isinstance(OpenAICandidateAdapter(), OpenAICandidateAdapter)


def test_secret_redaction_and_provider_status():
    raw = {"api_key": "should-not-leak", "nested": {"authorization": "Bearer x"}, "ok": 1}
    red = redact_secrets(raw)
    assert red["api_key"] == "***REDACTED***"
    assert "should-not-leak" not in json.dumps(red)
    statuses = provider_status_from_settings()
    assert all(hasattr(s, "api_key_configured") for s in statuses)


def test_allocation_and_batch_creation():
    alloc = load_allocation_config()
    assert alloc["requested_candidate_count"] == 1000
    assert sum(p["requested_count"] for p in alloc["providers"]) == 1000
    batch = build_planned_batch(
        source_path="docs/x.jsonl",
        source_sha256=SHA,
        allocation=alloc,
        created_at=datetime.now(UTC),
    )
    assert isinstance(batch, GenerationBatch)
    assert batch.batch_id == BATCH
    assert batch.live_generation_enabled is False
    with pytest.raises(ValidationError):
        DifficultyTargets(easy=0.5, medium=0.5, hard=0.5)


@pytest.mark.asyncio
async def test_dry_run_no_contentitem_mutation():
    """Dry-run without DB session still validates pipeline; no CMS writes."""
    result = await run_dry_run(session=None, write_artifacts=False)
    assert result["external_ai_calls"] == 0
    assert result["content_workflow_calls"] == 0
    assert result["demo_pipeline"]["malformed_rejected"] is True
    assert result["demo_pipeline"]["exact_duplicates"] >= 1
    assert result["source_sha256"] == SHA


def test_idempotent_allocation_defaults():
    a = load_allocation_config()
    b = load_allocation_config()
    assert a == b
