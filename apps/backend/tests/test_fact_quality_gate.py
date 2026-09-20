"""Regression tests for PYTHON-MCQ-ENGINE-003 fact eligibility rules."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.modules.cms.schemas.deterministic_fact_pack import (
    DeterministicFact,
    compute_stable_fact_id,
)
from app.modules.cms.services.fact_quality_gate import (
    FactQualityGate,
    OptionDefensibility,
    QuestionConstruction,
    TaxonomyBinding,
)

ROOT = Path(__file__).resolve().parents[3]
SYLLABUS = ROOT / "NEETSyllabus.txt"


def _taxonomy() -> TaxonomyBinding:
    return TaxonomyBinding(
        subject="CHEMISTRY",
        class_level="12",
        chapter_id="chapter-biomolecules",
        chapter="Biomolecules",
        topic_id="topic-carbohydrates",
        topic="Carbohydrates",
        concept_id="concept-classification",
        concept="Classification of Carbohydrates",
    )


def _fact(
    ncert_root: Path,
    *,
    canonical_fact: str = "Sucrose is a non reducing sugar.",
    evidence_text: str | None = None,
    fact_type: str = "DIRECT_FACT",
    transformations: list[str] | None = None,
    scope_outcome: str = "SUPPORTED",
) -> DeterministicFact:
    source = ncert_root / "book.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    evidence = evidence_text or (
        f"{canonical_fact} Glucose is a monosaccharide. Fructose is a "
        "monosaccharide. Ribose is a monosaccharide."
    )
    raw = {
        "schema_version": "ncert_fact_pack_v1",
        "fact_id": "ncert-fact-v1-" + ("0" * 64),
        "subject": "CHEMISTRY",
        "class_level": "12",
        "chapter_id": "chapter-biomolecules",
        "chapter": "Biomolecules",
        "topic_id": "topic-carbohydrates",
        "topic": "Carbohydrates",
        "concept_id": "concept-classification",
        "concept_name": "Classification of Carbohydrates",
        "source_pdf": str(source),
        "source_relative_path": "book.pdf",
        "ncert_reference": {"reference_level": "SOURCE_TEXT_ONLY"},
        "evidence_text": evidence,
        "fact_type": fact_type,
        "canonical_fact": canonical_fact,
        "allowed_transformations": transformations
        or ["DIRECT_RECALL", "OPTION_PERMUTATION"],
        "allowed_distractors": [
            {
                "value": "Glucose",
                "source": "SAME_EVIDENCE",
                "evidence_text": "Glucose is a monosaccharide.",
            },
            {
                "value": "Fructose",
                "source": "SAME_EVIDENCE",
                "evidence_text": "Fructose is a monosaccharide.",
            },
            {
                "value": "Ribose",
                "source": "SAME_EVIDENCE",
                "evidence_text": "Ribose is a monosaccharide.",
            },
        ],
        "syllabus_binding": {
            "subject": "CHEMISTRY",
            "unit_number": 19,
            "unit_name": "BIOMOLECULES",
            "topic_id": "CHEMISTRY:U19:T02",
            "syllabus_source": str(SYLLABUS),
        },
        "review_status": "REVIEWED",
        "provenance": {
            "origin": "canonical_ncert",
            "extraction_method": "manual_extraction",
            "extracted_by": "test-fixture",
        },
        "review_record": {
            "reviewed_by": "test-reviewer",
            "reviewed_at": "2026-09-14T00:00:00Z",
            "review_method": "source-review",
        },
        "scope_review": {
            "outcome": scope_outcome,
            "reviewed_by": "test-reviewer",
            "reviewed_at": "2026-09-14T00:00:00Z",
            "review_method": "syllabus-taxonomy-review",
            "syllabus_rationale": (
                "The fact is within the cited syllabus scope."
                if scope_outcome == "SUPPORTED"
                else "The fact meaning is outside the cited syllabus wording."
            ),
            "taxonomy_rationale": (
                "The fact matches the selected concept."
                if scope_outcome == "SUPPORTED"
                else "The fact is not represented by the selected concept."
            ),
        },
    }
    raw["fact_id"] = compute_stable_fact_id(raw)
    return DeterministicFact.model_validate(raw)


def _question(
    *,
    answer_relations: tuple[str, str, str, str] = (
        "ANSWERS_STEM",
        "DOES_NOT_ANSWER_STEM",
        "DOES_NOT_ANSWER_STEM",
        "DOES_NOT_ANSWER_STEM",
    ),
    transformation: str = "DIRECT_RECALL",
) -> QuestionConstruction:
    texts = (
        ("sucrose", "Sucrose", "Sucrose is a non reducing sugar."),
        ("glucose", "Glucose", "Glucose is a monosaccharide."),
        ("fructose", "Fructose", "Fructose is a monosaccharide."),
        ("ribose", "Ribose", "Ribose is a monosaccharide."),
    )
    return QuestionConstruction(
        stem="Which carbohydrate is identified as a non-reducing sugar?",
        transformation=transformation,
        correct_key="sucrose",
        options=tuple(
            OptionDefensibility(key, text, quote, relation)
            for (key, text, quote), relation in zip(
                texts,
                answer_relations,
                strict=True,
            )
        ),
    )


def _evaluate(
    fact: DeterministicFact,
    ncert_root: Path,
    *,
    question: QuestionConstruction | None = None,
    taxonomy: TaxonomyBinding | None = None,
):
    with patch(
        "app.modules.cms.services.fact_quality_gate.extract_ncert_source_text",
        return_value=fact.evidence_text,
    ):
        return FactQualityGate().evaluate(
            fact,
            taxonomy=taxonomy or _taxonomy(),
            authoritative_syllabus_path=SYLLABUS,
            question=question,
            source_root=ncert_root,
        )


def _codes(result) -> set[str]:
    return {reason.code for reason in result.reasons}


def test_valid_syllabus_concept_and_one_answer_become_mcq_eligible(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    result = _evaluate(_fact(root), root, question=_question())
    assert result.status == "FACT_APPROVED"
    assert result.workflow_stage == "MCQ_ELIGIBLE"
    assert result.mcq_eligible is True
    assert result.supported_answer_keys == ["sucrose"]


def test_home_sugar_pattern_is_rejected_by_general_scope_review_rule(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(
        root,
        canonical_fact="Sucrose is the most common sugar used in homes.",
        scope_outcome="UNSUPPORTED",
    )
    result = _evaluate(fact, root, question=_question())
    assert result.status == "FACT_REJECTED"
    assert "CONCEPT_MISBOUND" in _codes(result)


def test_maltose_linkage_pattern_is_rejected_by_general_scope_review_rule(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(
        root,
        canonical_fact="C1 of one glucose is linked to C4 of another glucose unit.",
        fact_type="ASSOCIATION",
        transformations=["ASSOCIATION_SELECTION"],
        scope_outcome="UNSUPPORTED",
    )
    result = _evaluate(fact, root)
    assert result.status == "FACT_REJECTED"
    assert "CONCEPT_MISBOUND" in _codes(result)


def test_glycosidic_definition_pattern_is_rejected_by_general_scope_review_rule(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(
        root,
        canonical_fact="A linkage through oxygen is called glycosidic linkage.",
        fact_type="DEFINITION",
        transformations=["DEFINITION_IDENTIFICATION"],
        scope_outcome="UNSUPPORTED",
    )
    result = _evaluate(fact, root)
    assert result.status == "FACT_REJECTED"
    assert "CONCEPT_MISBOUND" in _codes(result)


def test_oligosaccharide_pattern_rejects_disaccharide_as_second_defensible_answer(
    tmp_path,
):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    question = _question(
        answer_relations=(
            "ANSWERS_STEM",
            "ANSWERS_STEM",
            "DOES_NOT_ANSWER_STEM",
            "DOES_NOT_ANSWER_STEM",
        )
    )
    result = _evaluate(fact, root, question=question)
    assert result.status == "FACT_REJECTED"
    assert result.supported_answer_keys == ["sucrose", "glucose"]
    assert "FACT_AMBIGUOUS" in _codes(result)
    assert "DISTRACTOR_UNSAFE" in _codes(result)


def test_zero_defensible_answers_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    relations = ("DOES_NOT_ANSWER_STEM",) * 4
    result = _evaluate(_fact(root), root, question=_question(answer_relations=relations))
    assert "NO_SUPPORTED_ANSWER" in _codes(result)


def test_generic_multiple_defensible_answers_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    relations = (
        "ANSWERS_STEM",
        "DOES_NOT_ANSWER_STEM",
        "ANSWERS_STEM",
        "DOES_NOT_ANSWER_STEM",
    )
    result = _evaluate(_fact(root), root, question=_question(answer_relations=relations))
    assert "FACT_AMBIGUOUS" in _codes(result)


def test_unknown_distractor_relation_is_unsafe(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    relations = (
        "ANSWERS_STEM",
        "UNKNOWN",
        "DOES_NOT_ANSWER_STEM",
        "DOES_NOT_ANSWER_STEM",
    )
    result = _evaluate(_fact(root), root, question=_question(answer_relations=relations))
    assert "DISTRACTOR_UNSAFE" in _codes(result)


def test_invalid_source_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    outside = tmp_path / "StudyMaterial" / "legacy.pdf"
    outside.parent.mkdir()
    outside.write_bytes(b"%PDF-1.4\n")
    fact = fact.model_copy(update={"source_pdf": str(outside)})
    result = _evaluate(fact, root)
    assert result.status == "FACT_REJECTED"
    assert "NCERT_SOURCE_NOT_ALLOWED" in _codes(result)


def test_missing_evidence_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root).model_copy(update={"evidence_text": ""})
    result = _evaluate(fact, root)
    assert "EVIDENCE_MISSING" in _codes(result)


def test_taxonomy_ownership_mismatch_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    taxonomy = TaxonomyBinding(
        **{**_taxonomy().__dict__, "concept_id": "different-concept"}
    )
    result = _evaluate(_fact(root), root, taxonomy=taxonomy)
    assert "TAXONOMY_MISMATCH" in _codes(result)


def test_transformation_must_be_safe_for_fact_type(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root, transformations=["DEFINITION_IDENTIFICATION"])
    result = _evaluate(fact, root)
    assert "TRANSFORMATION_UNSAFE" in _codes(result)


def test_gate_result_is_deterministically_reproducible(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    first = _evaluate(fact, root, question=_question())
    second = _evaluate(fact, root, question=_question())
    assert first.to_dict() == second.to_dict()
