"""Publication evidence contracts for QUESTION bodies (T6-E-FIX).

These fields are optional on draft create, but QUESTION publish requires them
via publication_gates. Do not invent page numbers or calculation steps.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

NcertVerificationLevel = Literal[
    "NOT_VERIFIED",
    "SOURCE_TEXT_VERIFIED",
    "SECTION_VERIFIED",
    "PAGE_VERIFIED",
]

NumericalStatus = Literal[
    "NOT_NUMERICAL",
    "NUMERICAL_COMPLETE",
    "NUMERICAL_INCOMPLETE",
    "NUMERICAL_INVALID",
]

SimilarityBand = Literal["UNIQUE", "REVIEW", "NEAR_DUPLICATE", "DUPLICATE"]


class NcertEvidence(BaseModel):
    """Truthful NCERT provenance — never claim PAGE_VERIFIED without page_number."""

    verification_level: NcertVerificationLevel
    source_document: str = Field(min_length=1)
    document_version: str | None = None
    class_level: str = Field(min_length=1)
    chapter: str = Field(min_length=1)
    section: str | None = None
    page_number: int | None = None
    source_excerpt: str | None = None
    verification_method: str = Field(min_length=1)
    source_pdf_relpath: str | None = None

    @model_validator(mode="after")
    def reject_fabricated_page_claims(self) -> NcertEvidence:
        if self.verification_level == "PAGE_VERIFIED" and self.page_number is None:
            raise ValueError("PAGE_VERIFIED requires page_number")
        if self.page_number is not None and self.verification_level == "NOT_VERIFIED":
            raise ValueError("page_number present but verification_level is NOT_VERIFIED")
        if self.verification_level == "SECTION_VERIFIED" and not (self.section or "").strip():
            raise ValueError("SECTION_VERIFIED requires section")
        return self


class ProvenanceBlock(BaseModel):
    origin: str = Field(min_length=1)
    source: str = Field(min_length=1)
    batch_id: str | None = None
    validation_process: str | None = None
    verification_process: str | None = None
    class_level: str | None = None
    chapter: str | None = None
    section: str | None = None


class NumericalEvidence(BaseModel):
    """Explicit numerical contract — incomplete payloads must not pass science."""

    status: NumericalStatus = "NOT_NUMERICAL"
    given: dict[str, Any] = Field(default_factory=dict)
    formula: str | None = None
    substitution: str | None = None
    result: float | int | str | None = None
    unit: str | None = None
    correct_option: str | None = None
    # Raw calculation_check retained for deterministic recompute in gates
    calculation_check: dict[str, Any] = Field(default_factory=dict)
