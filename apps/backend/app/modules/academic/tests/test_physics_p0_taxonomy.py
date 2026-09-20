"""T4 Physics P0 taxonomy — 74 verified nodes; Gravitation excluded; no CMS writes."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.academic.physics_p0_manifest import (
    GRAVITATION_EXCLUDED_CODES,
    IMPLEMENTABLE_VERIFIED_NODES,
    validate_manifest,
)
from app.modules.academic.services.physics_p0_taxonomy_service import PhysicsP0TaxonomyService
from app.modules.cms.models import ContentItem


def test_manifest_static_integrity():
    result = validate_manifest()
    assert result["ok"], result["errors"]
    assert result["counts"]["total"] == IMPLEMENTABLE_VERIFIED_NODES
    assert result["counts"]["chapters"] == 5
    assert result["counts"]["topics"] == 24
    assert result["counts"]["concepts"] == 45
    codes = {n["code"] for n in result["nodes"]}
    assert codes.isdisjoint(GRAVITATION_EXCLUDED_CODES)


def test_manifest_excludes_gravitation_and_has_solids_naming():
    result = validate_manifest()
    solids = [n for n in result["nodes"] if n["code"] == "stress-strain-definitions"][0]
    assert solids["name"] == "Definitions of Stress and Strain"
    kin_topics = {
        n["code"]
        for n in result["nodes"]
        if n["node_type"] == "topic" and n["parent_code"] == "kinematics"
    }
    assert kin_topics == {"motion-in-a-straight-line", "motion-in-a-plane"}


@pytest.mark.asyncio(loop_scope="session")
async def test_ensure_idempotent_and_hierarchy(db_session):
    service = PhysicsP0TaxonomyService(db_session)
    r1 = await service.ensure(commit=True)
    assert r1["newly_inserted"] + r1["already_existing_exact_match"] == IMPLEMENTABLE_VERIFIED_NODES

    r2 = await service.ensure(commit=True)
    assert r2["newly_inserted"] == 0
    assert r2["already_existing_exact_match"] == IMPLEMENTABLE_VERIFIED_NODES

    verify = await service.verify_present()
    assert verify["approved_present"] == IMPLEMENTABLE_VERIFIED_NODES
    assert verify["approved_missing"] == []
    assert verify["gravitation_nodes_present"] == []

    # Kinematics: one chapter, two topics
    subject = (
        await db_session.execute(select(Subject).where(Subject.code == "PHYSICS"))
    ).scalar_one()
    kin = (
        await db_session.execute(
            select(Chapter).where(Chapter.subject_id == subject.id, Chapter.code == "kinematics")
        )
    ).scalar_one()
    topics = (
        await db_session.execute(select(Topic).where(Topic.chapter_id == kin.id, Topic.deleted_at.is_(None)))
    ).scalars().all()
    # may include only our two if chapter was empty
    codes = {t.code for t in topics}
    assert "motion-in-a-straight-line" in codes
    assert "motion-in-a-plane" in codes

    # Solids naming
    concept = (
        await db_session.execute(
            select(Concept, Topic)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .where(
                Chapter.code == "mechanical-properties-of-solids",
                Concept.code == "stress-strain-definitions",
            )
        )
    ).one()
    concept_row, topic_row = concept
    assert topic_row.name == "Stress and Strain"
    assert concept_row.name == "Definitions of Stress and Strain"

    # Kinetic Theory chapter exists and is separate from thermodynamics-physics
    kt = (
        await db_session.execute(
            select(Chapter).where(Chapter.subject_id == subject.id, Chapter.code == "kinetic-theory")
        )
    ).scalar_one_or_none()
    assert kt is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_ensure_does_not_modify_cms_questions(db_session):
    before = (
        await db_session.execute(
            select(ContentItem.id, ContentItem.concept_id, ContentItem.status, ContentItem.version)
            .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
            .order_by(ContentItem.id)
            .limit(200)
        )
    ).all()

    service = PhysicsP0TaxonomyService(db_session)
    await service.ensure(commit=True)

    after = (
        await db_session.execute(
            select(ContentItem.id, ContentItem.concept_id, ContentItem.status, ContentItem.version)
            .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
            .order_by(ContentItem.id)
            .limit(200)
        )
    ).all()
    assert before == after


@pytest.mark.asyncio(loop_scope="session")
async def test_no_gravitation_fill_codes_in_db_after_ensure(db_session):
    service = PhysicsP0TaxonomyService(db_session)
    await service.ensure(commit=True)
    for code in GRAVITATION_EXCLUDED_CODES:
        t = await db_session.execute(select(Topic.id).where(Topic.code == code))
        assert t.scalar_one_or_none() is None
        c = await db_session.execute(select(Concept.id).where(Concept.code == code))
        assert c.scalar_one_or_none() is None
