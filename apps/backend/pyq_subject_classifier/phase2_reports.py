from __future__ import annotations

import csv
import json

from .config import REPORTS_DIR


def _options_str(options) -> str:
    if not isinstance(options, dict):
        return ""
    return " | ".join(f"{k}: {options.get(k, '')}" for k in ("A", "B", "C", "D") if options.get(k))


def _ev_str(evidence: list) -> str:
    return "; ".join(
        f"{e.get('match_type')}:{e.get('matched_text','')[:40]}({e.get('ncert_book','')}#{e.get('ncert_chapter','')})"
        for e in evidence[:3]
    )


def write_phase2_csv(rows: list, path=None) -> None:
    path = path or (REPORTS_DIR / "ncert_subject_phase2.csv")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "question_id", "exam_year", "paper_code", "question_number",
            "physics_score", "chemistry_score", "biology_score",
            "top_subject", "second_subject", "score_margin",
            "predicted_subject", "confidence", "classification_status", "evidence",
        ])
        for r in rows:
            res = r["result"]
            w.writerow([
                r["question_id"], r["exam_year"], r["paper_code"], r["question_number"],
                res.scores["Physics"], res.scores["Chemistry"], res.scores["Biology"],
                res.top_subject or "", res.second_subject or "", res.score_margin,
                res.predicted_subject or "", res.confidence, res.classification_status,
                _ev_str(res.evidence),
            ])


def write_phase2_review_csv(rows: list, path=None) -> None:
    path = path or (REPORTS_DIR / "ncert_subject_phase2_review.csv")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "question_id", "exam_year", "paper_code", "question_number", "question", "options",
            "physics_score", "chemistry_score", "biology_score",
            "top_subject", "second_subject", "score_margin",
            "confidence", "classification_status",
            "ncert_book", "ncert_chapter", "ncert_page", "match_type", "evidence",
        ])
        for r in rows:
            res = r["result"]
            if res.classification_status == "RESOLVED":
                continue
            top_ev = res.evidence[0] if res.evidence else {}
            w.writerow([
                r["question_id"], r["exam_year"], r["paper_code"], r["question_number"],
                r["question"][:300], _options_str(r["options"]),
                res.scores["Physics"], res.scores["Chemistry"], res.scores["Biology"],
                res.top_subject or "", res.second_subject or "", res.score_margin,
                res.confidence, res.classification_status,
                top_ev.get("ncert_book", ""), top_ev.get("ncert_chapter", ""), top_ev.get("ncert_page", ""),
                top_ev.get("match_type", ""), _ev_str(res.evidence),
            ])


def write_phase2_summary(rows: list, *, applied: int, path=None) -> dict:
    path = path or (REPORTS_DIR / "ncert_subject_phase2_summary.json")
    counts = {"Physics": 0, "Chemistry": 0, "Biology": 0, "AMBIGUOUS": 0, "UNRESOLVED": 0}
    for r in rows:
        res = r["result"]
        if res.classification_status == "RESOLVED":
            counts[res.predicted_subject] += 1
        else:
            counts[res.classification_status] += 1

    summary = {
        "input_questions": len(rows),
        "resolved": counts["Physics"] + counts["Chemistry"] + counts["Biology"],
        "physics": counts["Physics"],
        "chemistry": counts["Chemistry"],
        "biology": counts["Biology"],
        "remaining_ambiguous": counts["AMBIGUOUS"],
        "remaining_unresolved": counts["UNRESOLVED"],
        "database_rows_updated": applied,
        "external_ai_calls": 0,
        "external_network_calls": 0,
        "classifier_version": "ncert-local-v2",
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary
