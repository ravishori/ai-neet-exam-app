"""Deterministic, fail-closed eligibility gate for NCERT structured facts."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from app.modules.cms.schemas.deterministic_fact_pack import DeterministicFact
from app.modules.cms.services.deterministic_fact_pack_loader import (
    extract_ncert_source_text,
)
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope
from app.modules.ingestion.services.ncert_canonical_source import (
    validate_ncert_generation_source,
)

FactQualityStatus = Literal[
    "FACT_APPROVED",
    "FACT_REVIEW_REQUIRED",
    "FACT_REJECTED",
]
FactWorkflowStage = Literal[
    "EXTRACTED",
    "REVIEW_REQUIRED",
    "FACT_APPROVED",
    "MCQ_ELIGIBLE",
    "REJECTED",
]
OptionRelation = Literal["ANSWERS_STEM", "DOES_NOT_ANSWER_STEM", "UNKNOWN"]

_WS = re.compile(r"\s+")
_SAFE_TRANSFORMATIONS = {
    "DIRECT_FACT": {"DIRECT_RECALL", "OPTION_PERMUTATION"},
    "DEFINITION": {"DEFINITION_IDENTIFICATION", "OPTION_PERMUTATION"},
    "SI_UNIT_TERMINOLOGY": {"SI_UNIT_SELECTION", "OPTION_PERMUTATION"},
    "FORMULA": {"NUMERICAL_SUBSTITUTION", "OPTION_PERMUTATION"},
    "ASSOCIATION": {"ASSOCIATION_SELECTION", "OPTION_PERMUTATION"},
}


def _normalise(value: str | None) -> str:
    return _WS.sub(" ", value or "").strip().casefold()


def _contains(haystack: str, needle: str) -> bool:
    return bool(_normalise(needle)) and _normalise(needle) in _normalise(haystack)


@dataclass(frozen=True)
class TaxonomyBinding:
    subject: str
    class_level: str
    chapter_id: str
    chapter: str
    topic_id: str
    topic: str
    concept_id: str
    concept: str


@dataclass(frozen=True)
class OptionDefensibility:
    key: str
    text: str
    evidence_quote: str
    relation_to_stem: OptionRelation


@dataclass(frozen=True)
class QuestionConstruction:
    stem: str
    transformation: str
    correct_key: str
    options: tuple[
        OptionDefensibility,
        OptionDefensibility,
        OptionDefensibility,
        OptionDefensibility,
    ]


@dataclass(frozen=True)
class FactQualityReason:
    code: str
    detail: str
    severity: Literal["REVIEW", "REJECT"]


@dataclass
class FactQualityResult:
    status: FactQualityStatus
    workflow_stage: FactWorkflowStage
    mcq_eligible: bool
    fact_id: str | None = None
    reasons: list[FactQualityReason] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    supported_answer_keys: list[str] = field(default_factory=list)
    source_relative_path: str | None = None
    syllabus_status: str | None = None
    provider_api_calls: int = 0
    production_db_mutations: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class FactQualityGate:
    """Approve only facts with explicit scope review and safe construction."""

    def evaluate(
        self,
        fact: DeterministicFact,
        *,
        taxonomy: TaxonomyBinding,
        authoritative_syllabus_path: str | Path,
        question: QuestionConstruction | None = None,
        source_root: Path | None = None,
    ) -> FactQualityResult:
        reasons: list[FactQualityReason] = []
        checks: dict[str, bool] = {}
        source_relative_path: str | None = None
        source_text = ""

        def reject(code: str, detail: str) -> None:
            reasons.append(FactQualityReason(code, detail, "REJECT"))

        def review(code: str, detail: str) -> None:
            reasons.append(FactQualityReason(code, detail, "REVIEW"))

        try:
            source = validate_ncert_generation_source(
                fact.source_pdf,
                root=source_root,
            )
            source_relative_path = source.relative_posix
            checks["canonical_source"] = (
                source.relative_posix
                == fact.source_relative_path.replace("\\", "/")
            )
            if not checks["canonical_source"]:
                reject(
                    "NCERT_SOURCE_IDENTITY_MISMATCH",
                    "declared source_relative_path does not match canonical source",
                )
            source_text = extract_ncert_source_text(
                source.resolved_path,
                fact.ncert_reference.page_number,
            )
            checks["source_readable"] = bool(source_text.strip())
            if not checks["source_readable"]:
                reject("NCERT_SOURCE_UNREADABLE", "cited NCERT source has no readable text")
        except Exception as exc:  # noqa: BLE001
            checks["canonical_source"] = False
            checks["source_readable"] = False
            reject(
                getattr(exc, "code", "NCERT_SOURCE_UNREADABLE"),
                type(exc).__name__,
            )

        checks["evidence_present"] = bool((fact.evidence_text or "").strip())
        if not checks["evidence_present"]:
            reject("EVIDENCE_MISSING", "evidence_text is empty")
        checks["evidence_in_source"] = (
            checks["evidence_present"]
            and bool(source_text)
            and _contains(source_text, fact.evidence_text)
        )
        if checks["evidence_present"] and not checks["evidence_in_source"]:
            reject("EVIDENCE_NOT_IN_NCERT_SOURCE", "evidence_text is not in cited source scope")
        checks["canonical_fact_supported"] = _contains(
            fact.evidence_text,
            fact.canonical_fact,
        )
        if not checks["canonical_fact_supported"]:
            reject(
                "CANONICAL_FACT_NOT_IN_EVIDENCE",
                "canonical fact meaning is not explicit in evidence_text",
            )

        syllabus_status: str | None = None
        try:
            syllabus_path = Path(authoritative_syllabus_path).resolve()
            declared_syllabus = Path(fact.syllabus_binding.syllabus_source).resolve()
            checks["authoritative_syllabus_source"] = syllabus_path == declared_syllabus
            if not checks["authoritative_syllabus_source"]:
                reject(
                    "SYLLABUS_SOURCE_MISMATCH",
                    "fact does not bind the authoritative syllabus",
                )
            syllabus = assert_blueprint_neet_syllabus_scope(
                {"neet_ug_2026": fact.syllabus_binding.model_dump(exclude_none=True)},
                academic_subject_code=fact.subject,
                syllabus_path=str(syllabus_path),
            )
            syllabus_status = syllabus.status
            checks["syllabus_in_scope"] = syllabus.is_in_scope
            if syllabus.status == "SYLLABUS_MAPPING_REVIEW_REQUIRED":
                review(
                    syllabus.status,
                    syllabus.detail or "syllabus binding requires review",
                )
            elif not syllabus.is_in_scope:
                reject(syllabus.status, syllabus.detail or "fact is outside syllabus")
        except Exception as exc:  # noqa: BLE001
            checks["authoritative_syllabus_source"] = False
            checks["syllabus_in_scope"] = False
            reject("SYLLABUS_SOURCE_INVALID", type(exc).__name__)

        taxonomy_matches = (
            fact.subject == taxonomy.subject
            and fact.class_level == taxonomy.class_level
            and fact.chapter_id == taxonomy.chapter_id
            and _normalise(fact.chapter) == _normalise(taxonomy.chapter)
            and fact.topic_id == taxonomy.topic_id
            and _normalise(fact.topic) == _normalise(taxonomy.topic)
            and fact.concept_id == taxonomy.concept_id
            and _normalise(fact.concept_name) == _normalise(taxonomy.concept)
        )
        checks["taxonomy_consistent"] = taxonomy_matches
        if not taxonomy_matches:
            reject(
                "TAXONOMY_MISMATCH",
                "fact chapter/topic/concept does not match authoritative concept ownership",
            )

        scope_review = fact.scope_review
        checks["semantic_scope_reviewed"] = (
            scope_review is not None and scope_review.outcome == "SUPPORTED"
        )
        if scope_review is None:
            review(
                "CONCEPT_BINDING_REVIEW_REQUIRED",
                "no explicit semantic syllabus/taxonomy scope review is present",
            )
        elif scope_review.outcome == "AMBIGUOUS":
            review(
                "SYLLABUS_MAPPING_REVIEW_REQUIRED",
                scope_review.syllabus_rationale,
            )
        elif scope_review.outcome == "UNSUPPORTED":
            reject(
                "CONCEPT_MISBOUND",
                f"{scope_review.syllabus_rationale} {scope_review.taxonomy_rationale}",
            )

        checks["provenance_valid"] = (
            fact.provenance.origin == "canonical_ncert"
            and bool(fact.provenance.extracted_by.strip())
        )
        if not checks["provenance_valid"]:
            reject("PROVENANCE_INVALID", "canonical NCERT provenance is incomplete")

        checks["fact_reviewed"] = fact.review_status in {"REVIEWED", "VERIFIED"}
        if fact.review_status in {"EXTRACTED", "REVIEW_REQUIRED"}:
            review("FACT_REVIEW_REQUIRED", f"fact status is {fact.review_status}")
        elif fact.review_status == "REJECTED":
            reject("FACT_REJECTED", "fact is already marked REJECTED")

        allowed_for_type = _SAFE_TRANSFORMATIONS.get(fact.fact_type, set())
        unsafe = sorted(set(fact.allowed_transformations) - allowed_for_type)
        checks["transformations_safe"] = not unsafe
        if unsafe:
            reject(
                "TRANSFORMATION_UNSAFE",
                f"unsupported for {fact.fact_type}: {', '.join(unsafe)}",
            )

        distractors_safe = all(
            (
                distractor.source in {"SAME_EVIDENCE", "SAFE_MAPPING"}
                and bool((distractor.evidence_text or "").strip())
                and _contains(source_text, distractor.evidence_text)
            )
            or (
                distractor.source == "NUMERICAL_TRANSFORM"
                and fact.fact_type == "FORMULA"
                and bool((distractor.transformation or "").strip())
            )
            for distractor in fact.allowed_distractors
        )
        checks["configured_distractors_safe"] = distractors_safe
        if not distractors_safe:
            reject("DISTRACTOR_UNSAFE", "configured distractor lacks allowed source support")

        supported_answer_keys: list[str] = []
        if question is not None:
            checks["question_has_four_options"] = (
                len(question.options) == 4
                and len({option.key for option in question.options}) == 4
                and len({_normalise(option.text) for option in question.options}) == 4
            )
            if not checks["question_has_four_options"]:
                reject("INVALID_EXPLICIT_OPTIONS", "question needs four distinct options")
            checks["requested_transformation_safe"] = (
                question.transformation in fact.allowed_transformations
                and question.transformation in allowed_for_type
            )
            if not checks["requested_transformation_safe"]:
                reject(
                    "TRANSFORMATION_UNSAFE",
                    f"question requests {question.transformation}",
                )

            option_evidence_ok = {
                option.key: _contains(source_text, option.evidence_quote)
                for option in question.options
            }
            supported_answer_keys = [
                option.key
                for option in question.options
                if option.relation_to_stem == "ANSWERS_STEM"
                and option_evidence_ok[option.key]
            ]
            checks["exactly_one_supported_answer"] = len(supported_answer_keys) == 1
            if not supported_answer_keys:
                reject("NO_SUPPORTED_ANSWER", "no option is supported as answering the stem")
            elif len(supported_answer_keys) > 1:
                reject(
                    "FACT_AMBIGUOUS",
                    "multiple options are supported as answering the stem: "
                    + ", ".join(supported_answer_keys),
                )
            elif supported_answer_keys[0] != question.correct_key:
                reject(
                    "ANSWER_KEY_MISMATCH",
                    "the unique supported answer does not match correct_key",
                )

            unsafe_question_distractors = [
                option.key
                for option in question.options
                if option.key != question.correct_key
                and (
                    option.relation_to_stem != "DOES_NOT_ANSWER_STEM"
                    or not option_evidence_ok[option.key]
                    or _normalise(option.text)
                    not in {
                        _normalise(distractor.value)
                        for distractor in fact.allowed_distractors
                    }
                )
            ]
            checks["question_distractors_safe"] = not unsafe_question_distractors
            if unsafe_question_distractors:
                reject(
                    "DISTRACTOR_UNSAFE",
                    "distractors are correct, unknown, or unsupported: "
                    + ", ".join(unsafe_question_distractors),
                )

        has_reject = any(reason.severity == "REJECT" for reason in reasons)
        has_review = any(reason.severity == "REVIEW" for reason in reasons)
        if has_reject:
            status: FactQualityStatus = "FACT_REJECTED"
            stage: FactWorkflowStage = "REJECTED"
        elif has_review:
            status = "FACT_REVIEW_REQUIRED"
            stage = "REVIEW_REQUIRED"
        else:
            status = "FACT_APPROVED"
            stage = "MCQ_ELIGIBLE" if question is not None else "FACT_APPROVED"
        return FactQualityResult(
            status=status,
            workflow_stage=stage,
            mcq_eligible=stage == "MCQ_ELIGIBLE",
            fact_id=fact.fact_id,
            reasons=reasons,
            checks=checks,
            supported_answer_keys=supported_answer_keys,
            source_relative_path=source_relative_path,
            syllabus_status=syllabus_status,
        )
