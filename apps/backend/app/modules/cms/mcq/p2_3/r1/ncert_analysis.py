"""P2.3-R1 analysis of model-rejected unsupported-NCERT records."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import fitz


def _excerpt_available(study_root: Path, source_file: str, source_page: int) -> tuple[bool, int]:
    pdf = study_root / source_file.replace("\\", "/")
    if not pdf.exists():
        return False, 0
    doc = fitz.open(pdf)
    try:
        idx = max(0, int(source_page) - 1)
        if idx >= doc.page_count:
            return False, 0
        text = (doc.load_page(idx).get_text("text") or "").strip()
        return len(text) >= 120, len(text)
    finally:
        doc.close()


def _infer_root_cause(rec: dict[str, Any], *, excerpt_len: int) -> str:
    errors = " ".join(str(e) for e in (rec.get("errors") or [])).lower()
    qtype = rec.get("question_type") or ""
    if excerpt_len < 120:
        return "NCERT evidence extraction"
    if qtype == "numerical" and ("numerical" in errors or "number" in errors):
        return "question blueprint"
    if "excerpt" in errors or "ncert" in errors or rec.get("generation_status") == "REJECTED":
        return "source selection"
    if rec.get("generation_provider") in ("anthropic", "openai") and rec.get("generation_status") == "FAILED":
        return "provider"
    return "prompt"


def build_ncert_failure_analysis(records: list[dict[str, Any]], *, study_root: Path) -> dict[str, Any]:
    """Analyze REJECTED / unsupported-NCERT generation failures (expected ~46)."""
    rejected = [
        r
        for r in records
        if r.get("generation_status") == "REJECTED"
        or "NOT_NCERT_SUPPORTED" in (r.get("errors") or [])
        or (r.get("source_support") or "").upper() not in ("", "NCERT-SUPPORTED")
        and r.get("generation_status") == "GENERATED"
    ]
    # Focus on explicit model REJECTED cohort
    cohort = [r for r in records if r.get("generation_status") == "REJECTED"]
    cases: list[dict[str, Any]] = []
    root_causes: Counter[str] = Counter()
    for rec in cohort:
        avail, excerpt_len = _excerpt_available(
            study_root, rec.get("source_file") or "", int(rec.get("source_page") or 1)
        )
        root = _infer_root_cause(rec, excerpt_len=excerpt_len)
        root_causes[root] += 1
        cases.append(
            {
                "question_id": rec.get("question_id"),
                "subject": rec.get("subject"),
                "class": rec.get("class"),
                "chapter": rec.get("chapter"),
                "topic": rec.get("topic"),
                "question_type": rec.get("question_type"),
                "source_locator": rec.get("source_locator"),
                "source_file": rec.get("source_file"),
                "source_page": rec.get("source_page"),
                "source_excerpt_available": avail,
                "source_excerpt_length": excerpt_len,
                "rejection_reason": (rec.get("errors") or [""])[0] if rec.get("errors") else "",
                "generation_provider": rec.get("generation_provider"),
                "generation_model": rec.get("generation_model"),
                "inferred_root_cause": root,
            }
        )
    return {
        "rejected_count": len(cohort),
        "by_subject": dict(Counter(c["subject"] for c in cases)),
        "by_question_type": dict(Counter(c["question_type"] for c in cases)),
        "by_provider": dict(Counter(c["generation_provider"] for c in cases)),
        "inferred_root_causes": dict(root_causes),
        "cases": cases,
    }
