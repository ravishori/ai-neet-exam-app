#!/usr/bin/env python3
"""FACTORY-PYQ-P3 — import the reconciled PYQ corpus into pyq.* staging tables.

Source of truth for this loader (per the read-only reconciliation + decision
gate passes that preceded this script):
  1. data/staging/pyq/2020-2025/papers/*/questions.jsonl   (72 papers, canonical)
  2. data/staging/pyq/2020-2025/p2_1e_full_r3/questions.p2_1e_full.jsonl (GREEN-gated OCR recovery)

Policy:
  - Import canonical non-empty records as-is (state=ANSWER_PENDING).
  - For a paper whose canonical records are OCR_REQUIRED placeholders
    (empty stem), use its r3-recovered records instead (state=ANSWER_PENDING)
    and skip the placeholders entirely — never import an empty stem when a
    usable r3 replacement exists for that paper.
  - If a placeholder's paper has no r3 coverage, insert it as state=BLOCKED
    (raw_stem/raw_options are empty but well-formed — never a corrupt row).
  - No answer_assertions / qa_reviews / promotion_log are written.
  - No LLM calls. No writes to cms.content_items. No writes outside pyq.*.
  - Idempotent: every insert is keyed by the source record's own staging_id
    (ON CONFLICT (staging_id) DO NOTHING) — a second run inserts 0 new rows.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger("cms.pyq.import")

SOURCE_KEY = "NEET_PYQ_OFFICIAL"
SOURCE_NAME = "NEET Official PYQ Papers (2020-2025, staged extraction)"
AUTHORITY_TYPE = "OFFICIAL_NEET_PAPER"
ZIP_SHA256 = "4b5925fd554e6f3e37c446904c9b71719fc681994059c21d0f51813c610eda4a"
PIPELINE_STAGE = "p2_canonical_plus_p2_1e_full_r3"

REPO_ROOT = Path(__file__).resolve().parents[3]
STAGING_ROOT = REPO_ROOT / "data" / "staging" / "pyq" / "2020-2025"
PAPERS_DIR = STAGING_ROOT / "papers"
R3_FILE = STAGING_ROOT / "p2_1e_full_r3" / "questions.p2_1e_full.jsonl"
MANIFEST_PATH = STAGING_ROOT / "p2_1e_full_r3" / "manifest.p2_1e_full.json"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _is_usable(rec: dict[str, Any]) -> bool:
    return bool((rec.get("stem") or "").strip()) and rec.get("validation_status") != "OCR_REQUIRED"


def _raw_options(rec: dict[str, Any]) -> dict[str, str]:
    out = {}
    for label, key in (("A", "option_a"), ("B", "option_b"), ("C", "option_c"), ("D", "option_d")):
        val = rec.get(key)
        if val is not None:
            out[label] = val
    return out


@dataclass
class ImportReport:
    papers_seen: int = 0
    canonical_records_seen: int = 0
    canonical_usable_imported: int = 0
    canonical_placeholder_skipped_r3_available: int = 0
    r3_records_imported: int = 0
    blocked_inserted: int = 0
    skipped_invalid: list[str] = field(default_factory=list)
    source_files_created: int = 0
    questions_inserted_this_run: int = 0


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


async def _get_or_create_batch(session: AsyncSession, source_id: uuid.UUID) -> uuid.UUID:
    row = (
        await session.execute(
            text(
                "SELECT id FROM pyq.import_batches "
                "WHERE source_id = :sid AND pipeline_stage = :stage AND zip_sha256 = :sha"
            ),
            {"sid": source_id, "stage": PIPELINE_STAGE, "sha": ZIP_SHA256},
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
            "sha": ZIP_SHA256,
            "manifest": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
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


async def _insert_question(
    session: AsyncSession,
    *,
    source_file_id: uuid.UUID,
    rec: dict[str, Any],
    state: str,
    usable: bool,
    existing_staging_ids: set[str],
    version_counters: dict[tuple[uuid.UUID, int | None], int],
) -> bool:
    """Returns True if a new row was inserted (False if it already existed).

    Idempotency: staging_id is the true identity of a source record and is
    checked in-memory against `existing_staging_ids` (preloaded for this
    batch) before ever attempting an insert — a second run never re-inserts
    a record it already has, regardless of extraction_version bookkeeping.

    Raw-data preservation: the corpus contains genuine duplicate
    question_number values within a single paper (distinct staging_ids,
    e.g. re-segmented fragments) — each becomes its own extraction_version
    under the same (source_file_id, question_number) slot rather than being
    dropped or overwriting one another.
    """
    staging_id = rec.get("staging_id")
    if not staging_id:
        return False
    if staging_id in existing_staging_ids:
        return False

    raw_stem = rec.get("stem") or ""
    raw_options = _raw_options(rec) if usable else {}
    question_number = rec.get("question_number")
    question_hash = rec.get("question_hash") or ""
    normalized_hash = rec.get("normalized_question_hash") or ""
    subject = rec.get("subject")
    validation_status = rec.get("validation_status") or "EXTRACTED"
    extraction_confidence = rec.get("extraction_confidence")

    slot = (source_file_id, question_number)
    extraction_version = version_counters.get(slot, 0) + 1
    version_counters[slot] = extraction_version

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
            :subject, NULL, :raw_stem, CAST(:raw_options AS jsonb),
            NULL, NULL, :extraction_confidence,
            :validation_status, :state, NULL
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
            "raw_stem": raw_stem,
            "raw_options": json.dumps(raw_options),
            "extraction_confidence": extraction_confidence,
            "validation_status": validation_status,
            "state": state,
        },
    )
    inserted = result.rowcount > 0
    if inserted:
        existing_staging_ids.add(staging_id)
    return inserted


async def run_import(session: AsyncSession) -> ImportReport:
    report = ImportReport()

    paper_dirs = sorted(p for p in PAPERS_DIR.iterdir() if p.is_dir())
    r3_records = _read_jsonl(R3_FILE) if R3_FILE.exists() else []
    r3_by_source_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in r3_records:
        sha = rec.get("source_sha256")
        if sha:
            r3_by_source_sha[sha].append(rec)

    source_id = await _get_or_create_source(session)
    batch_id = await _get_or_create_batch(session, source_id)

    existing_rows = (
        await session.execute(
            text(
                "SELECT q.staging_id, q.source_file_id, q.question_number, q.extraction_version "
                "FROM pyq.questions q "
                "JOIN pyq.source_files sf ON sf.id = q.source_file_id "
                "WHERE sf.batch_id = :bid"
            ),
            {"bid": batch_id},
        )
    ).all()
    existing_staging_ids: set[str] = {row[0] for row in existing_rows}
    version_counters: dict[tuple[uuid.UUID, int | None], int] = {}
    for _staging_id, source_file_id, question_number, extraction_version in existing_rows:
        slot = (source_file_id, question_number)
        version_counters[slot] = max(version_counters.get(slot, 0), extraction_version)

    for paper_dir in paper_dirs:
        report.papers_seen += 1
        source_sha = paper_dir.name
        jsonl_path = paper_dir / "questions.jsonl"
        if not jsonl_path.exists():
            report.skipped_invalid.append(f"{source_sha}: no questions.jsonl")
            continue

        canonical_records = _read_jsonl(jsonl_path)
        report.canonical_records_seen += len(canonical_records)

        usable = [r for r in canonical_records if _is_usable(r)]
        placeholders = [r for r in canonical_records if not _is_usable(r)]

        sample = canonical_records[0] if canonical_records else {}
        paper_id_short = sample.get("paper_id") or source_sha[:16]
        paper_code = sample.get("paper_code")
        exam_year = sample.get("exam_year")
        relative_path = sample.get("source_file") or f"NEET_PYQ_OFFICIAL/unknown/{source_sha}.pdf"

        r3_for_paper = r3_by_source_sha.get(source_sha, [])

        source_file_id = await _get_or_create_source_file(
            session,
            batch_id,
            paper_id=paper_id_short,
            paper_code=paper_code,
            exam_year=exam_year,
            relative_path=relative_path,
            file_sha256=source_sha,
        )
        report.source_files_created += 1

        # 1. Import canonical usable records as-is.
        for rec in usable:
            inserted = await _insert_question(
                session, source_file_id=source_file_id, rec=rec, state="ANSWER_PENDING", usable=True,
                existing_staging_ids=existing_staging_ids, version_counters=version_counters,
            )
            if inserted:
                report.canonical_usable_imported += 1
                report.questions_inserted_this_run += 1

        # 2. Placeholders: prefer r3 replacement; never import the empty stem
        #    when a usable r3 replacement exists for this paper.
        if placeholders:
            if r3_for_paper:
                report.canonical_placeholder_skipped_r3_available += len(placeholders)
                for rec in r3_for_paper:
                    if not _is_usable(rec):
                        continue
                    inserted = await _insert_question(
                        session, source_file_id=source_file_id, rec=rec, state="ANSWER_PENDING", usable=True,
                        existing_staging_ids=existing_staging_ids, version_counters=version_counters,
                    )
                    if inserted:
                        report.r3_records_imported += 1
                        report.questions_inserted_this_run += 1
            else:
                # No r3 replacement available — preserve as BLOCKED, never as
                # a fabricated/invalid usable question.
                for rec in placeholders:
                    inserted = await _insert_question(
                        session, source_file_id=source_file_id, rec=rec, state="BLOCKED", usable=False,
                        existing_staging_ids=existing_staging_ids, version_counters=version_counters,
                    )
                    if inserted:
                        report.blocked_inserted += 1
                        report.questions_inserted_this_run += 1

    await session.execute(
        text("UPDATE pyq.import_batches SET status = 'COMPLETED', completed_at = now() WHERE id = :id"),
        {"id": batch_id},
    )
    return report


async def main() -> int:
    parser = argparse.ArgumentParser(description="Import PYQ staging corpus into pyq.* tables")
    parser.add_argument("--dry-run", action="store_true", help="Run without committing")
    args = parser.parse_args()

    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            report = await run_import(session)
            if args.dry_run:
                await session.rollback()
                print("DRY RUN — rolled back, no changes persisted.")
            else:
                await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("pyq_import_failed")
            raise

    print(json.dumps(report.__dict__, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
