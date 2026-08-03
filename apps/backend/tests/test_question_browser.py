"""Integration tests: student-facing question browser (PR 2, questions.read permission)."""

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _concept_with_lineage(db_session) -> dict:
    """A real concept plus its topic/chapter/subject ids, for scope filter tests."""
    from app.modules.academic.models import Chapter, Concept, Topic

    result = await db_session.execute(
        select(Concept.id, Concept.topic_id, Topic.chapter_id, Chapter.subject_id)
        .join(Topic, Topic.id == Concept.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .limit(1)
    )
    row = result.one()
    return {
        "concept_id": str(row.id),
        "topic_id": str(row.topic_id),
        "chapter_id": str(row.chapter_id),
        "subject_id": str(row.subject_id),
    }


async def _publish_question(client, concept_id: str, *, stem: str = "2 + 2 = ?", correct_option: str = "B") -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": stem,
            "slug": f"browser-test-{concept_id[:8]}-{uuid.uuid4().hex[:8]}",
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


async def _create_draft_question(client, concept_id: str) -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Unpublished draft question",
            "slug": f"browser-test-draft-{concept_id[:8]}",
            "language": "en",
            "body": {
                "stem": "Never see me in the browser",
                "options": [{"label": "A", "text": "x"}, {"label": "B", "text": "y"}],
                "correct_option": "A",
                "explanation": "n/a",
            },
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    return create.json()["data"]["id"]


async def test_browse_requires_authentication(client):
    # Every seeded role (including the self-registration default, STUDENT)
    # already carries questions.read, so the only real boundary to test here
    # is "logged out" — require_permission short-circuits through
    # get_current_user, which 401s with no session at all.
    resp = await client.get("/api/v1/cms/questions")
    assert resp.status_code == 401


async def test_browse_only_returns_published_questions(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    published_id = await _publish_question(client, lineage["concept_id"])
    draft_id = await _create_draft_question(client, lineage["concept_id"])

    resp = await client.get("/api/v1/cms/questions", params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"]})
    assert resp.status_code == 200, resp.text
    ids = [q["id"] for q in resp.json()["data"]]
    assert published_id in ids
    assert draft_id not in ids


async def test_browse_redacts_correct_option_and_explanation(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    await _publish_question(client, lineage["concept_id"])

    resp = await client.get("/api/v1/cms/questions", params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"]})
    assert resp.status_code == 200, resp.text
    for question in resp.json()["data"]:
        assert "correct_option" not in question
        assert "explanation" not in question
        assert question["stem"]
        assert question["options"]


async def test_get_question_detail_redacts_answer_and_404s_for_draft(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    published_id = await _publish_question(client, lineage["concept_id"])
    draft_id = await _create_draft_question(client, lineage["concept_id"])

    ok = await client.get(f"/api/v1/cms/questions/{published_id}")
    assert ok.status_code == 200, ok.text
    assert "correct_option" not in ok.json()["data"]

    missing = await client.get(f"/api/v1/cms/questions/{draft_id}")
    assert missing.status_code == 404


async def test_browse_scope_filtering_by_subject_chapter_topic_concept(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    question_id = await _publish_question(client, lineage["concept_id"], stem="Scope filter probe")

    for scope_type, key in [("CONCEPT", "concept_id"), ("TOPIC", "topic_id"), ("CHAPTER", "chapter_id"), ("SUBJECT", "subject_id")]:
        resp = await client.get("/api/v1/cms/questions", params={"scope_type": scope_type, "scope_id": lineage[key]})
        assert resp.status_code == 200, resp.text
        ids = [q["id"] for q in resp.json()["data"]]
        assert question_id in ids, f"expected question visible under scope_type={scope_type}"
        assert resp.json()["data"][ids.index(question_id)]["subject"]["id"] == lineage["subject_id"]


async def test_browse_pagination(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    ids = [
        await _publish_question(client, lineage["concept_id"], stem=f"Pagination probe {i}", correct_option="A")
        for i in range(3)
    ]

    page1 = await client.get(
        "/api/v1/cms/questions", params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "limit": 2, "offset": 0}
    )
    assert page1.status_code == 200, page1.text
    body1 = page1.json()
    assert len(body1["data"]) == 2
    assert body1["meta"]["total"] >= 3

    page2 = await client.get(
        "/api/v1/cms/questions", params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "limit": 2, "offset": 2}
    )
    assert page2.status_code == 200, page2.text
    seen_ids = {q["id"] for q in page1.json()["data"]} | {q["id"] for q in page2.json()["data"]}
    assert all(i in seen_ids for i in ids)
