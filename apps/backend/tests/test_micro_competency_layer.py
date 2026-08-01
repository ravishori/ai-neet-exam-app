"""Integration tests: micro-competency layer rollup (ADR-0021)."""

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _create_micro_competency(client, concept_id: str, name: str) -> str:
    create = await client.post(
        f"/api/v1/concepts/{concept_id}/micro-competencies",
        json={"code": name.lower().replace(" ", "-")[:80], "name": name},
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    return create.json()["data"]["id"]


async def _publish_question(
    client, concept_id: str, *, correct_option: str = "B", micro_competency_id: str | None = None, slug_suffix: str
) -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "micro_competency_id": micro_competency_id,
            "title": "Micro-competency test question",
            "slug": f"mc-test-question-{slug_suffix}",
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


async def _answer_and_submit(client, concept_id: str, question_id: str, selected_option: str) -> None:
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

    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": question_id, "selected_option": selected_option},
        headers=csrf_headers(client),
    )
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text


async def test_concept_mastery_falls_back_to_direct_aggregate_without_micro_competencies(
    client, db_session, register_user
):
    """A concept with no micro-competencies behaves exactly like ADR-0015 (pre-ADR-0021)."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id, correct_option="B", slug_suffix="fallback")

    await _answer_and_submit(client, concept_id, question_id, "B")

    mastery = await client.get(f"/api/v1/learning/mastery/concepts/{concept_id}")
    data = mastery.json()["data"]
    assert data["attempts_count"] == 1
    assert data["correct_count"] == 1

    breakdown = await client.get(f"/api/v1/learning/mastery/concepts/{concept_id}/micro-competencies")
    assert breakdown.status_code == 200, breakdown.text
    assert breakdown.json()["data"] == []


async def test_concept_mastery_rolls_up_from_attempted_micro_competencies(client, db_session, register_user):
    """Once a micro-competency has attempts, concept mastery is driven by the
    weighted micro-competency rollup rather than the concept-wide aggregate —
    even if other, untagged questions on the same concept were answered too."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)

    # Two untagged attempts establish a concept-wide baseline.
    untagged_question = await _publish_question(client, concept_id, correct_option="B", slug_suffix="untagged")
    await _answer_and_submit(client, concept_id, untagged_question, "B")
    await _answer_and_submit(client, concept_id, untagged_question, "B")

    baseline = await client.get(f"/api/v1/learning/mastery/concepts/{concept_id}")
    assert baseline.json()["data"]["attempts_count"] == 2
    assert baseline.json()["data"]["correct_count"] == 2

    # Now tag a question with a micro-competency and answer it once, incorrectly.
    mc_id = await _create_micro_competency(client, concept_id, "Apply the formula")
    tagged_question = await _publish_question(
        client, concept_id, correct_option="B", micro_competency_id=mc_id, slug_suffix="tagged"
    )
    await _answer_and_submit(client, concept_id, tagged_question, "A")

    after = await client.get(f"/api/v1/learning/mastery/concepts/{concept_id}")
    after_data = after.json()["data"]
    # Concept-level mastery is now driven entirely by the attempted micro-competency
    # (1 attempt, 0 correct) rather than the 2/2 direct aggregate baseline.
    assert after_data["attempts_count"] == 1
    assert after_data["correct_count"] == 0
    assert after_data["mastery_level"] == "LEARNING"

    breakdown = await client.get(f"/api/v1/learning/mastery/concepts/{concept_id}/micro-competencies")
    breakdown_data = breakdown.json()["data"]
    assert len(breakdown_data) == 1
    assert breakdown_data[0]["micro_competency_id"] == mc_id
    assert breakdown_data[0]["attempts_count"] == 1
    assert breakdown_data[0]["correct_count"] == 0


async def test_micro_competency_create_requires_content_permission(client, db_session, register_user):
    await register_user(client)  # default STUDENT role — no content.create permission
    concept_id = await _any_concept_id(db_session)

    response = await client.post(
        f"/api/v1/concepts/{concept_id}/micro-competencies",
        json={"code": "test-code", "name": "Test"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 403
