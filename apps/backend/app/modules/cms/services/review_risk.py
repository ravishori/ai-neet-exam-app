"""HR-1 deterministic review-risk classification.

Pure function over data already persisted for a QUESTION content item —
no LLM call, no invented confidence score. Reuses the same deterministic
publication-gate report (`PublicationGateReport.content_ready`) that
`publish()` and TRUSTED-FACTORY-SUBMIT-001 already compute, so this never
duplicates gate logic.

DETERMINISTIC RULES (evaluated in order; first match wins):

RED (highest priority — needs the most careful human attention):
  - `content_ready` is False, i.e. at least one deterministic gate
    (structural / scientific-numerical / NCERT / taxonomy / duplicate /
    provenance) failed, OR
  - the latest AI-check report carries one or more `flags` (either a real
    EVALUATOR run flagged something, or an earlier factory QA step did).

GREEN (fast-track candidate — still requires a genuine human decision):
  - `content_ready` is True, AND
  - NCERT evidence `verification_level` is SECTION_VERIFIED or
    PAGE_VERIFIED (the two levels that carry a located source section/page,
    not just an unverified claim), AND
  - provenance lineage is known (`model_used` or `knowledge_unit_id` set
    on the version), AND
  - the AI-check report carries no flags (covers both an ordinary
    EVALUATOR pass and the deterministic TRUSTED-FACTORY-SUBMIT-001 skip,
    which explicitly always sets `flags: []`).

AMBER (default — everything else that passed the hard gates but doesn't
  clear the GREEN bar, e.g. missing/low NCERT verification level or no
  known generation lineage): assigned when neither RED nor GREEN applies.

KNOWN LIMITATION: this module does not attempt to infer question
difficulty balance, reviewer workload, or any similarity/duplicate score
beyond what `evaluate_question_publication_gates` already computes
(`duplicate_ok`, itself an exact/near-exact stem check) — a richer
similarity signal is not implemented here rather than fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_GREEN_NCERT_LEVELS = frozenset({"SECTION_VERIFIED", "PAGE_VERIFIED"})

RISK_BUCKETS = ("RED", "AMBER", "GREEN")


@dataclass
class ReviewRiskAssessment:
    bucket: str
    reasons: list[str] = field(default_factory=list)


def classify_review_risk(
    *,
    content_ready: bool,
    gate_reasons: list[str] | None,
    ai_check_flags: list[str] | None,
    ncert_verification_level: str | None,
    has_provenance_lineage: bool,
) -> ReviewRiskAssessment:
    """Pure, deterministic. No DB access, no LLM call, no randomness.

    Args mirror data already available from `PublicationGateReport` and
    `ContentVersion` — callers fetch those once per item and pass the
    already-computed values in.
    """
    flags = list(ai_check_flags or [])

    if not content_ready:
        reasons = ["One or more deterministic publication gates failed"]
        reasons.extend(gate_reasons or [])
        return ReviewRiskAssessment(bucket="RED", reasons=reasons)

    if flags:
        return ReviewRiskAssessment(
            bucket="RED", reasons=[f"AI-check report flagged: {f}" for f in flags]
        )

    if ncert_verification_level in _GREEN_NCERT_LEVELS and has_provenance_lineage:
        return ReviewRiskAssessment(
            bucket="GREEN",
            reasons=[
                f"NCERT evidence verified at {ncert_verification_level}",
                "Generation lineage known",
                "No AI-check flags",
            ],
        )

    reasons = ["Passed deterministic gates but does not meet GREEN criteria"]
    if ncert_verification_level not in _GREEN_NCERT_LEVELS:
        reasons.append(f"NCERT verification level is {ncert_verification_level or 'unset'}")
    if not has_provenance_lineage:
        reasons.append("No known generation lineage (model_used / knowledge_unit_id)")
    return ReviewRiskAssessment(bucket="AMBER", reasons=reasons)
