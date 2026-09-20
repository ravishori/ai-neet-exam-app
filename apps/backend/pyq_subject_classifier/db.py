"""DB access — psycopg only (already a project dependency), synchronous,
local Postgres socket. No ORM changes, no schema changes."""

from __future__ import annotations

import psycopg

from .config import DSN


def connect(read_only: bool):
    conn = psycopg.connect(DSN)
    conn.read_only = read_only
    return conn


def fetch_unanswered_null_subject(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            q.id AS question_id,
            sf.exam_year,
            sf.paper_id,
            sf.paper_code,
            q.question_number,
            q.subject,
            q.raw_stem AS question,
            q.raw_options AS options,
            q.state
        FROM pyq.questions q
        JOIN pyq.source_files sf ON sf.id = q.source_file_id
        LEFT JOIN pyq.answer_assertions aa ON aa.question_id = q.id
        WHERE aa.question_id IS NULL AND q.subject IS NULL
        ORDER BY sf.exam_year, sf.paper_id, q.question_number
        """
    )
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def fetch_remaining_null_subject(conn) -> list[dict]:
    """Phase 2 input: whatever is STILL subject IS NULL right now (i.e. the
    Phase 1 leftovers) — read fresh from the DB rather than assuming the
    2,775 figure is still exact, per the project's own repeated 'recount,
    don't trust a prior report' convention."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            q.id AS question_id,
            sf.exam_year,
            sf.paper_id,
            sf.paper_code,
            q.question_number,
            q.subject,
            q.raw_stem AS question,
            q.raw_options AS options,
            q.state
        FROM pyq.questions q
        JOIN pyq.source_files sf ON sf.id = q.source_file_id
        WHERE q.subject IS NULL
        ORDER BY sf.exam_year, sf.paper_id, q.question_number
        """
    )
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def audit_table_exists(conn) -> bool:
    """The audit table is created via the real Alembic migration
    (alembic/versions/c1d2e3f4b5a6_pyq_subject_classification_audit.py),
    not ad-hoc DDL here. This just confirms it's been applied."""
    cur = conn.cursor()
    cur.execute(
        "SELECT to_regclass('pyq.subject_classification_audit') IS NOT NULL"
    )
    return bool(cur.fetchone()[0])


def apply_classification(conn, *, question_id, new_subject, previous_subject, status, confidence, method, ncert_source, classifier_version) -> bool:
    """Updates subject only if it is still NULL at apply time (idempotency +
    never overwrite verified data). Records an audit row ONLY when the
    update actually happened — a no-op re-run (subject already set) must
    never insert a duplicate/no-op audit row. Returns True if the
    questions row was updated."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE pyq.questions SET subject = %s, updated_at = now() WHERE id = %s AND subject IS NULL",
        (new_subject, question_id),
    )
    updated = cur.rowcount > 0
    if updated:
        cur.execute(
            """
            INSERT INTO pyq.subject_classification_audit
                (question_id, previous_subject, new_subject, classification_status,
                 confidence, classification_method, ncert_source, classifier_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (question_id, previous_subject, new_subject, status, confidence, method, ncert_source, classifier_version),
        )
    return updated
