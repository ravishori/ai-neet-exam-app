"""Phase 4 — independent answer-assertion quality audit (read-only).
Never invents an answer, never infers correctness from option content."""

from __future__ import annotations

from collections import defaultdict

VALID_OPTIONS = {"A", "B", "C", "D"}


def audit_assertions_for_question(question_id: str, raw_options, assertions: list[dict]) -> list[str]:
    """assertions: list of {asserted_option, verification_status, assertion_source}."""
    issues: list[str] = []
    if not assertions:
        return issues  # absence is a normal, expected state — not an issue by itself

    options_present = (
        {k for k in ("A", "B", "C", "D") if isinstance(raw_options, dict) and str(raw_options.get(k, "")).strip()}
    )
    for a in assertions:
        opt = a["asserted_option"]
        if opt not in VALID_OPTIONS:
            issues.append(f"ANSWER_OUTSIDE_A_D:{opt}")
        elif options_present and opt not in options_present:
            issues.append(f"ANSWER_REFERENCES_MISSING_OPTION:{opt}")

    verified = [a for a in assertions if a["verification_status"] == "VERIFIED"]
    if len(verified) > 1:
        distinct_options = {a["asserted_option"] for a in verified}
        if len(distinct_options) > 1:
            issues.append("CONTRADICTORY_VERIFIED_ASSERTIONS")
        else:
            issues.append("MULTIPLE_VERIFIED_ASSERTIONS_SAME_OPTION")

    sources = [a["assertion_source"] for a in assertions]
    if any(not s or not s.strip() for s in sources):
        issues.append("MISSING_ASSERTION_PROVENANCE")

    if len(sources) != len(set(sources)):
        issues.append("DUPLICATE_ASSERTION_SOURCE")

    return issues


def group_assertions_by_question(rows: list[dict]) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for r in rows:
        out[r["question_id"]].append(r)
    return out
