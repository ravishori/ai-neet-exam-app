"""Phase 4 — deterministic failure-reason classification for NULL-subject
questions. Reuses the SCORES already computed by the existing Phase 2/3
scorers (from reports/ncert_subject_phase2*_resolution.csv) — this module
only categorizes an existing result, it never re-scores or lowers a bar.
"""

from __future__ import annotations

GAP_CATEGORIES = (
    "NO_NCERT_MATCH", "WEAK_NCERT_MATCH", "MULTI_SUBJECT_MATCH", "CROSS_DISCIPLINARY",
    "INSUFFICIENT_TEXT", "MALFORMED_SOURCE", "MISSING_OPTIONS", "EXTRACTION_ARTIFACT",
    "AMBIGUOUS_PHYSICS_CHEMISTRY", "AMBIGUOUS_BIOLOGY_SUBJECT", "INSUFFICIENT_PAGE_EVIDENCE", "OTHER",
)


def classify_gap_reason(
    *,
    quality_issues: list[str],
    physics_score: float,
    chemistry_score: float,
    biology_score: float,
    top_subject: str | None,
    second_subject: str | None,
    score_margin: float,
    match_type: str | None,
) -> str:
    if any(i.startswith("MISSING_STEM") or i.startswith("MALFORMED_STEM") for i in quality_issues):
        return "INSUFFICIENT_TEXT"
    if any(i.startswith("EXTRACTION_ARTIFACT") for i in quality_issues):
        return "EXTRACTION_ARTIFACT"
    if any(i.startswith("MISSING_ALL_OPTIONS") or i.startswith("MISSING_SOME_OPTIONS") for i in quality_issues):
        return "MISSING_OPTIONS"
    if any(i.startswith("MALFORMED_OPTIONS") for i in quality_issues):
        return "MALFORMED_SOURCE"

    scores = {"Physics": physics_score, "Chemistry": chemistry_score, "Biology": biology_score}
    nonzero = {s: v for s, v in scores.items() if v > 0}

    if not nonzero:
        return "NO_NCERT_MATCH"

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top_v, second_v, third_v = ranked[0][1], ranked[1][1], ranked[2][1]

    if top_v == second_v and top_v > 0:
        return "CROSS_DISCIPLINARY"

    if third_v > 0 and (top_v - third_v) < max(6.0, 0.35 * top_v):
        return "MULTI_SUBJECT_MATCH"

    if match_type == "EXACT_NCERT_PHRASE" and score_margin < max(6.0, 0.35 * top_v):
        return "INSUFFICIENT_PAGE_EVIDENCE"

    if top_v < 10:
        return "WEAK_NCERT_MATCH"

    pair = {top_subject, second_subject}
    if pair == {"Physics", "Chemistry"}:
        return "AMBIGUOUS_PHYSICS_CHEMISTRY"
    if "Biology" in pair and pair != {"Physics", "Chemistry"}:
        return "AMBIGUOUS_BIOLOGY_SUBJECT"

    return "OTHER"
