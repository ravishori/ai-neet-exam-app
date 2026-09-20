"""STEP 7/OUTPUTS — classification + review CSVs and JSON summary."""

from __future__ import annotations

import csv
import json

from .config import REPORTS_DIR


def _options_str(options) -> str:
    if not isinstance(options, dict):
        return ""
    return " | ".join(f"{k}: {options.get(k, '')}" for k in ("A", "B", "C", "D") if options.get(k))


def write_classification_csv(rows: list[dict], path=None) -> None:
    path = path or (REPORTS_DIR / "ncert_subject_classification.csv")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "question_id", "exam_year", "paper_code", "question_number",
            "predicted_subject", "confidence", "classification_status",
            "physics_score", "chemistry_score", "biology_score", "evidence",
        ])
        for r in rows:
            res = r["result"]
            w.writerow([
                r["question_id"], r["exam_year"], r["paper_code"], r["question_number"],
                res.predicted_subject or "", res.confidence, res.status,
                res.scores["Physics"], res.scores["Chemistry"], res.scores["Biology"],
                "; ".join(f"{e['term']}({e['book']} p{e['page']})" for e in res.evidence[:5]),
            ])


def write_review_csv(rows: list[dict], path=None) -> None:
    """AMBIGUOUS + UNRESOLVED only."""
    path = path or (REPORTS_DIR / "ncert_subject_review.csv")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "question_id", "exam_year", "paper_code", "question_number", "question", "options",
            "physics_score", "chemistry_score", "biology_score",
            "predicted_subject", "confidence", "classification_status",
            "ncert_book", "ncert_chapter", "ncert_page", "evidence",
        ])
        for r in rows:
            res = r["result"]
            if res.status == "RESOLVED":
                continue
            top_ev = res.evidence[0] if res.evidence else {}
            w.writerow([
                r["question_id"], r["exam_year"], r["paper_code"], r["question_number"],
                r["question"][:300], _options_str(r["options"]),
                res.scores["Physics"], res.scores["Chemistry"], res.scores["Biology"],
                res.predicted_subject or "", res.confidence, res.status,
                top_ev.get("book", ""), top_ev.get("chapter", ""), top_ev.get("page", ""),
                "; ".join(f"{e['term']}({e['book']} p{e['page']})" for e in res.evidence[:5]),
            ])


def write_summary_json(rows: list[dict], *, applied: int, existing_verified_changed: int, dry_run: bool, path=None) -> dict:
    path = path or (REPORTS_DIR / "ncert_subject_summary.json")
    counts = {"Physics": 0, "Chemistry": 0, "Biology": 0, "AMBIGUOUS": 0, "UNRESOLVED": 0}
    for r in rows:
        res = r["result"]
        if res.status == "RESOLVED":
            counts[res.predicted_subject] += 1
        else:
            counts[res.status] += 1

    summary = {
        "total_classified": len(rows),
        "physics": counts["Physics"],
        "chemistry": counts["Chemistry"],
        "biology": counts["Biology"],
        "ambiguous": counts["AMBIGUOUS"],
        "unresolved": counts["UNRESOLVED"],
        "database_rows_updated": applied,
        "existing_verified_rows_changed": existing_verified_changed,
        "external_ai_calls": 0,
        "external_network_calls": 0,
        "ncert_source": "local files",
        "classifier": "local deterministic",
        "mode": "dry-run" if dry_run else "apply",
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary
