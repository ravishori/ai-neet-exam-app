"""Failure taxonomy for human vs AI disagreements."""

from __future__ import annotations

from typing import Any

from app.modules.cms.mcq.p2_3.human_gold_gate.normalization import (
    normalize_answer_key,
    normalize_human_overall,
    normalize_ncert,
    normalize_neet,
)


def classify_disagreement(row: dict[str, Any], preaudit: dict[str, Any] | None) -> dict[str, str]:
    pa = preaudit or {}
    categories: list[str] = []
    severity = "MINOR"
    explanations: list[str] = []

    human = normalize_human_overall(row)
    prop = normalize_answer_key(row.get("proposed_answer"))
    human_ans = normalize_answer_key(row.get("human_answer"))

    if prop and human_ans and prop != human_ans:
        categories.append("WRONG_ANSWER")
        severity = "CRITICAL"
        explanations.append(f"proposed={prop} human={human_ans}")

    amb = str(row.get("human_ambiguity") or "").strip().upper()
    if amb in {"YES", "TRUE", "AMBIGUOUS", "HIGH"}:
        categories.append("AMBIGUOUS_STEM")
        severity = max_severity(severity, "MAJOR")

    dup = str(row.get("human_duplicate") or "").strip().upper()
    if dup in {"YES", "TRUE", "DUPLICATE", "EXACT_DUPLICATE", "NEAR_DUPLICATE", "SEMANTIC_DUPLICATE"}:
        categories.append("DUPLICATE")
        severity = max_severity(severity, "MAJOR")

    ncert_h = normalize_ncert(row.get("human_ncert_support"))
    if ncert_h in {"UNSUPPORTED", "INCORRECT_CITATION"}:
        cat = "NCERT_CITATION_ERROR" if ncert_h == "INCORRECT_CITATION" else "NCERT_UNSUPPORTED"
        categories.append(cat)
        severity = max_severity(severity, "MAJOR")

    neet_h = normalize_neet(row.get("human_neet_suitability"))
    if neet_h == "UNSUITABLE":
        categories.append("NEET_SUITABILITY_ERROR")
        severity = max_severity(severity, "MAJOR")

    if pa.get("preaudit_calculation_check") == "FAIL":
        categories.append("CALCULATION_ERROR")
        severity = max_severity(severity, "CRITICAL")

    if pa.get("preaudit_question_type_check") == "TYPE_MISMATCH":
        categories.append("QUESTION_TYPE_ERROR")
        severity = max_severity(severity, "MAJOR")

    if "proposed_option_correct=FALSE" in (pa.get("preaudit_assertion_reason_check") or ""):
        categories.append("ASSERTION_REASON_ERROR")
        severity = max_severity(severity, "MAJOR")

    if pa.get("preaudit_option_quality") in ("BAD", "WEAK"):
        categories.append("BAD_DISTRACTOR")
        severity = max_severity(severity, "MINOR")

    if human in ("MAJOR", "REJECT") and not categories:
        categories.append("OTHER")
        severity = max_severity(severity, "MAJOR")
        explanations.append(f"human_overall={human}")

    if not categories:
        categories.append("OTHER")
        explanations.append("disagreement without specific automated category")

    return {
        "failure_category": categories[0],
        "failure_categories": ";".join(categories),
        "failure_severity": severity,
        "failure_explanation": "; ".join(explanations) or categories[0],
    }


def recommended_pipeline_fix(row: dict[str, Any], failure: dict[str, str]) -> str:
    cat = failure.get("failure_category") or "OTHER"
    mapping = {
        "WRONG_ANSWER": "ANSWER_VALIDATOR_FIX",
        "CALCULATION_ERROR": "NUMERICAL_VALIDATION_FIX",
        "NCERT_UNSUPPORTED": "NCERT_RETRIEVAL_FIX",
        "NCERT_CITATION_ERROR": "SOURCE_SELECTION_FIX",
        "DUPLICATE": "DUPLICATE_DETECTOR_FIX",
        "QUESTION_TYPE_ERROR": "QUESTION_TYPE_RULE_FIX",
        "ASSERTION_REASON_ERROR": "ASSERTION_REASON_RULE_FIX",
        "DIFFICULTY_ERROR": "DIFFICULTY_RULE_FIX",
        "NEET_SUITABILITY_ERROR": "GENERATOR_PROMPT_FIX",
        "BAD_DISTRACTOR": "GENERATOR_PROMPT_FIX",
        "AMBIGUOUS_STEM": "GENERATOR_PROMPT_FIX",
    }
    fix = mapping.get(cat, "NO_PIPELINE_CHANGE")
    human = normalize_human_overall(row)
    if human == "MINOR" and cat in {"BAD_DISTRACTOR", "AMBIGUOUS_STEM"}:
        return "HUMAN_ONLY"
    return fix


def max_severity(current: str, new: str) -> str:
    rank = {"MINOR": 1, "MAJOR": 2, "CRITICAL": 3}
    return new if rank.get(new, 0) > rank.get(current, 0) else current
