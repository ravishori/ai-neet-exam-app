"""Integration tests: student-facing flashcard browser (PR 10).

Mirrors test_question_browser.py's structure — same scope-filtering,
pagination, and published-only conventions, minus answer redaction
(flashcards carry no answer to protect)."""

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _concept_with_lineage(db_session) -> dict:
    from app.modules.academic.models import Chapter, Concept, Topic

    result = await db_session.execute(
        select(Concept.id, Concept.topic_id, Topic.chapter_id, Chapter.subject_id)
        .join(Topic, Topic.id == Concept.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .limit(1)
    )
    row = result.one()
    return {
        "concept_id": str(row[0]),
        "topic_id": str(row[1]),
        "chapter_id": str(row[2]),
        "subject_id": str(row[3]),
    }


async def _publish_flashcard(client, concept_id: str, *, front: str = "What is Ohm's Law?") -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "FLASHCARD",
            "concept_id": concept_id,
            "title": front[:50],
            "slug": f"flashcard-test-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": {"front": front, "back": "V = IR"},
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


async def _create_draft_flashcard(client, concept_id: str) -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "FLASHCARD",
            "concept_id": concept_id,
            "title": "Draft flashcard",
            "slug": f"flashcard-draft-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": {"front": "Never see me", "back": "n/a"},
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    return create.json()["data"]["id"]


async def test_browse_flashcards_requires_authentication(client):
    resp = await client.get("/api/v1/cms/flashcards")
    assert resp.status_code == 401


async def test_browse_only_returns_published_flashcards(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    published_id = await _publish_flashcard(client, lineage["concept_id"])
    draft_id = await _create_draft_flashcard(client, lineage["concept_id"])

    resp = await client.get("/api/v1/cms/flashcards", params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"]})
    assert resp.status_code == 200, resp.text
    ids = [f["id"] for f in resp.json()["data"]]
    assert published_id in ids
    assert draft_id not in ids


async def test_browse_flashcards_returns_front_and_back(client, db_session, register_user):
    # Unlike questions, flashcards have no answer to redact — front/back
    # both belong in a plain browse response.
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    await _publish_flashcard(client, lineage["concept_id"], front="What is Ohm's Law?")

    resp = await client.get("/api/v1/cms/flashcards", params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"]})
    assert resp.status_code == 200, resp.text
    card = next(f for f in resp.json()["data"] if f["front"] == "What is Ohm's Law?")
    assert card["back"] == "V = IR"
    assert card["subject"]["id"] == lineage["subject_id"]


async def test_browse_flashcards_scope_filtering(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:8]
    flashcard_id = await _publish_flashcard(client, lineage["concept_id"], front=f"Scope probe {tag}")

    for scope_type, key in [("CONCEPT", "concept_id"), ("TOPIC", "topic_id"), ("CHAPTER", "chapter_id"), ("SUBJECT", "subject_id")]:
        resp = await client.get("/api/v1/cms/flashcards", params={"scope_type": scope_type, "scope_id": lineage[key]})
        assert resp.status_code == 200, resp.text
        ids = [f["id"] for f in resp.json()["data"]]
        assert flashcard_id in ids, f"expected flashcard visible under scope_type={scope_type}"

    other_subject_resp = await client.get("/api/v1/cms/flashcards", params={"scope_type": "SUBJECT", "scope_id": str(uuid.uuid4())})
    assert flashcard_id not in [f["id"] for f in other_subject_resp.json()["data"]]


async def test_browse_flashcards_pagination(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:8]
    ids = [await _publish_flashcard(client, lineage["concept_id"], front=f"Pagination probe {tag} {i}") for i in range(3)]

    page1 = await client.get(
        "/api/v1/cms/flashcards", params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "limit": 2, "offset": 0}
    )
    assert page1.status_code == 200, page1.text
    assert len(page1.json()["data"]) == 2
    assert page1.json()["meta"]["total"] >= 3

    page2 = await client.get(
        "/api/v1/cms/flashcards", params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "limit": 2, "offset": 2}
    )
    seen = {f["id"] for f in page1.json()["data"]} | {f["id"] for f in page2.json()["data"]}
    assert all(i in seen for i in ids)
