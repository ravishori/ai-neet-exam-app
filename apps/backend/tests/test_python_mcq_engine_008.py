"""Focused tests for PYTHON-MCQ-ENGINE-008 Chemical Kinetics grounding disposition."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.modules.cms.services.deterministic_fact_adapter import (
    DeterministicFactToQuestionAdapter,
    FactAdapterError,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (
    extract_ncert_source_text,
    load_deterministic_fact_pack,
)
from app.modules.cms.services.deterministic_mcq_engine import (
    DeterministicEvidenceContext,
    DeterministicMcqEngine,
)
from app.modules.cms.services.fact_quality_gate import FactQualityGate, TaxonomyBinding
from app.modules.cms.services.factory_candidate_validation import (
    validate_candidate_body_detailed,
)
from app.modules.cms.services.ncert_claim_grounding import (
    detect_multiple_defensible_answers,
    validate_ncert_claim_grounding,
)
from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack
from app.modules.ingestion.services.ncert_canonical_source import (
    validate_ncert_generation_source,
)

ROOT = Path(__file__).resolve().parents[3]
BACKEND = Path(__file__).resolve().parents[1]
SYLLABUS = ROOT / "NEETSyllabus.txt"
PACK_006 = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_008 = (
    Path(__file__).parent / "fixtures/python_mcq_engine_008_kinetics_rate_law_retired.json"
)
AUDIT_007 = ROOT / "docs/audits/python_mcq_engine_007.json"
FACT_ID = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)
SEED = 20260914
SCRIPTS = BACKEND / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from python_mcq_engine_003_audit import _read_only_snapshot  # noqa: E402


def _taxonomy(fact) -> TaxonomyBinding:
    return TaxonomyBinding(
        subject=fact.subject,
        class_level=fact.class_level,
        chapter_id=fact.chapter_id,
        chapter=fact.chapter,
        topic_id=fact.topic_id,
        topic=fact.topic,
        concept_id=fact.concept_id or "",
        concept=fact.concept_name or "",
    )


def _engine006_fact():
    loaded = load_deterministic_fact_pack(PACK_006)
    return next(fact for fact in loaded.facts if fact.fact_id == FACT_ID)


def test_engine006_fixture_unchanged_sha_matches_007_audit():
    digest = hashlib.sha256(PACK_006.read_bytes()).hexdigest()
    audit = json.loads(AUDIT_007.read_text(encoding="utf-8"))
    loaded = load_deterministic_fact_pack(PACK_006)
    assert loaded.input_sha256 == audit["fact_pack"]["input_sha256"]
    assert digest  # fixture still on disk and readable
    assert FACT_ID in {fact.fact_id for fact in loaded.facts}


def test_original_fact_fails_grounding_as_ncert_ambiguous():
    fact = _engine006_fact()
    assert fact.concept_name == "Integrated Rate Equations"
    adapted = DeterministicFactToQuestionAdapter().adapt(
        fact,
        taxonomy=_taxonomy(fact),
        authoritative_syllabus_path=SYLLABUS,
    )
    source = validate_ncert_generation_source(fact.source_pdf)
    text = extract_ncert_source_text(source.resolved_path, None)
    assert "rate law or rate expression" in " ".join(text.split()).casefold()
    assert "known as rate law" in " ".join(text.split()).casefold()
    context = DeterministicEvidenceContext(
        subject=fact.subject,
        class_level=fact.class_level,
        chapter=fact.chapter,
        topic=fact.topic,
        concept=fact.concept_name,
        source_path=fact.source_pdf,
        constraints={
            "ncert_derived": True,
            "ncert_source_path": fact.source_pdf,
            "neet_ug_2026": fact.syllabus_binding.model_dump(exclude_none=True),
        },
        provenance_tier="authoritative",
        evidence=NcertEvidencePack(
            status="NCERT_EVIDENCE_READY",
            pdf_path=fact.source_pdf,
            relative_posix=fact.source_relative_path,
            evidence_text=text,
            page_numbers=[],
            detail="ENGINE-008 grounding reproduction",
        ),
    )
    built = DeterministicMcqEngine()._build_explicit_choice(
        context, adapted.spec, seed=SEED
    )
    detailed = validate_candidate_body_detailed(
        built,
        expected_difficulty=adapted.spec.difficulty,
        constraints=context.constraints,
    )
    assert detailed["ok"] and detailed["body"] is not None
    multi = detect_multiple_defensible_answers(detailed["body"], text)
    assert len(multi) >= 2
    grounding = validate_ncert_claim_grounding(detailed["body"], context.evidence)
    assert grounding.ok is False
    assert grounding.verdict == "NCERT_AMBIGUOUS"
    result = DeterministicMcqEngine().generate_eligible(
        context,
        [adapted.spec],
        quality_results={adapted.fact_id: adapted.quality},
        seed=SEED,
    )
    assert result.created == 0
    assert result.skipped[0].reason == "NCERT_GROUNDING_FAILED"
    assert "NCERT_AMBIGUOUS" in result.skipped[0].details


def test_retired_disposition_is_rejected_not_mcq_eligible():
    loaded = load_deterministic_fact_pack(
        PACK_008,
        minimum_review_status="REJECTED",
    )
    assert len(loaded.facts) == 1
    fact = loaded.facts[0]
    assert fact.fact_id == FACT_ID
    assert fact.review_status == "REJECTED"
    assert fact.scope_review is not None
    assert fact.scope_review.outcome == "UNSUPPORTED"
    quality = FactQualityGate().evaluate(
        fact,
        taxonomy=_taxonomy(fact),
        authoritative_syllabus_path=SYLLABUS,
        question=None,
    )
    assert quality.status == "FACT_REJECTED"
    assert quality.mcq_eligible is False
    with pytest.raises(FactAdapterError) as exc:
        DeterministicFactToQuestionAdapter().adapt(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
        )
    assert exc.value.code == "FACT_NOT_MCQ_ELIGIBLE"


def test_engine007_verified_yield_record_unchanged():
    audit = json.loads(AUDIT_007.read_text(encoding="utf-8"))
    metrics = audit["metrics"]
    assert metrics["candidates_created"] == 99
    assert metrics["independent_PASS"] == 99
    assert metrics["independent_FAIL"] == 0
    assert metrics["verified_yield"] == 1.0
    assert metrics["generation_skip_reason_counts"]["NCERT_GROUNDING_FAILED"] == 1


def test_read_only_db_unchanged():
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(engine)
    load_deterministic_fact_pack(PACK_008, minimum_review_status="REJECTED")
    after = _read_only_snapshot(engine)
    engine.dispose()
    assert before == after
