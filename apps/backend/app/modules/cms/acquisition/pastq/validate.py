"""Deterministic validation for pastq staged questions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.modules.cms.acquisition.pastq.enrich import map_option_to_letter
from app.modules.cms.pyq.pyq_extraction import ExtractedQuestion

HEADER_FOOTER_MARKERS = (
    "space for rough work",
    "test booklet code",
    "aglasem.com",
    "chapter & topicwise",
)
ANSWER_KEY_IN_STEM = re.compile(r"\banswer\s*key\b", re.I)
CONCAT_HINT = re.compile(r"(?m)^\s*\d{1,3}\.\s+.+\n\s*\d{1,3}\.\s+", re.S)


@dataclass
class ValidationResult:
    ok: bool
    ready_for_import: bool
    needs_review: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate_class: str = "UNIQUE"


def validate_extracted_question(
    q: ExtractedQuestion,
    *,
    inventory_sha256: str | None,
    paper_year: int | None,
    paper_needs_review: bool = False,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if q.validation_status in {"OCR_REQUIRED", "OCR_FAILED"}:
        errors.append(q.validation_status)
    if q.question_number is None:
        errors.append("MISSING_QUESTION_NUMBER")
    stem = (q.stem or "").strip()
    if not stem:
        errors.append("EMPTY_STEM")
    opts = [q.option_a or "", q.option_b or "", q.option_c or "", q.option_d or ""]
    filled = [o.strip() for o in opts]
    if any(not o for o in filled):
        errors.append("EMPTY_OPTION")
    if len(filled) == 4 and len({o.lower() for o in filled}) < 4:
        errors.append("DUPLICATE_OPTIONS")
    if sum(1 for o in filled if o) not in {0, 4}:
        errors.append("INCOMPLETE_OPTION_SET")

    letter = map_option_to_letter(q.correct_option)
    if q.correct_option and letter is None:
        errors.append("INVALID_ANSWER_LABEL")
    if q.answer_status == "ANSWER_CONFLICT":
        errors.append("ANSWER_CONFLICT")

    if inventory_sha256 and q.source_sha256 and q.source_sha256 != inventory_sha256:
        errors.append("SHA256_MISMATCH")
    if q.source_page is not None and q.source_page < 1:
        errors.append("INVALID_PAGE")

    low_stem = stem.lower()
    if any(m in low_stem for m in HEADER_FOOTER_MARKERS):
        warnings.append("HEADER_FOOTER_CONTAMINATION")
    if ANSWER_KEY_IN_STEM.search(stem):
        errors.append("ANSWER_KEY_TEXT_IN_STEM")
    if CONCAT_HINT.search(q.raw_extracted_text or ""):
        warnings.append("POSSIBLE_QUESTION_CONCATENATION")

    if paper_year is None:
        warnings.append("YEAR_NULL")
    if paper_needs_review:
        warnings.append("PAPER_NEEDS_REVIEW")
    if "VISUAL_REVIEW_REQUIRED" in (q.anomalies or []):
        warnings.append("VISUAL_REVIEW_REQUIRED")
    if not q.subject:
        warnings.append("ACADEMIC_MAPPING_REVIEW_REQUIRED")

    # OCR corruption heuristics (flag, do not repair)
    if re.search(r"[\uf0b4\uf02d\ufffd]", q.raw_extracted_text or ""):
        warnings.append("OCR_SYMBOL_CORRUPTION")
    if stem and len(stem) < 12:
        warnings.append("STEM_VERY_SHORT")

    needs_review = bool(errors or warnings or paper_needs_review or not letter)
    # Ready for CMS import only when structurally valid AND answer known (schema requires correct_option).
    ready = (
        not errors
        and bool(stem)
        and all(filled)
        and letter is not None
        and q.answer_status == "ANSWER_KNOWN"
    )
    ok = not errors
    return ValidationResult(
        ok=ok,
        ready_for_import=ready,
        needs_review=needs_review or not ready,
        errors=errors,
        warnings=warnings,
    )


def question_to_staging_record(
    q: ExtractedQuestion,
    *,
    meta: dict[str, Any],
    validation: ValidationResult,
    visual: dict[str, Any],
    duplicate_class: str,
) -> dict[str, Any]:
    letter = map_option_to_letter(q.correct_option)
    return {
        "source": {
            "file": q.source_file,
            "sha256": q.source_sha256,
            "page_start": q.source_page,
            "page_end": q.source_page,
        },
        "paper": {
            "exam": meta.get("exam_name", "NEET"),
            "year": meta.get("year"),
            "year_source": meta.get("year_source"),
            "set": meta.get("set_code"),
            "set_source": meta.get("set_source"),
            "paper_id": q.paper_id,
            "language": meta.get("language") or q.language,
            "needs_review": meta.get("needs_review", False),
            "warnings": meta.get("warnings") or [],
        },
        "question": {
            "number": q.question_number,
            "subject": q.subject,
            "stem": q.stem,
            "options": {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d,
            },
            "chapter": None,
            "topic": None,
            "concept": None,
        },
        "answer": {
            "value": letter,
            "source": q.answer_source,
            "status": q.answer_status,
            "source_page": q.answer_source_page,
        },
        "visual": visual,
        "quality": {
            "extraction_confidence": q.extraction_confidence,
            "extraction_mode": q.extraction_mode,
            "validation_status": q.validation_status,
            "needs_review": validation.needs_review,
            "ready_for_import": validation.ready_for_import,
            "warnings": validation.warnings + list(q.anomalies or []),
            "errors": validation.errors,
            "duplicate_class": duplicate_class,
        },
        "hashes": {
            "question_hash": q.question_hash,
            "normalized_question_hash": q.normalized_question_hash,
            "staging_id": q.staging_id,
        },
        "provenance": {
            "origin": "past_question_paper",
            "ncert_derived": False,
            "source_type": "past_question_paper",
        },
        "raw_extracted_text": q.raw_extracted_text,
    }
