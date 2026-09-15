"""Reviewed schema for provider-free deterministic NCERT fact packs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FACT_PACK_SCHEMA_VERSION = "ncert_fact_pack_v1"

FactType = Literal[
    "DIRECT_FACT",
    "DEFINITION",
    "SI_UNIT_TERMINOLOGY",
    "FORMULA",
    "ASSOCIATION",
]
AllowedTransformation = Literal[
    "DIRECT_RECALL",
    "DEFINITION_IDENTIFICATION",
    "SI_UNIT_SELECTION",
    "NUMERICAL_SUBSTITUTION",
    "ASSOCIATION_SELECTION",
    "OPTION_PERMUTATION",
]
ReviewStatus = Literal[
    "EXTRACTED",
    "REVIEW_REQUIRED",
    "REVIEWED",
    "VERIFIED",
    "REJECTED",
]

_WS = re.compile(r"\s+")


def _normalise(value: str | None) -> str:
    return _WS.sub(" ", value or "").strip().casefold()


class StrictFactModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NcertReference(StrictFactModel):
    reference_level: Literal["SOURCE_TEXT_ONLY", "SECTION_LOCATED", "PAGE_LOCATED"]
    section: str | None = None
    page_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_reference_claim(self) -> NcertReference:
        if self.reference_level == "SECTION_LOCATED" and not (self.section or "").strip():
            raise ValueError("SECTION_LOCATED requires section")
        if self.reference_level == "PAGE_LOCATED" and self.page_number is None:
            raise ValueError("PAGE_LOCATED requires page_number")
        if self.page_number is not None and self.reference_level != "PAGE_LOCATED":
            raise ValueError("page_number requires PAGE_LOCATED")
        return self


class FactSyllabusBinding(StrictFactModel):
    subject: Literal["PHYSICS", "CHEMISTRY", "BIOLOGY"]
    unit_number: int = Field(ge=1)
    unit_name: str | None = None
    topic_id: str | None = None
    topic: str | None = None
    subtopic: str | None = None
    syllabus_source: str = Field(min_length=1)
    syllabus_sha256: str | None = None


class FactProvenance(StrictFactModel):
    origin: Literal["canonical_ncert"]
    extraction_method: Literal["manual_extraction", "deterministic_extraction"]
    extracted_by: str = Field(min_length=1)
    source_audit: str | None = None
    notes: str | None = None


class ReviewRecord(StrictFactModel):
    reviewed_by: str = Field(min_length=1)
    reviewed_at: datetime
    review_method: str = Field(min_length=1)
    notes: str | None = None


class VerificationRecord(StrictFactModel):
    verified_by: str = Field(min_length=1)
    verified_at: datetime
    verification_method: str = Field(min_length=1)
    scope: Literal["SOURCE_TEXT_AND_SYLLABUS"]
    notes: str | None = None


class ScopeReview(StrictFactModel):
    outcome: Literal["SUPPORTED", "UNSUPPORTED", "AMBIGUOUS"]
    reviewed_by: str = Field(min_length=1)
    reviewed_at: datetime
    review_method: str = Field(min_length=1)
    syllabus_rationale: str = Field(min_length=1)
    taxonomy_rationale: str = Field(min_length=1)
    source_audit: str | None = None


class AllowedDistractor(StrictFactModel):
    value: str = Field(min_length=1)
    source: Literal["SAME_EVIDENCE", "SAFE_MAPPING", "NUMERICAL_TRANSFORM"]
    evidence_text: str | None = None
    transformation: str | None = None

    @model_validator(mode="after")
    def require_source_support(self) -> AllowedDistractor:
        if self.source == "SAME_EVIDENCE" and not (self.evidence_text or "").strip():
            raise ValueError("SAME_EVIDENCE distractor requires evidence_text")
        if self.source == "SAFE_MAPPING" and not (self.evidence_text or "").strip():
            raise ValueError("SAFE_MAPPING distractor requires evidence_text")
        if self.source == "NUMERICAL_TRANSFORM" and not (self.transformation or "").strip():
            raise ValueError("NUMERICAL_TRANSFORM distractor requires transformation")
        return self


class QuestionTemplateOption(StrictFactModel):
    key: str = Field(min_length=1)
    text: str = Field(min_length=1)
    evidence_quote: str = Field(min_length=1)
    relation_to_stem: Literal[
        "ANSWERS_STEM",
        "DOES_NOT_ANSWER_STEM",
        "UNKNOWN",
    ]


class ExplicitQuestionTemplate(StrictFactModel):
    question_type: Literal[
        "DIRECT_FACT",
        "DEFINITION_IDENTIFICATION",
        "SI_UNIT_TERMINOLOGY",
        "CONTROLLED_ASSOCIATION",
    ]
    transformation: AllowedTransformation
    stem: str = Field(min_length=1)
    stem_evidence_quote: str = Field(min_length=1)
    options: list[QuestionTemplateOption] = Field(min_length=4, max_length=4)
    correct_key: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    explanation_evidence_quote: str = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"] = "easy"

    @model_validator(mode="after")
    def validate_option_contract(self) -> ExplicitQuestionTemplate:
        keys = [option.key for option in self.options]
        texts = [_normalise(option.text) for option in self.options]
        if len(set(keys)) != 4 or len(set(texts)) != 4:
            raise ValueError("question template options must have unique keys and text")
        if self.correct_key not in keys:
            raise ValueError("question template correct_key must identify an option")
        return self


class DeterministicFact(StrictFactModel):
    schema_version: Literal["ncert_fact_pack_v1"] = FACT_PACK_SCHEMA_VERSION
    fact_id: str = Field(pattern=r"^ncert-fact-v1-[0-9a-f]{64}$")
    subject: Literal["PHYSICS", "CHEMISTRY", "BIOLOGY", "BOTANY", "ZOOLOGY"]
    class_level: Literal["11", "12"]
    chapter_id: str = Field(min_length=1)
    chapter: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    concept_id: str | None = None
    concept_name: str | None = None
    source_pdf: str = Field(min_length=1)
    source_relative_path: str = Field(min_length=1)
    ncert_reference: NcertReference
    evidence_text: str = Field(min_length=1)
    fact_type: FactType
    canonical_fact: str = Field(min_length=1)
    allowed_transformations: list[AllowedTransformation] = Field(min_length=1)
    allowed_distractors: list[AllowedDistractor] = Field(default_factory=list)
    syllabus_binding: FactSyllabusBinding
    review_status: ReviewStatus
    provenance: FactProvenance
    review_record: ReviewRecord | None = None
    verification_record: VerificationRecord | None = None
    scope_review: ScopeReview | None = None
    question_template: ExplicitQuestionTemplate | None = None

    @model_validator(mode="after")
    def validate_review_truthfulness(self) -> DeterministicFact:
        if self.review_status in {"EXTRACTED", "REVIEW_REQUIRED"}:
            if self.review_record is not None or self.verification_record is not None:
                raise ValueError(
                    f"{self.review_status} fact cannot carry review/verification records"
                )
        elif self.review_status == "REVIEWED":
            if self.review_record is None:
                raise ValueError("REVIEWED fact requires review_record")
            if self.verification_record is not None:
                raise ValueError("REVIEWED fact cannot claim independent verification")
        elif self.review_status == "VERIFIED":
            if self.review_record is None or self.verification_record is None:
                raise ValueError(
                    "VERIFIED fact requires review_record and verification_record"
                )
        elif self.review_record is None:
            raise ValueError("REJECTED fact requires review_record")
        return self


class DeterministicFactPack(StrictFactModel):
    schema_version: Literal["ncert_fact_pack_v1"] = FACT_PACK_SCHEMA_VERSION
    pack_id: str = Field(min_length=1)
    facts: list[DeterministicFact] = Field(min_length=1)


def fact_identity_payload(fact: DeterministicFact | dict) -> dict:
    raw = fact.model_dump(mode="json") if isinstance(fact, DeterministicFact) else dict(fact)
    syllabus = raw.get("syllabus_binding") or {}
    return {
        "schema_version": raw.get("schema_version", FACT_PACK_SCHEMA_VERSION),
        "subject": str(raw.get("subject") or "").upper(),
        "class_level": str(raw.get("class_level") or ""),
        "chapter_id": str(raw.get("chapter_id") or ""),
        "chapter": _normalise(str(raw.get("chapter") or "")),
        "topic_id": str(raw.get("topic_id") or ""),
        "topic": _normalise(str(raw.get("topic") or "")),
        "concept_id": str(raw.get("concept_id") or ""),
        "concept_name": _normalise(str(raw.get("concept_name") or "")),
        "source_relative_path": str(raw.get("source_relative_path") or "").replace("\\", "/"),
        "fact_type": str(raw.get("fact_type") or ""),
        "canonical_fact": _normalise(str(raw.get("canonical_fact") or "")),
        "evidence_text": _normalise(str(raw.get("evidence_text") or "")),
        "syllabus_topic_id": str(syllabus.get("topic_id") or ""),
        "syllabus_topic": _normalise(str(syllabus.get("topic") or "")),
    }


def compute_stable_fact_id(fact: DeterministicFact | dict) -> str:
    payload = fact_identity_payload(fact)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"ncert-fact-v1-{hashlib.sha256(encoded).hexdigest()}"
