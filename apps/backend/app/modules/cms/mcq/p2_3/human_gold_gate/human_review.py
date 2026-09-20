"""Human review completion detection with PENDING preservation."""

from __future__ import annotations

from typing import Any

from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import (
    HUMAN_REVIEW_REQUIRED_FIELDS,
    INCOMPLETE_HUMAN_VALUES,
    HumanReviewStatus,
)


def _normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_incomplete_human_value(value: Any) -> bool:
    text = _normalize_cell(value)
    if text in INCOMPLETE_HUMAN_VALUES:
        return True
    return False


def human_review_status(row: dict[str, Any]) -> HumanReviewStatus:
    filled = 0
    for field in HUMAN_REVIEW_REQUIRED_FIELDS:
        val = _normalize_cell(row.get(field))
        if not is_incomplete_human_value(val):
            filled += 1
    if filled == 0:
        return "HUMAN_REVIEW_PENDING"
    if filled < len(HUMAN_REVIEW_REQUIRED_FIELDS):
        return "HUMAN_REVIEW_PARTIAL"
    return "HUMAN_REVIEW_COMPLETE"


def completion_stats(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    pending = partial = complete = 0
    for row in rows:
        status = human_review_status(row)
        if status == "HUMAN_REVIEW_PENDING":
            pending += 1
        elif status == "HUMAN_REVIEW_PARTIAL":
            partial += 1
        else:
            complete += 1
    total = len(rows) or 1
    return {
        "reviewed_count": complete,
        "pending_count": pending,
        "partial_count": partial,
        "completion_rate": round(complete / total, 4),
    }


def preserve_human_fields(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """Copy human columns from source to target without normalizing PENDING."""
    from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import HUMAN_REVIEW_COLUMNS

    out = dict(target)
    for col in HUMAN_REVIEW_COLUMNS:
        if col in source:
            out[col] = source[col]
    return out


def verify_source_human_fields_unchanged(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> None:
    from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import HUMAN_REVIEW_COLUMNS

    before_by = {r["question_id"]: r for r in before}
    for row in after:
        qid = row["question_id"]
        orig = before_by[qid]
        for col in HUMAN_REVIEW_COLUMNS:
            if _normalize_cell(orig.get(col)) != _normalize_cell(row.get(col)):
                raise ValueError(f"Source human field {col} modified for {qid}")
