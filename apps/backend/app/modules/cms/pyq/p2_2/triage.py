"""P2.2 read-only triage for recovery candidates."""

from __future__ import annotations

import re
from typing import Any

from app.modules.cms.pyq.p2_2.schemas import TriageCategory, TriageResult

DIAGRAM_CUES = ("figure", "shown in", "diagram", "circuit is", "as shown", "graph", "plot")
CHEM_PATTERN = re.compile(r"(CH[,\d]|COOH|NH[,\d]|\[|\]|→|⇌)", re.I)
MATH_PATTERN = re.compile(r"(\\frac|\^|_\{|∫|∑|√|θ|°|×10|\d+/\d+)")


def question_id(record: dict[str, Any]) -> str:
    return f"{(record.get('source_sha256') or '')[:16]}:p{record.get('source_page')}:q{record.get('question_number')}"


def missing_fields(record: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if not (record.get("stem") or "").strip():
        out.append("stem")
    for key, label in zip(("option_a", "option_b", "option_c", "option_d"), ("1", "2", "3", "4")):
        if not (record.get(key) or "").strip():
            out.append(f"option_{label}")
    return out


def known_defects(record: dict[str, Any]) -> list[str]:
    defects: list[str] = []
    stem = (record.get("stem") or "").lower()
    if record.get("missing_options"):
        defects.append("missing_options")
    if any(c in stem for c in DIAGRAM_CUES):
        defects.append("diagram_dependent")
    if record.get("geometry_quality_flags"):
        defects.append("geometry_flags")
    if record.get("rejection_reason"):
        defects.append(str(record["rejection_reason"]))
    for a in record.get("anomalies") or []:
        defects.append(str(a))
    return defects


def triage_record(
    record: dict[str, Any],
    *,
    has_source_pdf: bool,
    has_ocr_words: bool,
    is_c_grade: bool = False,
) -> TriageResult:
    qid = question_id(record)
    status = record.get("p2_1e_quality_status") or record.get("p2_1c_quality_status") or "UNKNOWN"
    missing = missing_fields(record)
    defects = known_defects(record)
    stem = record.get("stem") or ""
    raw = record.get("raw_extracted_text") or ""

    if status not in ("PARTIAL", "NEEDS_REVIEW", "DIAGRAM_DEPENDENT") and not is_c_grade:
        return TriageResult(qid, "SOURCE_INSUFFICIENT", "not_in_recovery_population", status, missing, defects)

    if not has_source_pdf and not has_ocr_words and not raw.strip():
        return TriageResult(qid, "SOURCE_INSUFFICIENT", "no_source_pdf_or_ocr", status, missing, defects)

    if status == "DIAGRAM_DEPENDENT" or "diagram_dependent" in defects:
        return TriageResult(qid, "HUMAN_REVIEW", "diagram_dependent_requires_human", status, missing, defects)

    if not has_ocr_words and not raw.strip():
        return TriageResult(qid, "SOURCE_INSUFFICIENT", "ocr_evidence_missing", status, missing, defects)

    filled = 4 - len([k for k in ("option_a", "option_b", "option_c", "option_d") if not (record.get(k) or "").strip()])
    if missing and raw.strip() and filled >= 1 and not any(c in stem.lower() for c in DIAGRAM_CUES):
        if all(m.startswith("option_") for m in missing) or (missing == ["stem"] and raw):
            return TriageResult(qid, "DETERMINISTIC_RECOVERABLE", "raw_block_reparse_candidate", status, missing, defects)

    if CHEM_PATTERN.search(stem + " ".join(record.get(k) or "" for k in ("option_a", "option_b", "option_c", "option_d"))):
        if status == "PARTIAL":
            return TriageResult(qid, "AI_MULTIMODAL_RECOVERABLE", "chemistry_ocr_fragmentation", status, missing, defects)

    if MATH_PATTERN.search(stem):
        return TriageResult(qid, "AI_MULTIMODAL_RECOVERABLE", "mathematical_notation", status, missing, defects)

    if record.get("geometry_quality_flags") or "option_boundary" in " ".join(defects):
        return TriageResult(qid, "AI_MULTIMODAL_RECOVERABLE", "layout_or_boundary_defect", status, missing, defects)

    if len(missing) >= 3 or not stem.strip():
        return TriageResult(qid, "HUMAN_REVIEW", "severe_fragmentation", status, missing, defects)

    if status == "PARTIAL" or is_c_grade:
        return TriageResult(qid, "AI_MULTIMODAL_RECOVERABLE", "partial_extraction_default", status, missing, defects)

    return TriageResult(qid, "HUMAN_REVIEW", "ambiguous_default_route", status, missing, defects)


def triage_population(
    records: list[dict[str, Any]],
    *,
    c_grade_ids: set[str],
    source_availability: dict[str, dict[str, bool]],
) -> list[TriageResult]:
    results: list[TriageResult] = []
    for rec in records:
        qid = question_id(rec)
        avail = source_availability.get(qid, {})
        is_partial = (rec.get("p2_1e_quality_status") in ("PARTIAL", "NEEDS_REVIEW", "DIAGRAM_DEPENDENT"))
        is_c = qid in c_grade_ids
        if not is_partial and not is_c:
            continue
        results.append(
            triage_record(
                rec,
                has_source_pdf=avail.get("has_pdf", False),
                has_ocr_words=avail.get("has_ocr_words", False),
                is_c_grade=is_c,
            )
        )
    return results
