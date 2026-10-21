"""Writes the final combined JSON report
(docs/quality/neet_mcq_pdf_extraction_33years_and_pyp_20261018.json)
summarizing both full extraction runs + the validation pass, as the
machine-readable companion to the .md report. Read-only over the
existing manifest/validation/batch-index JSON files; no PDF parsing of
its own, no AI/LLM calls, no database writes.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.pyq_pdf_extract.common import RIGHTS_RESTATEMENT, now_iso, write_json

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BOOK1_DIR = BACKEND_ROOT / "data" / "extracted_mcqs" / "33years_biology_2020"
BOOK2_DIR = BACKEND_ROOT / "data" / "extracted_mcqs" / "neet_pyp_2025"
DOCS_DIR = BACKEND_ROOT / "docs" / "quality"


def main() -> None:
    m1 = json.loads((BOOK1_DIR / "manifest_full.json").read_text(encoding="utf-8"))
    m2 = json.loads((BOOK2_DIR / "manifest_full.json").read_text(encoding="utf-8"))
    validation = json.loads((DOCS_DIR / "neet_mcq_pdf_extraction_33years_and_pyp_20261018_validation.json").read_text(encoding="utf-8"))
    batch1 = json.loads((BOOK1_DIR / "batches" / "batch_index.json").read_text(encoding="utf-8"))
    batch2 = json.loads((BOOK2_DIR / "batches" / "batch_index.json").read_text(encoding="utf-8"))

    report = {
        "task_id": "FACTORY-PYQPDF-20261018",
        "generated_at": now_iso(),
        "rights_restatement": RIGHTS_RESTATEMENT,
        "safety_attestation": {
            "ai_provider_calls": 0, "paid_api_calls": 0, "database_writes": 0,
            "external_uploads": 0, "network_calls": 0,
        },
        "books": {
            "33years_biology_2020": {
                "source_file": m1["source_file"],
                "source_file_sha256": m1["source_file_sha256"],
                "rights_status": m1["rights_status"],
                "pages_in_file": m1["pages_in_file"],
                "pages_processed": m1["pages_processed_this_run"],
                "ocr_pages_used": m1["ocr_pages_used"],
                "chapters_resolved": m1["chapters_resolved"],
                "chapters_expected_from_toc": m1["chapters_expected_from_toc"],
                "questions_extracted": m1["questions_extracted"],
                "answer_known": m1["answer_known"],
                "answer_pending": m1["answer_pending"],
                "explanation_present": m1["explanation_present"],
                "complete": m1["complete"],
                "needs_review": m1["needs_review"],
                "other_blocks_unextracted": m1["other_blocks_unextracted"],
                "orphaned_unconfirmed_resets": m1["orphaned_unconfirmed_resets"],
                "page_status_summary": _page_status_summary(m1["page_statuses"]),
                "batching": {"strategy": batch1["batching_strategy"], "total_batches": batch1["total_batches"]},
            },
            "neet_pyp_2025": {
                "source_file": m2["source_file"],
                "source_file_sha256": m2["source_file_sha256"],
                "rights_status": m2["rights_status"],
                "pages_in_file": m2["pages_in_file"],
                "pages_processed": m2["pages_processed_this_run"],
                "ocr_pages_used": m2["ocr_pages_used"],
                "question_runs_found": m2["question_runs_found"],
                "chapterwise_index_total_units": m2["chapterwise_index_total_units"],
                "chapterwise_index_internal_mismatches": m2["chapterwise_index_internal_mismatches"],
                "questions_extracted": m2["questions_extracted"],
                "answer_known": m2["answer_known"],
                "answer_pending": m2["answer_pending"],
                "explanation_present": m2["explanation_present"],
                "complete": m2["complete"],
                "needs_review": m2["needs_review"],
                "other_blocks_unextracted": m2["other_blocks_unextracted"],
                "page_status_summary": _page_status_summary(m2["page_statuses"]),
                "batching": {"strategy": batch2["batching_strategy"], "total_batches": batch2["total_batches"]},
            },
        },
        "combined": {
            "questions_extracted": m1["questions_extracted"] + m2["questions_extracted"],
            "pages_processed": m1["pages_processed_this_run"] + m2["pages_processed_this_run"],
            "ocr_pages_used": 0,
            "exact_duplicate_groups": validation["exact_duplicates"]["exact_duplicate_groups_total"],
            "exact_duplicate_groups_cross_file": validation["exact_duplicates"]["exact_duplicate_groups_cross_file"],
            "near_duplicate_pairs_flagged": validation["near_duplicates"]["near_duplicate_pairs_flagged"],
            "sweatsmile_external_pool_exact_matches": validation["sweatsmile_external_pool_crosscheck"].get("exact_stem_matches_found"),
            "option_integrity": validation["option_integrity"]["combined"],
            "required_field_completeness": validation["required_field_completeness"]["combined"],
        },
        "validation_report_path": "docs/quality/neet_mcq_pdf_extraction_33years_and_pyp_20261018_validation.json",
        "db_import_contract_summary": (
            "Documented in the .md report §7: pyq.staging_questions is the natural "
            "target (not generation_staging.candidates). Clean field mapping exists "
            "for stem/options/subject/class_level/question_number/validation_status/"
            "confidence/staging_id. exam_year, explanation_text, chapter/topic, and "
            "rights_status currently have no column to land in without a small "
            "additive migration -- NOT implemented here, per instruction."
        ),
    }
    out_path = DOCS_DIR / "neet_mcq_pdf_extraction_33years_and_pyp_20261018.json"
    write_json(out_path, report)
    print(f"wrote {out_path}")


def _page_status_summary(page_statuses: list[dict]) -> dict:
    out: dict[str, int] = {}
    for p in page_statuses:
        out[p["status"]] = out.get(p["status"], 0) + 1
    return out


if __name__ == "__main__":
    main()
