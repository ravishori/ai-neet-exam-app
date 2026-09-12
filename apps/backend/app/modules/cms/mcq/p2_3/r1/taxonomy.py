"""P2.3-R1 deterministic QA failure taxonomy."""

from __future__ import annotations

from collections import Counter
from typing import Any

# Map QA error codes → taxonomy bucket
ERROR_BUCKET: dict[str, str] = {
    "EMPTY_STEM": "missing_stem",
    "QUESTION_TOO_SHORT": "formatting_failure",
    "OPTION_COUNT": "invalid_option_count",
    "EMPTY_OPTION": "missing_option",
    "DUPLICATE_OPTIONS": "multiple_defensible_answers",
    "INVALID_ANSWER": "invalid_answer",
    "EMPTY_EXPLANATION": "missing_explanation",
    "EXPLANATION_TOO_SHORT": "missing_explanation",
    "NOT_NCERT_SUPPORTED": "missing_ncert_evidence",
    "MISSING_SOURCE_REF": "missing_ncert_evidence",
    "MISSING_PROVIDER_PROVENANCE": "missing_metadata",
    "INVALID_QUESTION_TYPE": "missing_metadata",
    "INVALID_DIFFICULTY": "missing_metadata",
    "NUMERICAL_MISSING_NUMBERS": "formatting_failure",
}

BUCKET_LABELS: dict[str, str] = {
    "missing_stem": "schema/parser failure — missing stem",
    "missing_option": "missing option",
    "invalid_option_count": "invalid option count",
    "invalid_answer": "invalid answer",
    "multiple_defensible_answers": "duplicate/near-duplicate options",
    "missing_explanation": "missing explanation",
    "missing_ncert_evidence": "missing NCERT evidence",
    "missing_metadata": "missing metadata",
    "formatting_failure": "formatting failure",
    "provider_failure": "provider failure (not scientific QA)",
    "model_rejected_ncert": "unsupported NCERT (model rejected)",
    "other": "other",
}


def _origin_for_record(rec: dict[str, Any], primary_bucket: str) -> str:
    gen_status = rec.get("generation_status") or ""
    errors = rec.get("errors") or []
    err_text = " ".join(str(e) for e in errors).lower()

    if gen_status == "FAILED" and any("billing" in str(e).lower() or "credit" in str(e).lower() for e in errors):
        return "MODEL_GENERATION_FAILURE"
    if gen_status == "FAILED":
        return "MODEL_GENERATION_FAILURE"
    if gen_status == "REJECTED":
        if "ncert" in err_text or "excerpt" in err_text or "unsupported" in err_text:
            return "SOURCE_PLANNING_FAILURE"
        return "MODEL_GENERATION_FAILURE"
    if primary_bucket in ("missing_stem", "invalid_option_count", "missing_option", "invalid_answer"):
        if gen_status == "GENERATED":
            return "PARSER/SCHEMA_FAILURE"
        return "MODEL_GENERATION_FAILURE"
    if primary_bucket == "missing_ncert_evidence":
        return "SOURCE_PLANNING_FAILURE"
    return "UNKNOWN"


def classify_qa_failure(rec: dict[str, Any]) -> dict[str, Any]:
    """Classify a single QA-fail record."""
    if rec.get("qa_status") == "PASS":
        return {"bucket": None, "origin": None, "errors": []}

    errors = list(rec.get("errors") or [])
    gen_status = rec.get("generation_status") or ""

    if gen_status == "FAILED":
        bucket = "provider_failure"
    elif gen_status == "REJECTED":
        bucket = "model_rejected_ncert"
    else:
        buckets = [ERROR_BUCKET.get(e, "other") for e in errors if e in ERROR_BUCKET]
        bucket = buckets[0] if buckets else "other"

    return {
        "question_id": rec.get("question_id"),
        "bucket": bucket,
        "bucket_label": BUCKET_LABELS.get(bucket, bucket),
        "origin": _origin_for_record(rec, bucket),
        "errors": errors,
        "generation_provider": rec.get("generation_provider"),
        "generation_status": gen_status,
    }


def build_qa_failure_taxonomy(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build taxonomy for all QA-fail records (expected ~386)."""
    fails = [r for r in records if r.get("qa_status") != "PASS"]
    classified = [classify_qa_failure(r) for r in fails]
    bucket_counts: Counter[str] = Counter(c["bucket"] for c in classified if c["bucket"])
    origin_counts: Counter[str] = Counter(c["origin"] for c in classified if c["origin"])
    total = len(fails) or 1
    return {
        "qa_fail_count": len(fails),
        "bucket_counts": dict(bucket_counts),
        "bucket_percentages": {k: round(100.0 * v / total, 2) for k, v in bucket_counts.items()},
        "origin_counts": dict(origin_counts),
        "origin_percentages": {k: round(100.0 * v / total, 2) for k, v in origin_counts.items()},
        "records": classified,
    }
