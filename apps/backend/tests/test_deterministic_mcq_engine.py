"""Focused provider-free tests for PYTHON-MCQ-ENGINE-001."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from app.modules.cms.services.deterministic_mcq_engine import (
    DeterministicEvidenceContext,
    DeterministicMcqEngine,
    EvidenceOption,
    ExplicitChoiceSpec,
    NumericalSpec,
)
from app.modules.cms.services.fact_quality_gate import FactQualityResult
from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack
from app.modules.cms.syllabus.neet_2026_scope import SyllabusScopeResult
from app.modules.ingestion.services.ncert_canonical_source import ValidatedNcertSource


def _context(source_path: str = "/canonical/book.pdf") -> DeterministicEvidenceContext:
    evidence_text = (
        "Force equals mass times acceleration. "
        "Alpha is the explicitly correct term. Beta, Gamma and Delta are alternatives."
    )
    return DeterministicEvidenceContext(
        subject="PHYSICS",
        class_level="11",
        chapter="Laws of Motion",
        topic="Force and acceleration",
        concept="Newton's second law",
        source_path=source_path,
        constraints={
            "ncert_derived": True,
            "ncert_source_path": source_path,
            "neet_ug_2026": {
                "subject": "PHYSICS",
                "unit_number": 3,
                "topic_id": "PHYSICS:U03:T01",
            },
        },
        provenance_tier="authoritative",
        evidence=NcertEvidencePack(
            status="NCERT_EVIDENCE_READY",
            pdf_path=source_path,
            relative_posix="Class 11/Physics/book.pdf",
            evidence_text=evidence_text,
            page_numbers=[1],
            detail="test evidence",
        ),
    )


def _choice() -> ExplicitChoiceSpec:
    return ExplicitChoiceSpec(
        fact_id="fact-alpha",
        question_type="DIRECT_FACT",
        stem="Which term is explicitly identified as correct?",
        stem_evidence_quote="Alpha is the explicitly correct term",
        options=(
            EvidenceOption("alpha", "Alpha", "Alpha is the explicitly correct term"),
            EvidenceOption("beta", "Beta", "Beta, Gamma and Delta are alternatives"),
            EvidenceOption("gamma", "Gamma", "Beta, Gamma and Delta are alternatives"),
            EvidenceOption("delta", "Delta", "Beta, Gamma and Delta are alternatives"),
        ),
        correct_key="alpha",
        explanation="Alpha is explicitly identified as the correct term in the supplied evidence.",
        explanation_evidence_quote="Alpha is the explicitly correct term",
    )


def _source(_path: str) -> ValidatedNcertSource:
    root = Path("/canonical")
    return ValidatedNcertSource(
        resolved_path=Path("/canonical/book.pdf"),
        relative_posix="Class 11/Physics/book.pdf",
        root=root,
    )


def _in_scope(*_args, **_kwargs) -> SyllabusScopeResult:
    return SyllabusScopeResult(
        status="IN_SYLLABUS",
        subject="PHYSICS",
        unit_number=3,
        unit_name="LAWS OF MOTION",
        topic="Force and acceleration",
        topic_id="PHYSICS:U03:T01",
    )


def _generate(specs, *, seed=17, existing_stems=None):
    with (
        patch(
            "app.modules.cms.services.deterministic_mcq_engine.validate_ncert_generation_source",
            side_effect=_source,
        ),
        patch(
            "app.modules.cms.services.deterministic_mcq_engine.assert_blueprint_neet_syllabus_scope",
            side_effect=_in_scope,
        ),
    ):
        return DeterministicMcqEngine().generate(
            _context(),
            specs,
            seed=seed,
            existing_stem_hashes=existing_stems,
        )


def test_deterministic_reproducibility_shape_provenance_and_draft():
    first = _generate([_choice()], seed=19)
    second = _generate([_choice()], seed=19)
    assert first.created == second.created == 1
    assert first.candidates[0].to_dict() == second.candidates[0].to_dict()
    candidate = first.candidates[0]
    assert candidate.status == "DRAFT"
    assert candidate.generation_method == "deterministic_python"
    assert candidate.body["provenance"]["source"] == "canonical_ncert"
    assert len(candidate.body["options"]) == 4
    assert len({option["text"] for option in candidate.body["options"]}) == 4
    assert candidate.body["correct_option"] in {"A", "B", "C", "D"}
    assert first.provider_api_calls == 0


def test_duplicate_stem_is_rejected():
    first = _generate([_choice()])
    duplicate = _generate([_choice()], existing_stems={first.candidates[0].stem_hash})
    assert duplicate.created == 0
    assert duplicate.duplicate_failures == 1
    assert duplicate.skipped[0].reason == "DUPLICATE_STEM"


def test_generate_eligible_requires_explicit_fact_quality_approval():
    approved = FactQualityResult(
        status="FACT_APPROVED",
        workflow_stage="MCQ_ELIGIBLE",
        mcq_eligible=True,
    )
    rejected = FactQualityResult(
        status="FACT_REJECTED",
        workflow_stage="REJECTED",
        mcq_eligible=False,
    )
    with (
        patch(
            "app.modules.cms.services.deterministic_mcq_engine.validate_ncert_generation_source",
            side_effect=_source,
        ),
        patch(
            "app.modules.cms.services.deterministic_mcq_engine.assert_blueprint_neet_syllabus_scope",
            side_effect=_in_scope,
        ),
    ):
        accepted = DeterministicMcqEngine().generate_eligible(
            _context(),
            [_choice()],
            quality_results={"fact-alpha": approved},
            seed=17,
        )
        blocked = DeterministicMcqEngine().generate_eligible(
            _context(),
            [_choice()],
            quality_results={"fact-alpha": rejected},
            seed=17,
        )
        missing = DeterministicMcqEngine().generate_eligible(
            _context(),
            [_choice()],
            quality_results={},
            seed=17,
        )
    assert accepted.created == 1
    assert blocked.created == missing.created == 0
    assert blocked.skipped[0].reason == "FACT_QUALITY_REJECTED"
    assert missing.skipped[0].reason == "FACT_QUALITY_REVIEW_REQUIRED"


def test_si_unit_and_association_patterns_use_the_explicit_choice_path():
    for question_type in ("SI_UNIT_TERMINOLOGY", "CONTROLLED_ASSOCIATION"):
        result = _generate([replace(_choice(), question_type=question_type)])
        assert result.created == 1
        assert result.candidates[0].question_type == question_type


def test_unsupported_source_is_rejected_before_syllabus_or_generation():
    result = DeterministicMcqEngine().generate(
        _context("D:/repo/StudyMaterial/legacy.pdf"),
        [_choice()],
        seed=1,
    )
    assert result.created == 0
    assert result.source_gate_failures == 1
    assert result.skipped[0].reason == "SOURCE_GATE_FAILED"


def test_missing_syllabus_binding_fails_closed():
    context = _context()
    context = DeterministicEvidenceContext(
        **{**context.__dict__, "constraints": {"ncert_derived": True}}
    )
    with patch(
        "app.modules.cms.services.deterministic_mcq_engine.validate_ncert_generation_source",
        side_effect=_source,
    ):
        result = DeterministicMcqEngine().generate(context, [_choice()], seed=1)
    assert result.created == 0
    assert result.syllabus_gate_failures == 1


def test_numerical_answer_is_recomputed_and_uniquely_keyed():
    numerical = NumericalSpec(
        fact_id="force-six",
        stem="Using F = ma, what force acts when m = 2 kg and a = 3 m s^-2?",
        stem_evidence_quote="Force equals mass times acceleration",
        calculation_check={"formula": "F=ma", "m": 2, "a": 3, "F": 6},
        correct_value=Decimal("6"),
        unit="N",
        distractor_offsets=(Decimal("-2"), Decimal("2"), Decimal("4")),
        formula_evidence_quote="Force equals mass times acceleration",
        explanation="Python independently evaluates F = 2 × 3 = 6 N from the sourced relation.",
    )
    result = _generate([numerical])
    assert result.created == 1
    body = result.candidates[0].body
    keyed = next(
        option["text"]
        for option in body["options"]
        if option["label"] == body["correct_option"]
    )
    assert keyed == "6 N"
    assert body["numerical_evidence"]["status"] == "NUMERICAL_COMPLETE"


def test_numerical_mismatch_is_skipped():
    numerical = NumericalSpec(
        fact_id="force-wrong",
        stem="Using F = ma, what force acts when m = 2 kg and a = 3 m s^-2?",
        stem_evidence_quote="Force equals mass times acceleration",
        calculation_check={"formula": "F=ma", "m": 2, "a": 3, "F": 6},
        correct_value=Decimal("7"),
        unit="N",
        distractor_offsets=(Decimal("-2"), Decimal("2"), Decimal("4")),
        formula_evidence_quote="Force equals mass times acceleration",
        explanation="Python independently evaluates the sourced relation.",
    )
    result = _generate([numerical])
    assert result.created == 0
    assert result.numerical_failures == 1
    assert result.skipped[0].reason == "NUMERICAL_ANSWER_MISMATCH"
