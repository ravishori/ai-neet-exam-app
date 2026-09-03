"""SEED_V2 practice isolation — exact allowlist, count cap, exclusions, V1 regression."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.modules.assessment.schemas.assessment import GenerateRequest
from app.modules.assessment.seed_v1_allowlist import (
    EXPECTED_ALLOWLIST_SHA256 as V1_SHA,
)
from app.modules.assessment.seed_v1_allowlist import seed_v1_uuid_strings
from app.modules.assessment.seed_v2_allowlist import (
    ALLOWLIST_COUNT,
    EXPECTED_ALLOWLIST_SHA256,
    allowlist_sha,
    seed_v2_allowlist_sha256,
    seed_v2_uuid_strings,
)
from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")

T6D_TAG = "physics-t6d-pilot-20260902"
T6F2_TAG = "physics-t6f1-pilot-20260902"
LEGACY_TAG = "legacy-physics-5000-import-20260902"
VISUAL_SUPERSEDED = "seed-v2-rematerialization-superseded-20260903"
NUM_SUPERSEDED = "seed-v2-numerical-remediation-superseded-20260904"

V1_EXPECTED_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"
V2_EXPECTED_SHA = "a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978"


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


async def _insert_question(
    db_session,
    *,
    item_id: uuid.UUID,
    concept_id: uuid.UUID,
    stem: str,
    tags: list[str] | None = None,
    correct: str = "A",
    status: str = "PUBLISHED",
) -> uuid.UUID:
    from app.modules.cms.models import ContentItem, ContentVersion

    body = _body(stem, correct=correct)
    item = ContentItem(
        id=item_id,
        content_type="QUESTION",
        concept_id=concept_id,
        title=stem[:80],
        slug=f"seed-v2-iso-{item_id.hex[:12]}",
        tags=tags or [],
        language="en",
        status=status,
    )
    db_session.add(item)
    await db_session.flush()
    version = ContentVersion(
        content_item_id=item.id,
        version_no=1,
        body=body,
        change_summary="seed v2 isolation fixture",
        workflow_state=status,
        authored_at=datetime.now(UTC),
    )
    db_session.add(version)
    await db_session.flush()
    item.latest_version_id = version.id
    item.current_version_id = version.id
    await db_session.commit()
    return item.id


def _v2_patches(allow: list[uuid.UUID]):
    return (
        patch("app.modules.assessment.seed_v2_allowlist.seed_v2_uuids", return_value=allow),
        patch(
            "app.modules.assessment.seed_v2_allowlist.seed_v2_allowlist_sha256",
            return_value=EXPECTED_ALLOWLIST_SHA256,
        ),
    )


async def test_seed_v2_allowlist_hash_membership_and_subjects():
    ids = seed_v2_uuid_strings()
    assert len(ids) == ALLOWLIST_COUNT == 100
    assert len(set(ids)) == 100
    assert allowlist_sha(ids) == EXPECTED_ALLOWLIST_SHA256 == V2_EXPECTED_SHA
    assert seed_v2_allowlist_sha256() == V2_EXPECTED_SHA
    for raw in ids:
        uuid.UUID(raw)

    auth_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "audits"
        / "TALOS_PRODUCTION_SEED_V2_PUBLICATION_AUTHORIZATION_20260904.json"
    )
    data = json.loads(auth_path.read_text(encoding="utf-8"))
    assert data["exact_allowlist"] == ids
    assert data["allowlist_sha256"] == V2_EXPECTED_SHA
    assert data["subject_distribution"] == {"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15}


async def test_seed_v1_allowlist_unchanged_by_v2_module():
    v1 = seed_v1_uuid_strings()
    assert len(v1) == 30
    assert V1_SHA == V1_EXPECTED_SHA
    assert set(v1).isdisjoint(set(seed_v2_uuid_strings()))


async def test_question_count_bounds_isolated_to_seed_v2():
    GenerateRequest(scope_type="FULL", question_count=90)
    GenerateRequest(scope_type="SEED_V1", question_count=90)
    GenerateRequest(scope_type="SEED_V2", question_count=90)
    GenerateRequest(scope_type="SEED_V2", question_count=91)
    GenerateRequest(scope_type="SEED_V2", question_count=100)
    with pytest.raises(ValidationError):
        GenerateRequest(scope_type="FULL", question_count=91)
    with pytest.raises(ValidationError):
        GenerateRequest(scope_type="SEED_V1", question_count=91)
    with pytest.raises(ValidationError):
        GenerateRequest(scope_type="FULL", question_count=100)
    with pytest.raises(ValidationError):
        GenerateRequest(scope_type="SEED_V2", question_count=101)
    with pytest.raises(ValidationError):
        GenerateRequest(scope_type="FULL", question_count=101)
    with pytest.raises(ValidationError):
        GenerateRequest(scope_type="SEED_V2", question_count=0)


async def test_http_question_count_90_100_101(client, db_session, register_user):
    await register_user(client)
    concept_id = await _concept_id(db_session)
    seed = uuid.uuid4()
    await _insert_question(db_session, item_id=seed, concept_id=concept_id, stem="V2 count?")
    allow = [seed]
    p0, p1 = _v2_patches(allow)
    with p0, p1:
        ok90_full = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "FULL", "question_count": 90},
            headers=csrf_headers(client),
        )
        bad91_full = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "FULL", "question_count": 91},
            headers=csrf_headers(client),
        )
        ok91_v2 = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "SEED_V2", "question_count": 91},
            headers=csrf_headers(client),
        )
        ok100_v2 = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "SEED_V2", "question_count": 100},
            headers=csrf_headers(client),
        )
        bad101_v2 = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "SEED_V2", "question_count": 101},
            headers=csrf_headers(client),
        )
        full_through_v2_count = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "FULL", "question_count": 100},
            headers=csrf_headers(client),
        )
    assert ok90_full.status_code == 201, ok90_full.text
    assert bad91_full.status_code == 422
    assert ok91_v2.status_code == 201, ok91_v2.text
    assert ok91_v2.json()["data"]["scope_type"] == "SEED_V2"
    assert ok100_v2.status_code == 201, ok100_v2.text
    assert ok100_v2.json()["meta"]["requested_count"] == 100
    assert bad101_v2.status_code == 422
    assert full_through_v2_count.status_code == 422


async def test_seed_v2_session_firewall_and_student_flow(client, db_session, register_user):
    await register_user(client)
    concept_id = await _concept_id(db_session)

    seed_a = uuid.uuid4()
    seed_b = uuid.uuid4()
    seed_c = uuid.uuid4()
    v1_id = uuid.uuid4()
    t6d = uuid.uuid4()
    t6f2 = uuid.uuid4()
    legacy = uuid.uuid4()
    other_pub = uuid.uuid4()
    superseded_hist = uuid.uuid4()
    draft_id = uuid.uuid4()
    approved_id = uuid.uuid4()
    ghost = uuid.uuid4()

    await _insert_question(db_session, item_id=seed_a, concept_id=concept_id, stem="V2 A?")
    await _insert_question(db_session, item_id=seed_b, concept_id=concept_id, stem="V2 B?", correct="B")
    await _insert_question(db_session, item_id=seed_c, concept_id=concept_id, stem="V2 C?", correct="C")
    await _insert_question(db_session, item_id=v1_id, concept_id=concept_id, stem="V1 decoy?")
    await _insert_question(db_session, item_id=t6d, concept_id=concept_id, stem="T6D decoy?", tags=[T6D_TAG])
    await _insert_question(db_session, item_id=t6f2, concept_id=concept_id, stem="T6F2 decoy?", tags=[T6F2_TAG])
    await _insert_question(db_session, item_id=legacy, concept_id=concept_id, stem="Legacy decoy?", tags=[LEGACY_TAG])
    await _insert_question(db_session, item_id=other_pub, concept_id=concept_id, stem="Arbitrary published?")
    await _insert_question(
        db_session,
        item_id=superseded_hist,
        concept_id=concept_id,
        stem="Superseded historical?",
        tags=[VISUAL_SUPERSEDED, NUM_SUPERSEDED],
    )
    await _insert_question(db_session, item_id=draft_id, concept_id=concept_id, stem="V2 draft?", status="DRAFT")
    await _insert_question(
        db_session, item_id=approved_id, concept_id=concept_id, stem="V2 approved?", status="APPROVED"
    )

    allow = [seed_a, seed_b, seed_c, superseded_hist, draft_id, approved_id, ghost]
    p0, p1 = _v2_patches(allow)
    with p0, p1:
        gen = await client.post(
            "/api/v1/assessments/practice",
            json={
                "scope_type": "SEED_V2",
                "question_count": 100,
                "question_ids": [str(other_pub), str(v1_id)],
                "exact_allowlist": [str(other_pub)],
                "allowlist": [str(t6d)],
                "seed_v2_allowlist_sha256": "0" * 64,
                "scope_id": str(concept_id),
            },
            headers=csrf_headers(client),
        )
    assert gen.status_code == 201, gen.text
    body = gen.json()
    assert body["data"]["scope_type"] == "SEED_V2"
    assert body["data"]["title"] == "Production Seed V2 practice"
    assert body["data"]["question_count"] == 3
    assert body["meta"]["available_count"] == 3
    assert body["meta"]["requested_count"] == 100
    assert body["meta"]["seed_v2_allowlist_sha256"] == EXPECTED_ALLOWLIST_SHA256
    assert body["meta"]["seed_v2_allowlist_count"] == 100

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
    forbidden = {
        str(v1_id),
        str(t6d),
        str(t6f2),
        str(legacy),
        str(other_pub),
        str(superseded_hist),
        str(draft_id),
        str(approved_id),
        str(ghost),
    }
    assert presented.isdisjoint(forbidden)
    assert all(q.get("explanation") in (None, "") and q.get("correct_option") is None for q in questions)

    ans_ok = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        headers=csrf_headers(client),
        json={"content_item_id": str(seed_a), "selected_option": "A"},
    )
    assert ans_ok.status_code == 200
    dup_answer = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        headers=csrf_headers(client),
        json={"content_item_id": str(seed_a), "selected_option": "A"},
    )
    assert dup_answer.status_code == 200
    ans_bad = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        headers=csrf_headers(client),
        json={"content_item_id": str(seed_b), "selected_option": "A"},
    )
    assert ans_bad.status_code == 200
    ans_c = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        headers=csrf_headers(client),
        json={"content_item_id": str(seed_c), "selected_option": "C"},
    )
    assert ans_c.status_code == 200

    progress = await client.get(f"/api/v1/attempts/{attempt_id}")
    assert progress.status_code == 200
    assert progress.json()["data"]["status"] == "IN_PROGRESS"
    answered = [q for q in progress.json()["data"]["questions"] if q.get("selected_option")]
    assert len(answered) == 3

    submitted = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()["data"]
    assert result["status"] == "SUBMITTED"
    assert result["correct_count"] == 2
    assert result["incorrect_count"] == 1
    assert result["score"] is not None

    dup_submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert dup_submit.status_code in (400, 409)

    review = await client.get(f"/api/v1/attempts/{attempt_id}")
    rq = review.json()["data"]["questions"]
    assert all(q.get("explanation") for q in rq)
    assert all(q.get("correct_option") for q in rq)
    assert len({q["content_item_id"] for q in rq}) == 3

    restart = await client.post(
        f"/api/v1/assessments/{body['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    assert restart.status_code == 201, restart.text
    restart_id = restart.json()["data"]["id"]
    assert restart_id != attempt_id
    restart_detail = await client.get(f"/api/v1/attempts/{restart_id}")
    assert restart_detail.json()["data"]["status"] == "IN_PROGRESS"
    assert all(
        q.get("explanation") in (None, "") and q.get("correct_option") is None
        for q in restart_detail.json()["data"]["questions"]
    )


async def test_forged_client_scope_does_not_become_seed_v2(client, db_session, register_user):
    await register_user(client)
    concept_id = await _concept_id(db_session)
    outsider = uuid.uuid4()
    seed = uuid.uuid4()
    await _insert_question(db_session, item_id=outsider, concept_id=concept_id, stem="FULL outsider?")
    await _insert_question(db_session, item_id=seed, concept_id=concept_id, stem="V2 only?")
    allow = [seed]
    p0, p1 = _v2_patches(allow)
    with p0, p1:
        forged_scope = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "SEED_V1", "question_count": 30, "scope_type_override": "SEED_V2"},
            headers=csrf_headers(client),
        )
        full_same_endpoint = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "FULL", "question_count": 30},
            headers=csrf_headers(client),
        )
        unknown = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "SEED_V2 ", "question_count": 10},
            headers=csrf_headers(client),
        )
        v2 = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "SEED_V2", "question_count": 100},
            headers=csrf_headers(client),
        )
    assert full_same_endpoint.status_code == 201
    assert full_same_endpoint.json()["data"]["scope_type"] == "FULL"
    assert full_same_endpoint.json()["meta"].get("seed_v2_allowlist_sha256") is None
    assert unknown.status_code == 400
    assert v2.status_code == 201
    assert v2.json()["data"]["scope_type"] == "SEED_V2"
    v2_start = await client.post(
        f"/api/v1/assessments/{v2.json()['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    v2_qs = (await client.get(f"/api/v1/attempts/{v2_start.json()['data']['id']}")).json()["data"]["questions"]
    assert {q["content_item_id"] for q in v2_qs} == {str(seed)}
    assert str(outsider) not in {q["content_item_id"] for q in v2_qs}
    # SEED_V1 on the shared endpoint is not SEED_V2 (may 201 or 422 depending on V1 pool).
    assert forged_scope.status_code in (201, 422)
    if forged_scope.status_code == 201:
        assert forged_scope.json()["data"]["scope_type"] == "SEED_V1"
        assert forged_scope.json()["data"]["title"] == "Production Seed V1 practice"


async def test_v1_practice_regression_hero_full_and_seed_v1(client, db_session, register_user):
    await register_user(client)
    concept_id = await _concept_id(db_session)
    seed_v1 = uuid.uuid4()
    outsider = uuid.uuid4()
    await _insert_question(db_session, item_id=seed_v1, concept_id=concept_id, stem="V1 iso?")
    await _insert_question(db_session, item_id=outsider, concept_id=concept_id, stem="Outside V1?")
    allow = [seed_v1]
    with (
        patch("app.modules.assessment.seed_v1_allowlist.seed_v1_uuids", return_value=allow),
        patch(
            "app.modules.assessment.seed_v1_allowlist.seed_v1_allowlist_sha256",
            return_value=V1_EXPECTED_SHA,
        ),
    ):
        seed_gen = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "SEED_V1", "question_count": 30},
            headers=csrf_headers(client),
        )
        full_gen = await client.post(
            "/api/v1/assessments/practice",
            json={"scope_type": "FULL", "question_count": 30},
            headers=csrf_headers(client),
        )
    assert seed_gen.status_code == 201, seed_gen.text
    assert full_gen.status_code == 201, full_gen.text
    assert seed_gen.json()["data"]["scope_type"] == "SEED_V1"
    assert seed_gen.json()["data"]["title"] == "Production Seed V1 practice"
    assert seed_gen.json()["meta"]["seed_v1_allowlist_sha256"] == V1_EXPECTED_SHA
    assert seed_gen.json()["meta"]["seed_v1_allowlist_count"] == 30
    assert full_gen.json()["data"]["scope_type"] == "FULL"
    assert "seed_v2_allowlist_sha256" not in (full_gen.json().get("meta") or {})
    seed_attempt = await client.post(
        f"/api/v1/assessments/{seed_gen.json()['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    seed_qs = (await client.get(f"/api/v1/attempts/{seed_attempt.json()['data']['id']}")).json()["data"]["questions"]
    assert {q["content_item_id"] for q in seed_qs} == {str(seed_v1)}
    assert str(outsider) not in {q["content_item_id"] for q in seed_qs}
