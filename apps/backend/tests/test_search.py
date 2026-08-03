"""Integration tests: question search (PR 3) — PostgreSQL FTS primary,
pg_trgm typo-tolerant fallback, reindex-on-publish."""

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _concept_with_lineage(db_session) -> dict:
    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    result = await db_session.execute(
        select(Concept.id, Concept.topic_id, Topic.chapter_id, Chapter.subject_id, Chapter.name, Topic.name, Subject.name)
        .join(Topic, Topic.id == Concept.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .limit(1)
    )
    row = result.one()
    return {
        "concept_id": str(row[0]),
        "topic_id": str(row[1]),
        "chapter_id": str(row[2]),
        "subject_id": str(row[3]),
        "chapter_name": row[4],
        "topic_name": row[5],
        "subject_name": row[6],
    }


async def _publish_question(
    client,
    concept_id: str,
    *,
    stem: str,
    options: list[dict] | None = None,
    explanation: str = "A generic explanation.",
    difficulty: str = "medium",
    pyq_year: int | None = None,
    correct_option: str = "B",
) -> str:
    body = {
        "stem": stem,
        "options": options
        or [
            {"label": "A", "text": "Wrong 1"},
            {"label": "B", "text": "Correct answer"},
            {"label": "C", "text": "Wrong 2"},
            {"label": "D", "text": "Wrong 3"},
        ],
        "correct_option": correct_option,
        "explanation": explanation,
        "difficulty": difficulty,
    }
    if pyq_year:
        body["pyq_year"] = pyq_year

    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": stem[:50],
            "slug": f"search-test-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": body,
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


async def _create_draft_question(client, concept_id: str, *, stem: str) -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": stem[:50],
            "slug": f"search-test-draft-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": {
                "stem": stem,
                "options": [{"label": "A", "text": "x"}, {"label": "B", "text": "y"}],
                "correct_option": "A",
                "explanation": "n/a",
            },
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    return create.json()["data"]["id"]


async def test_search_requires_authentication(client):
    resp = await client.get("/api/v1/cms/search", params={"q": "anything"})
    assert resp.status_code == 401


async def test_search_exact_match_finds_reindexed_question_immediately_after_publish(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    unique = f"zenithoscopy{uuid.uuid4().hex[:6]}"
    item_id = await _publish_question(client, lineage["concept_id"], stem=f"What organ does {unique} examine?")

    # No manual reindex call anywhere in this test — publish() must have
    # triggered SearchRepository.reindex_item() on its own.
    resp = await client.get("/api/v1/cms/search", params={"q": unique})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["search_mode"] == "fulltext"
    ids = [r["id"] for r in body["data"]]
    assert item_id in ids
    matched = body["data"][ids.index(item_id)]
    assert matched["rank"] > 0
    assert "stem" in matched["matched_fields"]
    assert any(seg["highlighted"] for seg in matched["snippet"])
    assert unique in "".join(seg["text"] for seg in matched["snippet"])


async def test_search_multi_word_query_uses_and_semantics(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:6]
    both_id = await _publish_question(client, lineage["concept_id"], stem=f"Krebs{tag} cycle occurs in the mitochondrial matrix")
    only_one_id = await _publish_question(client, lineage["concept_id"], stem=f"The Krebs{tag} cycle is a metabolic pathway")

    resp = await client.get("/api/v1/cms/search", params={"q": f"Krebs{tag} mitochondrial"})
    assert resp.status_code == 200, resp.text
    ids = [r["id"] for r in resp.json()["data"]]
    assert both_id in ids
    assert only_one_id not in ids  # doesn't contain "mitochondrial" -> AND query excludes it


async def test_search_ranks_stem_match_above_explanation_only_match(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:6]
    stem_match_id = await _publish_question(client, lineage["concept_id"], stem=f"Explain glyoxysome{tag} function in seeds")
    explanation_match_id = await _publish_question(
        client, lineage["concept_id"], stem=f"Unrelated stem {tag}", explanation=f"This relates to glyoxysome{tag} biology."
    )

    resp = await client.get("/api/v1/cms/search", params={"q": f"glyoxysome{tag}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    ids = [r["id"] for r in data]
    assert stem_match_id in ids and explanation_match_id in ids
    assert ids.index(stem_match_id) < ids.index(explanation_match_id)  # weight A (stem) ranks above weight C (explanation)
    stem_row = data[ids.index(stem_match_id)]
    explanation_row = data[ids.index(explanation_match_id)]
    assert stem_row["rank"] > explanation_row["rank"]
    assert "stem" in stem_row["matched_fields"]
    assert "explanation" in explanation_row["matched_fields"]
    assert "correct_option" not in explanation_row and "explanation" not in explanation_row  # never leaked verbatim


async def test_search_filters_by_subject_chapter_topic(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:6]
    item_id = await _publish_question(client, lineage["concept_id"], stem=f"Scope filter probe {tag}")

    for key, param in [("subject_id", "subject_id"), ("chapter_id", "chapter_id"), ("topic_id", "topic_id")]:
        resp = await client.get("/api/v1/cms/search", params={"q": tag, param: lineage[key]})
        assert resp.status_code == 200, resp.text
        ids = [r["id"] for r in resp.json()["data"]]
        assert item_id in ids, f"expected match under {param}"

    other_subject_resp = await client.get("/api/v1/cms/search", params={"q": tag, "subject_id": str(uuid.uuid4())})
    assert other_subject_resp.status_code == 200
    assert item_id not in [r["id"] for r in other_subject_resp.json()["data"]]


async def test_search_filters_by_difficulty_and_pyq_year(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:6]
    hard_id = await _publish_question(client, lineage["concept_id"], stem=f"Difficulty probe {tag}", difficulty="hard", pyq_year=2022)
    easy_id = await _publish_question(client, lineage["concept_id"], stem=f"Difficulty probe {tag}", difficulty="easy")

    hard_resp = await client.get("/api/v1/cms/search", params={"q": tag, "difficulty": "hard"})
    hard_ids = [r["id"] for r in hard_resp.json()["data"]]
    assert hard_id in hard_ids and easy_id not in hard_ids

    year_resp = await client.get("/api/v1/cms/search", params={"q": tag, "pyq_year": 2022})
    year_ids = [r["id"] for r in year_resp.json()["data"]]
    assert hard_id in year_ids and easy_id not in year_ids


async def test_search_pagination(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:6]
    ids = [await _publish_question(client, lineage["concept_id"], stem=f"Pagination probe {tag} number {i}") for i in range(3)]

    page1 = await client.get("/api/v1/cms/search", params={"q": tag, "limit": 2, "offset": 0})
    assert page1.status_code == 200, page1.text
    body1 = page1.json()
    assert len(body1["data"]) == 2
    assert body1["meta"]["total"] >= 3

    page2 = await client.get("/api/v1/cms/search", params={"q": tag, "limit": 2, "offset": 2})
    seen = {r["id"] for r in page1.json()["data"]} | {r["id"] for r in page2.json()["data"]}
    assert all(i in seen for i in ids)


async def test_search_typo_falls_back_to_fuzzy_match(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    item_id = await _publish_question(client, lineage["concept_id"], stem="Mitochondria are the powerhouse of the cell")

    # "mitocondria" (missing an 'h') never appears verbatim anywhere in the
    # index, so tier 1 (FTS) must return nothing before tier 2 fires.
    resp = await client.get("/api/v1/cms/search", params={"q": "mitocondria"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["search_mode"] == "fuzzy"
    assert item_id in [r["id"] for r in body["data"]]


async def test_search_no_match_returns_empty_not_an_error(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get("/api/v1/cms/search", params={"q": f"nonexistentgibberish{uuid.uuid4().hex}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == []
    assert resp.json()["meta"]["search_mode"] == "empty"


async def test_search_only_returns_published_questions(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    tag = uuid.uuid4().hex[:6]
    draft_id = await _create_draft_question(client, lineage["concept_id"], stem=f"Draft probe {tag}")

    resp = await client.get("/api/v1/cms/search", params={"q": tag})
    assert resp.status_code == 200, resp.text
    assert draft_id not in [r["id"] for r in resp.json()["data"]]
