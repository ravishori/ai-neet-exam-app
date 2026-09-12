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


async def _set_certification(db_session, item_id: str, status: str) -> None:
    from sqlalchemy.orm.attributes import flag_modified

    from app.modules.cms.models import ContentItem, ContentVersion

    item = await db_session.get(ContentItem, uuid.UUID(item_id))
    assert item is not None and item.current_version_id is not None
    ver = await db_session.get(ContentVersion, item.current_version_id)
    assert ver is not None
    body = dict(ver.body or {})
    body["certification_status"] = status
    body["certification_reason"] = f"test:{status}"
    ver.body = body
    flag_modified(ver, "body")
    tags = [t for t in (item.tags or []) if not str(t).startswith("audit:")]
    tags.append(f"audit:{status}")
    item.tags = tags
    flag_modified(item, "tags")
    if status == "REJECTED":
        item.status = "ARCHIVED"
    await db_session.commit()


async def test_publication_gate_excludes_rejected_flashcards(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:8]
    ok_id = await _publish_flashcard(client, lineage["concept_id"], front=f"Gate OK {tag}")
    rejected_id = await _publish_flashcard(client, lineage["concept_id"], front=f"Gate REJECT {tag}")
    await _set_certification(db_session, rejected_id, "REJECTED")

    resp = await client.get(
        "/api/v1/cms/flashcards",
        params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "limit": 100},
    )
    assert resp.status_code == 200, resp.text
    ids = [f["id"] for f in resp.json()["data"]]
    assert ok_id in ids
    assert rejected_id not in ids
    assert resp.json()["meta"]["publication_gate"]["rejects_excluded"] is True


async def test_certified_only_returns_verified_cards(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:8]
    verified_id = await _publish_flashcard(client, lineage["concept_id"], front=f"Certified {tag}")
    review_id = await _publish_flashcard(client, lineage["concept_id"], front=f"Review {tag}")
    await _set_certification(db_session, verified_id, "VERIFIED")
    await _set_certification(db_session, review_id, "REVIEW")

    all_resp = await client.get(
        "/api/v1/cms/flashcards",
        params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "limit": 100},
    )
    all_ids = {f["id"] for f in all_resp.json()["data"]}
    assert verified_id in all_ids
    assert review_id in all_ids

    cert_resp = await client.get(
        "/api/v1/cms/flashcards",
        params={
            "scope_type": "CONCEPT",
            "scope_id": lineage["concept_id"],
            "certified_only": True,
            "limit": 100,
        },
    )
    assert cert_resp.status_code == 200, cert_resp.text
    cert_ids = {f["id"] for f in cert_resp.json()["data"]}
    assert verified_id in cert_ids
    assert review_id not in cert_ids
    card = next(f for f in cert_resp.json()["data"] if f["id"] == verified_id)
    assert card["certification_status"] == "VERIFIED"
    review_card = next(f for f in all_resp.json()["data"] if f["id"] == review_id)
    assert review_card["certification_status"] == "REVIEW"
    assert review_card["certification_status"] != "VERIFIED"


async def test_review_cards_expose_non_certified_status(client, db_session, register_user):
    """Regression: REVIEW must never be labelled as certified in API payload."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:8]
    review_id = await _publish_flashcard(client, lineage["concept_id"], front=f"Label check {tag}")
    await _set_certification(db_session, review_id, "REVIEW")

    resp = await client.get(
        "/api/v1/cms/flashcards",
        params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "limit": 100},
    )
    assert resp.status_code == 200
    card = next(f for f in resp.json()["data"] if f["id"] == review_id)
    assert card["certification_status"] == "REVIEW"
