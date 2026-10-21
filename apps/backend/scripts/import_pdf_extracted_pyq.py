#!/usr/bin/env python3
"""Import the two PDF-extracted PYQ corpora (33-years Biology book + neet_pyp.pdf)
into pyq.* staging tables, per the user-approved partial-import plan recorded in
docs/quality/neet_mcq_IMPORT_PREFLIGHT_FINAL_20261018.json.

Policy (explicitly approved by the user, 2026-10-18):
  - Import only the ids listed under eligible_insert_ids (3,438 records).
  - Skip the ids listed under exact_duplicate_skip (21 records) -- never overwrite.
  - Exclude the ids listed under excluded_review_case (51 records) entirely.
  - Map class_level 'XI'/'XII' -> '11'/'12' (the pre-existing academic.chapters
    convention); any other value is left NULL rather than invented.
  - No rights_status column is added -- per explicit user instruction to keep
    this import simple. Rights status is NOT persisted to the DB by this
    script; it remains traceable only in the source JSON files on disk
    (data/extracted_mcqs/*/questions_full.json), which this script never
    modifies or deletes.
  - Idempotent: INSERT ... ON CONFLICT (staging_id) DO NOTHING, staging_id is
    this record's own extraction "id" (a stable uuid4 assigned at extraction
    time, never regenerated here) -- a second run inserts 0 new rows.
  - No LLM calls. No paid API calls. No writes outside pyq.*.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger("cms.pyq.import_pdf_extracted")

REPO_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_JSON = REPO_ROOT / "docs" / "quality" / "neet_mcq_IMPORT_PREFLIGHT_FINAL_20261018.json"

SOURCE_KEY = "NEET_PDF_EXTRACTED_2026_10_18"
SOURCE_NAME = "PDF-extracted NEET MCQs (33 Years Biology book + neet_pyp.pdf, 2026-10-18 extraction)"
AUTHORITY_TYPE = "THIRD_PARTY_BOOK_EXTRACTION"
PIPELINE_STAGE = "pyq_pdf_extract_v1_20261018"

BOOKS = [
    {
        "key": "33years_biology_2020",
        "paper_id": "33years_biology_2020",
        "paper_code": "33_YEARS_NEET_AIPMT_BIOLOGY_2020",
        "exam_year": None,
        "questions_full": REPO_ROOT / "data" / "extracted_mcqs" / "33years_biology_2020" / "questions_full.json",
        "relative_path": "Latest Study material/33 Years NEET-AIPMT Chapterwise Solutions - Biology 2020.pdf",
        "file_sha256": "8f23cda453f56ff38a057111be63453b032519dbd4630a9972a8966b624ad53e",
    },
    {
        "key": "neet_pyp_2025",
        "paper_id": "neet_pyp_2025",
        "paper_code": "NEET_PYP_2025",
        "exam_year": "2025",
        "questions_full": REPO_ROOT / "data" / "extracted_mcqs" / "neet_pyp_2025" / "questions_full.json",
        "relative_path": "Latest Study material/neet_pyp.pdf",
        "file_sha256": "d3e6b7cbf603830a11cae496e23b0f1431daf68a7f6348f99af7898ce6d79ac9",
    },
]

CLASS_LEVEL_MAP = {"XI": "11", "XII": "12"}


def _load_preflight_id_sets() -> tuple[set[str], set[str], set[str]]:
    data = json.loads(PREFLIGHT_JSON.read_text(encoding="utf-8"))
    t1 = data["task_1_mutually_exclusive_classification"]
    eligible = set(t1["eligible_insert_ids"])
    exact_dup = {entry["id"] for entry in t1["exact_duplicate_skip"]}
    review_case = {entry["id"] for entry in t1["excluded_review_case"]}
    assert len(eligible) == 3438, f"expected 3438 eligible ids, got {len(eligible)}"
    assert len(exact_dup) == 21, f"expected 21 exact-duplicate ids, got {len(exact_dup)}"
    assert len(review_case) == 51, f"expected 51 review-case ids, got {len(review_case)}"
    return eligible, exact_dup, review_case


def _raw_options(rec: dict[str, Any]) -> dict[str, str]:
    out = {}
    for opt in rec.get("options") or []:
        label = (opt.get("label") or "").upper()
        if label in ("A", "B", "C", "D"):
            out[label] = opt.get("text") or ""
    return out


def _class_level(rec: dict[str, Any]) -> str | None:
    raw = rec.get("class_level")
    if raw is None:
        return None
    return CLASS_LEVEL_MAP.get(str(raw).strip().upper())


@dataclass
class ImportReport:
    books_processed: int = 0
    records_seen_total: int = 0
    eligible_matched: int = 0
    exact_duplicate_skipped: int = 0
    review_case_excluded: int = 0
    unclassified_skipped: list[str] = field(default_factory=list)
    questions_inserted_this_run: int = 0
    already_present_skipped: int = 0


async def _get_or_create_source(session: AsyncSession) -> uuid.UUID:
    row = (
        await session.execute(text("SELECT id FROM pyq.sources WHERE source_key = :k"), {"k": SOURCE_KEY})
    ).first()
    if row:
        return row[0]
    new_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO pyq.sources (id, source_key, name, authority_type) "
            "VALUES (:id, :key, :name, :authority) "
            "ON CONFLICT (source_key) DO NOTHING"
        ),
        {"id": new_id, "key": SOURCE_KEY, "name": SOURCE_NAME, "authority": AUTHORITY_TYPE},
    )
    row = (
        await session.execute(text("SELECT id FROM pyq.sources WHERE source_key = :k"), {"k": SOURCE_KEY})
    ).first()
    return row[0]


async def _get_or_create_batch(session: AsyncSession, source_id: uuid.UUID, zip_sha256: str, manifest_path: str) -> uuid.UUID:
    row = (
        await session.execute(
            text(
                "SELECT id FROM pyq.import_batches "
                "WHERE source_id = :sid AND pipeline_stage = :stage AND zip_sha256 = :sha"
            ),
            {"sid": source_id, "stage": PIPELINE_STAGE, "sha": zip_sha256},
        )
    ).first()
    if row:
        batch_id = row[0]
        await session.execute(
            text("UPDATE pyq.import_batches SET status = 'RUNNING', started_at = now() WHERE id = :id"),
            {"id": batch_id},
        )
        return batch_id
    batch_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO pyq.import_batches "
            "(id, source_id, pipeline_stage, zip_sha256, status, manifest_path, started_at) "
            "VALUES (:id, :sid, :stage, :sha, 'RUNNING', :manifest, now())"
        ),
        {
            "id": batch_id,
            "sid": source_id,
            "stage": PIPELINE_STAGE,
            "sha": zip_sha256,
            "manifest": manifest_path,
        },
    )
    return batch_id


async def _get_or_create_source_file(
    session: AsyncSession,
    batch_id: uuid.UUID,
    *,
    paper_id: str,
    paper_code: str | None,
    exam_year: str | None,
    relative_path: str,
    file_sha256: str,
) -> uuid.UUID:
    row = (
        await session.execute(
            text("SELECT id FROM pyq.source_files WHERE batch_id = :bid AND paper_id = :pid"),
            {"bid": batch_id, "pid": paper_id},
        )
    ).first()
    if row:
        return row[0]
    sf_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO pyq.source_files "
            "(id, batch_id, paper_id, paper_code, exam_year, relative_path, file_sha256) "
            "VALUES (:id, :bid, :pid, :code, :year, :path, :sha) "
            "ON CONFLICT (batch_id, paper_id) DO NOTHING"
        ),
        {
            "id": sf_id,
            "bid": batch_id,
            "pid": paper_id,
            "code": paper_code,
            "year": exam_year,
            "path": relative_path,
            "sha": file_sha256,
        },
    )
    row = (
        await session.execute(
            text("SELECT id FROM pyq.source_files WHERE batch_id = :bid AND paper_id = :pid"),
            {"bid": batch_id, "pid": paper_id},
        )
    ).first()
    return row[0]


async def run_import(session: AsyncSession) -> ImportReport:
    report = ImportReport()
    eligible_ids, exact_dup_ids, review_case_ids = _load_preflight_id_sets()

    source_id = await _get_or_create_source(session)

    for book in BOOKS:
        report.books_processed += 1
        records = json.loads(book["questions_full"].read_text(encoding="utf-8"))
        report.records_seen_total += len(records)

        manifest_rel = str((book["questions_full"].parent / "manifest_full.json").relative_to(REPO_ROOT))
        batch_id = await _get_or_create_batch(session, source_id, book["file_sha256"], manifest_rel)
        source_file_id = await _get_or_create_source_file(
            session,
            batch_id,
            paper_id=book["paper_id"],
            paper_code=book["paper_code"],
            exam_year=book["exam_year"],
            relative_path=book["relative_path"],
            file_sha256=book["file_sha256"],
        )

        existing_staging_ids: set[str] = {
            row[0]
            for row in (
                await session.execute(
                    text("SELECT staging_id FROM pyq.questions WHERE source_file_id = :sfid"),
                    {"sfid": source_file_id},
                )
            ).all()
        }

        version_counters: dict[int | None, int] = {}
        existing_max = (
            await session.execute(
                text(
                    "SELECT question_number, MAX(extraction_version) FROM pyq.questions "
                    "WHERE source_file_id = :sfid GROUP BY question_number"
                ),
                {"sfid": source_file_id},
            )
        ).all()
        for qnum, maxver in existing_max:
            version_counters[qnum] = maxver

        for rec in records:
            rec_id = rec["id"]
            if rec_id in review_case_ids:
                report.review_case_excluded += 1
                continue
            if rec_id in exact_dup_ids:
                report.exact_duplicate_skipped += 1
                continue
            if rec_id not in eligible_ids:
                report.unclassified_skipped.append(rec_id)
                continue

            report.eligible_matched += 1
            staging_id = rec_id
            if staging_id in existing_staging_ids:
                report.already_present_skipped += 1
                continue

            try:
                question_number = int(rec.get("question_number_raw"))
            except (TypeError, ValueError):
                question_number = rec.get("global_sequence_in_file")

            slot = question_number
            extraction_version = version_counters.get(slot, 0) + 1
            version_counters[slot] = extraction_version

            subject = rec.get("subject")
            class_level = _class_level(rec)
            raw_stem = rec.get("stem_text") or ""
            raw_options = _raw_options(rec)
            validation_status = rec.get("extraction_status") or "EXTRACTED"
            extraction_confidence = rec.get("extraction_confidence")
            question_hash = rec.get("identity_key") or ""
            normalized_hash = rec.get("identity_key") or ""

            stmt = text(
                """
                INSERT INTO pyq.questions (
                    id, source_file_id, question_number, extraction_version,
                    staging_id, question_hash, normalized_question_hash,
                    subject, class_level, raw_stem, raw_options,
                    normalized_stem, normalized_options, extraction_confidence,
                    validation_status, state, concept_id
                ) VALUES (
                    :id, :source_file_id, :question_number, :extraction_version,
                    :staging_id, :question_hash, :normalized_hash,
                    :subject, :class_level, :raw_stem, CAST(:raw_options AS jsonb),
                    NULL, NULL, :extraction_confidence,
                    :validation_status, 'ANSWER_PENDING', NULL
                )
                ON CONFLICT (staging_id) DO NOTHING
                """
            )
            result = await session.execute(
                stmt,
                {
                    "id": uuid.uuid4(),
                    "source_file_id": source_file_id,
                    "question_number": question_number,
                    "extraction_version": extraction_version,
                    "staging_id": staging_id,
                    "question_hash": question_hash,
                    "normalized_hash": normalized_hash,
                    "subject": subject,
                    "class_level": class_level,
                    "raw_stem": raw_stem,
                    "raw_options": json.dumps(raw_options),
                    "extraction_confidence": extraction_confidence,
                    "validation_status": validation_status,
                },
            )
            if result.rowcount > 0:
                existing_staging_ids.add(staging_id)
                report.questions_inserted_this_run += 1

        await session.execute(
            text("UPDATE pyq.import_batches SET status = 'COMPLETED', completed_at = now() WHERE id = :id"),
            {"id": batch_id},
        )

    return report


async def main() -> int:
    parser = argparse.ArgumentParser(description="Import PDF-extracted PYQ corpus into pyq.* tables")
    parser.add_argument("--dry-run", action="store_true", help="Run without committing")
    args = parser.parse_args()

    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            report = await run_import(session)
            if args.dry_run:
                await session.rollback()
                print("DRY RUN -- rolled back, no changes persisted.")
            else:
                await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("pyq_pdf_extracted_import_failed")
            raise

    print(json.dumps(report.__dict__, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
