"""Validator V2 — structural + metadata audit overlays (no candidate rewrite)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.modules.cms.acquisition.mmf.approved_concepts import APPROVED_CONCEPT_CODES
from app.modules.cms.acquisition.mmf.audit import audit_candidate_metadata
from app.modules.cms.acquisition.mmf.normalize import normalize_text
from app.modules.cms.acquisition.mmf.validation import validate_candidate_dict

ConceptStatus = Literal["RESOLVED", "UNRESOLVED"]

_LEAK = re.compile(
    r"(?i)\b(answer\s*is|correct\s*(option|answer|choice)\s*is|option\s*[abcd]\s+is\s+correct)\b"
)
_ANS_LETTER = re.compile(
    r"(?i)\b(?:correct\s*(?:answer|option)|answer)\s*(?:is|:)\s*([ABCD])\b"
)


@dataclass
class StructuralFinding:
    reason_code: str
    detail: str = ""


@dataclass
class ValidatorV2Result:
    candidate_id: str
    schema_ok: bool
    schema_errors: list[str] = field(default_factory=list)
    structural_findings: list[StructuralFinding] = field(default_factory=list)
    metadata_audit: dict[str, Any] = field(default_factory=dict)
    concept_status: ConceptStatus = "UNRESOLVED"
    concept_code: str | None = None
    concept_reason_code: str = "CONCEPT_UNRESOLVED"
    ncert_trace: dict[str, Any] = field(default_factory=dict)
    mutated: bool = False  # always False in this gate


def resolve_concept(concept: str | None) -> tuple[ConceptStatus, str | None, str]:
    raw = (concept or "").strip()
    if not raw:
        return "UNRESOLVED", None, "CONCEPT_MISSING"
    if raw in APPROVED_CONCEPT_CODES:
        return "RESOLVED", raw, "CONCEPT_APPROVED_CODE"
    # Free-text / non-canonical — do not invent taxonomy
    return "UNRESOLVED", None, "CONCEPT_FREE_TEXT_NOT_IN_APPROVED_SET"


def structural_answer_checks(raw: dict[str, Any]) -> list[StructuralFinding]:
    findings: list[StructuralFinding] = []
    opts = raw.get("options") or {}
    if not isinstance(opts, dict):
        findings.append(StructuralFinding("OPTIONS_NOT_OBJECT"))
        return findings
    vals = {k: str(opts.get(k) or "") for k in ("A", "B", "C", "D")}
    if set(opts.keys()) - {"A", "B", "C", "D"}:
        findings.append(StructuralFinding("UNSUPPORTED_OPTION_KEYS"))
    if any(not vals[k].strip() for k in "ABCD"):
        findings.append(StructuralFinding("EMPTY_OPTION"))
    norms = [normalize_text(vals[k]) for k in "ABCD"]
    if len(set(norms)) < 4:
        findings.append(StructuralFinding("DUPLICATE_OPTIONS"))

    ans = str(raw.get("correct_answer") or "").strip().upper()
    if ans not in {"A", "B", "C", "D"}:
        findings.append(StructuralFinding("ANSWER_LETTER_INVALID"))
    else:
        ans_text = raw.get("correct_answer_text") or raw.get("answer_text")
        if ans_text is not None:
            expected = normalize_text(vals[ans])
            if normalize_text(str(ans_text)) != expected:
                findings.append(
                    StructuralFinding(
                        "ANSWER_TEXT_MISMATCH_SELECTED_OPTION",
                        detail=f"correct_answer={ans}",
                    )
                )

    stem = str(raw.get("stem") or "")
    expl = str(raw.get("explanation") or "")
    if _LEAK.search(stem):
        findings.append(StructuralFinding("OPTION_LEAKAGE_IN_STEM"))

    m = _ANS_LETTER.search(expl)
    if m and ans in {"A", "B", "C", "D"} and m.group(1).upper() != ans:
        findings.append(
            StructuralFinding(
                "EXPLANATION_CONTRADICTS_ANSWER_LETTER",
                detail=f"explanation_says={m.group(1).upper()} correct_answer={ans}",
            )
        )

    # Multiple defensible answers — detectable when two options are identical after normalize
    # (already DUPLICATE_OPTIONS) or explanation explicitly endorses two letters
    endorsed = set(re.findall(r"(?i)\b(?:options?\s*)([ABCD])\s*(?:and|&|/)\s*([ABCD])\b", expl))
    if endorsed:
        findings.append(StructuralFinding("MULTIPLE_DEFENSIBLE_ANSWERS_SIGNAL"))

    # Unsupported option claims — empty source_evidence with strong option scientific claims is soft
    if not str(raw.get("source_evidence") or "").strip():
        findings.append(StructuralFinding("MISSING_SOURCE_EVIDENCE"))

    # Option leakage: correct option text embedded in stem
    if ans in vals and vals[ans].strip() and normalize_text(vals[ans]) in normalize_text(stem):
        if len(normalize_text(vals[ans])) > 12:
            findings.append(StructuralFinding("OPTION_LEAKAGE_ANSWER_TEXT_IN_STEM"))

    return findings


def ncert_trace_fields(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_document": raw.get("source_document"),
        "source_sha256": raw.get("source_sha256"),
        "source_evidence_present": bool(str(raw.get("source_evidence") or "").strip()),
        "generation_batch_id": raw.get("generation_batch_id"),
        "provider": raw.get("provider"),
        "model": raw.get("model"),
        "prompt_version": raw.get("prompt_version"),
        "page_number_fabricated": "page_number" in raw and raw.get("page_number") is not None,
        "grounding_upgrade_forbidden": True,
    }


def validate_candidate_v2(
    raw: dict[str, Any],
    *,
    expected_source_sha: str | None = None,
) -> ValidatorV2Result:
    """Validate + audit without mutating the input candidate."""
    cid = str(raw.get("candidate_id") or "unknown")
    cand, schema_errors = validate_candidate_dict(raw, expected_source_sha=expected_source_sha)
    schema_ok = cand is not None and not schema_errors
    findings = structural_answer_checks(raw)
    meta = audit_candidate_metadata(raw)
    status, code, reason = resolve_concept(str(raw.get("concept") or ""))
    return ValidatorV2Result(
        candidate_id=cid,
        schema_ok=schema_ok,
        schema_errors=list(schema_errors),
        structural_findings=findings,
        metadata_audit=meta,
        concept_status=status,
        concept_code=code,
        concept_reason_code=reason,
        ncert_trace=ncert_trace_fields(raw),
        mutated=False,
    )


def validate_candidate_list_v2(
    rows: list[dict[str, Any]],
    *,
    expected_source_sha: str | None = None,
) -> dict[str, Any]:
    results = [validate_candidate_v2(r, expected_source_sha=expected_source_sha) for r in rows]
    type_mismatch = sum(1 for r in results if r.metadata_audit.get("question_type_status") == "MISMATCH")
    type_match = sum(1 for r in results if r.metadata_audit.get("question_type_status") == "MATCH")
    diff_agree = sum(1 for r in results if r.metadata_audit.get("difficulty_agreement") is True)
    diff_disagree = sum(1 for r in results if r.metadata_audit.get("difficulty_agreement") is False)
    unresolved = sum(1 for r in results if r.concept_status == "UNRESOLVED")
    structural_codes: dict[str, int] = {}
    for r in results:
        for f in r.structural_findings:
            structural_codes[f.reason_code] = structural_codes.get(f.reason_code, 0) + 1
    return {
        "count": len(results),
        "schema_ok": sum(1 for r in results if r.schema_ok),
        "schema_fail": sum(1 for r in results if not r.schema_ok),
        "question_type_MATCH": type_match,
        "question_type_MISMATCH": type_mismatch,
        "difficulty_agree": diff_agree,
        "difficulty_disagree": diff_disagree,
        "concept_RESOLVED": sum(1 for r in results if r.concept_status == "RESOLVED"),
        "concept_UNRESOLVED": unresolved,
        "structural_reason_counts": structural_codes,
        "mutated_any": any(r.mutated for r in results),
        "results": [
            {
                "candidate_id": r.candidate_id,
                "schema_ok": r.schema_ok,
                "schema_errors": r.schema_errors,
                "structural_reason_codes": [f.reason_code for f in r.structural_findings],
                "metadata_audit": r.metadata_audit,
                "concept_status": r.concept_status,
                "concept_code": r.concept_code,
                "concept_reason_code": r.concept_reason_code,
                "ncert_trace": r.ncert_trace,
                "mutated": r.mutated,
            }
            for r in results
        ],
    }


__all__ = [
    "StructuralFinding",
    "ValidatorV2Result",
    "resolve_concept",
    "structural_answer_checks",
    "validate_candidate_list_v2",
    "validate_candidate_v2",
]
