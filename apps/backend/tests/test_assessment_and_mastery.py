"""Integration tests: assessment scoring + mastery recompute (ADR-0013/0015/0020)."""

import pytest
from sqlalchemy import select

from conftest import csrf_headers

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
            "body": {
                "stem": "2 + 2 = ?",
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
