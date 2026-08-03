"""Integration tests: Question Solving Experience (PR 11).

Covers the new attempt-answer fields (confidence, marked_for_review,
time_spent_seconds), cross-attempt question history, bookmarks, notes,
content reports, related questions, and the academic-metadata/NCERT-reference
enrichment on the in-progress and submitted question views.
"""

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _publish_question(client, concept_id: str, *, correct_option: str = "B", stem: str = "2 + 2 = ?") -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "PR11 test question",
            "slug": f"pr11-test-question-{concept_id[:8]}-{correct_option}-{abs(hash(stem)) % 100000}",
            "language": "en",
            "body": {
                "stem": stem,
                "options": [
                    {"label": "A", "text": "3"},
                    {"label": "B", "text": "4"},
                    {"label": "C", "text": "5"},
                    {"label": "D", "text": "22"},
                ],
                "correct_option": correct_option,
                "explanation": "Basic arithmetic.",
                "difficulty": "easy",
            },
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]

    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{item_id}/review", json={"decision": "approve"}, headers=csrf_headers(client)
    )
    await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    return item_id


async def _start_attempt(client, concept_id: str) -> tuple[str, str]:
    generate = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": concept_id},
        headers=csrf_headers(client),
    )
    assert generate.status_code == 201, generate.text
    assessment_id = generate.json()["data"]["id"]
    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    assert start.status_code == 201, start.text
    return assessment_id, start.json()["data"]["id"]


async def test_answer_records_confidence_review_flag_and_time_spent(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)
    _, attempt_id = await _start_attempt(client, concept_id)

    answer = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={
            "content_item_id": question_id,
            "selected_option": "B",
            "confidence": "medium",
            "marked_for_review": True,
            "time_spent_seconds": 42,
        },
        headers=csrf_headers(client),
    )
    assert answer.status_code == 200, answer.text

    in_progress = await client.get(f"/api/v1/attempts/{attempt_id}")
    q = in_progress.json()["data"]["questions"][0]
    assert q["confidence"] == "medium"
    assert q["marked_for_review"] is True
    assert q["question_type"] == "MCQ"

    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text

    result = await client.get(f"/api/v1/attempts/{attempt_id}")
    q = result.json()["data"]["questions"][0]
    assert q["time_spent_seconds"] == 42
    assert q["is_correct"] is True
    assert q["confidence"] == "medium"
    assert q["marked_for_review"] is True


async def test_answer_accumulates_time_spent_across_saves(client, db_session, register_user):
    """A question can be revisited across several short viewings before the
    attempt is submitted — time_spent_seconds should accumulate, not
    overwrite, so the total reflects the whole solving experience."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)
    _, attempt_id = await _start_attempt(client, concept_id)

    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": question_id, "selected_option": "B", "time_spent_seconds": 20},
        headers=csrf_headers(client),
    )
    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": question_id, "selected_option": "B", "time_spent_seconds": 15},
        headers=csrf_headers(client),
    )

    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text

    result = await client.get(f"/api/v1/attempts/{attempt_id}")
    q = result.json()["data"]["questions"][0]
    assert q["time_spent_seconds"] == 35


async def test_question_history_returns_only_submitted_attempts(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id, correct_option="B")

    # First submitted attempt — correct.
    _, attempt_1 = await _start_attempt(client, concept_id)
    await client.post(
        f"/api/v1/attempts/{attempt_1}/answers",
        json={"content_item_id": question_id, "selected_option": "B"},
        headers=csrf_headers(client),
    )
    await client.post(f"/api/v1/attempts/{attempt_1}/submit", headers=csrf_headers(client))

    # Second attempt, still in progress — must not appear in history yet.
    _, attempt_2 = await _start_attempt(client, concept_id)
    await client.post(
        f"/api/v1/attempts/{attempt_2}/answers",
        json={"content_item_id": question_id, "selected_option": "A"},
        headers=csrf_headers(client),
    )

    history = await client.get(f"/api/v1/questions/{question_id}/history")
    assert history.status_code == 200, history.text
    entries = history.json()["data"]
    assert len(entries) == 1
    assert entries[0]["attempt_id"] == attempt_1
    assert entries[0]["is_correct"] is True

    await client.post(f"/api/v1/attempts/{attempt_2}/submit", headers=csrf_headers(client))
    history_after = await client.get(f"/api/v1/questions/{question_id}/history")
    assert len(history_after.json()["data"]) == 2


async def test_bookmark_toggle_is_idempotent_flip(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)

    first = await client.post(f"/api/v1/learning/questions/{question_id}/bookmark/toggle", headers=csrf_headers(client))
    assert first.status_code == 200, first.text
    assert first.json()["data"]["bookmarked"] is True

    second = await client.post(f"/api/v1/learning/questions/{question_id}/bookmark/toggle", headers=csrf_headers(client))
    assert second.json()["data"]["bookmarked"] is False

    # Bookmark state surfaces on the attempt question payload too.
    _, attempt_id = await _start_attempt(client, concept_id)
    await client.post(f"/api/v1/learning/questions/{question_id}/bookmark/toggle", headers=csrf_headers(client))
    attempt = await client.get(f"/api/v1/attempts/{attempt_id}")
    assert attempt.json()["data"]["questions"][0]["bookmarked"] is True


async def test_note_upsert_get_and_delete(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)

    empty = await client.get(f"/api/v1/learning/questions/{question_id}/note")
    assert empty.json()["data"]["note_text"] is None

    upsert = await client.put(
        f"/api/v1/learning/questions/{question_id}/note", json={"note_text": "Remember the formula"}, headers=csrf_headers(client)
    )
    assert upsert.status_code == 200, upsert.text
    assert upsert.json()["data"]["note_text"] == "Remember the formula"

    replace = await client.put(
        f"/api/v1/learning/questions/{question_id}/note", json={"note_text": "Updated note"}, headers=csrf_headers(client)
    )
    assert replace.json()["data"]["note_text"] == "Updated note"

    fetched = await client.get(f"/api/v1/learning/questions/{question_id}/note")
    assert fetched.json()["data"]["note_text"] == "Updated note"

    deleted = await client.delete(f"/api/v1/learning/questions/{question_id}/note", headers=csrf_headers(client))
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["note_text"] is None

    after_delete = await client.get(f"/api/v1/learning/questions/{question_id}/note")
    assert after_delete.json()["data"]["note_text"] is None


async def test_report_question_valid_reason_persists_row(client, db_session, register_user):
    from app.modules.cms.models import ContentReport

    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)

    report = await client.post(
        f"/api/v1/cms/questions/{question_id}/report",
        json={"reason": "UNCLEAR", "comment": "Ambiguous wording"},
        headers=csrf_headers(client),
    )
    assert report.status_code == 201, report.text
    assert report.json()["data"]["reported"] is True

    import uuid as uuid_module

    result = await db_session.execute(
        select(ContentReport).where(ContentReport.content_item_id == uuid_module.UUID(question_id))
    )
    row = result.scalar_one()
    assert row.reason == "UNCLEAR"
    assert row.status == "OPEN"


async def test_report_question_rejects_unknown_reason(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)

    report = await client.post(
        f"/api/v1/cms/questions/{question_id}/report", json={"reason": "NONSENSE"}, headers=csrf_headers(client)
    )
    assert report.status_code == 400
    assert report.json()["errors"][0]["code"] == "INVALID_REASON"


async def test_related_questions_scoped_to_concept_and_excludes_self(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id, stem="Question one")
    sibling_id = await _publish_question(client, concept_id, stem="Question two")

    related = await client.get(f"/api/v1/cms/questions/{question_id}/related")
    assert related.status_code == 200, related.text
    related_ids = [q["id"] for q in related.json()["data"]]
    assert sibling_id in related_ids
    assert question_id not in related_ids


async def test_question_payload_includes_academic_metadata_and_ncert_reference(client, db_session, register_user):
    from app.modules.academic.models import Concept

    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)

    concept = await db_session.get(Concept, __import__("uuid").UUID(concept_id))
    concept.ncert_reference = "NCERT Class 12, Chapter 3"
    await db_session.commit()

    question_id = await _publish_question(client, concept_id)
    detail = await client.get(f"/api/v1/cms/questions/{question_id}")
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["ncert_reference"] == "NCERT Class 12, Chapter 3"
    assert data["question_type"] == "MCQ"
    assert data["concept"]["id"] == concept_id
