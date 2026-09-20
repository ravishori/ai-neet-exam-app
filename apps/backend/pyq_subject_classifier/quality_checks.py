"""Phase 4 — pure, deterministic per-question integrity/quality checks.
No DB access, no NCERT access — just structural validation of one row's
fields. Never modifies raw_stem/raw_options; normalization here is for
analysis only.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

VALID_SUBJECTS = {"Physics", "Chemistry", "Biology", "Botany", "Zoology"}
OPTION_LABELS = ("A", "B", "C", "D")

_EXTRACTION_ARTIFACT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]|�|�")
_WS_RE = re.compile(r"\s+")


def normalize_for_dedup(text: str | None) -> str:
    """Analysis-only normalization for duplicate detection / hashing.
    Never applied to the persisted raw_stem/raw_options."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _EXTRACTION_ARTIFACT_RE.sub("", t)
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


def stem_hash(raw_stem: str | None) -> str:
    return hashlib.sha256(normalize_for_dedup(raw_stem).encode("utf-8")).hexdigest()


def options_hash(raw_options) -> str:
    if not isinstance(raw_options, dict):
        return hashlib.sha256(b"").hexdigest()
    parts = [normalize_for_dedup(str(raw_options.get(k, ""))) for k in OPTION_LABELS]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def check_question_integrity(*, raw_stem: str | None, raw_options, question_number, subject: str | None) -> list[str]:
    """Returns a list of issue codes — empty list means no issues found."""
    issues: list[str] = []

    if not raw_stem or not raw_stem.strip():
        issues.append("MISSING_STEM")
    elif len(normalize_for_dedup(raw_stem)) < 8:
        issues.append("MALFORMED_STEM_TOO_SHORT")
    if raw_stem and _EXTRACTION_ARTIFACT_RE.search(raw_stem):
        issues.append("EXTRACTION_ARTIFACT_IN_STEM")

    if not isinstance(raw_options, dict):
        issues.append("MALFORMED_OPTIONS_NOT_OBJECT")
    else:
        present = [k for k in OPTION_LABELS if str(raw_options.get(k, "")).strip()]
        if len(present) == 0:
            issues.append("MISSING_ALL_OPTIONS")
        elif len(present) < 4:
            issues.append("MISSING_SOME_OPTIONS")
        texts = [normalize_for_dedup(str(raw_options.get(k, ""))) for k in present]
        if len(texts) != len(set(texts)) and len(texts) > 0:
            issues.append("DUPLICATE_OPTION_TEXT")
        extra_keys = set(raw_options.keys()) - set(OPTION_LABELS)
        if extra_keys:
            issues.append("UNEXPECTED_OPTION_LABELS")

    if question_number is None:
        issues.append("MISSING_QUESTION_NUMBER")
    elif isinstance(question_number, int) and question_number < 1:
        issues.append("INVALID_QUESTION_NUMBER")

    if subject is not None and subject not in VALID_SUBJECTS:
        issues.append(f"INVALID_SUBJECT_VALUE:{subject}")

    return issues
