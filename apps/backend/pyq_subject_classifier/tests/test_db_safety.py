"""Integration tests against the real dev DB (read-only where possible).
Uses a savepoint-rollback pattern so nothing persists."""

import uuid

import pytest

from pyq_subject_classifier.db import apply_classification, audit_table_exists, connect


@pytest.fixture
def rw_conn():
    conn = connect(read_only=False)
    yield conn
    conn.rollback()
    conn.close()


def test_audit_table_exists(rw_conn):
    assert audit_table_exists(rw_conn) is True


def test_apply_classification_never_overwrites_existing_subject(rw_conn):
    cur = rw_conn.cursor()
    cur.execute("SELECT id, subject FROM pyq.questions WHERE subject IS NOT NULL LIMIT 1")
    row = cur.fetchone()
    if not row:
        pytest.skip("no subject-populated question available")
    qid, original_subject = row

    updated = apply_classification(
        rw_conn, question_id=qid, new_subject="Biology", previous_subject=original_subject,
        status="RESOLVED", confidence="HIGH", method="test", ncert_source="test", classifier_version="test-v1",
    )
    assert updated is False  # subject already set -> WHERE subject IS NULL guard prevents the write

    cur.execute("SELECT subject FROM pyq.questions WHERE id = %s", (qid,))
    assert cur.fetchone()[0] == original_subject  # unchanged


def test_apply_classification_is_idempotent(rw_conn):
    cur = rw_conn.cursor()
    cur.execute("SELECT id FROM pyq.questions WHERE subject IS NULL LIMIT 1")
    row = cur.fetchone()
    if not row:
        pytest.skip("no NULL-subject question available")
    qid = row[0]

    first = apply_classification(
        rw_conn, question_id=qid, new_subject="Physics", previous_subject=None,
        status="RESOLVED", confidence="HIGH", method="test", ncert_source="test", classifier_version="test-v1",
    )
    assert first is True

    cur.execute("SELECT COUNT(*) FROM pyq.subject_classification_audit WHERE question_id = %s", (qid,))
    assert cur.fetchone()[0] == 1  # exactly one audit row after the real write

    second = apply_classification(
        rw_conn, question_id=qid, new_subject="Chemistry", previous_subject="Physics",
        status="RESOLVED", confidence="HIGH", method="test", ncert_source="test", classifier_version="test-v1",
    )
    assert second is False  # already non-NULL now -> guard blocks a second overwrite

    cur.execute("SELECT subject FROM pyq.questions WHERE id = %s", (qid,))
    assert cur.fetchone()[0] == "Physics"  # first write wins, not silently changed

    cur.execute("SELECT COUNT(*) FROM pyq.subject_classification_audit WHERE question_id = %s", (qid,))
    assert cur.fetchone()[0] == 1  # the skipped no-op re-apply must NOT add a duplicate audit row


def test_apply_classification_writes_audit_row(rw_conn):
    cur = rw_conn.cursor()
    cur.execute("SELECT id FROM pyq.questions WHERE subject IS NULL LIMIT 1")
    row = cur.fetchone()
    if not row:
        pytest.skip("no NULL-subject question available")
    qid = row[0]

    apply_classification(
        rw_conn, question_id=qid, new_subject="Biology", previous_subject=None,
        status="RESOLVED", confidence="MEDIUM", method="test", ncert_source="test-src", classifier_version="test-v1",
    )
    cur.execute(
        "SELECT new_subject, classification_method, classifier_version FROM pyq.subject_classification_audit "
        "WHERE question_id = %s ORDER BY classified_at DESC LIMIT 1",
        (qid,),
    )
    audit_row = cur.fetchone()
    assert audit_row == ("Biology", "test", "test-v1")


def test_dry_run_connection_is_read_only():
    conn = connect(read_only=True)
    try:
        with pytest.raises(Exception):  # noqa: B017, PT011 — driver-specific ReadOnlySqlTransaction error
            cur = conn.cursor()
            cur.execute(
                "UPDATE pyq.questions SET subject = 'Physics' WHERE id = %s",
                (uuid.uuid4(),),
            )
    finally:
        conn.rollback()
        conn.close()
