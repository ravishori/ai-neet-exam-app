"""CLI entrypoint: run the deterministic PYQ extraction pipeline against
one or more PDFs in `NEET Past Papers/` and load results into the local
`pyq_image_staging.questions` / `pyq_image_staging.images` tables.

Usage:
    .venv/Scripts/python.exe scripts/pyq_image_pipeline/run_ingest.py --file "<name>.pdf"
    .venv/Scripts/python.exe scripts/pyq_image_pipeline/run_ingest.py --all

Resumable: re-running is safe. Rows are inserted with
ON CONFLICT (identity_key) DO NOTHING, so already-processed
(file, page, question) tuples are never duplicated in staging, while a
genuinely re-run pipeline simply no-ops on rows it already wrote.

LOCAL DATABASE ONLY: this script refuses to run unless the resolved
DATABASE_URL_SYNC host is localhost/127.0.0.1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.pyq_image_pipeline.extractor import extract_file  # noqa: E402

SOURCE_DIR = Path(r"D:\ravishori\AI Neet Exam App\NEET Past Papers")
IMAGE_OUT_DIR = BACKEND_ROOT / "data" / "pyq_image_staging" / "images"


def _load_dotenv_sync_url() -> str:
    env_path = BACKEND_ROOT / ".env"
    url = None
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL_SYNC="):
                url = line.split("=", 1)[1].strip()
                break
    if not url:
        url = os.environ.get("DATABASE_URL_SYNC", "")
    return url


def assert_local(url: str) -> None:
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql"))
    host = parsed.hostname or ""
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise SystemExit(
            f"REFUSING: DATABASE_URL_SYNC host is '{host}', not localhost. "
            "This pipeline only writes to a local database."
        )
    print(f"[confirmed-local] DATABASE_URL_SYNC host = {host!r} (db={parsed.path})")


def get_conn(url: str):
    # psycopg wants plain postgresql:// scheme
    plain = url.replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(plain)


def ingest_one(pdf_path: Path, conn) -> dict:
    questions, images = extract_file(pdf_path, IMAGE_OUT_DIR)

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
                    json.dumps(q.review_flags), q.has_image_reference, "pyq_image_pipeline_v1",
                ),
            )
            if cur.fetchone() is not None:
                q_inserted += 1
            else:
                q_skipped += 1
        conn.commit()

        # build identity_key -> question_id map for association (re-query, since
        # some rows may already have existed from a prior run)
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
    ap.add_argument("--file", help="single PDF filename within NEET Past Papers/")
    ap.add_argument("--all", action="store_true", help="process all PDFs in the folder")
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
            r = ingest_one(f, conn)
            results.append(r)
            print(json.dumps(r, indent=2))
    finally:
        conn.close()

    print("\n=== SUMMARY ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
