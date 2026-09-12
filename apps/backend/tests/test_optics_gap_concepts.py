"""WAVE-P0-11A: Optics hierarchy gap concepts — idempotent; no CMS question writes."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.cms.acquisition.batch_a_acquisition_service import BatchAAcquisitionService
from app.modules.cms.acquisition.batch_a_hierarchy import BATCH_A_HIERARCHY
from app.modules.cms.acquisition.optics_gap_concepts import (
    OPTICS_GAP_CONCEPT_CODES,
    audit_optics_hierarchy,
    ensure_optics_gap_concepts,
)
from app.modules.cms.models import ContentItem

pytestmark = pytest.mark.asyncio(loop_scope="session")


def test_optics_gap_codes_are_in_batch_a_hierarchy_definition():
    optics = BATCH_A_HIERARCHY["optics"]
    codes = {c[0] for _, _, concepts in optics for c in concepts}
    for code in OPTICS_GAP_CONCEPT_CODES:
        assert code in codes


async def test_ensure_optics_gap_concepts_idempotent(db_session, register_user, client):
    # Ensure optics topics exist (Batch A hierarchy)
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    await BatchAAcquisitionService(db_session).ensure_hierarchy()

    r1 = await ensure_optics_gap_concepts(db_session)
    await db_session.commit()
    assert set(c["code"] for c in r1["created"] + r1["already_existed"]) == set(OPTICS_GAP_CONCEPT_CODES)

    r2 = await ensure_optics_gap_concepts(db_session)
    await db_session.commit()
    assert r2["created"] == []
    assert len(r2["already_existed"]) == 3

    audit = await audit_optics_hierarchy(db_session)
    assert all(audit["gap_status"][c] == "exists" for c in OPTICS_GAP_CONCEPT_CODES)

    # Parent-child integrity
    for code in OPTICS_GAP_CONCEPT_CODES:
        row = (
            await db_session.execute(
                select(Concept.code, Topic.code, Chapter.code)
                .select_from(Concept)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .where(Concept.code == code)
            )
        ).one()
        assert row[2] == "optics"
        if code == "principal-focus-spherical-mirror":
            assert row[1] == "reflection-mirrors"
        else:
            assert row[1] == "refraction-lenses"


async def test_ensure_optics_gaps_does_not_touch_random_content(db_session, register_user, client):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    await BatchAAcquisitionService(db_session).ensure_hierarchy()

    before = (
        await db_session.execute(
            select(ContentItem.id, ContentItem.status, ContentItem.concept_id, ContentItem.version, ContentItem.updated_at)
        )
    ).all()
    await ensure_optics_gap_concepts(db_session)
    await db_session.commit()
    after = (
        await db_session.execute(
            select(ContentItem.id, ContentItem.status, ContentItem.concept_id, ContentItem.version, ContentItem.updated_at)
        )
    ).all()
    assert before == after
