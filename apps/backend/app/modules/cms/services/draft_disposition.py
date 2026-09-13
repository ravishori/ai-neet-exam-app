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
