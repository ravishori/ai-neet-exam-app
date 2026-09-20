"""PYTHON-MCQ-ENGINE-005 — 100-fact read-only evaluation tests."""

from __future__ import annotations

import sys
from collections import Counter
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
from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack
from app.modules.ingestion.services.ncert_canonical_source import (
    validate_ncert_generation_source,
)

ROOT = Path(__file__).resolve().parents[3]
BACKEND = Path(__file__).resolve().parents[1]
SYLLABUS = ROOT / "NEETSyllabus.txt"
PACK = Path(__file__).parent / "fixtures/python_mcq_engine_005_eval_100.json"
SEED = 20260914
SCRIPTS = BACKEND / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from python_mcq_engine_003_audit import _read_only_snapshot  # noqa: E402
from python_mcq_engine_005_audit import _independent_verify  # noqa: E402


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
def loaded_pack():
    return load_deterministic_fact_pack(
        PACK,
        minimum_review_status="EXTRACTED",
    )


def test_100_fact_loading(loaded_pack):
    assert loaded_pack.pack_id == "python-mcq-engine-005-eval-100-v1"
    assert loaded_pack.schema_version == "ncert_fact_pack_v1"
    assert len(loaded_pack.facts) == 100


def test_subject_distribution(loaded_pack):
    counts = Counter(fact.subject for fact in loaded_pack.facts)
    assert dict(counts) == {
        "PHYSICS": 25,
        "CHEMISTRY": 25,
        "BOTANY": 25,
        "ZOOLOGY": 25,
    }


def test_chapter_distribution_at_least_five_per_subject(loaded_pack):
    by_subject: dict[str, set[str]] = {
        "PHYSICS": set(),
        "CHEMISTRY": set(),
        "BOTANY": set(),
        "ZOOLOGY": set(),
    }
    for fact in loaded_pack.facts:
        by_subject[fact.subject].add(fact.chapter)
    for subject, chapters in by_subject.items():
        assert len(chapters) >= 5, f"{subject} has only {chapters}"


def test_quality_gate_enforcement_no_silent_upgrade(loaded_pack):
    gate = FactQualityGate()
    statuses = Counter()
    reviewed = 0
    for fact in loaded_pack.facts:
        if fact.review_status == "REVIEWED":
            reviewed += 1
        quality = gate.evaluate(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
            question=None,
        )
        statuses[quality.status] += 1
        if fact.review_status == "EXTRACTED":
            assert quality.status == "FACT_REVIEW_REQUIRED"
            assert quality.mcq_eligible is False
    assert reviewed == 5
    assert statuses["FACT_APPROVED"] == 5
    assert statuses["FACT_REVIEW_REQUIRED"] == 95
    assert statuses.get("FACT_REJECTED", 0) == 0


def test_typed_adapter_only_for_reviewed_templates(loaded_pack):
    adapter = DeterministicFactToQuestionAdapter()
    adapted = []
    for fact in loaded_pack.facts:
        if fact.question_template is None:
            with pytest.raises(FactAdapterError) as exc:
                adapter.adapt(
                    fact,
                    taxonomy=_taxonomy(fact),
                    authoritative_syllabus_path=SYLLABUS,
                )
            assert exc.value.code == "QUESTION_TEMPLATE_MISSING"
            continue
        result = adapter.adapt(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
        )
        assert result.quality.mcq_eligible is True
        adapted.append(result)
    assert len(adapted) == 5


def test_deterministic_generation_validation_and_duplicates(loaded_pack):
    adapter = DeterministicFactToQuestionAdapter()
    reviewed = [
        fact
        for fact in loaded_pack.facts
        if fact.review_status == "REVIEWED" and fact.question_template is not None
    ]
    adapted = [
        adapter.adapt(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
        )
        for fact in reviewed
    ]
    first = reviewed[0]
    source = validate_ncert_generation_source(first.source_pdf)
    context = DeterministicEvidenceContext(
        subject=first.subject,
        class_level=first.class_level,
        chapter=first.chapter,
        topic=first.topic,
        concept=first.concept_name,
        source_path=first.source_pdf,
        constraints={
            "ncert_derived": True,
            "ncert_source_path": first.source_pdf,
            "neet_ug_2026": first.syllabus_binding.model_dump(exclude_none=True),
        },
        provenance_tier="authoritative",
        evidence=NcertEvidencePack(
            status="NCERT_EVIDENCE_READY",
            pdf_path=first.source_pdf,
            relative_posix=first.source_relative_path,
            evidence_text=extract_ncert_source_text(source.resolved_path, None),
            page_numbers=[],
            detail="ENGINE-005 focused test evidence",
        ),
    )
    quality_map = {item.fact_id: item.quality for item in adapted}
    specs = [item.spec for item in adapted]
    result = DeterministicMcqEngine().generate_eligible(
        context,
        specs,
        quality_results=quality_map,
        seed=SEED,
    )
    assert result.created == 5
    assert result.validation_failures == 0
    assert result.duplicate_failures == 0
    assert result.provider_api_calls == 0
    stems = {candidate.stem_hash for candidate in result.candidates}
    assert len(stems) == 5


def test_reproducibility_of_generated_candidates(loaded_pack):
    adapter = DeterministicFactToQuestionAdapter()
    reviewed = [
        fact
        for fact in loaded_pack.facts
        if fact.review_status == "REVIEWED" and fact.question_template is not None
    ]
    adapted = [
        adapter.adapt(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
        )
        for fact in reviewed
    ]
    first = reviewed[0]
    source = validate_ncert_generation_source(first.source_pdf)
    context = DeterministicEvidenceContext(
        subject=first.subject,
        class_level=first.class_level,
        chapter=first.chapter,
        topic=first.topic,
        concept=first.concept_name,
        source_path=first.source_pdf,
        constraints={
            "ncert_derived": True,
            "ncert_source_path": first.source_pdf,
            "neet_ug_2026": first.syllabus_binding.model_dump(exclude_none=True),
        },
        provenance_tier="authoritative",
        evidence=NcertEvidencePack(
            status="NCERT_EVIDENCE_READY",
            pdf_path=first.source_pdf,
            relative_posix=first.source_relative_path,
            evidence_text=extract_ncert_source_text(source.resolved_path, None),
            page_numbers=[],
            detail="ENGINE-005 reproducibility evidence",
        ),
    )
    quality_map = {item.fact_id: item.quality for item in adapted}
    specs = [item.spec for item in adapted]
    engine = DeterministicMcqEngine()
    first_run = engine.generate_eligible(
        context, specs, quality_results=quality_map, seed=SEED
    )
    second_run = engine.generate_eligible(
        context, specs, quality_results=quality_map, seed=SEED
    )
    assert [item.to_dict() for item in first_run.candidates] == [
        item.to_dict() for item in second_run.candidates
    ]


def test_independent_verification_pass_for_generated(loaded_pack):
    """Structural independent checks reused from the evaluation harness."""
    adapter = DeterministicFactToQuestionAdapter()
    reviewed = [
        fact
        for fact in loaded_pack.facts
        if fact.review_status == "REVIEWED" and fact.question_template is not None
    ]
    adapted = [
        adapter.adapt(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
        )
        for fact in reviewed
    ]
    first = reviewed[0]
    source = validate_ncert_generation_source(first.source_pdf)
    source_text = extract_ncert_source_text(source.resolved_path, None)
    context = DeterministicEvidenceContext(
        subject=first.subject,
        class_level=first.class_level,
        chapter=first.chapter,
        topic=first.topic,
        concept=first.concept_name,
        source_path=first.source_pdf,
        constraints={
            "ncert_derived": True,
            "ncert_source_path": first.source_pdf,
            "neet_ug_2026": first.syllabus_binding.model_dump(exclude_none=True),
        },
        provenance_tier="authoritative",
        evidence=NcertEvidencePack(
            status="NCERT_EVIDENCE_READY",
            pdf_path=first.source_pdf,
            relative_posix=first.source_relative_path,
            evidence_text=source_text,
            page_numbers=[],
            detail="ENGINE-005 independent verification",
        ),
    )
    quality_map = {item.fact_id: item.quality for item in adapted}
    result = DeterministicMcqEngine().generate_eligible(
        context,
        [item.spec for item in adapted],
        quality_results=quality_map,
        seed=SEED,
    )
    adapted_map = {item.fact_id: item for item in adapted}
    classifications = []
    for candidate in result.candidates:
        finding = _independent_verify(
            candidate, adapted_map[candidate.fact_id], source_text
        )
        classifications.append(finding["classification"])
    assert classifications == ["PASS"] * 5


def test_read_only_db_behavior_snapshot_stable():
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(engine)
    load_deterministic_fact_pack(PACK, minimum_review_status="EXTRACTED")
    after = _read_only_snapshot(engine)
    engine.dispose()
    assert before == after
