"""Local-database staging store for deterministic MCQ generation candidates.

Additive to (never a replacement for) the existing JSON file output written
by ``deterministic_batch_runner.write_batch_outputs``. Every candidate the
runner produces — accepted AND rejected/duplicate — is persisted here with
full provenance, so duplicates are no longer silently discarded.

Hard safety rules enforced by this module:
- LOCAL DATABASE ONLY. ``assert_local_database_target`` raises if the
  configured connection does not resolve to localhost/127.0.0.1. Every
  write path in this module calls it first.
- No uniqueness constraint on question content: a content-duplicate
  candidate is flagged via ``is_duplicate`` / ``duplicate_of_question_id``,
  never rejected by the database.
- The only unique key is the staging row's own identity
  (batch_id, fact_id, attempt_number) — this makes resumed/retried batch
  runs idempotent (an existing row for that key is left untouched, not
  re-inserted), independent of content-level duplicate detection.
- ``concept_id`` is always optional.
- No FK into cms.*/pyq.* content tables — ``duplicate_of_question_id`` is a
  plain string reference, never an enforced foreign key.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class NotLocalDatabaseError(RuntimeError):
    """Raised when the configured DB target does not resolve to localhost."""


def _host_of(url: str) -> str | None:
    match = re.search(r"@([^:/]+)", url or "")
    return match.group(1) if match else None


def assert_local_database_target(url: str) -> str:
    """Return the host if ``url`` resolves to localhost; raise otherwise.

    Never logs or returns credentials — only the host is inspected/returned.
    """
    host = _host_of(url)
    if host not in _LOCAL_HOSTS:
        raise NotLocalDatabaseError(
            "generation_staging_store refuses to write: configured database "
            f"host {host!r} is not localhost/127.0.0.1. This store is "
            "local-dev-only by design and must never target production."
        )
    return host


async def assert_engine_is_local(engine: AsyncEngine) -> str:
    """Runtime check (in addition to the static config check) that the
    engine's own URL resolves to a local host. Belt-and-braces safeguard
    against a swapped-in engine pointing elsewhere."""
    return assert_local_database_target(str(engine.url))


def _session_bind_url(session: AsyncSession) -> str:
    """``AsyncSession.bind`` is an ``AsyncEngine`` in normal app usage, but
    tests (and any code using a SAVEPOINT-per-test pattern) bind the
    session directly to an ``AsyncConnection``, which exposes its URL via
    ``.engine.url`` rather than ``.url``. Handle both without guessing."""
    bind = session.bind
    url = getattr(bind, "url", None)
    if url is None:
        engine_obj = getattr(bind, "engine", None)
        url = getattr(engine_obj, "url", None)
    if url is None:
        raise NotLocalDatabaseError(
            "generation_staging_store could not determine the database URL "
            "for this session's bind; refusing to write."
        )
    return str(url)


@dataclass
class StagingCandidateRecord:
    """One row to persist — either an accepted candidate or a rejection."""

    batch_id: str
    sequence_in_batch: int
    fact_id: str
    outcome: str  # "ACCEPTED" | "REJECTED"
    attempt_number: int = 1
    generation_method: str | None = None
    engine_version: str | None = None
    seed: int | None = None
    source_pdf: str | None = None
    source_relative_path: str | None = None
    evidence_pages: Any = None
    evidence_quoted_text: str | None = None
    provenance: Any = None
    subject: str | None = None
    class_level: str | None = None
    chapter: str | None = None
    topic: str | None = None
    concept: str | None = None
    concept_id: str | None = None
    syllabus_binding: Any = None
    question_type: str | None = None
    difficulty: str | None = None
    question_text: str | None = None
    options: Any = None
    correct_answer: str | None = None
    explanation: str | None = None
    stem_hash: str | None = None
    option_stem_hash: str | None = None
    rejection_reason: str | None = None
    rejection_details: Any = None
    validation_status: str | None = None
    validation_result: Any = None
    is_duplicate: bool = False
    duplicate_of_question_id: str | None = None
    duplicate_matched_source_file: str | None = None
    duplicate_similarity: float | None = None
    raw_candidate: Any = None
    # MCQ-FACTORY-GROQ-001 additive columns (migration a1b2c3d4e5f6). Both
    # stay None/NULL for every pre-existing producer (deterministic_batch_runner
    # never sets them) — only the Groq-backed generation pipeline populates them.
    candidate_kind: str | None = None  # "GENERATED_PRACTICE" | "HISTORICAL_PYQ"
    evidence_relocation_confirmed: bool | None = None


_INSERT_SQL = text(
    """
    INSERT INTO generation_staging.candidates (
        id, batch_id, sequence_in_batch, attempt_number, generation_method,
        engine_version, seed, fact_id, source_pdf, source_relative_path,
        evidence_pages, evidence_quoted_text, provenance, subject,
        class_level, chapter, topic, concept, concept_id, syllabus_binding,
        question_type, difficulty, question_text, options, correct_answer,
        explanation, stem_hash, option_stem_hash, outcome, rejection_reason,
        rejection_details, validation_status, validation_result,
        is_duplicate, duplicate_of_question_id, duplicate_matched_source_file,
        duplicate_similarity, raw_candidate, candidate_kind,
        evidence_relocation_confirmed
    ) VALUES (
        :id, :batch_id, :sequence_in_batch, :attempt_number,
        :generation_method, :engine_version, :seed, :fact_id, :source_pdf,
        :source_relative_path, :evidence_pages, :evidence_quoted_text,
        :provenance, :subject, :class_level, :chapter, :topic, :concept,
        :concept_id, :syllabus_binding, :question_type, :difficulty,
        :question_text, :options, :correct_answer, :explanation, :stem_hash,
        :option_stem_hash, :outcome, :rejection_reason, :rejection_details,
        :validation_status, :validation_result, :is_duplicate,
        :duplicate_of_question_id, :duplicate_matched_source_file,
        :duplicate_similarity, :raw_candidate, :candidate_kind,
        :evidence_relocation_confirmed
    )
    ON CONFLICT ON CONSTRAINT uq_generation_staging_candidates_batch_fact_attempt
    DO NOTHING
    """
)

_EXISTS_SQL = text(
    """
    SELECT 1 FROM generation_staging.candidates
    WHERE batch_id = :batch_id AND fact_id = :fact_id
      AND attempt_number = :attempt_number
    """
)

_COUNT_SQL = text(
    "SELECT outcome, is_duplicate, count(*) FROM generation_staging.candidates "
    "WHERE batch_id = :batch_id GROUP BY outcome, is_duplicate"
)

# NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: cross-BATCH duplicate lookup. A row
# only ever has a non-NULL stem_hash once a real candidate was generated
# and parsed (a pipeline-level REJECTED row — out-of-syllabus, no
# groundable evidence — never has one), so this naturally never matches a
# pre-generation rejection; no extra WHERE clause is needed to exclude
# those. ORDER BY created_at ASC so the EARLIEST match is first — useful
# for provenance ("this duplicates the original, not a later copy").
_STEM_HASH_MATCH_SQL = text(
    """
    SELECT id, batch_id, fact_id, attempt_number
    FROM generation_staging.candidates
    WHERE stem_hash = :stem_hash
    ORDER BY created_at ASC
    """
)


@dataclass(frozen=True)
class StagingStemHashMatch:
    """One real staging row (any batch) whose ``stem_hash`` exactly
    matches the queried hash. Plain data — the orchestrator-side adapter
    (``orchestrator.CrossBatchDuplicateMatch``) is a separate type so this
    module never has to import the mcq_factory_groq package."""

    staging_id: str
    batch_id: str
    fact_id: str
    attempt_number: int


async def find_staging_candidates_by_stem_hash(
    session: AsyncSession, stem_hash_value: str
) -> list[StagingStemHashMatch]:
    """Read-only cross-batch duplicate lookup — reads the REAL table
    directly, across ALL batches, every call (never a stale snapshot taken
    once at construction time). This is the concrete fix for the
    structural gap documented in
    docs/quality/neet_mcq_factory_MULTI_ATTEMPT_PLAN_20261013.md §1.3:
    ``validators.find_cross_corpus_conflicts``'s ``existing_corpus`` was
    never populated by the real CLI at all, so duplicate detection was a
    live no-op in every real run to date. This function, together with
    ``orchestrator.GroqFactoryOrchestrator``'s ``cross_batch_duplicate_lookup``
    wiring, is the fix — see ``scripts/mcq_factory_groq_bulk_run.py``'s
    ``default_live_dependencies``."""
    assert_local_database_target(_session_bind_url(session))
    result = await session.execute(_STEM_HASH_MATCH_SQL, {"stem_hash": stem_hash_value})
    return [
        StagingStemHashMatch(
            staging_id=str(row.id),
            batch_id=row.batch_id,
            fact_id=row.fact_id,
            attempt_number=row.attempt_number,
        )
        for row in result.fetchall()
    ]


async def staging_row_exists(
    session: AsyncSession, *, batch_id: str, fact_id: str, attempt_number: int = 1
) -> bool:
    assert_local_database_target(_session_bind_url(session))
    result = await session.execute(
        _EXISTS_SQL,
        {"batch_id": batch_id, "fact_id": fact_id, "attempt_number": attempt_number},
    )
    return result.first() is not None


async def insert_staging_candidate(
    session: AsyncSession, record: StagingCandidateRecord
) -> bool:
    """Insert one staging row. Idempotent on (batch_id, fact_id,
    attempt_number): a retried/resumed run re-inserting the same attempt is
    a silent no-op (ON CONFLICT DO NOTHING), not an error and not a second
    row. Returns True if a new row was inserted, False if it already
    existed. Never rejects content-duplicate candidates — those are simply
    flagged via record.is_duplicate."""
    assert_local_database_target(_session_bind_url(session))
    params = {
        "id": str(uuid.uuid4()),
        "batch_id": record.batch_id,
        "sequence_in_batch": record.sequence_in_batch,
        "attempt_number": record.attempt_number,
        "generation_method": record.generation_method,
        "engine_version": record.engine_version,
        "seed": record.seed,
        "fact_id": record.fact_id,
        "source_pdf": record.source_pdf,
        "source_relative_path": record.source_relative_path,
        "evidence_pages": record.evidence_pages,
        "evidence_quoted_text": record.evidence_quoted_text,
        "provenance": record.provenance,
        "subject": record.subject,
        "class_level": record.class_level,
        "chapter": record.chapter,
        "topic": record.topic,
        "concept": record.concept,
        "concept_id": record.concept_id,
        "syllabus_binding": record.syllabus_binding,
        "question_type": record.question_type,
        "difficulty": record.difficulty,
        "question_text": record.question_text,
        "options": record.options,
        "correct_answer": record.correct_answer,
        "explanation": record.explanation,
        "stem_hash": record.stem_hash,
        "option_stem_hash": record.option_stem_hash,
        "outcome": record.outcome,
        "rejection_reason": record.rejection_reason,
        "rejection_details": record.rejection_details,
        "validation_status": record.validation_status,
        "validation_result": record.validation_result,
        "is_duplicate": record.is_duplicate,
        "duplicate_of_question_id": record.duplicate_of_question_id,
        "duplicate_matched_source_file": record.duplicate_matched_source_file,
        "duplicate_similarity": record.duplicate_similarity,
        "raw_candidate": record.raw_candidate,
        "candidate_kind": record.candidate_kind,
        "evidence_relocation_confirmed": record.evidence_relocation_confirmed,
    }
    import json as _json

    for key in ("evidence_pages", "provenance", "syllabus_binding", "options", "rejection_details", "validation_result", "raw_candidate"):
        if params[key] is not None and not isinstance(params[key], str):
            params[key] = _json.dumps(params[key], ensure_ascii=False, default=str)

    already = await staging_row_exists(
        session,
        batch_id=record.batch_id,
        fact_id=record.fact_id,
        attempt_number=record.attempt_number,
    )
    if already:
        return False
    await session.execute(_INSERT_SQL, params)
    return True


async def count_staging_rows_for_batch(
    session: AsyncSession, batch_id: str
) -> dict[tuple[str, bool], int]:
    assert_local_database_target(_session_bind_url(session))
    result = await session.execute(_COUNT_SQL, {"batch_id": batch_id})
    return {(row[0], row[1]): row[2] for row in result.fetchall()}
