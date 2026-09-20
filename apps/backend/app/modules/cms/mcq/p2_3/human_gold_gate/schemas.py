"""P2.3 human-gold validation gate schemas and configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GATE_VERSION = "p2_3_human_gold_gate_v1"
GOLD_SAMPLE_SIZE = 100

HumanReviewStatus = Literal["HUMAN_REVIEW_PENDING", "HUMAN_REVIEW_PARTIAL", "HUMAN_REVIEW_COMPLETE"]
GoldLabel = Literal["ACCEPT", "MINOR", "MAJOR", "REJECT", "INCONCLUSIVE", "INVALID_HUMAN_LABEL"]
GateStatus = Literal["GREEN", "YELLOW", "RED"]
TenKRecommendation = Literal["PROCEED", "REMEDIATE_FIRST", "DO_NOT_PROCEED"]

HUMAN_REVIEW_REQUIRED_FIELDS = frozenset(
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
    }
)

HUMAN_REVIEW_OPTIONAL_FIELDS = frozenset({"reviewer_notes"})

HUMAN_REVIEW_COLUMNS = HUMAN_REVIEW_REQUIRED_FIELDS | HUMAN_REVIEW_OPTIONAL_FIELDS

INCOMPLETE_HUMAN_VALUES = frozenset(
    {"", "PENDING", "pending", "N/A", "NOT_REVIEWED", "null", "None"}
)

REVIEW_CSV_COLUMNS = [
    "question_id",
    "subject",
    "class",
    "chapter",
    "topic",
    "question",
    "option_A",
    "option_B",
    "option_C",
    "option_D",
    "proposed_answer",
    "validator_verdict",
    "validation_status_before_R1",
    "validation_status_after_R1",
    "r1_validator_provider",
    "preaudit_priority",
    "preaudit_verdict",
    "preaudit_reason",
    "preaudit_recommended_action",
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
]

PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

FAILURE_CATEGORIES = [
    "WRONG_ANSWER",
    "MULTIPLE_CORRECT_OPTIONS",
    "NO_CORRECT_OPTION",
    "AMBIGUOUS_STEM",
    "MISSING_CONTEXT",
    "BAD_DISTRACTOR",
    "DUPLICATE",
    "NCERT_UNSUPPORTED",
    "NCERT_CITATION_ERROR",
    "SCIENTIFIC_ERROR",
    "CALCULATION_ERROR",
    "ASSERTION_REASON_ERROR",
    "QUESTION_TYPE_ERROR",
    "DIFFICULTY_ERROR",
    "NEET_SUITABILITY_ERROR",
    "FORMATTING_ERROR",
    "INCOMPLETE_QUESTION",
    "OTHER",
]

PIPELINE_FIXES = [
    "GENERATOR_PROMPT_FIX",
    "SOURCE_SELECTION_FIX",
    "ANSWER_VALIDATOR_FIX",
    "NCERT_RETRIEVAL_FIX",
    "DUPLICATE_DETECTOR_FIX",
    "QUESTION_TYPE_RULE_FIX",
    "DIFFICULTY_RULE_FIX",
    "ASSERTION_REASON_RULE_FIX",
    "NUMERICAL_VALIDATION_FIX",
    "NO_PIPELINE_CHANGE",
    "HUMAN_ONLY",
]

PROTECTED_ARTIFACT_PATHS = [
    "data/staging/mcq/p2_3/human_gold_sample.csv",
    "data/staging/mcq/p2_3/generation_results.jsonl",
    "data/staging/mcq/p2_3/validation_results.jsonl",
    "data/staging/mcq/p2_3_r1/human_gold_sample_r1_annotated.csv",
    "data/staging/mcq/p2_3_r1/r1_merged_validation.jsonl",
    "data/staging/mcq/p2_3_pre_human_audit/pre_human_audit.jsonl",
]


@dataclass(frozen=True)
class GateThresholds:
    """Quality thresholds for GREEN. None → THRESHOLDS_PENDING_POLICY."""

    human_gold_min_reviewed: int = 100
    max_false_pass_rate_green: float | None = None
    min_answer_key_agreement_green: float | None = None
    min_overall_agreement_green: float | None = None
    max_critical_false_pass_green: int = 0

    def thresholds_pending(self) -> bool:
        return (
            self.max_false_pass_rate_green is None
            or self.min_answer_key_agreement_green is None
            or self.min_overall_agreement_green is None
        )
