"""Task C persistence tests — student STRONG/NEUTRAL/WEAK preferences."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.learning.models import StudentScopePreference
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _one_of_each(db_session):
    row = (
        await db_session.execute(
            select(Subject.id, Topic.id, Concept.id)
            .join(Chapter, Chapter.subject_id == Subject.id)
            .join(Topic, Topic.chapter_id == Chapter.id)
            .join(Concept, Concept.topic_id == Topic.id)
            .limit(1)
        )
    ).first()
    assert row is not None, "seeded academic hierarchy is missing"
    return str(row[0]), str(row[1]), str(row[2])


async def test_upsert_creates_then_updates_single_row(client, db_session, register_user):
    await register_user(client, db_session=db_session)
    subj_id, _t, _c = await _one_of_each(db_session)

    r1 = await client.put(
        "/api/v1/preferences",
        json={"scope_type": "SUBJECT", "scope_id": subj_id, "preference": "WEAK"},
        headers=csrf_headers(client),
    )
    assert r1.status_code == 200, r1.text
    first_id = r1.json()["data"]["id"]

    r2 = await client.put(
        "/api/v1/preferences",
        json={"scope_type": "SUBJECT", "scope_id": subj_id, "preference": "STRONG"},
        headers=csrf_headers(client),
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["id"] == first_id
    assert r2.json()["data"]["preference"] == "STRONG"

    # Exactly one row survives — the unique constraint enforces this.
    count = (
        await db_session.execute(
            select(func.count(StudentScopePreference.id))
            .where(StudentScopePreference.scope_id == uuid.UUID(subj_id))
        )
    ).scalar_one()
    assert count == 1


async def test_list_returns_only_current_users_rows(client, db_session, register_user):
    await register_user(client, db_session=db_session)
    subj_id, topic_id, concept_id = await _one_of_each(db_session)
    for scope, sid, pref in [
        ("SUBJECT", subj_id, "WEAK"),
        ("TOPIC", topic_id, "NEUTRAL"),
        ("CONCEPT", concept_id, "STRONG"),
    ]:
        r = await client.put(
            "/api/v1/preferences",
            json={"scope_type": scope, "scope_id": sid, "preference": pref},
            headers=csrf_headers(client),
        )
        assert r.status_code == 200, r.text
    resp = await client.get("/api/v1/preferences")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert {i["scope_type"] for i in items} == {"SUBJECT", "TOPIC", "CONCEPT"}
    assert {i["preference"] for i in items} == {"WEAK", "NEUTRAL", "STRONG"}


async def test_reset_one_and_reset_all(client, db_session, register_user):
    await register_user(client, db_session=db_session)
    subj_id, topic_id, _c = await _one_of_each(db_session)
    for scope, sid in [("SUBJECT", subj_id), ("TOPIC", topic_id)]:
        await client.put(
            "/api/v1/preferences",
            json={"scope_type": scope, "scope_id": sid, "preference": "WEAK"},
            headers=csrf_headers(client),
        )
    r = await client.delete(f"/api/v1/preferences/SUBJECT/{subj_id}", headers=csrf_headers(client))
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] is True
    remaining = (await client.get("/api/v1/preferences")).json()["data"]
    assert [row["scope_type"] for row in remaining] == ["TOPIC"]

    r_all = await client.post("/api/v1/preferences/reset", headers=csrf_headers(client))
    assert r_all.status_code == 200
    assert r_all.json()["data"]["deleted"] == 1
    assert (await client.get("/api/v1/preferences")).json()["data"] == []


async def test_invalid_scope_or_preference_rejected(client, db_session, register_user):
    await register_user(client, db_session=db_session)
    subj_id, _t, _c = await _one_of_each(db_session)
    bad_scope = await client.put(
        "/api/v1/preferences",
        json={"scope_type": "CHAPTER", "scope_id": subj_id, "preference": "WEAK"},
        headers=csrf_headers(client),
    )
    assert bad_scope.status_code == 422
    assert bad_scope.json()["errors"][0]["code"] == "PREFERENCE_SCOPE_INVALID"

    bad_pref = await client.put(
        "/api/v1/preferences",
        json={"scope_type": "SUBJECT", "scope_id": subj_id, "preference": "AWFUL"},
        headers=csrf_headers(client),
    )
    assert bad_pref.status_code == 422
    assert bad_pref.json()["errors"][0]["code"] == "PREFERENCE_VALUE_INVALID"


async def test_unknown_scope_id_is_404(client, db_session, register_user):
    await register_user(client, db_session=db_session)
    fake = str(uuid.uuid4())
    r = await client.put(
        "/api/v1/preferences",
        json={"scope_type": "SUBJECT", "scope_id": fake, "preference": "WEAK"},
        headers=csrf_headers(client),
    )
    assert r.status_code == 404
    assert r.json()["errors"][0]["code"] == "PREFERENCE_SCOPE_NOT_FOUND"


async def test_isolated_by_user(client, db_session, register_user):
    # user A
    await register_user(client, db_session=db_session)
    subj_id, _t, _c = await _one_of_each(db_session)
    await client.put(
        "/api/v1/preferences",
        json={"scope_type": "SUBJECT", "scope_id": subj_id, "preference": "WEAK"},
        headers=csrf_headers(client),
    )
    await client.post("/api/v1/auth/logout")
    # user B — fresh session
    await register_user(client, db_session=db_session)
    listed = await client.get("/api/v1/preferences")
    assert listed.json()["data"] == []
