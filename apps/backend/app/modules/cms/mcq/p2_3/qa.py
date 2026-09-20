"""P2.3 deterministic QA before independent validation."""

from __future__ import annotations

import re
from typing import Any

from app.modules.cms.mcq.p2_3.schemas import McqRecord
from app.modules.cms.pyq.p2_2.live_mcq import structural_validate

NUMERIC_PATTERN = re.compile(r"\d+\.?\d*")


def automated_qa(record: McqRecord) -> tuple[str, list[str]]:
    errors: list[str] = []
    if not record.question.strip():
        errors.append("EMPTY_STEM")
    if not record.explanation.strip():
        errors.append("EMPTY_EXPLANATION")
    if not record.source_file or not record.source_excerpt_hash:
        errors.append("MISSING_SOURCE_REF")
    if not record.generation_provider:
        errors.append("MISSING_PROVIDER_PROVENANCE")
    if record.question_type not in (
        "factual",
        "conceptual",
        "statement_based",
        "assertion_reasoning",
        "application",
        "numerical",
        "match_relationship",
    ):
        errors.append("INVALID_QUESTION_TYPE")
    if record.difficulty not in ("EASY", "MEDIUM", "HARD"):
        errors.append("INVALID_DIFFICULTY")

    body = {
        "status": "GENERATED",
        "question": record.question,
        "options": record.options,
        "correct_answer": record.correct_option,
        "explanation": record.explanation,
        "source_support": record.source_support or "NCERT-SUPPORTED",
        "difficulty": record.difficulty,
    }
    errors.extend(structural_validate(body))

    if record.question_type == "numerical":
        if not NUMERIC_PATTERN.search(record.question + " ".join(record.options.values())):
            errors.append("NUMERICAL_MISSING_NUMBERS")

    if errors:
        return "REJECT", errors
    return "PASS", []


def map_validator_to_status(validator: dict[str, Any] | None) -> str:
    if not validator:
        return "INCONCLUSIVE"
    overall = validator.get("overall")
    if overall == "PASS":
        ncert = validator.get("ncert_support_class") or validator.get("ncert_support")
        if validator.get("ambiguity") == "FAIL":
            return "MAJOR_REVISION"
        if ncert in ("WEAK_SUPPORT", "NO_SUPPORT", "FAIL"):
            return "MAJOR_REVISION"
        if validator.get("difficulty") == "FAIL" or validator.get("stem") == "FAIL":
            return "MINOR_REVISION"
        return "READY"
    if overall == "FAIL":
        return "REJECT"
    return "INCONCLUSIVE"
