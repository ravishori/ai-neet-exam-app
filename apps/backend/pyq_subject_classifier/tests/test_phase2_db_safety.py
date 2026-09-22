import pytest

from pyq_subject_classifier import config
from pyq_subject_classifier.db import apply_classification, audit_table_exists, connect


def _db_reachable() -> bool:
    import psycopg

    try:
        with psycopg.connect(config.DSN, connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_reachable(), reason="pyq_subject_classifier dev DB not reachable")


@pytest.fixture
def rw_conn():
    conn = connect(read_only=False)
    yield conn
    conn.rollback()
    conn.close()


def test_phase2_reuses_existing_audit_table_no_second_table(rw_conn):
    """Phase 2 must not create a second/parallel audit table."""
    assert audit_table_exists(rw_conn) is True
    cur = rw_conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = 'pyq' AND table_name LIKE '%%classification_audit%%'"
    )
    assert cur.fetchone()[0] == 1


def test_phase2_writes_v2_classifier_version(rw_conn):
    cur = rw_conn.cursor()
    cur.execute("SELECT id FROM pyq.questions WHERE subject IS NULL LIMIT 1")
    row = cur.fetchone()
    if not row:
        pytest.skip("no NULL-subject question available")
    qid = row[0]

    apply_classification(
        rw_conn, question_id=qid, new_subject="Chemistry", previous_subject=None,
        status="RESOLVED", confidence="HIGH", method="ncert_phase2_deep_retrieval",
        ncert_source="kech105.pdf#kech105", classifier_version=config.CLASSIFIER_VERSION_PHASE2,
    )
    cur.execute(
        "SELECT classifier_version, classification_method FROM pyq.subject_classification_audit "
        "WHERE question_id = %s ORDER BY classified_at DESC LIMIT 1",
        (qid,),
    )
    version, method = cur.fetchone()
    assert version == "ncert-local-v2"
    assert method == "ncert_phase2_deep_retrieval"


def test_phase2_never_overwrites_phase1_classification(rw_conn):
    cur = rw_conn.cursor()
    cur.execute("SELECT id, subject FROM pyq.questions WHERE subject IS NOT NULL LIMIT 1")
    row = cur.fetchone()
    if not row:
        pytest.skip("no subject-populated question available")
    qid, original = row

    updated = apply_classification(
        rw_conn, question_id=qid, new_subject="Biology", previous_subject=original,
        status="RESOLVED", confidence="HIGH", method="ncert_phase2_deep_retrieval",
        ncert_source="test", classifier_version=config.CLASSIFIER_VERSION_PHASE2,
    )
    assert updated is False
    cur.execute("SELECT subject FROM pyq.questions WHERE id = %s", (qid,))
    assert cur.fetchone()[0] == original
