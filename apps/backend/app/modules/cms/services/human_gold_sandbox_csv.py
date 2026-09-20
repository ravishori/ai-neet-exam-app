"""CSV validation for P2.3 Human Gold Review Sandbox."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections import Counter
from typing import Any

MAX_CSV_BYTES = 5 * 1024 * 1024
ALLOWED_MIME = {"text/csv", "text/plain", "application/csv", "application/vnd.ms-excel"}

REQUIRED_COLUMNS = frozenset(
    {
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
        "NCERT_source",
        "validator_verdict",
    }
)

PREAUDIT_COLUMNS = frozenset(
    {
        "preaudit_priority",
        "preaudit_verdict",
        "preaudit_reason",
        "preaudit_recommended_action",
    }
)

HUMAN_COLUMNS = frozenset(
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

VALID_ANSWERS = frozenset({"A", "B", "C", "D"})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_filename(name: str) -> str:
    base = name.replace("\\", "/").split("/")[-1]
    base = re.sub(r"[^\w.\-]", "_", base)[:200]
    return base or "upload.csv"


def validate_upload(*, filename: str, content_type: str | None, data: bytes) -> None:
    if not filename.lower().endswith(".csv"):
        raise ValueError("INVALID_EXTENSION")
    if content_type and content_type not in ALLOWED_MIME:
        raise ValueError("INVALID_MIME")
    if len(data) == 0:
        raise ValueError("EMPTY_FILE")
    if len(data) > MAX_CSV_BYTES:
        raise ValueError("FILE_TOO_LARGE")


def parse_csv(data: bytes) -> tuple[list[dict[str, str]], dict[str, Any]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("INVALID_UTF8") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("MISSING_HEADER")
    columns = {c.strip() for c in reader.fieldnames if c}
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(f"MISSING_COLUMNS:{','.join(sorted(missing))}")

    rows: list[dict[str, str]] = []
    errors: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for idx, raw in enumerate(reader, start=2):
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        qid = row.get("question_id", "")
        row_errors: list[str] = []
        if not qid:
            row_errors.append("MISSING_QUESTION_ID")
        elif qid in seen_ids:
            row_errors.append("DUPLICATE_QUESTION_ID")
        else:
            seen_ids.add(qid)
        ans = row.get("proposed_answer", "").upper()
        if ans and ans not in VALID_ANSWERS:
            row_errors.append("INVALID_PROPOSED_ANSWER")
        for opt in ("option_A", "option_B", "option_C", "option_D"):
            if not row.get(opt):
                row_errors.append(f"EMPTY_{opt}")
        if row_errors:
            errors.append({"row": idx, "question_id": qid, "errors": row_errors})
        else:
            rows.append(row)

    report: dict[str, Any] = {
        "filename_valid": True,
        "row_count": len(rows) + len(errors),
        "valid_rows": len(rows),
        "invalid_rows": len(errors),
        "errors": errors,
        "duplicate_question_ids": [],
        "subjects": dict(Counter(r.get("subject", "") for r in rows)),
        "has_preaudit": bool(PREAUDIT_COLUMNS & columns),
        "has_human_columns": bool(HUMAN_COLUMNS & columns),
        "preaudit_present": bool(PREAUDIT_COLUMNS & columns),
        "preaudit_missing_note": None if (PREAUDIT_COLUMNS & columns) else "PRE-HUMAN AUDIT DATA NOT PRESENT",
        "priorities": dict(Counter(r.get("preaudit_priority") or "LOW" for r in rows)),
        "sha256": sha256_bytes(data),
        "import_status": "READY" if rows and not errors else "INVALID",
    }
    return rows, report


def escape_csv_formula(value: str) -> str:
    if value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value
