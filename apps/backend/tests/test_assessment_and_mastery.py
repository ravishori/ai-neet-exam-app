"""Integration tests: assessment scoring + mastery recompute (ADR-0013/0015/0020)."""

import pytest
from sqlalchemy import select

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _publish_question(client, concept_id: str, *, correct_option: str = "B") -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Scoring test question",
            "slug": f"scoring-test-question-{concept_id[:8]}",
            "language": "en",
            "body": publishable_question_body(stem="2 + 2 = ?", correct_option=correct_option, explanation="Basic arithmetic.", options=[
                    {"label": "A", "text": "3"},
                    {"label": "B", "text": "4"},
                    {"label": "C", "text": "5"},
                    {"label": "D", "text": "22"},
                ],),
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


async def test_practice_attempt_scores_correct_answer(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id, correct_option="B")

    generate = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": concept_id},
        headers=csrf_headers(client),
    )
    assert generate.status_code == 201, generate.text
    assessment_id = generate.json()["data"]["id"]

    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    assert start.status_code == 201, start.text
    attempt_id = start.json()["data"]["id"]

    answer = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": question_id, "selected_option": "B"},
        headers=csrf_headers(client),
    )
    assert answer.status_code == 200, answer.text

    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text
    result = submit.json()["data"]
    assert result["correct_count"] == 1
    assert result["incorrect_count"] == 0
    assert result["score"] == 1.0


async def test_practice_attempt_scores_incorrect_answer_with_no_penalty(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id, correct_option="B")

    generate = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": concept_id},
        headers=csrf_headers(client),
    )
    assessment_id = generate.json()["data"]["id"]
    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    attempt_id = start.json()["data"]["id"]

    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": question_id, "selected_option": "A"},
        headers=csrf_headers(client),
    )
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    result = submit.json()["data"]
    assert result["correct_count"] == 0
    assert result["incorrect_count"] == 1
    assert result["score"] == 0.0  # PRACTICE has no negative marking


async def _publish_pending_answer_question(db_session, concept_id: str) -> str:
    """Inserts a PUBLISHED QUESTION content_item with no correct_option in
    its body — the same shape the real PYQ-promotion path writes (raw
    INSERT, bypassing the CMS create/publish API's QuestionBody schema,
    which requires correct_option: str and would reject this). This is
    the only way to construct this state: the validated API path cannot
    produce a QUESTION with a missing answer at all."""
    import uuid as _uuid
    from datetime import UTC, datetime

    from app.modules.cms.models import ContentItem, ContentVersion

    item_id = _uuid.uuid4()
    version_id = _uuid.uuid4()
    body = {
        "stem": "A PYQ with no verified answer yet: 2 + 2 = ?",
        "options": [
            {"label": "A", "text": "3"},
            {"label": "B", "text": "4"},
            {"label": "C", "text": "5"},
            {"label": "D", "text": "22"},
        ],
        "correct_option": None,
        "answer_status": "ANSWER_PENDING",
        "explanation": None,
    }
    db_session.add(
        ContentItem(
            id=item_id, content_type="QUESTION", concept_id=concept_id, title="Pending PYQ",
            slug=f"pending-pyq-{str(item_id)[:8]}", tags=["PYQ"], language="en", status="PUBLISHED",
            current_version_id=None, latest_version_id=None, version=1,
        )
    )
    await db_session.flush()
    db_session.add(
        ContentVersion(
            id=version_id, content_item_id=item_id, version_no=1, body=body,
            workflow_state="PUBLISHED", authored_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    item = await db_session.get(ContentItem, item_id)
    item.current_version_id = version_id
    item.latest_version_id = version_id
    await db_session.commit()
    return str(item_id)


async def test_practice_attempt_with_pending_answer_scores_neutrally(client, db_session, register_user):
    """A question with no verified correct_option (e.g. an ANSWER_PENDING
    PYQ, represented the same way — correct_option missing/empty in the
    published body) must never be counted correct or incorrect, and must
    never attract negative marking — it is genuinely unknown, not wrong."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_pending_answer_question(db_session, concept_id)

    generate = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": concept_id},
        headers=csrf_headers(client),
    )
    assessment_id = generate.json()["data"]["id"]
    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    attempt_id = start.json()["data"]["id"]

    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": question_id, "selected_option": "A"},
        headers=csrf_headers(client),
    )
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text
    result = submit.json()["data"]
    assert result["correct_count"] == 0
    assert result["incorrect_count"] == 0
    assert result["score"] == 0.0  # no positive, no negative marking

    history = await client.get(f"/api/v1/questions/{question_id}/history")
    entries = history.json()["data"]
    assert len(entries) == 1
    assert entries[0]["is_correct"] is None


async def test_mastery_recomputes_after_attempt_submission(client, db_session, register_user):
    """Regression coverage for the recompute-on-submit flow built in Sprint 6."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id, correct_option="B")

    before = await client.get(f"/api/v1/learning/mastery/concepts/{concept_id}")
    assert before.json()["data"]["mastery_level"] == "NOT_STARTED"

    generate = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": concept_id},
        headers=csrf_headers(client),
    )
    assessment_id = generate.json()["data"]["id"]
    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    attempt_id = start.json()["data"]["id"]
    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": question_id, "selected_option": "B"},
        headers=csrf_headers(client),
    )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))

    after = await client.get(f"/api/v1/learning/mastery/concepts/{concept_id}")
    after_data = after.json()["data"]
    assert after_data["mastery_level"] == "LEARNING"  # below the 3-attempt floor
    assert after_data["attempts_count"] == 1
    assert after_data["correct_count"] == 1
    assert after_data["mastery_score"] == 100
