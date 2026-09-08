"""Integration tests: student-facing question browser (PR 2, questions.read permission)."""

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers
try:
    # Phase 2 tests need publication_gates evidence when the WIP publish
    # pipeline is loaded; the helper adds it in one place. Import is soft
    # so the file still parses if the helper is absent at a given HEAD.
    from helpers_publishable_question import publishable_question_body  # noqa: F401
except ImportError:  # pragma: no cover
    publishable_question_body = None  # type: ignore[assignment]

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


async def _publish_question(
    client,
    concept_id: str,
    *,
    stem: str = "2 + 2 = ?",
    correct_option: str = "B",
    tags: list[str] | None = None,
) -> str:
    default_options = [
        {"label": "A", "text": "3"},
        {"label": "B", "text": "4"},
        {"label": "C", "text": "5"},
        {"label": "D", "text": "22"},
    ]
    if publishable_question_body is not None:
        # WIP publication gates require NCERT-evidence/provenance/numerical_evidence
        # blocks — the shared helper builds them so this test file stays a
        # single call site rather than repeating the schema.
        body = publishable_question_body(
            stem=stem,
            correct_option=correct_option,
            explanation="Basic arithmetic.",
            options=default_options,
        )
    else:
        body = {
            "stem": stem,
            "options": default_options,
            "correct_option": correct_option,
            "explanation": "Basic arithmetic.",
            "difficulty": "easy",
        }
    payload = {
        "content_type": "QUESTION",
        "concept_id": concept_id,
        "title": stem,
        "slug": f"browser-test-{concept_id[:8]}-{uuid.uuid4().hex[:8]}",
        "language": "en",
        "body": body,
    }
    if tags:
        payload["tags"] = tags
    create = await client.post("/api/v1/cms/content-items", json=payload, headers=csrf_headers(client))
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]

    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{item_id}/review", json={"decision": "approve"}, headers=csrf_headers(client)
    )
    await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    return item_id


async def _create_draft_question(client, concept_id: str) -> str:
    if publishable_question_body is not None:
        body = publishable_question_body(
            stem="Never see me in the browser",
            correct_option="A",
            explanation="Draft — must never surface in browse view.",
        )
    else:
        body = {
            "stem": "Never see me in the browser",
            "options": [{"label": "A", "text": "x"}, {"label": "B", "text": "y"}],
            "correct_option": "A",
            "explanation": "n/a",
        }
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Unpublished draft question",
            "slug": f"browser-test-draft-{concept_id[:8]}",
            "language": "en",
            "body": body,
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


# ---------------------------------------------------------------------------
# Phase 2 — Question Bank filters (class_level + provenance surfacing)
# ---------------------------------------------------------------------------


async def test_class_level_filter_returns_only_matching_class(client, db_session, register_user):
    """class_level=11 must return only questions tagged class:11; class_level=12 only class:12."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    q11 = await _publish_question(client, lineage["concept_id"], stem="Class 11 probe", tags=["class:11"])
    q12 = await _publish_question(client, lineage["concept_id"], stem="Class 12 probe", tags=["class:12"])
    qnone = await _publish_question(client, lineage["concept_id"], stem="No class tag probe")

    r11 = await client.get(
        "/api/v1/cms/questions",
        params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "class_level": "11"},
    )
    assert r11.status_code == 200, r11.text
    ids11 = [q["id"] for q in r11.json()["data"]]
    assert q11 in ids11
    assert q12 not in ids11
    assert qnone not in ids11
    assert all(q["class_level"] == "11" for q in r11.json()["data"] if q["id"] in {q11})

    r12 = await client.get(
        "/api/v1/cms/questions",
        params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "class_level": "12"},
    )
    assert r12.status_code == 200, r12.text
    ids12 = [q["id"] for q in r12.json()["data"]]
    assert q12 in ids12
    assert q11 not in ids12
    assert qnone not in ids12


async def test_class_level_rejects_invalid_value(client, db_session, register_user):
    """Only '11' or '12' are honoured; anything else must be a 400 with a clear code."""
    await register_user(client)  # default role_codes=["STUDENT"] via registration
    resp = await client.get("/api/v1/cms/questions", params={"class_level": "13"})
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "INVALID_CLASS_LEVEL"


async def test_combined_filters_subject_class_return_intersection(client, db_session, register_user):
    """Subject + class must AND together — subject-only vs subject+class differ."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    q11 = await _publish_question(client, lineage["concept_id"], stem="Combined 11", tags=["class:11"])
    q12 = await _publish_question(client, lineage["concept_id"], stem="Combined 12", tags=["class:12"])

    subject_only = await client.get(
        "/api/v1/cms/questions",
        params={"scope_type": "SUBJECT", "scope_id": lineage["subject_id"], "limit": 100},
    )
    subject_11 = await client.get(
        "/api/v1/cms/questions",
        params={"scope_type": "SUBJECT", "scope_id": lineage["subject_id"], "class_level": "11", "limit": 100},
    )
    assert subject_only.status_code == 200 and subject_11.status_code == 200
    all_ids = {q["id"] for q in subject_only.json()["data"]}
    c11_ids = {q["id"] for q in subject_11.json()["data"]}
    assert q11 in all_ids and q12 in all_ids
    assert q11 in c11_ids
    assert q12 not in c11_ids


async def test_combined_filters_subject_class_chapter_topic_all_apply(client, db_session, register_user):
    """SUBJECT + CLASS + CHAPTER + TOPIC scope collapses correctly — the deepest scope wins on the client
    but the class filter must still narrow the result set on top of scope."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    q11 = await _publish_question(client, lineage["concept_id"], stem="Deep 11", tags=["class:11"])
    q12 = await _publish_question(client, lineage["concept_id"], stem="Deep 12", tags=["class:12"])

    # TOPIC scope + class:11 → must include q11 only
    r = await client.get(
        "/api/v1/cms/questions",
        params={"scope_type": "TOPIC", "scope_id": lineage["topic_id"], "class_level": "11"},
    )
    assert r.status_code == 200, r.text
    ids = [q["id"] for q in r.json()["data"]]
    assert q11 in ids
    assert q12 not in ids


async def test_empty_result_valid_combination_returns_empty_envelope(client, db_session, register_user):
    """A syntactically valid filter combination that matches zero rows returns success:true, data:[], total:0.
    (Never a 404 or 500.)"""
    await register_user(client)  # default role_codes=["STUDENT"] via registration
    resp = await client.get(
        "/api/v1/cms/questions",
        params={"scope_type": "CONCEPT", "scope_id": str(uuid.uuid4()), "class_level": "11"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["meta"]["total"] == 0


async def test_provenance_block_returns_stored_data_never_fabricates(client, db_session, register_user):
    """The provenance block must project ONLY fields already stored — no invented source/verification claims.
    A vanilla project-authored question must land under source=PROJECT_AUTHORED with all AI fields null."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    qid = await _publish_question(
        client,
        lineage["concept_id"],
        stem="Provenance probe",
        tags=["class:11", "ncert_level:SECTION_VERIFIED", "ncert:NCERT XI Physics Ch 1 §1.2"],
    )

    resp = await client.get(f"/api/v1/cms/questions/{qid}")
    assert resp.status_code == 200, resp.text
    q = resp.json()["data"]
    # class_level is derived only from the tag we stored — nothing else
    assert q["class_level"] == "11"
    prov = q["provenance"]
    assert prov["ncert_verification_level"] == "SECTION_VERIFIED"
    assert prov["ncert_reference_tag"] == "NCERT XI Physics Ch 1 §1.2"
    # Not AI-generated in this test, so these must be null (never a placeholder)
    assert prov["model_used"] is None
    assert prov["prompt_version"] is None
    assert prov["confidence_score"] is None
    # authored_at exists on every version — must be an ISO string, not fabricated
    assert prov["authored_at"] is not None and "T" in prov["authored_at"]
    assert prov["source"] == "PROJECT_AUTHORED"


async def test_browse_response_does_not_leak_answer_key_with_class_filter(
    client, db_session, register_user
):
    """Adding class_level must not open a hole in the pre-existing answer-redaction contract."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    lineage = await _concept_with_lineage(db_session)
    await _publish_question(client, lineage["concept_id"], stem="Redact probe", tags=["class:11"])

    resp = await client.get(
        "/api/v1/cms/questions",
        params={"scope_type": "CONCEPT", "scope_id": lineage["concept_id"], "class_level": "11"},
    )
    assert resp.status_code == 200, resp.text
    for question in resp.json()["data"]:
        assert "correct_option" not in question
        assert "explanation" not in question
        # And the provenance block must never surface internal-only fields
        prov = question.get("provenance", {})
        for forbidden in ("password", "secret", "api_key", "internal_prompt"):
            assert forbidden not in prov
