"""Typed reviewed-fact adapter and five-candidate round-trip tests."""

from __future__ import annotations

from pathlib import Path

import pytest

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
from app.modules.cms.services.fact_quality_gate import TaxonomyBinding
from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack
from app.modules.ingestion.services.ncert_canonical_source import (
    get_ncert_source_root,
    validate_ncert_generation_source,
)

ROOT = Path(__file__).resolve().parents[3]
SYLLABUS = ROOT / "NEETSyllabus.txt"
PACK = Path(__file__).parent / "fixtures/python_mcq_engine_004_biomolecules.json"


def _taxonomy() -> TaxonomyBinding:
    return TaxonomyBinding(
        subject="CHEMISTRY",
        class_level="12",
        chapter_id="933a0d17-537f-4995-b0ae-6ce23a32a449",
        chapter="Biomolecules",
        topic_id="8927ce2d-26d4-4e3a-aa11-3a3f27279a5a",
        topic="Carbohydrates",
        concept_id="9384555f-5e4e-4273-943e-caa935827bba",
        concept="Classification of Carbohydrates",
    )


def _loaded():
    return load_deterministic_fact_pack(PACK)


def _adapt(fact):
    return DeterministicFactToQuestionAdapter().adapt(
        fact,
        taxonomy=_taxonomy(),
        authoritative_syllabus_path=SYLLABUS,
    )


def _context(facts) -> DeterministicEvidenceContext:
    first = facts[0]
    source = validate_ncert_generation_source(first.source_pdf)
    evidence_text = extract_ncert_source_text(source.resolved_path, None)
    return DeterministicEvidenceContext(
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
            evidence_text=evidence_text,
            page_numbers=list(range(1, 23)),
            detail="ENGINE-004 reviewed fact-pack full canonical source",
        ),
    )


def test_valid_reviewed_pack_contains_only_five_approved_facts():
    loaded = _loaded()
    assert loaded.schema_version == "ncert_fact_pack_v1"
    assert len(loaded.facts) == 5
    assert all(fact.review_status == "REVIEWED" for fact in loaded.facts)
    combined = " ".join(fact.canonical_fact.casefold() for fact in loaded.facts)
    assert "most common sugar used in homes" not in combined
    assert "glycosidic linkage" not in combined
    assert "c1 of one glucose" not in combined
    assert "oligosaccharides" not in combined


def test_typed_adapter_accepts_approved_fact_and_preserves_metadata():
    fact = _loaded().facts[0]
    adapted = _adapt(fact)
    assert adapted.quality.mcq_eligible is True
    assert adapted.fact_id == adapted.spec.fact_id == fact.fact_id
    assert adapted.source_pdf == fact.source_pdf
    assert adapted.source_relative_path == fact.source_relative_path
    assert adapted.syllabus_binding == fact.syllabus_binding.model_dump(
        exclude_none=True
    )
    assert adapted.provenance == fact.provenance.model_dump(exclude_none=True)
    assert adapted.concept_id == fact.concept_id


def test_typed_adapter_rejects_unapproved_fact():
    fact = _loaded().facts[0]
    unsupported = fact.scope_review.model_copy(update={"outcome": "UNSUPPORTED"})
    fact = fact.model_copy(update={"scope_review": unsupported})
    with pytest.raises(FactAdapterError) as exc:
        _adapt(fact)
    assert exc.value.code == "FACT_NOT_MCQ_ELIGIBLE"


def test_undeclared_transformation_is_rejected():
    fact = next(item for item in _loaded().facts if item.fact_type == "DEFINITION")
    template = fact.question_template.model_copy(update={"transformation": "DIRECT_RECALL"})
    fact = fact.model_copy(update={"question_template": template})
    with pytest.raises(FactAdapterError) as exc:
        _adapt(fact)
    assert exc.value.code == "TRANSFORMATION_UNSAFE"


def test_missing_evidence_is_rejected():
    fact = _loaded().facts[0].model_copy(update={"evidence_text": ""})
    with pytest.raises(FactAdapterError) as exc:
        _adapt(fact)
    assert exc.value.code == "EVIDENCE_MISSING"


def test_invalid_source_path_is_rejected(tmp_path):
    outside = tmp_path / "StudyMaterial" / "legacy.pdf"
    outside.parent.mkdir()
    outside.write_bytes(b"%PDF-1.4\n")
    fact = _loaded().facts[0].model_copy(update={"source_pdf": str(outside)})
    with pytest.raises(FactAdapterError) as exc:
        _adapt(fact)
    assert exc.value.code == "FACT_NOT_MCQ_ELIGIBLE"
    assert "NCERT_SOURCE_NOT_ALLOWED" in exc.value.detail


def test_invalid_syllabus_binding_is_rejected():
    fact = _loaded().facts[0]
    binding = fact.syllabus_binding.model_copy(
        update={"topic_id": "CHEMISTRY:U19:T99"}
    )
    fact = fact.model_copy(update={"syllabus_binding": binding})
    with pytest.raises(FactAdapterError) as exc:
        _adapt(fact)
    assert exc.value.code == "FACT_NOT_MCQ_ELIGIBLE"
    assert "SYLLABUS_OUT_OF_SCOPE" in exc.value.detail


def test_adapter_output_is_stable():
    fact = _loaded().facts[0]
    assert _adapt(fact) == _adapt(fact)


def test_five_candidate_round_trip_is_reproducible_and_in_memory_only():
    loaded = _loaded()
    adapter = DeterministicFactToQuestionAdapter()
    adapted = adapter.adapt_many(
        loaded.facts,
        taxonomy=_taxonomy(),
        authoritative_syllabus_path=SYLLABUS,
        max_items=5,
    )
    specs = [item.spec for item in adapted]
    quality = {item.fact_id: item.quality for item in adapted}
    context = _context(loaded.facts)
    first = DeterministicMcqEngine().generate_eligible(
        context,
        specs,
        quality_results=quality,
        seed=20260914,
    )
    second = DeterministicMcqEngine().generate_eligible(
        context,
        specs,
        quality_results=quality,
        seed=20260914,
    )
    assert first.created == second.created == 5
    assert [item.to_dict() for item in first.candidates] == [
        item.to_dict() for item in second.candidates
    ]
    assert {item.fact_id for item in first.candidates} == {
        fact.fact_id for fact in loaded.facts
    }
    assert all(item.status == "DRAFT" for item in first.candidates)
    assert all(item.provider_api_calls == 0 for item in (first, second))
    assert get_ncert_source_root() == Path(first.candidates[0].source_path).parents[3]
    assert all(item.quality.production_db_mutations == 0 for item in adapted)
