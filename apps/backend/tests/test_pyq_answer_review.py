"""Tests for the TALOS PYQ individual answer-review feature:
app/modules/cms/pyq/pyq_option_eligibility.py,
app/modules/cms/pyq/pyq_answer_review.py, and
app/modules/cms/pyq/api/pyq_answer_review_router.py.

Follows the established conventions: raw-SQL fixture seeding (see
test_backfill_pyq_pdf_extracted_answer_assertions.py) for service-level
tests, and client/db_session/register_user fixtures (see
test_admin_phase1.py) for HTTP/permission/IDOR tests.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.modules.cms.pyq.pyq_answer_review import (
    QuestionNotEligibleError,
    ReviewQueueFilters,
    SourceNotConsultedError,
    StaleQuestionStateError,
    get_queue_counts,
    list_review_queue,
    save_answer_review,
    skip_question_review,
)
from app.modules.cms.pyq.pyq_option_eligibility import classify_option_structure
from conftest import csrf_headers

SOURCE_KEY = "NEET_PYQ_OFFICIAL"  # the service hardcodes this filter; db_session is SAVEPOINT-isolated per test


# ---------------------------------------------------------------------------
# Eligibility classification (pure function, no DB)
# ---------------------------------------------------------------------------


def test_four_distinct_options_is_eligible():
    assert classify_option_structure({"A": "x", "B": "y", "C": "z", "D": "w"}).value == "FOUR_VALID_OPTIONS"


def test_missing_option_excluded():
    assert classify_option_structure({"A": "x", "B": "", "C": "z", "D": "w"}).value == "MISSING_OPTION"


def test_whitespace_only_option_treated_as_missing():
    assert classify_option_structure({"A": "x", "B": "   ", "C": "z", "D": "w"}).value == "MISSING_OPTION"


def test_duplicate_options_excluded():
    assert classify_option_structure({"A": "x", "B": "x", "C": "z", "D": "w"}).value == "DUPLICATE_OPTIONS"


def test_numerically_distinct_options_not_flagged_duplicate():
    # Conservative normalization: '2 mC' and '4 mC' must stay distinct.
    assert (
        classify_option_structure({"A": "2 mC", "B": "4 mC", "C": "6 mC", "D": "8 mC"}).value
        == "FOUR_VALID_OPTIONS"
    )


def test_inconsistent_nullability_is_malformed():
    assert classify_option_structure({"A": "x", "B": None, "C": "z", "D": "w"}).value == "MALFORMED_OPTIONS"


def test_corrupted_multiline_duplicate_is_malformed_not_duplicate():
    garbled = "S\r\n3gS\r\n \r\n4\r\n2\r\n,"
    assert (
        classify_option_structure({"A": garbled, "B": garbled, "C": "z", "D": "w"}).value == "MALFORMED_OPTIONS"
    )


def test_image_dependent_missing_option_requires_manual_review():
    result = classify_option_structure({"A": "x", "B": "", "C": "as shown in the figure", "D": "w"})
    assert result.value == "REQUIRES_MANUAL_REVIEW"


def test_stem_control_character_corruption_is_malformed_even_with_clean_options():
    # The actual gap found in the 2026-10-22 deeper audit: the stem has an
    # embedded control byte but all four options are otherwise clean —
    # before passing raw_stem into classify_option_structure this would
    # have been misclassified FOUR_VALID_OPTIONS.
    result = classify_option_structure({"A": "a", "B": "b", "C": "c", "D": "d"}, raw_stem="stem with \x01 byte")
    assert result.value == "MALFORMED_OPTIONS"


def test_stem_without_control_characters_unaffected():
    result = classify_option_structure({"A": "a", "B": "b", "C": "c", "D": "d"}, raw_stem="2.50×10⁻³ clean stem")
    assert result.value == "FOUR_VALID_OPTIONS"


def test_scientific_notation_in_options_not_flagged_by_control_char_rule():
    result = classify_option_structure({"A": "2.50×10⁻³", "B": "H₂SO₄", "C": "α β Δ", "D": "A → B ⇌ C at 25°"})
    assert result.value == "FOUR_VALID_OPTIONS"


# ---------------------------------------------------------------------------
# Fixture seeding helpers
# ---------------------------------------------------------------------------


async def _seed_source_chain(db_session, *, source_key: str = SOURCE_KEY, exam_year: str = "2024"):
    source_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO pyq.sources (id, source_key, name, authority_type) VALUES (:id, :key, 'test', 'OFFICIAL')"),
        {"id": source_id, "key": source_key},
    )
    batch_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO pyq.import_batches (id, source_id, pipeline_stage, zip_sha256, status, manifest_path) "
            "VALUES (:id, :sid, 'test', 'deadbeef', 'COMPLETED', 'test')"
        ),
        {"id": batch_id, "sid": source_id},
    )
    source_file_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO pyq.source_files (id, batch_id, paper_id, exam_year, relative_path, file_sha256) "
            "VALUES (:id, :bid, 'test_paper', :year, 'test/path.pdf', 'deadbeef')"
        ),
        {"id": source_file_id, "bid": batch_id, "year": exam_year},
    )
    return source_file_id


async def _seed_question(
    db_session,
    source_file_id,
    *,
    question_number: int = 1,
    raw_options: dict | None = None,
    state: str = "ANSWER_PENDING",
    subject: str = "Physics",
) -> uuid.UUID:
    import json

    question_id = uuid.uuid4()
    opts = raw_options if raw_options is not None else {"A": "a", "B": "b", "C": "c", "D": "d"}
    await db_session.execute(
        text(
            "INSERT INTO pyq.questions "
            "(id, source_file_id, question_number, extraction_version, staging_id, question_hash, "
            "normalized_question_hash, subject, raw_stem, raw_options, validation_status, state) "
            "VALUES (:id, :sfid, :qn, 1, :staging_id, :hash, :hash, :subject, 'stem text', "
            "CAST(:opts AS jsonb), 'EXTRACTED', :state)"
        ),
        {
            "id": question_id,
            "sfid": source_file_id,
            "qn": question_number,
            "staging_id": str(uuid.uuid4()),
            "hash": uuid.uuid4().hex,
            "subject": subject,
            "opts": json.dumps(opts),
            "state": state,
        },
    )
    return question_id



async def _seed_reviewer_user(db_session) -> uuid.UUID:
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO identity.users (id, email, password_hash, status, email_verified, "
            "preferred_language, timezone, failed_login_attempts, version) "
            "VALUES (:id, :email, 'x', 'active', true, 'en', 'UTC', 0, 1)"
        ),
        {"id": user_id, "email": f"reviewer-{user_id}@example.com"},
    )
    return user_id


# ---------------------------------------------------------------------------
# Queue / counts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_queue_counts_reflect_live_classification(db_session):
    sf = await _seed_source_chain(db_session)
    await _seed_question(db_session, sf, question_number=1, raw_options={"A": "a", "B": "b", "C": "c", "D": "d"})
    await _seed_question(db_session, sf, question_number=2, raw_options={"A": "a", "B": "", "C": "c", "D": "d"})
    await db_session.commit()

    counts = await get_queue_counts(db_session)
    assert counts["eligible"] >= 1
    assert counts["structurally_invalid"] >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_queue_list_excludes_non_pending_and_non_official_source(db_session):
    sf = await _seed_source_chain(db_session)
    await _seed_question(db_session, sf, question_number=1)

    other_sf = await _seed_source_chain(db_session, source_key="SOME_OTHER_SOURCE")
    await _seed_question(db_session, other_sf, question_number=1)

    await _seed_question(db_session, sf, question_number=2, state="ANSWER_VERIFIED")
    await db_session.commit()

    result = await list_review_queue(
        db_session, ReviewQueueFilters(page=1, page_size=50)
    )
    staging_ids = {item["staging_id"] for item in result["items"]}
    assert len(staging_ids) == len(result["items"])  # no duplicates


@pytest.mark.asyncio(loop_scope="session")
async def test_queue_list_filters_by_subject(db_session):
    sf = await _seed_source_chain(db_session)
    await _seed_question(db_session, sf, question_number=1, subject="Chemistry")
    await _seed_question(db_session, sf, question_number=2, subject="Botany")
    await db_session.commit()

    result = await list_review_queue(
        db_session, ReviewQueueFilters(subject="Chemistry", page=1, page_size=50)
    )
    assert all(item["subject"] == "Chemistry" for item in result["items"])


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_save_review_persists_option_and_verifies_question(db_session):
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    reviewer_id = await _seed_reviewer_user(db_session)
    await db_session.commit()

    result = await save_answer_review(
        db_session,
        question_id=qid,
        reviewer_user_id=reviewer_id,
        asserted_option="b",
        evidence_source_type="OFFICIAL_ANSWER_KEY",
        evidence_locator="Key p.12",
        review_note="clear",
        expected_state="ANSWER_PENDING",
        source_consulted_confirmed=True,
    )
    assert result.status == "saved"
    assert result.question_state == "ANSWER_VERIFIED"

    row = (
        await db_session.execute(
            text(
                "SELECT asserted_option, verification_status, reviewer_user_id, evidence_source_type "
                "FROM pyq.answer_assertions WHERE question_id = :qid"
            ),
            {"qid": qid},
        )
    ).first()
    assert row.asserted_option == "B"
    assert row.verification_status == "VERIFIED"
    assert row.reviewer_user_id == reviewer_id
    assert row.evidence_source_type == "OFFICIAL_ANSWER_KEY"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_review_rejects_invalid_option(db_session):
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    await db_session.commit()

    with pytest.raises(Exception) as exc_info:
        await save_answer_review(
            db_session,
            question_id=qid,
            reviewer_user_id=uuid.uuid4(),
            asserted_option="E",
            evidence_source_type="OTHER",
            evidence_locator=None,
            review_note=None,
            expected_state="ANSWER_PENDING",
            source_consulted_confirmed=True,
        )
    assert "INVALID_OPTION" in str(exc_info.value) or exc_info.value.__class__.__name__ == "InvalidOptionError"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_review_rejected_when_source_not_confirmed(db_session):
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    await db_session.commit()

    with pytest.raises(SourceNotConsultedError):
        await save_answer_review(
            db_session, question_id=qid, reviewer_user_id=uuid.uuid4(), asserted_option="A",
            evidence_source_type="OFFICIAL_ANSWER_KEY", evidence_locator="p.1", review_note=None,
            expected_state="ANSWER_PENDING",
            source_consulted_confirmed=False,
        )

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM pyq.answer_assertions WHERE question_id = :qid"), {"qid": qid}
        )
    ).scalar_one()
    assert count == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_skip_review_persists_no_assertion_and_leaves_state_unchanged(db_session):
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    await db_session.commit()

    result = await skip_question_review(db_session, question_id=qid, reviewer_user_id=uuid.uuid4())
    assert result.status == "skipped"

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM pyq.answer_assertions WHERE question_id = :qid"), {"qid": qid}
        )
    ).scalar_one()
    assert count == 0

    state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :qid"), {"qid": qid})
    ).scalar_one()
    assert state == "ANSWER_PENDING"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_review_identical_retry_is_idempotent(db_session):
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    reviewer_id = await _seed_reviewer_user(db_session)
    await db_session.commit()

    await save_answer_review(
        db_session, question_id=qid, reviewer_user_id=reviewer_id, asserted_option="A",
        evidence_source_type="OTHER", evidence_locator=None, review_note=None,
        expected_state="ANSWER_PENDING",
        source_consulted_confirmed=True,
    )
    second = await save_answer_review(
        db_session, question_id=qid, reviewer_user_id=reviewer_id, asserted_option="A",
        evidence_source_type="OTHER", evidence_locator=None, review_note=None,
        expected_state="ANSWER_VERIFIED",
        source_consulted_confirmed=True,
    )
    assert second.status == "idempotent_noop"

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM pyq.answer_assertions WHERE question_id = :qid"), {"qid": qid}
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_second_reviewer_different_option_routes_to_conflict(db_session):
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    reviewer_1 = await _seed_reviewer_user(db_session)
    reviewer_2 = await _seed_reviewer_user(db_session)
    await db_session.commit()

    first = await save_answer_review(
        db_session, question_id=qid, reviewer_user_id=reviewer_1, asserted_option="A",
        evidence_source_type="OTHER", evidence_locator=None, review_note=None,
        expected_state="ANSWER_PENDING",
        source_consulted_confirmed=True,
    )
    assert first.question_state == "ANSWER_VERIFIED"

    second = await save_answer_review(
        db_session, question_id=qid, reviewer_user_id=reviewer_2, asserted_option="B",
        evidence_source_type="OTHER", evidence_locator=None, review_note=None,
        expected_state="ANSWER_VERIFIED",
        source_consulted_confirmed=True,
    )
    assert second.status == "conflict_recorded"
    assert second.question_state == "ANSWER_CONFLICT"

    statuses = (
        await db_session.execute(
            text("SELECT verification_status FROM pyq.answer_assertions WHERE question_id = :qid"), {"qid": qid}
        )
    ).scalars().all()
    assert set(statuses) == {"DISPUTED"}


@pytest.mark.asyncio(loop_scope="session")
async def test_stale_state_write_rejected(db_session):
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    await db_session.commit()

    with pytest.raises(StaleQuestionStateError):
        await save_answer_review(
            db_session, question_id=qid, reviewer_user_id=uuid.uuid4(), asserted_option="A",
            evidence_source_type="OTHER", evidence_locator=None, review_note=None,
            expected_state="ANSWER_VERIFIED",  # wrong — actual state is ANSWER_PENDING
            source_consulted_confirmed=True,
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_identical_retry_with_original_stale_expected_state_is_idempotent(db_session):
    """Regression for the idempotency-vs-staleness ordering bug: a client
    that retries with the ORIGINAL expected_state it saw before its own
    earlier save moved the question ANSWER_PENDING -> ANSWER_VERIFIED must
    get idempotent_noop, not a false-positive 409 StaleQuestionStateError,
    even though that expected_state is now stale relative to the question's
    current (post-save) state."""
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    reviewer_id = await _seed_reviewer_user(db_session)
    await db_session.commit()

    first = await save_answer_review(
        db_session, question_id=qid, reviewer_user_id=reviewer_id, asserted_option="A",
        evidence_source_type="OFFICIAL_ANSWER_KEY", evidence_locator="p.1", review_note=None,
        expected_state="ANSWER_PENDING",
        source_consulted_confirmed=True,
    )
    assert first.status == "saved"
    assert first.question_state == "ANSWER_VERIFIED"

    # Retry resends the ORIGINAL "ANSWER_PENDING" expected_state (the state
    # the client knew about before its own first call), not the question's
    # actual current state ("ANSWER_VERIFIED") -- this must still succeed
    # as a no-op, not raise StaleQuestionStateError.
    second = await save_answer_review(
        db_session, question_id=qid, reviewer_user_id=reviewer_id, asserted_option="A",
        evidence_source_type="OFFICIAL_ANSWER_KEY", evidence_locator="p.1", review_note=None,
        expected_state="ANSWER_PENDING",  # the ORIGINAL, now-stale state
        source_consulted_confirmed=True,
    )
    assert second.status == "idempotent_noop"
    assert second.question_state == "ANSWER_VERIFIED"

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM pyq.answer_assertions WHERE question_id = :qid"), {"qid": qid}
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_conflicting_retry_with_different_option_is_not_treated_as_idempotent(db_session):
    """A retry carrying the SAME reviewer but a DIFFERENT option must never
    be silently absorbed by the idempotency shortcut -- it has to fall
    through to ordinary handling (here: a plain state update, since no
    other reviewer is involved) using the request's own expected_state."""
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    reviewer_id = await _seed_reviewer_user(db_session)
    await db_session.commit()

    first = await save_answer_review(
        db_session, question_id=qid, reviewer_user_id=reviewer_id, asserted_option="A",
        evidence_source_type="OFFICIAL_ANSWER_KEY", evidence_locator="p.1", review_note=None,
        expected_state="ANSWER_PENDING",
        source_consulted_confirmed=True,
    )
    assert first.status == "saved"

    # Same reviewer, DIFFERENT option, correct up-to-date expected_state:
    # must not be reported idempotent_noop.
    second = await save_answer_review(
        db_session, question_id=qid, reviewer_user_id=reviewer_id, asserted_option="B",
        evidence_source_type="OFFICIAL_ANSWER_KEY", evidence_locator="p.1", review_note=None,
        expected_state="ANSWER_VERIFIED",
        source_consulted_confirmed=True,
    )
    assert second.status != "idempotent_noop"

    # Same reviewer, different option, but the STALE original expected_state
    # -- must be rejected as stale, not silently accepted as idempotent.
    with pytest.raises(StaleQuestionStateError):
        await save_answer_review(
            db_session, question_id=qid, reviewer_user_id=reviewer_id, asserted_option="C",
            evidence_source_type="OFFICIAL_ANSWER_KEY", evidence_locator="p.1", review_note=None,
            expected_state="ANSWER_PENDING",  # stale and this option was never asserted before
            source_consulted_confirmed=True,
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_genuinely_new_submission_with_stale_state_still_rejected(db_session):
    """A brand-new submission (never asserted before by this reviewer) must
    still be correctly rejected as stale when expected_state doesn't match
    -- the idempotency-first reordering must not weaken this path."""
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    reviewer_1 = await _seed_reviewer_user(db_session)
    reviewer_2 = await _seed_reviewer_user(db_session)
    await db_session.commit()

    first = await save_answer_review(
        db_session, question_id=qid, reviewer_user_id=reviewer_1, asserted_option="A",
        evidence_source_type="OFFICIAL_ANSWER_KEY", evidence_locator="p.1", review_note=None,
        expected_state="ANSWER_PENDING",
        source_consulted_confirmed=True,
    )
    assert first.question_state == "ANSWER_VERIFIED"

    # reviewer_2 has never asserted on this question before -- existing_own
    # is None, so the idempotency shortcut must not fire, and the stale
    # expected_state (still "ANSWER_PENDING") must be rejected.
    with pytest.raises(StaleQuestionStateError):
        await save_answer_review(
            db_session, question_id=qid, reviewer_user_id=reviewer_2, asserted_option="A",
            evidence_source_type="OFFICIAL_ANSWER_KEY", evidence_locator="p.1", review_note=None,
            expected_state="ANSWER_PENDING",  # stale
            source_consulted_confirmed=True,
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_ineligible_question_rejected(db_session):
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(
        db_session, sf, question_number=1, raw_options={"A": "a", "B": "", "C": "c", "D": "d"}
    )
    await db_session.commit()

    with pytest.raises(QuestionNotEligibleError):
        await save_answer_review(
            db_session, question_id=qid, reviewer_user_id=uuid.uuid4(), asserted_option="A",
            evidence_source_type="OTHER", evidence_locator=None, review_note=None,
            expected_state="ANSWER_PENDING",
            source_consulted_confirmed=True,
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_failed_write_leaves_no_partial_row(db_session):
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(
        db_session, sf, question_number=1, raw_options={"A": "a", "B": "", "C": "c", "D": "d"}
    )
    await db_session.commit()

    with pytest.raises(QuestionNotEligibleError):
        await save_answer_review(
            db_session, question_id=qid, reviewer_user_id=uuid.uuid4(), asserted_option="A",
            evidence_source_type="OTHER", evidence_locator=None, review_note=None,
            expected_state="ANSWER_PENDING",
            source_consulted_confirmed=True,
        )

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM pyq.answer_assertions WHERE question_id = :qid"), {"qid": qid}
        )
    ).scalar_one()
    assert count == 0


# ---------------------------------------------------------------------------
# HTTP / security (permission-gated endpoints, IDOR)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_queue_counts_requires_authentication(client):
    resp = await client.get("/api/v1/admin/pyq-answer-review/counts")
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_queue_counts_forbidden_for_student(client, db_session, register_user):
    await register_user(client, db_session=db_session)  # default STUDENT role
    resp = await client.get("/api/v1/admin/pyq-answer-review/counts")
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_queue_counts_allowed_for_admin(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    resp = await client.get("/api/v1/admin/pyq-answer-review/counts")
    assert resp.status_code == 200, resp.text
    assert "eligible" in resp.json()["data"]


@pytest.mark.asyncio(loop_scope="session")
async def test_question_detail_404_for_nonexistent_id(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    resp = await client.get(f"/api/v1/admin/pyq-answer-review/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_review_save_rejected_without_csrf_header(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    resp = await client.post(
        f"/api/v1/admin/pyq-answer-review/{uuid.uuid4()}/review",
        json={
            "asserted_option": "A",
            "evidence_source_type": "OTHER",
            "expected_state": "ANSWER_PENDING",
            "source_consulted_confirmed": True,
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_review_save_rejected_for_student_even_with_valid_payload(client, db_session, register_user):
    await register_user(client, db_session=db_session)  # STUDENT
    resp = await client.post(
        f"/api/v1/admin/pyq-answer-review/{uuid.uuid4()}/review",
        json={
            "asserted_option": "A",
            "evidence_source_type": "OTHER",
            "expected_state": "ANSWER_PENDING",
            "source_consulted_confirmed": True,
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio(loop_scope="session")
async def test_review_save_end_to_end_via_http_as_admin(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/admin/pyq-answer-review/{qid}/review",
        json={
            "asserted_option": "C",
            "evidence_source_type": "OFFICIAL_ANSWER_KEY",
            "evidence_locator": "Official key, Q1",
            "expected_state": "ANSWER_PENDING",
            "source_consulted_confirmed": True,
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "saved"
    assert resp.json()["data"]["question_state"] == "ANSWER_VERIFIED"


@pytest.mark.asyncio(loop_scope="session")
async def test_review_save_rejects_tampered_option_via_direct_api_call(client, db_session, register_user):
    """Direct API bypass of any frontend-level option restriction must still
    be rejected server-side."""
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/admin/pyq-answer-review/{qid}/review",
        json={
            "asserted_option": "Z",
            "evidence_source_type": "OTHER",
            "expected_state": "ANSWER_PENDING",
            "source_consulted_confirmed": True,
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_review_save_rejected_via_http_when_confirmation_missing(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/admin/pyq-answer-review/{qid}/review",
        json={
            "asserted_option": "A",
            "evidence_source_type": "OFFICIAL_ANSWER_KEY",
            "expected_state": "ANSWER_PENDING",
            # source_consulted_confirmed omitted
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_review_save_rejected_via_http_when_confirmation_false(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/admin/pyq-answer-review/{qid}/review",
        json={
            "asserted_option": "A",
            "evidence_source_type": "OFFICIAL_ANSWER_KEY",
            "expected_state": "ANSWER_PENDING",
            "source_consulted_confirmed": False,
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_skip_review_end_to_end_via_http(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    sf = await _seed_source_chain(db_session)
    qid = await _seed_question(db_session, sf, question_number=1)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/admin/pyq-answer-review/{qid}/skip",
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "skipped"

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM pyq.answer_assertions WHERE question_id = :qid"), {"qid": qid}
        )
    ).scalar_one()
    assert count == 0
