"""Focused tests for PYTHON-MCQ-ENGINE-006 reviewed multi-subject fact pack."""

from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path

import pytest

from app.modules.cms.schemas.deterministic_fact_pack import DeterministicFact
from app.modules.cms.services.deterministic_fact_adapter import (
    DeterministicFactToQuestionAdapter,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (
    extract_ncert_source_text,
    load_deterministic_fact_pack,
)
from app.modules.cms.services.fact_quality_gate import FactQualityGate, TaxonomyBinding
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope
from app.modules.ingestion.services.ncert_canonical_source import (
    validate_ncert_generation_source,
)

ROOT = Path(__file__).resolve().parents[3]
BACKEND = Path(__file__).resolve().parents[1]
SYLLABUS = ROOT / "NEETSyllabus.txt"
PACK = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"
SCRIPTS = BACKEND / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from python_mcq_engine_003_audit import _read_only_snapshot  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402


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


def test_reviewed_pack_size_and_subject_targets(loaded):
    assert loaded.pack_id == "python-mcq-engine-006-reviewed-multisubject-v1"
    assert len(loaded.facts) == 100
    counts = Counter(fact.subject for fact in loaded.facts)
    assert dict(counts) == {
        "PHYSICS": 25,
        "CHEMISTRY": 25,
        "BOTANY": 25,
        "ZOOLOGY": 25,
    }


def test_multi_chapter_coverage(loaded):
    by_subject: dict[str, set[str]] = {
        "PHYSICS": set(),
        "CHEMISTRY": set(),
        "BOTANY": set(),
        "ZOOLOGY": set(),
    }
    for fact in loaded.facts:
        by_subject[fact.subject].add(fact.chapter)
    for subject, chapters in by_subject.items():
        assert len(chapters) >= 3, f"{subject} chapters={chapters}"


def test_stable_ids_and_deterministic_ordering(loaded):
    ids = [fact.fact_id for fact in loaded.facts]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)
    second = load_deterministic_fact_pack(PACK)
    assert [fact.fact_id for fact in second.facts] == ids


def test_all_facts_reviewed_with_scope_and_template(loaded):
    for fact in loaded.facts:
        assert fact.review_status == "REVIEWED"
        assert fact.review_record is not None
        assert fact.scope_review is not None
        assert fact.scope_review.outcome == "SUPPORTED"
        assert fact.question_template is not None
        assert fact.provenance.origin == "canonical_ncert"


def test_ncert_evidence_and_source_guard(loaded):
    for fact in loaded.facts[:20]:  # sample for speed; full pack audited in script
        source = validate_ncert_generation_source(fact.source_pdf)
        assert "StudyMaterial" not in str(source.resolved_path)
        text = extract_ncert_source_text(source.resolved_path, None)
        assert fact.evidence_text.casefold() in " ".join(text.split()).casefold()
        for distractor in fact.allowed_distractors:
            assert distractor.evidence_text
            assert distractor.evidence_text.casefold() in " ".join(text.split()).casefold()


def test_syllabus_binding_and_taxonomy_consistency(loaded):
    for fact in loaded.facts:
        syllabus = assert_blueprint_neet_syllabus_scope(
            {"neet_ug_2026": fact.syllabus_binding.model_dump(exclude_none=True)},
            academic_subject_code=fact.subject,
            syllabus_path=str(SYLLABUS),
        )
        assert syllabus.is_in_scope
        taxonomy = _taxonomy(fact)
        assert fact.chapter_id == taxonomy.chapter_id
        assert fact.topic_id == taxonomy.topic_id
        assert fact.concept_id == taxonomy.concept_id


def test_all_facts_mcq_eligible_via_adapter(loaded):
    adapter = DeterministicFactToQuestionAdapter()
    for fact in loaded.facts:
        adapted = adapter.adapt(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
        )
        assert adapted.quality.status == "FACT_APPROVED"
        assert adapted.quality.mcq_eligible is True
        assert adapted.quality.workflow_stage == "MCQ_ELIGIBLE"


def test_transformation_and_distractor_safety(loaded):
    for fact in loaded.facts:
        assert "OPTION_PERMUTATION" in fact.allowed_transformations
        assert len(fact.allowed_distractors) == 3
        template = fact.question_template
        assert template is not None
        assert template.transformation in fact.allowed_transformations
        answering = [
            option
            for option in template.options
            if option.relation_to_stem == "ANSWERS_STEM"
        ]
        assert len(answering) == 1
        distractors = [
            option
            for option in template.options
            if option.relation_to_stem == "DOES_NOT_ANSWER_STEM"
        ]
        assert len(distractors) == 3


def test_extracted_facts_cannot_silently_become_eligible(loaded):
    gate = FactQualityGate()
    sample = loaded.facts[0]
    raw = sample.model_dump(mode="json")
    raw["review_status"] = "EXTRACTED"
    raw.pop("review_record", None)
    raw.pop("verification_record", None)
    # Keep scope/template to prove review_status alone blocks eligibility.
    extracted = DeterministicFact.model_validate(raw)
    quality = gate.evaluate(
        extracted,
        taxonomy=_taxonomy(extracted),
        authoritative_syllabus_path=SYLLABUS,
        question=None,
    )
    assert quality.status == "FACT_REVIEW_REQUIRED"
    assert quality.mcq_eligible is False


def test_rejected_facts_remain_rejected(loaded):
    gate = FactQualityGate()
    sample = loaded.facts[1]
    raw = sample.model_dump(mode="json")
    raw["review_status"] = "REJECTED"
    raw["review_record"] = {
        "reviewed_by": "ENGINE-006-TEST",
        "reviewed_at": "2026-09-14T15:30:00+00:00",
        "review_method": "forced rejection fixture",
    }
    rejected = DeterministicFact.model_validate(raw)
    quality = gate.evaluate(
        rejected,
        taxonomy=_taxonomy(rejected),
        authoritative_syllabus_path=SYLLABUS,
        question=None,
    )
    assert quality.status == "FACT_REJECTED"
    assert quality.mcq_eligible is False


def test_duplicate_canonical_identity_detection(loaded):
    first = loaded.facts[0]
    twin = copy.deepcopy(first)
    # Same identity payload should yield the same stable id.
    from app.modules.cms.schemas.deterministic_fact_pack import compute_stable_fact_id

    assert compute_stable_fact_id(twin) == first.fact_id


def test_read_only_db_unchanged_after_pack_load():
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(engine)
    load_deterministic_fact_pack(PACK)
    after = _read_only_snapshot(engine)
    engine.dispose()
    assert before == after
