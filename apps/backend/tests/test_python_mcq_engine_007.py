"""Focused tests for PYTHON-MCQ-ENGINE-007 reviewed-pack evaluation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.modules.cms.services.deterministic_fact_adapter import (
    DeterministicFactToQuestionAdapter,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (
    extract_ncert_source_text,
    load_deterministic_fact_pack,
)
from app.modules.cms.services.deterministic_mcq_engine import (
    DeterministicEvidenceContext,
    DeterministicMcqEngine,
)
from app.modules.cms.services.fact_quality_gate import TaxonomyBinding
from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack
from app.modules.ingestion.services.ncert_canonical_source import (
    validate_ncert_generation_source,
)

ROOT = Path(__file__).resolve().parents[3]
BACKEND = Path(__file__).resolve().parents[1]
SYLLABUS = ROOT / "NEETSyllabus.txt"
PACK = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"
AUDIT = ROOT / "docs/audits/python_mcq_engine_007.json"
SEED = 20260914
SCRIPTS = BACKEND / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from python_mcq_engine_007_audit import independent_verify  # noqa: E402


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


@pytest.fixture(scope="module")
def loaded():
    return load_deterministic_fact_pack(PACK)


def test_reviewed_pack_unchanged_sha_matches_audit(loaded):
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert loaded.pack_id == "python-mcq-engine-006-reviewed-multisubject-v1"
    assert len(loaded.facts) == 100
    assert loaded.input_sha256 == audit["fact_pack"]["input_sha256"]
    assert audit["fact_pack"]["fixture_unchanged"] is True


def test_sample_generation_reproducible_and_independently_pass(loaded):
    adapter = DeterministicFactToQuestionAdapter()
    sample = sorted(loaded.facts, key=lambda fact: fact.fact_id)[:3]
    engine = DeterministicMcqEngine()
    for fact in sample:
        adapted = adapter.adapt(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
        )
        assert adapted.quality.mcq_eligible is True
        source = validate_ncert_generation_source(fact.source_pdf)
        source_text = extract_ncert_source_text(source.resolved_path, None)
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
                evidence_text=source_text,
                page_numbers=[],
                detail="ENGINE-007 focused sample",
            ),
        )
        first = engine.generate_eligible(
            context,
            [adapted.spec],
            quality_results={adapted.fact_id: adapted.quality},
            seed=SEED,
        )
        second = engine.generate_eligible(
            context,
            [adapted.spec],
            quality_results={adapted.fact_id: adapted.quality},
            seed=SEED,
        )
        assert first.created == 1
        assert [item.to_dict() for item in first.candidates] == [
            item.to_dict() for item in second.candidates
        ]
        finding = independent_verify(first.candidates[0], adapted, source_text)
        assert finding["classification"] == "PASS"


def test_audit_metrics_are_honest_about_generation_shortfall():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    metrics = audit["metrics"]
    assert metrics["facts_selected"] == 100
    assert metrics["candidates_created"] == 99
    assert metrics["generation_failure_rate"] == 0.01
    assert metrics["independent_PASS"] == 99
    assert metrics["independent_FAIL"] == 0
    assert metrics["independent_AMBIGUOUS"] == 0
    assert metrics["verified_yield"] == 1.0
    assert metrics["verified_yield_label"] == "READ-ONLY EVALUATION VERIFIED YIELD"
    assert metrics["reproducible"] is True
    assert audit["production_safety_unchanged"] is True
    assert audit["provider_api_calls"] == 0
    assert audit["production_db_mutations"] == 0
