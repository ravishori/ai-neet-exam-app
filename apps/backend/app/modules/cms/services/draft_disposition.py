"""Phase 3.2 — evidence-based disposition labels for unmapped DRAFT backlog.

Read-only classification helpers. Never publishes. Never marks content valid
merely because a row exists. Operators may optionally apply `disposition:*`
tags via an explicit CLI flag — classification alone does not mutate the DB.
"""

from __future__ import annotations

from typing import Any, Literal

DispositionCode = Literal[
    "UNMAPPED",
    "MAPPABLE",
    "NEEDS_SOURCE",
    "NEEDS_REVIEW",
    "POSSIBLE_DUPLICATE",
    "INVALID",
    "OBSOLETE",
    "READY_FOR_ECAEP",
]

DISPOSITION_CODES: tuple[DispositionCode, ...] = (
    "UNMAPPED",
    "MAPPABLE",
    "NEEDS_SOURCE",
    "NEEDS_REVIEW",
    "POSSIBLE_DUPLICATE",
    "INVALID",
    "OBSOLETE",
    "READY_FOR_ECAEP",
)

DISPOSITION_TAG_PREFIX = "disposition:"

# Readiness labels for Chemistry / Zoology operational reports (operators only).
ReadinessLabel = Literal[
    "READY",
    "NEEDS REVIEW",
    "NEEDS MAPPING",
    "NEEDS SOURCE",
    "NEEDS NCERT VERIFICATION",
    "DUPLICATE / POSSIBLE DUPLICATE",
    "NOT READY",
]

# Phase 3.3 Chemistry/Zoology draft intake categories (operator triage; never publish).
IntakeCode = Literal[
    "READY_FOR_REVIEW",
    "NEEDS_REVIEW",
    "NEEDS_SOURCE",
    "NEEDS_MAPPING",
    "POSSIBLE_DUPLICATE",
    "NOT_READY",
]


def intake_code_for_draft(
    *,
    status: str,
    concept_id: Any | None,
    structural_valid: bool,
    has_provenance_lineage: bool,
    suspected_duplicate: bool,
    has_stem: bool,
) -> IntakeCode:
    """Classify DRAFT (or reviewable) items for controlled intake — never auto-promotes."""
    if suspected_duplicate:
        return "POSSIBLE_DUPLICATE"
    if not concept_id:
        return "NEEDS_MAPPING"
    if not has_stem or not structural_valid:
        return "NOT_READY"
    if not has_provenance_lineage:
        return "NEEDS_SOURCE"
    if status == "DRAFT" and structural_valid and concept_id and has_provenance_lineage:
        return "READY_FOR_REVIEW"
    if status in ("DRAFT", "CHANGES_REQUESTED", "IN_REVIEW"):
        return "NEEDS_REVIEW"
    return "NOT_READY"


def ncert_state_from_evidence(*, tags: list[str] | None, body: dict | None) -> dict[str, Any]:
    """Read-only NCERT representation. Provenance must not be treated as verification."""
    tags = tags or []
    level = None
    for t in tags:
        if not isinstance(t, str):
            continue
        if t.startswith("ncert_level:"):
            level = t.split(":", 1)[1] or None
            break
        if t.startswith("ncert:") and t.split(":", 1)[1] in (
            "SOURCE_TEXT_VERIFIED",
            "SECTION_VERIFIED",
            "PAGE_VERIFIED",
            "NOT_VERIFIED",
        ):
            level = t.split(":", 1)[1]
            break
    evidence = None
    if isinstance(body, dict):
        raw = body.get("ncert_evidence")
        if isinstance(raw, dict):
            evidence = {
                "verification_level": raw.get("verification_level"),
                "chapter": raw.get("chapter"),
                "section": raw.get("section"),
                "page_number": raw.get("page_number"),
                "source_pdf_relpath": raw.get("source_pdf_relpath"),
                "verification_method": raw.get("verification_method"),
            }
            if not level:
                level = raw.get("verification_level")
    verified = bool(level) and str(level).upper() not in ("", "NOT_VERIFIED", "NONE", "0")
    return {
        "verification_level": level,
        "is_verified": verified,
        "has_structured_evidence": evidence is not None,
        "evidence_summary": evidence,
        "disclaimer": (
            "Provenance/source fields are not NCERT certification. "
            "Only structured ncert_evidence / explicit certify-ncert counts. "
            "Do not invent NCERT verification."
        ),
    }


def disposition_tag(code: DispositionCode) -> str:
    return f"{DISPOSITION_TAG_PREFIX}{code}"


def disposition_from_tags(tags: list[str] | None) -> DispositionCode | None:
    if not tags:
        return None
    for code in DISPOSITION_CODES:
        if disposition_tag(code) in tags:
            return code
    return None


def classify_draft_disposition(
    *,
    status: str,
    concept_id: Any | None,
    structural_valid: bool,
    has_provenance_lineage: bool,
    suspected_duplicate: bool,
    has_stem: bool,
    obsolete_markers: bool = False,
) -> DispositionCode:
    """Heuristic operator triage — not scientific validity, not publish authority."""
    if obsolete_markers:
        return "OBSOLETE"
    if status != "DRAFT":
        # Disposition model targets the draft backlog; other statuses stay review-path.
        if not concept_id:
            return "UNMAPPED"
        return "NEEDS_REVIEW"
    if not has_stem or not structural_valid:
        return "INVALID"
    if suspected_duplicate:
        return "POSSIBLE_DUPLICATE"
    if not concept_id:
        return "UNMAPPED"
    if not has_provenance_lineage:
        return "NEEDS_SOURCE"
    # Mapped + structural + lineage → eligible to enter ECAEP submit, not publish.
    return "READY_FOR_ECAEP"


def readiness_label_for_question(
    *,
    status: str,
    concept_id: Any | None,
    structural_valid: bool,
    has_provenance_lineage: bool,
    ncert_verified: bool,
    suspected_duplicate: bool,
) -> ReadinessLabel:
    """Per-question readiness for Chem/Zoo reports. Never implies auto-publish."""
    if suspected_duplicate:
        return "DUPLICATE / POSSIBLE DUPLICATE"
    if not concept_id:
        return "NEEDS MAPPING"
    if not structural_valid:
        return "NOT READY"
    if not has_provenance_lineage:
        return "NEEDS SOURCE"
    if status in ("DRAFT", "CHANGES_REQUESTED"):
        return "NEEDS REVIEW"
    if status == "IN_REVIEW":
        return "NEEDS REVIEW"
    if status == "APPROVED" and not ncert_verified:
        # Approval ≠ NCERT certification; flag for operators without blocking publish policy.
        return "NEEDS NCERT VERIFICATION"
    if status == "APPROVED":
        return "READY"  # ready for explicit gated publish — not published
    if status == "PUBLISHED" and not ncert_verified:
        return "NEEDS NCERT VERIFICATION"
    if status == "PUBLISHED":
        return "READY"
    return "NOT READY"
