"""SEED_V1 practice isolation — allowlist membership, exclusions, FULL regression."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.modules.assessment.seed_v1_allowlist import (
    EXPECTED_ALLOWLIST_SHA256,
    allowlist_sha,
    seed_v1_allowlist_sha256,
    seed_v1_uuid_strings,
)
from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")

T6D_TAG = "physics-t6d-pilot-20260902"
T6F2_TAG = "physics-t6f1-pilot-20260902"
LEGACY_TAG = "legacy-physics-5000-import-20260902"


def _body(stem: str, correct: str = "A"):
    return publishable_question_body(
        stem=stem,
        options=[
            {"label": "A", "text": "One"},
            {"label": "B", "text": "Two"},
            {"label": "C", "text": "Three"},
            {"label": "D", "text": "Four"},
        ],
        explanation=f"Explanation for {stem}",
        correct_option=correct,
    )


async def _concept_id(db_session) -> uuid.UUID:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return result.scalar_one()


async def _insert_published(
    db_session,
    *,
    item_id: uuid.UUID,
    concept_id: uuid.UUID,
    stem: str,
    tags: list[str] | None = None,
    correct: str = "A",
) -> uuid.UUID:
    from datetime import UTC, datetime

    from app.modules.cms.models import ContentItem, ContentVersion

    body = _body(stem, correct=correct)
    item = ContentItem(
        id=item_id,
        content_type="QUESTION",
        concept_id=concept_id,
        title=stem[:80],
        slug=f"seed-iso-{item_id.hex[:12]}",
        tags=tags or [],
        language="en",
        status="PUBLISHED",
    )
    db_session.add(item)
    await db_session.flush()
    version = ContentVersion(
        content_item_id=item.id,
        version_no=1,
        body=body,
        change_summary="seed isolation fixture",
        workflow_state="PUBLISHED",
        authored_at=datetime.now(UTC),
    )
    db_session.add(version)
    await db_session.flush()
    item.latest_version_id = version.id
    item.current_version_id = version.id
    await db_session.commit()
    return item.id


async def test_seed_v1_allowlist_hash_and_membership():
    ids = seed_v1_uuid_strings()
    assert len(ids) == 30
    assert len(set(ids)) == 30
    assert allowlist_sha(ids) == EXPECTED_ALLOWLIST_SHA256
    assert seed_v1_allowlist_sha256() == EXPECTED_ALLOWLIST_SHA256
    for raw in ids:
        uuid.UUID(raw)


async def test_practice_unknown_scope_rejected(client, register_user):
    await register_user(client)
    resp = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "NOT_A_SCOPE", "question_count": 5},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "INVALID_SCOPE"


async def test_seed_v1_membership_excludes_protected_and_non_seed(client, db_session, register_user):
    await register_user(client)
    concept_id = await _concept_id(db_session)

    seed_a = uuid.uuid4()
    seed_b = uuid.uuid4()
    seed_c = uuid.uuid4()
    t6d = uuid.uuid4()
    t6f2 = uuid.uuid4()
    legacy = uuid.uuid4()
    other = uuid.uuid4()

    await _insert_published(db_session, item_id=seed_a, concept_id=concept_id, stem="Seed A?")
    await _insert_published(db_session, item_id=seed_b, concept_id=concept_id, stem="Seed B?", correct="B")
    await _insert_published(db_session, item_id=seed_c, concept_id=concept_id, stem="Seed C?", correct="C")
    await _insert_published(
        db_session, item_id=t6d, concept_id=concept_id, stem="T6D decoy?", tags=[T6D_TAG]
    )
    await _insert_published(
        db_session, item_id=t6f2, concept_id=concept_id, stem="T6F2 decoy?", tags=[T6F2_TAG]
    )
    await _insert_published(
        db_session, item_id=legacy, concept_id=concept_id, stem="Legacy decoy?", tags=[LEGACY_TAG]
    )
    await _insert_published(db_session, item_id=other, concept_id=concept_id, stem="Other published?")

    allow = [seed_a, seed_b, seed_c]
    # Repository imports seed_v1_uuids at call time from the allowlist module.
    with (
        patch("app.modules.assessment.seed_v1_allowlist.seed_v1_uuids", return_value=allow),
        patch(
            "app.modules.assessment.seed_v1_allowlist.seed_v1_allowlist_sha256",
            return_value=EXPECTED_ALLOWLIST_SHA256,
        ),
    ):
        gen = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "SEED_V1", "question_count": 30},
            headers=csrf_headers(client),
        )
    assert gen.status_code == 201, gen.text
    body = gen.json()
    assert body["data"]["scope_type"] == "SEED_V1"
    assert body["data"]["title"] == "Production Seed V1 practice"
    assert body["data"]["question_count"] == 3
    assert body["meta"]["available_count"] == 3
    assert body["meta"]["seed_v1_allowlist_sha256"] == EXPECTED_ALLOWLIST_SHA256

    start = await client.post(
        f"/api/v1/assessments/{body['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    assert start.status_code == 201, start.text
    attempt_id = start.json()["data"]["id"]

    detail = await client.get(f"/api/v1/attempts/{attempt_id}")
    assert detail.status_code == 200
    questions = detail.json()["data"]["questions"]
    presented = {q["content_item_id"] for q in questions}
    assert presented == {str(seed_a), str(seed_b), str(seed_c)}
    assert str(t6d) not in presented
    assert str(t6f2) not in presented
    assert str(legacy) not in presented
    assert str(other) not in presented

    # Pre-submit: no explanation leak
    assert all(q.get("explanation") in (None, "") and q.get("correct_option") is None for q in questions)

    # Answer one correct, one incorrect
    ans_ok = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        headers=csrf_headers(client),
        json={"content_item_id": str(seed_a), "selected_option": "A"},
    )
    assert ans_ok.status_code == 200
    ans_bad = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        headers=csrf_headers(client),
        json={"content_item_id": str(seed_b), "selected_option": "A"},  # correct is B
    )
    assert ans_bad.status_code == 200
    ans_c = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        headers=csrf_headers(client),
        json={"content_item_id": str(seed_c), "selected_option": "C"},
    )
    assert ans_c.status_code == 200

    submitted = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()["data"]
    assert result["status"] == "SUBMITTED"
    assert result["correct_count"] == 2
    assert result["incorrect_count"] == 1

    review = await client.get(f"/api/v1/attempts/{attempt_id}")
    rq = review.json()["data"]["questions"]
    assert all(q.get("explanation") for q in rq)
    assert all(q.get("correct_option") for q in rq)
    # Next-question order: three distinct IDs preserved
    assert len({q["content_item_id"] for q in rq}) == 3


async def test_full_scope_still_broader_than_seed(client, db_session, register_user):
    """FULL must remain able to draw outside a Seed-sized allowlist."""
    await register_user(client)
    concept_id = await _concept_id(db_session)
    seed_only = uuid.uuid4()
    outsider = uuid.uuid4()
    await _insert_published(db_session, item_id=seed_only, concept_id=concept_id, stem="Seed-ish FULL?")
    await _insert_published(db_session, item_id=outsider, concept_id=concept_id, stem="Outside FULL?")

    allow = [seed_only]
    with patch("app.modules.assessment.seed_v1_allowlist.seed_v1_uuids", return_value=allow), patch(
        "app.modules.assessment.seed_v1_allowlist.seed_v1_allowlist_sha256",
        return_value=EXPECTED_ALLOWLIST_SHA256,
    ):
        seed_gen = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "SEED_V1", "question_count": 30},
            headers=csrf_headers(client),
        )
        full_gen = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "FULL", "question_count": 90},
            headers=csrf_headers(client),
        )

    assert seed_gen.status_code == 201, seed_gen.text
    assert full_gen.status_code == 201, full_gen.text
    assert seed_gen.json()["data"]["scope_type"] == "SEED_V1"
    assert full_gen.json()["data"]["scope_type"] == "FULL"
    assert full_gen.json()["meta"]["available_count"] >= seed_gen.json()["meta"]["available_count"]
    assert full_gen.json()["data"]["question_count"] >= seed_gen.json()["data"]["question_count"]

    # Seed session cannot include outsider
    seed_attempt = await client.post(
        f"/api/v1/assessments/{seed_gen.json()['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    seed_qs = (await client.get(f"/api/v1/attempts/{seed_attempt.json()['data']['id']}")).json()["data"]["questions"]
    assert {q["content_item_id"] for q in seed_qs} == {str(seed_only)}

    full_attempt = await client.post(
        f"/api/v1/assessments/{full_gen.json()['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    full_qs = (await client.get(f"/api/v1/attempts/{full_attempt.json()['data']['id']}")).json()["data"]["questions"]
    full_ids = {q["content_item_id"] for q in full_qs}
    # FULL pool is broader; with question_count=90 it may or may not include outsider,
    # but available_count for FULL must exceed Seed's 1 when both seed_only and outsider exist.
    assert full_gen.json()["meta"]["available_count"] > 1
    assert str(seed_only) in full_ids or str(outsider) in full_ids or len(full_ids) > 0
