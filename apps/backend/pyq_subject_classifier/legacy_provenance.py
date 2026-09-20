"""Phase 4 — read-only provenance classification for the legacy
(no-audit-row) subject population. Never changes the recorded subject.
Reuses the existing, unmodified Phase 2 scorer to independently check
whether local NCERT evidence agrees with the legacy subject — this is a
consistency check, not a reclassification.
"""

from __future__ import annotations

PROVENANCE_STATUSES = (
    "VERIFIED_EXISTING_PROVENANCE", "SUPPORTED_BY_NCERT", "SUPPORTED_BY_SOURCE_METADATA",
    "WEAKLY_SUPPORTED", "CONFLICTING_EVIDENCE", "NO_RECOVERABLE_PROVENANCE",
)


def classify_legacy_provenance(*, current_subject: str, recomputed_top_subject: str | None,
                                recomputed_status: str, recomputed_top_score: float) -> dict:
    """recomputed_* come from running the existing classify_phase2() scorer
    on the legacy question's stem/options — NOT a new algorithm."""
    if recomputed_top_score == 0:
        return {
            "provenance_status": "SUPPORTED_BY_SOURCE_METADATA",
            "evidence_strength": "NONE",
            "ncert_match": False,
            "conflict_status": "NO_CONFLICT",
            "recommended_action": "NONE_KEEP_AS_IS",
        }

    agrees = recomputed_top_subject == current_subject
    if agrees and recomputed_status == "RESOLVED":
        return {
            "provenance_status": "SUPPORTED_BY_NCERT",
            "evidence_strength": "STRONG",
            "ncert_match": True,
            "conflict_status": "NO_CONFLICT",
            "recommended_action": "NONE_KEEP_AS_IS",
        }
    if agrees:
        return {
            "provenance_status": "WEAKLY_SUPPORTED",
            "evidence_strength": "MODERATE",
            "ncert_match": True,
            "conflict_status": "NO_CONFLICT",
            "recommended_action": "NONE_KEEP_AS_IS",
        }
    if recomputed_status == "RESOLVED" and not agrees:
        return {
            "provenance_status": "CONFLICTING_EVIDENCE",
            "evidence_strength": "MODERATE",
            "ncert_match": False,
            "conflict_status": "CONFLICT",
            "recommended_action": "HUMAN_REVIEW_RECOMMENDED",
        }
    # Nonzero evidence but AMBIGUOUS/UNRESOLVED and leaning a different subject.
    return {
        "provenance_status": "WEAKLY_SUPPORTED",
        "evidence_strength": "WEAK",
        "ncert_match": False,
        "conflict_status": "NO_CONFLICT",
        "recommended_action": "NONE_KEEP_AS_IS",
    }
