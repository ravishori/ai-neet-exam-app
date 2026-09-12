"""Contract V2 / validator / retry / semantic-dedup interface tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.modules.cms.acquisition.mmf.approved_concepts import APPROVED_CONCEPT_CODES
from app.modules.cms.acquisition.mmf.audit import (
    audit_candidate_metadata,
    audit_difficulty_report,
    audit_question_type_report,
)
from app.modules.cms.acquisition.mmf.config import CH04_FIXTURE_SHA, DEFAULT_POC_BATCH_ID
from app.modules.cms.acquisition.mmf.contract_v2 import (
    CONTRACT_VERSION,
    PROMPT_VERSION_V2,
    PROVIDER_CAPS,
    SYSTEM_PROMPT_V2,
    TOTAL_CAP,
    contract_v2_document,
)
from app.modules.cms.acquisition.mmf.reliability import ProviderReliabilityMetrics, classify_provider_error
from app.modules.cms.acquisition.mmf.retry import (
    AllocationCapError,
    RetryPolicy,
    assert_allocation_caps,
    assert_no_cross_provider_fill,
    execute_with_retry,
)
from app.modules.cms.acquisition.mmf.schemas import CandidateRecord
from app.modules.cms.acquisition.mmf.semantic_dedupe import (
    ConfigurableSemanticDuplicateDetector,
    HashBagEmbeddingBackend,
    NullEmbeddingBackend,
    SemanticDedupConfig,
    StubSemanticDuplicateDetector,
)
from app.modules.cms.acquisition.mmf.validation_v2 import (
    resolve_concept,
    structural_answer_checks,
    validate_candidate_v2,
)

SHA = CH04_FIXTURE_SHA
BATCH = DEFAULT_POC_BATCH_ID


def _cand(**overrides):
    base = {
        "candidate_id": f"{BATCH}-V2-0001",
        "generation_batch_id": BATCH,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
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
        "explanation": "Sponges show cellular level of organisation as stated in NCERT.",
        "source_evidence": "sponges exhibit cellular level of organisation",
        "prompt_version": PROMPT_VERSION_V2,
        "provenance": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "prompt_version": PROMPT_VERSION_V2,
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


def test_contract_v2_document_and_prompt():
    doc = contract_v2_document()
    assert doc["contract_version"] == CONTRACT_VERSION
    assert doc["allocation_caps"]["anthropic"] == 400
    assert doc["allocation_caps"]["total"] == TOTAL_CAP
    assert "independently audited" in SYSTEM_PROMPT_V2.lower() or "independently audited" in doc["system_prompt_v2"].lower()
    assert doc["metadata_policy"]["authority"].startswith("AUDITED")
    assert sum(PROVIDER_CAPS.values()) == TOTAL_CAP


def test_declared_vs_audited_question_type_match_and_mismatch():
    match = audit_question_type_report(
        "Sponges exhibit which level of organisation?",
        "factual",
    )
    assert match.status == "MATCH"
    assert match.audited in {"FACTUAL", "DIRECT"}

    mismatch = audit_question_type_report(
        "Consider the following statements about coelom and select the correct option:",
        "factual",
    )
    assert mismatch.status == "MISMATCH"
    assert mismatch.audited == "MULTI_STATEMENT"
    assert mismatch.reason_code.startswith("TYPE_MISMATCH")


def test_declared_vs_audited_difficulty():
    easy = audit_difficulty_report(
        stem="What is Sycon an example of?",
        declared_difficulty="easy",
        question_type="factual",
        options={"A": "Porifera", "B": "Cnidaria", "C": "Annelida", "D": "Mollusca"},
    )
    assert easy.audited in {"EASY", "MEDIUM", "UNCERTAIN"}
    hard_decl_easy = audit_difficulty_report(
        stem=(
            "Consider the following statements about chordates and select the incorrect one: "
            "(i) Notochord (ii) Dorsal hollow nerve cord (iii) Pharyngeal gill slits "
            "(iv) Ventral heart exclusively in invertebrates — which statement is wrong?"
        ),
        declared_difficulty="easy",
        question_type="multi_statement",
        options={
            "A": "long option one about notochord presence throughout life in all vertebrates",
            "B": "long option two about nerve cord orientation and embryonic origin details",
            "C": "long option three about pharyngeal slits and their adult derivatives",
            "D": "long option four combining multiple chordate features incorrectly",
        },
    )
    assert hard_decl_easy.agreement is False or hard_decl_easy.audited == "UNCERTAIN"
    meta = audit_candidate_metadata(_cand())
    assert "declared_question_type" in meta and "audited_question_type" in meta
    assert "declared_difficulty" in meta and "audited_difficulty" in meta


def test_answer_letter_and_explanation_consistency():
    findings = structural_answer_checks(
        _cand(explanation="The correct answer is B because tissue level is present.")
    )
    codes = {f.reason_code for f in findings}
    assert "EXPLANATION_CONTRADICTS_ANSWER_LETTER" in codes

    findings2 = structural_answer_checks(
        _cand(
            correct_answer_text="Tissue",
            correct_answer="A",
        )
    )
    assert any(f.reason_code == "ANSWER_TEXT_MISMATCH_SELECTED_OPTION" for f in findings2)

    findings3 = structural_answer_checks(
        _cand(options={"A": "Cellular", "B": "Cellular", "C": "Organ", "D": "Organ system"})
    )
    assert any(f.reason_code == "DUPLICATE_OPTIONS" for f in findings3)


def test_free_text_concept_unresolved():
    status, code, reason = resolve_concept("Some Free Text Label About Sponges")
    assert status == "UNRESOLVED"
    assert code is None
    assert reason == "CONCEPT_FREE_TEXT_NOT_IN_APPROVED_SET"

    status2, code2, reason2 = resolve_concept("ak-porifera-characters")
    assert status2 == "RESOLVED"
    assert code2 == "ak-porifera-characters"
    assert "ak-porifera-characters" in APPROVED_CONCEPT_CODES

    res = validate_candidate_v2(_cand(concept="Porifera Characters Free Text"), expected_source_sha=SHA)
    assert res.concept_status == "UNRESOLVED"
    assert res.mutated is False


@pytest.mark.asyncio
async def test_semantic_duplicate_interface_and_threshold_config():
    with pytest.raises(ValueError):
        SemanticDedupConfig(similarity_threshold=1.5)

    cfg = SemanticDedupConfig(similarity_threshold=0.88, calibrated=False)
    assert cfg.calibrated is False
    assert "calibration" in cfg.calibration_note.lower()

    a = CandidateRecord.model_validate(_cand(candidate_id=f"{BATCH}-SEM-1"))
    b = CandidateRecord.model_validate(
        _cand(
            candidate_id=f"{BATCH}-SEM-2",
            stem="Sponges exhibit which level of organisation?",
            options={"A": "Cellular", "B": "Tissue", "C": "Organ", "D": "Organ system"},
        )
    )
    stub = await StubSemanticDuplicateDetector().detect([a, b], config=cfg)
    assert stub.metadata["semantic_deduplication_status"] == "NOT_EXECUTED"
    assert stub.metadata["external_embedding_calls"] == 0

    null = await ConfigurableSemanticDuplicateDetector(NullEmbeddingBackend()).detect([a, b], config=cfg)
    assert null.metadata["semantic_deduplication_status"] == "NOT_EXECUTED"

    det = ConfigurableSemanticDuplicateDetector(HashBagEmbeddingBackend())
    out = await det.detect([a, b], config=SemanticDedupConfig(similarity_threshold=0.99, calibrated=False))
    assert out.metadata["candidates_deleted"] == 0
    assert "similarity_threshold" in out.metadata
    assert out.metadata["threshold_calibrated"] is False
    # Near-identical stems should produce high pair scores
    assert any(p.similarity_score >= 0.99 for p in out.pair_scores) or len(out.clusters) >= 1


@pytest.mark.asyncio
async def test_retry_empty_then_success():
    metrics = ProviderReliabilityMetrics(provider="anthropic", requested=1)
    calls = {"n": 0}

    async def call():
        calls["n"] += 1
        if calls["n"] == 1:
            return ""
        return '{"questions":[]}'

    async def nosleep(_t: float):
        return None

    result, kind = await execute_with_retry(
        call=call,
        is_empty=lambda t: not (t or "").strip(),
        metrics=metrics,
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.01),
        sleep=nosleep,
    )
    assert kind is None
    assert result and "questions" in result
    assert metrics.attempted == 2
    assert metrics.successful == 1
    assert metrics.empty_response == 1
    assert metrics.terminal_failure == 0


@pytest.mark.asyncio
async def test_retry_budget_exhaustion():
    metrics = ProviderReliabilityMetrics(provider="anthropic", requested=1)

    async def always_empty():
        return ""

    async def nosleep(_t: float):
        return None

    result, kind = await execute_with_retry(
        call=always_empty,
        is_empty=lambda t: not (t or "").strip(),
        metrics=metrics,
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.01),
        sleep=nosleep,
    )
    assert result == ""
    assert kind == "EMPTY_RESPONSE"
    assert metrics.attempted == 3
    assert metrics.terminal_failure == 1
    assert metrics.successful == 0


def test_allocation_caps_and_no_cross_provider_fill():
    assert_allocation_caps(provider="anthropic", requested=400, already_generated=320, additional=0)
    with pytest.raises(AllocationCapError):
        assert_allocation_caps(provider="anthropic", requested=401)
    with pytest.raises(AllocationCapError):
        assert_allocation_caps(provider="anthropic", requested=400, already_generated=399, additional=2)
    with pytest.raises(AllocationCapError):
        assert_no_cross_provider_fill("openai", "anthropic")
    assert_no_cross_provider_fill("anthropic", "anthropic")


def test_error_classification_empty_json():
    assert classify_provider_error("Expecting value: line 1 column 1 (char 0)") == "EMPTY_RESPONSE"


def test_optional_v2_fields_do_not_break_v1_candidate():
    cand = CandidateRecord.model_validate(_cand())
    assert cand.audited_question_type is None
    assert cand.concept_status is None
    # overlays may be set without rewriting stem/options
    data = cand.model_dump(by_alias=True)
    data["declared_question_type"] = "factual"
    data["audited_question_type"] = "FACTUAL"
    data["question_type_audit_status"] = "MATCH"
    data["declared_difficulty"] = "easy"
    data["audited_difficulty"] = "EASY"
    data["difficulty_agreement"] = True
    data["concept_status"] = "RESOLVED"
    cand2 = CandidateRecord.model_validate(data)
    assert cand2.question_type_audit_status == "MATCH"


@pytest.mark.asyncio
async def test_no_contentitem_mutation_from_validator_v2():
    raw = _cand()
    before = dict(raw)
    res = validate_candidate_v2(raw, expected_source_sha=SHA)
    assert res.mutated is False
    assert raw == before
    assert res.ncert_trace["source_sha256"] == SHA
    assert res.ncert_trace["grounding_upgrade_forbidden"] is True
