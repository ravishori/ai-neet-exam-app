"""Phase 4 — orchestrates the full-corpus, read-only data-quality audit.
Reuses: DB layer (db.py), NCERT indices (ncert_index/phase2_index), the
existing unmodified Phase 2 scorer (phase2_scoring.classify_phase2), and
the Phase 4 pure-check modules (quality_checks/duplicates/answer_quality/
evidence_gaps/legacy_provenance). Never writes to PostgreSQL.
"""

from __future__ import annotations

import csv
import json
from collections import Counter

from .answer_quality import audit_assertions_for_question, group_assertions_by_question
from .config import REPORTS_DIR
from .db import connect
from .duplicates import find_exact_duplicates, find_near_duplicates
from .evidence_gaps import classify_gap_reason
from .legacy_provenance import classify_legacy_provenance
from .ncert_index import build_index
from .ncert_manifest import load_or_build_manifest
from .phase2_index import build_phase2_index
from .phase2_scoring import classify_phase2
from .quality_checks import check_question_integrity


def _opt_str(o) -> str:
    if not isinstance(o, dict):
        return ""
    return " | ".join(f"{k}: {o.get(k,'')}" for k in ("A", "B", "C", "D") if o.get(k))


def _fetch_all_questions(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT q.id::text AS question_id, sf.exam_year, sf.paper_id, sf.paper_code, q.question_number,
               q.subject, q.raw_stem, q.raw_options, q.source_file_id::text
        FROM pyq.questions q JOIN pyq.source_files sf ON sf.id = q.source_file_id
        ORDER BY sf.exam_year, sf.paper_id, q.question_number
        """
    )
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def _fetch_assertions(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT question_id::text, asserted_option, verification_status, assertion_source FROM pyq.answer_assertions"
    )
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def _fetch_audit(conn) -> dict[str, dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT ON (question_id) question_id::text, classifier_version, classification_status, new_subject
        FROM pyq.subject_classification_audit
        ORDER BY question_id, classified_at DESC
        """
    )
    cols = [c.name for c in cur.description]
    out = {}
    for r in cur.fetchall():
        row = dict(zip(cols, r, strict=True))
        out[row["question_id"]] = row
    return out


def run_quality_audit() -> dict:
    conn = connect(read_only=True)
    try:
        questions = _fetch_all_questions(conn)
        assertions = _fetch_assertions(conn)
        audit_by_qid = _fetch_audit(conn)
    finally:
        conn.rollback()
        conn.close()

    total_questions = len(questions)
    assertions_by_qid = group_assertions_by_question(assertions)

    # ---------- STEP 3/4: per-question integrity + answer quality ----------
    quality_rows = []
    answer_rows = []
    issues_by_qid: dict[str, list[str]] = {}
    malformed_count = 0
    malformed_options_count = 0
    invalid_answer_count = 0
    subject_counter = Counter()
    has_answer_count = 0

    for q in questions:
        issues = check_question_integrity(
            raw_stem=q["raw_stem"], raw_options=q["raw_options"],
            question_number=q["question_number"], subject=q["subject"],
        )
        issues_by_qid[q["question_id"]] = issues
        if issues:
            if any("STEM" in i for i in issues):
                malformed_count += 1
            if any("OPTION" in i for i in issues):
                malformed_options_count += 1

        subject_counter[q["subject"] or "NULL"] += 1

        quality_rows.append({
            "question_id": q["question_id"], "exam_year": q["exam_year"], "paper_id": q["paper_id"],
            "paper_code": q["paper_code"], "question_number": q["question_number"],
            "subject": q["subject"] or "", "issues": ";".join(issues) if issues else "",
        })

        my_assertions = assertions_by_qid.get(q["question_id"], [])
        if my_assertions:
            has_answer_count += 1
            a_issues = audit_assertions_for_question(q["question_id"], q["raw_options"], my_assertions)
            if a_issues:
                invalid_answer_count += 1
            answer_rows.append({
                "question_id": q["question_id"], "assertion_count": len(my_assertions),
                "asserted_options": ";".join(sorted({a["asserted_option"] for a in my_assertions})),
                "verification_statuses": ";".join(sorted({a["verification_status"] for a in my_assertions})),
                "issues": ";".join(a_issues) if a_issues else "",
            })

    with open(REPORTS_DIR / "pyq_data_quality_questions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["question_id", "exam_year", "paper_id", "paper_code", "question_number", "subject", "issues"])
        w.writeheader()
        for r in quality_rows:
            w.writerow(r)

    with open(REPORTS_DIR / "pyq_answer_quality.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["question_id", "assertion_count", "asserted_options", "verification_statuses", "issues"])
        w.writeheader()
        for r in answer_rows:
            w.writerow(r)

    # ---------- STEP 6: duplicates ----------
    dup_rows_input = [
        {"question_id": q["question_id"], "raw_stem": q["raw_stem"], "raw_options": q["raw_options"],
         "exam_year": q["exam_year"], "paper_code": q["paper_code"], "question_number": q["question_number"]}
        for q in questions
    ]
    exact_findings = find_exact_duplicates(dup_rows_input)
    exact_ids = {f.question_id for f in exact_findings}
    near_findings = find_near_duplicates(dup_rows_input, exclude_ids=exact_ids)

    with open(REPORTS_DIR / "pyq_duplicate_candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["question_id", "duplicate_group_id", "match_type", "similarity_score", "source_file", "exam_year", "paper", "question_number"])
        for finding in exact_findings + near_findings:
            w.writerow([finding.question_id, finding.duplicate_group_id, finding.match_type,
                        finding.similarity_score, "", finding.exam_year, finding.paper_code, finding.question_number])

    exact_dup_count = len(exact_findings)
    near_dup_count = len(near_findings)

    # ---------- shared NCERT infra (reused, not rebuilt) ----------
    manifest = load_or_build_manifest()
    term_idx = build_index(manifest)
    phase2_idx = build_phase2_index(manifest)

    # ---------- STEP 7/8: NULL evidence gaps (reuse existing Phase 2/3 CSVs) ----------
    phase3_rows_by_qid: dict[str, dict] = {}
    for fname in ("ncert_subject_phase2_ambiguous_resolution.csv", "ncert_subject_phase2_unresolved_resolution.csv"):
        path = REPORTS_DIR / fname
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    phase3_rows_by_qid[row["question_id"]] = row

    null_gap_rows = []
    ncert_supported = weak_evidence = no_match = ambiguous_gap = other_gap = 0
    null_qids = [q["question_id"] for q in questions if q["subject"] is None]
    by_qid = {q["question_id"]: q for q in questions}

    for qid in null_qids:
        p3 = phase3_rows_by_qid.get(qid)
        issues = issues_by_qid.get(qid, [])
        if p3 is None:
            # Should not happen (Phase 3 covered the full NULL population),
            # but never silently skip — report explicitly.
            gap_reason = "OTHER"
            physics_score = chemistry_score = biology_score = 0.0
            top_subject = second_subject = None
            score_margin = 0.0
            match_type = ""
            ncert_book = ncert_chapter = ncert_page = ""
        else:
            physics_score = float(p3["physics_score"])
            chemistry_score = float(p3["chemistry_score"])
            biology_score = float(p3["biology_score"])
            top_subject = p3["top_subject"] or None
            second_subject = p3["second_subject"] or None
            score_margin = float(p3["score_margin"])
            match_type = p3["match_type"]
            ncert_book = p3["ncert_book"]
            ncert_chapter = p3["ncert_chapter"]
            ncert_page = p3["ncert_page"]
            gap_reason = classify_gap_reason(
                quality_issues=issues, physics_score=physics_score, chemistry_score=chemistry_score,
                biology_score=biology_score, top_subject=top_subject, second_subject=second_subject,
                score_margin=score_margin, match_type=match_type or None,
            )

        if gap_reason == "NO_NCERT_MATCH":
            no_match += 1
        elif gap_reason in ("WEAK_NCERT_MATCH",):
            weak_evidence += 1
        elif gap_reason in ("AMBIGUOUS_PHYSICS_CHEMISTRY", "AMBIGUOUS_BIOLOGY_SUBJECT", "MULTI_SUBJECT_MATCH", "CROSS_DISCIPLINARY"):
            ambiguous_gap += 1
        elif max(physics_score, chemistry_score, biology_score) > 0 and gap_reason not in ("INSUFFICIENT_TEXT", "MISSING_OPTIONS", "MALFORMED_SOURCE", "EXTRACTION_ARTIFACT"):
            other_gap += 1
        else:
            other_gap += 1

        q = by_qid[qid]
        null_gap_rows.append({
            "question_id": qid, "current_subject": "", "best_candidate_subject": top_subject or "",
            "candidate_score": max(physics_score, chemistry_score, biology_score),
            "score_margin": score_margin,
            "ncert_evidence_level": "NONE" if max(physics_score, chemistry_score, biology_score) == 0 else ("STRONG" if match_type == "EXACT_NCERT_PHRASE" else "PARTIAL"),
            "ncert_book": ncert_book, "ncert_class": "", "ncert_subject": top_subject or "",
            "ncert_chapter": ncert_chapter, "ncert_pdf_page": ncert_page or "UNAVAILABLE",
            "evidence_terms": "", "evidence_status": p3["confidence"] if p3 else "UNRESOLVED",
            "evidence_gap_reason": gap_reason,
        })

    with open(REPORTS_DIR / "pyq_null_evidence_gaps.csv", "w", newline="", encoding="utf-8") as f:
        fieldnames = list(null_gap_rows[0].keys()) if null_gap_rows else [
            "question_id", "current_subject", "best_candidate_subject", "candidate_score", "score_margin",
            "ncert_evidence_level", "ncert_book", "ncert_class", "ncert_subject", "ncert_chapter",
            "ncert_pdf_page", "evidence_terms", "evidence_status", "evidence_gap_reason",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in null_gap_rows:
            w.writerow(r)

    # ---------- STEP 9/10: legacy provenance + subject conflicts (recompute via existing scorer only) ----------
    legacy_rows_out = []
    conflict_rows_out = []
    legacy_status_counts = Counter()

    classified_qids = [q["question_id"] for q in questions if q["subject"] is not None]
    for qid in classified_qids:
        q = by_qid[qid]
        has_audit = qid in audit_by_qid
        result = classify_phase2(q["raw_stem"] or "", q["raw_options"] if isinstance(q["raw_options"], dict) else {}, term_idx, phase2_idx)

        if not has_audit:
            prov = classify_legacy_provenance(
                current_subject=q["subject"], recomputed_top_subject=result.top_subject,
                recomputed_status=result.classification_status, recomputed_top_score=max(result.scores.values()),
            )
            legacy_status_counts[prov["provenance_status"]] += 1
            legacy_rows_out.append({
                "question_id": qid, "current_subject": q["subject"], "provenance_status": prov["provenance_status"],
                "provenance_source": "original_import_section_header_scan",
                "evidence_strength": prov["evidence_strength"], "ncert_match": prov["ncert_match"],
                "conflict_status": prov["conflict_status"], "recommended_action": prov["recommended_action"],
            })
            if prov["conflict_status"] == "CONFLICT":
                conflict_rows_out.append({
                    "question_id": qid, "current_subject": q["subject"], "source": "LEGACY",
                    "recomputed_subject": result.top_subject or "", "recomputed_status": result.classification_status,
                    "recomputed_score": max(result.scores.values()), "conflict_status": "CONFLICT",
                })
        else:
            # Phase1/Phase2-classified — check for disagreement with independent re-evidence.
            if result.classification_status == "RESOLVED" and result.top_subject != q["subject"]:
                conflict_rows_out.append({
                    "question_id": qid, "current_subject": q["subject"],
                    "source": f"AUDITED:{audit_by_qid[qid]['classifier_version']}",
                    "recomputed_subject": result.top_subject or "", "recomputed_status": result.classification_status,
                    "recomputed_score": max(result.scores.values()), "conflict_status": "CONFLICT",
                })

    with open(REPORTS_DIR / "pyq_legacy_provenance_audit.csv", "w", newline="", encoding="utf-8") as f:
        fieldnames = ["question_id", "current_subject", "provenance_status", "provenance_source",
                      "evidence_strength", "ncert_match", "conflict_status", "recommended_action"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in legacy_rows_out:
            w.writerow(r)

    with open(REPORTS_DIR / "pyq_subject_conflicts.csv", "w", newline="", encoding="utf-8") as f:
        fieldnames = ["question_id", "current_subject", "source", "recomputed_subject", "recomputed_status", "recomputed_score", "conflict_status"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in conflict_rows_out:
            w.writerow(r)

    # ---------- STEP 11: scorecard ----------
    summary = {
        "total_questions": total_questions,
        "subject_classified": total_questions - subject_counter.get("NULL", 0),
        "subject_null": subject_counter.get("NULL", 0),
        "invalid_subject": sum(1 for issues in issues_by_qid.values() if any(i.startswith("INVALID_SUBJECT_VALUE") for i in issues)),
        "questions_with_answers": has_answer_count,
        "questions_without_answers": total_questions - has_answer_count,
        "exact_duplicates": exact_dup_count,
        "near_duplicate_candidates": near_dup_count,
        "missing_stems": sum(1 for issues in issues_by_qid.values() if "MISSING_STEM" in issues),
        "malformed_options": malformed_options_count,
        "invalid_answer_assertions": invalid_answer_count,
        "legacy_without_provenance": legacy_status_counts.get("NO_RECOVERABLE_PROVENANCE", 0),
        "legacy_total": len(legacy_rows_out),
        "ncert_supported": legacy_status_counts.get("SUPPORTED_BY_NCERT", 0),
        "ncert_unsupported": legacy_status_counts.get("SUPPORTED_BY_SOURCE_METADATA", 0) + legacy_status_counts.get("NO_RECOVERABLE_PROVENANCE", 0),
        "subject_conflicts": len(conflict_rows_out),
        "data_quality_warnings": malformed_count + malformed_options_count + invalid_answer_count,
        "null_evidence_gap_breakdown": {
            "ncert_supported": ncert_supported, "weak_evidence": weak_evidence,
            "no_ncert_match": no_match, "ambiguous": ambiguous_gap, "other": other_gap,
        },
        "legacy_provenance_breakdown": dict(legacy_status_counts),
    }
    with open(REPORTS_DIR / "pyq_data_quality_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary
