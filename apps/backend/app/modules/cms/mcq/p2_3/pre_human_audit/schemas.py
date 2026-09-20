"""P2.3 pre-human gold sample audit schemas."""

from __future__ import annotations

from typing import Any, Literal

PRE_AUDIT_VERSION = "p2_3_pre_human_audit_v1"
GOLD_SAMPLE_SIZE = 100

Priority = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
Verdict = Literal["PREAUDIT_FLAGGED", "PREAUDIT_REVIEW", "PREAUDIT_LIKELY_PASS"]
Severity = Literal["NONE", "MINOR", "MAJOR", "CRITICAL"]
OptionQuality = Literal["GOOD", "ACCEPTABLE", "WEAK", "BAD"]
NcertSupport = Literal[
    "DIRECT",
    "SUPPORTED_INFERENCE",
    "WEAK_SUPPORT",
    "UNSUPPORTED",
    "INCORRECT_CITATION",
    "NOT_VERIFIABLE",
]
NeetSuitability = Literal["SUITABLE", "SUITABLE_WITH_MINOR_EDIT", "QUESTIONABLE", "UNSUITABLE"]
DifficultyEst = Literal["EASY", "MEDIUM", "HARD", "UNKNOWN"]
DuplicateStatus = Literal["UNIQUE", "EXACT_DUPLICATE", "NEAR_DUPLICATE", "SEMANTIC_DUPLICATE", "POSSIBLE_DUPLICATE"]
CalcStatus = Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_APPLICABLE"]
AnswerCheck = Literal["CORRECT", "WRONG", "MULTIPLE_CORRECT", "NO_CORRECT", "INCONCLUSIVE", "NOT_CHECKED"]
TypeCheck = Literal["TYPE_CORRECT", "TYPE_MISMATCH", "QUESTION_TYPE_UNCLEAR"]
RecommendedAction = Literal[
    "HUMAN_VERIFY",
    "HUMAN_RECALCULATE",
    "HUMAN_CHECK_NCERT",
    "HUMAN_REVIEW_WORDING",
    "HUMAN_REVIEW_OPTIONS",
    "HUMAN_REVIEW_ANSWER",
    "HUMAN_REVIEW_ASSERTION_REASON",
    "HUMAN_REVIEW_DUPLICATE",
    "LIKELY_ACCEPT",
    "REJECT_AFTER_HUMAN_CONFIRMATION",
]

HUMAN_REVIEW_COLUMNS = frozenset(
    {
        "human_stem",
        "human_option_A",
        "human_option_B",
        "human_option_C",
        "human_option_D",
        "human_answer",
        "human_explanation",
        "human_ncert_support",
        "human_ambiguity",
        "human_duplicate",
        "human_difficulty",
        "human_neet_suitability",
        "human_overall",
        "reviewer_notes",
    }
)

PREAUDIT_OUTPUT_COLUMNS = [
    "question_id",
    "subject",
    "class",
    "chapter",
    "topic",
    "provider",
    "question_type",
    "question",
    "option_A",
    "option_B",
    "option_C",
    "option_D",
    "proposed_answer",
    "NCERT_source",
    "validator_verdict",
    "preaudit_answer_check",
    "preaudit_answer_confidence",
    "preaudit_calculation_check",
    "preaudit_calculated_answer",
    "preaudit_calculation_notes",
    "preaudit_stem_issue",
    "preaudit_stem_severity",
    "preaudit_option_quality",
    "preaudit_option_issue",
    "preaudit_option_severity",
    "preaudit_ncert_support",
    "preaudit_ncert_issue",
    "preaudit_scientific_issue",
    "preaudit_scientific_severity",
    "preaudit_assertion_reason_check",
    "preaudit_question_type_check",
    "preaudit_neet_suitability",
    "preaudit_independent_difficulty",
    "preaudit_duplicate_status",
    "preaudit_duplicate_question_id",
    "preaudit_duplicate_similarity",
    "preaudit_priority",
    "preaudit_verdict",
    "preaudit_reason",
    "preaudit_recommended_action",
]

QUEUE_COLUMNS = [
    "question_id",
    "subject",
    "chapter",
    "question",
    "proposed_answer",
    "validator_verdict",
    "preaudit_priority",
    "preaudit_verdict",
    "main_issue",
    "reason",
    "recommended_action",
    "preaudit_answer_confidence",
]

PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def empty_audit_record(row: dict[str, Any]) -> dict[str, Any]:
    """Build audit record preserving all original gold-sample fields."""
    out = dict(row)
    out.update(
        {
            "preaudit_answer_check": "NOT_CHECKED",
            "preaudit_answer_confidence": 0.0,
            "preaudit_calculation_check": "NOT_APPLICABLE",
            "preaudit_calculated_answer": "",
            "preaudit_calculation_notes": "",
            "preaudit_stem_issue": "",
            "preaudit_stem_severity": "NONE",
            "preaudit_option_quality": "ACCEPTABLE",
            "preaudit_option_issue": "",
            "preaudit_option_severity": "NONE",
            "preaudit_ncert_support": "NOT_VERIFIABLE",
            "preaudit_ncert_issue": "",
            "preaudit_scientific_issue": "",
            "preaudit_scientific_severity": "NONE",
            "preaudit_assertion_reason_check": "",
            "preaudit_question_type_check": "TYPE_CORRECT",
            "preaudit_neet_suitability": "SUITABLE",
            "preaudit_independent_difficulty": row.get("difficulty") or "UNKNOWN",
            "preaudit_duplicate_status": "UNIQUE",
            "preaudit_duplicate_question_id": "",
            "preaudit_duplicate_similarity": 0.0,
            "preaudit_priority": "LOW",
            "preaudit_verdict": "PREAUDIT_LIKELY_PASS",
            "preaudit_reason": "",
            "preaudit_recommended_action": "LIKELY_ACCEPT",
            "preaudit_version": PRE_AUDIT_VERSION,
        }
    )
    return out
