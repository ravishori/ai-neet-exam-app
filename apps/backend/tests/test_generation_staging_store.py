"""Tests for the local-database generation staging store.

Uses the project's own `db_session` fixture (conftest.py): a
SAVEPOINT-isolated session against trinetra_test_db (localhost — see
conftest.py TEST_DATABASE_URL) that is rolled back automatically at
teardown, so these tests never need manual cleanup and never leave rows
behind even on failure.

They prove the hard requirements from the staging task: content
duplicates are storable (not rejected by a DB constraint), retried/resumed
batch runs don't create duplicate staging rows, writes only ever target a
local engine, and concept_id=NULL is accepted.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.database import engine
from app.modules.cms.services.generation_staging_store import (
    NotLocalDatabaseError,
    StagingCandidateRecord,
    assert_local_database_target,
    insert_staging_candidate,
    staging_row_exists,
)

def _batch_id() -> str:
    return f"TEST-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# (c) staging writes only ever target the local DB connection
# ---------------------------------------------------------------------------


def test_assert_local_database_target_accepts_localhost():
    assert assert_local_database_target(
        "postgresql+asyncpg://user:pw@localhost:5432/db"
    ) == "localhost"
    assert assert_local_database_target(
        "postgresql+asyncpg://user:pw@127.0.0.1:5432/db"
    ) == "127.0.0.1"


def test_assert_local_database_target_rejects_non_local_host():
    with pytest.raises(NotLocalDatabaseError):
        assert_local_database_target(
            "postgresql+asyncpg://user:pw@some-production-host.railway.app:5432/db"
        )


def test_configured_engine_is_local():
    """Safeguard: the actual app engine used by this test suite must be
    local, or every other test in this file would be silently exercising
    production."""
    assert assert_local_database_target(str(engine.url)) in ("localhost", "127.0.0.1", "::1")


# ---------------------------------------------------------------------------
# (a) a duplicate candidate CAN be inserted into staging, correctly flagged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_candidate_is_storable_and_flagged(db_session):
    batch_id = _batch_id()
    record = StagingCandidateRecord(
        batch_id=batch_id,
        sequence_in_batch=1,
        fact_id="ncert-fact-test-dup-1",
        outcome="REJECTED",
        generation_method="deterministic_fact_engine",
        question_text="Duplicate stem for test purposes",
        is_duplicate=True,
        duplicate_of_question_id="GEN-NEET-0001",
        duplicate_matched_source_file="neet_mcq_batch_001.json",
        duplicate_similarity=0.87,
        rejection_reason="DUPLICATE_OF_EXISTING_CORPUS_ROW",
    )
    inserted = await insert_staging_candidate(db_session, record)
    await db_session.commit()
    assert inserted is True

    result = await db_session.execute(
        text(
            "SELECT is_duplicate, duplicate_of_question_id, duplicate_similarity, outcome "
            "FROM generation_staging.candidates WHERE batch_id = :b AND fact_id = :f"
        ),
        {"b": batch_id, "f": "ncert-fact-test-dup-1"},
    )
    row = result.first()
    assert row is not None
    assert row.is_duplicate is True
    assert row.duplicate_of_question_id == "GEN-NEET-0001"
    assert row.outcome == "REJECTED"


# ---------------------------------------------------------------------------
# (b) resuming/retrying a batch does not create duplicate STAGING rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_resumed_batch_does_not_duplicate_staging_rows(db_session):
    batch_id = _batch_id()
    record = StagingCandidateRecord(
        batch_id=batch_id,
        sequence_in_batch=1,
        fact_id="ncert-fact-test-resume-1",
        outcome="ACCEPTED",
        generation_method="deterministic_fact_engine",
        question_text="First attempt stem",
    )
    first_insert = await insert_staging_candidate(db_session, record)
    await db_session.commit()
    assert first_insert is True

    # Simulate a resumed/retried run re-processing the same fact at the
    # same attempt_number — this must be a no-op, not a second row and not
    # an error.
    retry_record = StagingCandidateRecord(
        batch_id=batch_id,
        sequence_in_batch=1,
        fact_id="ncert-fact-test-resume-1",
        outcome="ACCEPTED",
        generation_method="deterministic_fact_engine",
        question_text="First attempt stem",
    )
    second_insert = await insert_staging_candidate(db_session, retry_record)
    await db_session.commit()
    assert second_insert is False

    result = await db_session.execute(
        text(
            "SELECT count(*) FROM generation_staging.candidates "
            "WHERE batch_id = :b AND fact_id = :f"
        ),
        {"b": batch_id, "f": "ncert-fact-test-resume-1"},
    )
    assert result.scalar_one() == 1

    exists = await staging_row_exists(
        db_session, batch_id=batch_id, fact_id="ncert-fact-test-resume-1"
    )
    assert exists is True


# ---------------------------------------------------------------------------
# (d) concept_id = NULL is accepted without error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_concept_id_null_is_accepted(db_session):
    batch_id = _batch_id()
    record = StagingCandidateRecord(
        batch_id=batch_id,
        sequence_in_batch=1,
        fact_id="ncert-fact-test-noconcept-1",
        outcome="ACCEPTED",
        generation_method="deterministic_fact_engine",
        question_text="Stem with no concept binding",
        concept_id=None,
        concept=None,
    )
    inserted = await insert_staging_candidate(db_session, record)
    await db_session.commit()
    assert inserted is True

    result = await db_session.execute(
        text(
            "SELECT concept_id FROM generation_staging.candidates "
            "WHERE batch_id = :b AND fact_id = :f"
        ),
        {"b": batch_id, "f": "ncert-fact-test-noconcept-1"},
    )
    assert result.scalar_one() is None
