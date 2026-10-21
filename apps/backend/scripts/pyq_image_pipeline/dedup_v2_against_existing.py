"""Deterministic duplicate check for the `NEET Past Papers_V2` batch
(780 rows, pipeline_version='pyq_image_pipeline_v2') against:
  (a) each other (within-batch, across the 4 new PDFs), and
  (b) the existing 899-row 'pyq_image_pipeline_v1' batch already staged
      in the same `pyq_image_staging.questions` table.

Reuses the project's existing significant-word Jaccard near-duplicate
method (`pyq_subject_classifier.duplicates.find_near_duplicates`,
threshold 0.6, min 4 shared significant words) rather than inventing a
new similarity metric. Detection only -- never deletes or merges rows.
No AI calls. Local DB only (reuses run_ingest's assert_local).

Usage:
    .venv/Scripts/python.exe scripts/pyq_image_pipeline/dedup_v2_against_existing.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from pyq_subject_classifier.duplicates import find_near_duplicates  # noqa: E402
from scripts.pyq_image_pipeline.run_ingest import _load_dotenv_sync_url, assert_local, get_conn  # noqa: E402


def _fetch_rows(cur, pipeline_version: str) -> list[dict]:
    cur.execute(
        """
        SELECT id, source_file, exam_year, paper_code, question_number_raw, stem_text
        FROM pyq_image_staging.questions
        WHERE pipeline_version = %s AND stem_text IS NOT NULL
        """,
        (pipeline_version,),
    )
    rows = []
    for qid, source_file, exam_year, paper_code, qnum, stem in cur.fetchall():
        rows.append({
            "question_id": str(qid),
            "raw_stem": stem,
            "raw_options": "",
            "exam_year": str(exam_year) if exam_year else "",
            "paper_code": paper_code or "",
            "question_number": qnum,
            "source_file": source_file,
        })
    return rows


def main() -> None:
    url = _load_dotenv_sync_url()
    assert_local(url)
    conn = get_conn(url)
    try:
        with conn.cursor() as cur:
            v1_rows = _fetch_rows(cur, "pyq_image_pipeline_v1")
            v2_rows = _fetch_rows(cur, "pyq_image_pipeline_v2")

        print(f"v1 (existing) rows with stem_text: {len(v1_rows)}")
        print(f"v2 (new NEET Past Papers_V2 batch) rows with stem_text: {len(v2_rows)}")

        # --- (a) within-batch (v2 vs v2) ---
        within_findings = find_near_duplicates(v2_rows, exclude_ids=set())
        within_ids = {f.question_id for f in within_findings}
        within_meta = {r["question_id"]: r for r in v2_rows}

        # --- (b) v2 vs v1 (cross-batch) ---
        combined = v1_rows + v2_rows
        combined_meta = {r["question_id"]: r for r in combined}
        cross_findings = find_near_duplicates(combined, exclude_ids=set())
        v1_ids = {r["question_id"] for r in v1_rows}
        v2_ids = {r["question_id"] for r in v2_rows}
        # keep only findings whose duplicate_group contains at least one v1 AND one v2 id
        groups: dict[str, list] = {}
        for f in cross_findings:
            groups.setdefault(f.duplicate_group_id, []).append(f)
        cross_batch_findings = []
        for gid, members in groups.items():
            ids = {m.question_id for m in members}
            if ids & v1_ids and ids & v2_ids:
                cross_batch_findings.extend(members)

        report = {
            "method": "significant-word Jaccard, threshold=0.6, min_shared_words=4 "
                      "(pyq_subject_classifier.duplicates.find_near_duplicates)",
            "v1_existing_row_count": len(v1_rows),
            "v2_new_row_count": len(v2_rows),
            "within_v2_batch_near_duplicate_pairs": len(within_ids),
            "cross_batch_v2_vs_v1_near_duplicate_rows": len({f.question_id for f in cross_batch_findings} & v2_ids),
            "within_batch_detail": [
                {
                    "question_id": f.question_id,
                    "group": f.duplicate_group_id,
                    "score": f.similarity_score,
                    "source_file": within_meta[f.question_id]["source_file"],
                    "question_number": within_meta[f.question_id]["question_number"],
                }
                for f in within_findings
            ],
            "cross_batch_detail": [
                {
                    "question_id": f.question_id,
                    "group": f.duplicate_group_id,
                    "score": f.similarity_score,
                    "batch": "v2_new" if f.question_id in v2_ids else "v1_existing",
                    "source_file": combined_meta[f.question_id]["source_file"],
                    "question_number": combined_meta[f.question_id]["question_number"],
                }
                for f in cross_batch_findings
            ],
        }

        out_path = BACKEND_ROOT / "data" / "generated_mcqs" / "pyq_v2_dedup_report.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote dedup report: {out_path}")
        print(f"within-batch near-dup rows: {report['within_v2_batch_near_duplicate_pairs']}")
        print(f"cross-batch (v2 vs existing 899) near-dup v2 rows: {report['cross_batch_v2_vs_v1_near_duplicate_rows']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
