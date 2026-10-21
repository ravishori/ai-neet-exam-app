"""CLI entrypoint: run the deterministic PYQ extraction pipeline against
the `NEET Past Papers_V2/` batch (NEET 2020 Code-F1, 2022, 2023, 2024 UG)
and load results into the SAME local `pyq_image_staging.questions` /
`pyq_image_staging.images` tables used by the original 7-PDF batch
(`run_ingest.py`).

This is a separate CLI (not a flag on run_ingest.py) so the original
batch's invocation and source directory are left completely untouched,
while reusing its `ingest_one` / `get_conn` / `assert_local` machinery
unmodified (imported, not copied) and routing extraction through
`extractor.extract_file_v2` instead of `extract_file`.

Usage:
    .venv/Scripts/python.exe scripts/pyq_image_pipeline/run_ingest_v2.py --file "<name>.pdf"
    .venv/Scripts/python.exe scripts/pyq_image_pipeline/run_ingest_v2.py --all

Resumable (same ON CONFLICT (identity_key) DO NOTHING idempotency as the
original batch). LOCAL DATABASE ONLY — refuses to run unless the resolved
DATABASE_URL_SYNC host is localhost/127.0.0.1.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.pyq_image_pipeline.extractor import extract_file_v2  # noqa: E402
from scripts.pyq_image_pipeline.run_ingest import (  # noqa: E402
    _load_dotenv_sync_url,
    assert_local,
    get_conn,
)
from scripts.pyq_image_pipeline.run_ingest import ingest_one as _ingest_one_base  # noqa: E402

SOURCE_DIR = Path(r"D:\ravishori\AI Neet Exam App\NEET Past Papers_V2")
IMAGE_OUT_DIR = BACKEND_ROOT / "data" / "pyq_image_staging" / "images"


def ingest_one_v2(pdf_path: Path, conn) -> dict:
    """Identical row-insertion logic to run_ingest.ingest_one, just fed
    questions/images from extract_file_v2 instead of extract_file. We
    reuse ingest_one's SQL by temporarily monkey-patching extract_file at
    call time is avoided in favor of duplicating the (short) insertion
    loop would be fragile; instead we directly call the same SQL path by
    constructing the extraction ourselves and delegating to a shared
    inner helper imported from run_ingest would require changing that
    module's signature. To avoid modifying the original, already-tested
    run_ingest.py at all, this function reimplements the identical insert
    logic against the v2 extraction output."""
    import psycopg  # noqa: F401  (ensures dependency presence is checked early)

    questions, images = extract_file_v2(pdf_path, IMAGE_OUT_DIR)

    q_inserted = 0
    q_skipped = 0
    with conn.cursor() as cur:
        for q in questions:
            cur.execute(
                """
                INSERT INTO pyq_image_staging.questions (
                    id, source_file, source_file_sha256, page_number,
                    question_number_raw, paper_code, identity_key,
                    exam_year, exam_name, subject, doc_kind,
                    stem_text, options, answer_raw, explanation_text,
                    raw_block_text, extraction_status, extraction_confidence,
                    review_flags, has_image_reference, pipeline_version
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (identity_key) DO NOTHING
                RETURNING id
                """,
                (
                    q.id, q.source_file, q.source_file_sha256, q.page_number,
                    q.question_number_raw, q.paper_code, q.identity_key,
                    q.exam_year, q.exam_name, q.subject, q.doc_kind,
                    q.stem_text, json.dumps(q.options) if q.options is not None else None,
                    q.answer_raw, q.explanation_text, q.raw_block_text,
                    q.extraction_status, q.extraction_confidence,
                    json.dumps(q.review_flags), q.has_image_reference, "pyq_image_pipeline_v2",
                ),
            )
            if cur.fetchone() is not None:
                q_inserted += 1
            else:
                q_skipped += 1
        conn.commit()

        key_to_id = {}
        if images:
            identity_keys = list({img.question_identity_key for img in images if img.question_identity_key})
            if identity_keys:
                cur.execute(
                    "SELECT identity_key, id FROM pyq_image_staging.questions WHERE identity_key = ANY(%s)",
                    (identity_keys,),
                )
                key_to_id = {k: v for k, v in cur.fetchall()}

        img_inserted = 0
        img_skipped = 0
        for img in images:
            q_id = key_to_id.get(img.question_identity_key) if img.question_identity_key else None
            cur.execute(
                """
                INSERT INTO pyq_image_staging.images (
                    id, question_id, source_file, source_file_sha256, page_number,
                    image_index_on_page, identity_key, stored_path, width_px, height_px,
                    image_format, association_confidence, association_basis
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (identity_key) DO NOTHING
                RETURNING id
                """,
                (
                    img.id, q_id, img.source_file, img.source_file_sha256, img.page_number,
                    img.image_index_on_page, img.identity_key, img.stored_path, img.width_px,
                    img.height_px, img.image_format, img.association_confidence, img.association_basis,
                ),
            )
            if cur.fetchone() is not None:
                img_inserted += 1
            else:
                img_skipped += 1
        conn.commit()

    status_counts: dict[str, int] = {}
    for q in questions:
        status_counts[q.extraction_status] = status_counts.get(q.extraction_status, 0) + 1

    return {
        "file": pdf_path.name,
        "questions_extracted_total": len(questions),
        "questions_inserted_new": q_inserted,
        "questions_already_present_skipped": q_skipped,
        "images_extracted_total": len(images),
        "images_inserted_new": img_inserted,
        "images_already_present_skipped": img_skipped,
        "status_counts": status_counts,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="single PDF filename within NEET Past Papers_V2/")
    ap.add_argument("--all", action="store_true", help="process all PDFs in the V2 folder")
    args = ap.parse_args()

    url = _load_dotenv_sync_url()
    assert_local(url)

    files: list[Path]
    if args.all:
        files = sorted(SOURCE_DIR.glob("*.pdf"))
    elif args.file:
        files = [SOURCE_DIR / args.file]
    else:
        raise SystemExit("pass --file <name.pdf> or --all")

    conn = get_conn(url)
    results = []
    try:
        for f in files:
            if not f.exists():
                print(f"MISSING: {f}")
                continue
            r = ingest_one_v2(f, conn)
            results.append(r)
            print(json.dumps(r, indent=2))
    finally:
        conn.close()

    print("\n=== SUMMARY ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
