"""FACTORY-P2: learning objectives, families, blueprints, coverage planning."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _concept_chain(db_session, subject_code: str = "PHYSICS"):
    """Resolve a real Subject→Chapter→Topic→Concept chain (seed only fleshes one chapter)."""
    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    subject = (
        await db_session.execute(select(Subject).where(Subject.code == subject_code))
    ).scalar_one()
    result = await db_session.execute(
        select(Concept, Topic, Chapter)
        .join(Topic, Topic.id == Concept.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .where(Chapter.subject_id == subject.id)
        .limit(1)
    )
    row = result.one()
    concept, topic, chapter = row
    return subject, chapter, topic, concept


async def test_student_denied_planning(client, register_user):
    await register_user(client)
    assert (await client.get("/api/v1/cms/learning-objectives")).status_code == 403
    assert (await client.get("/api/v1/cms/question-blueprints")).status_code == 403
    assert (await client.get("/api/v1/cms/content-coverage")).status_code == 403


async def test_teacher_denied_planning_create(client, register_user, db_session):
    await register_user(client, role_codes=["TEACHER"], db_session=db_session)
    subject, chapter, topic, concept = await _concept_chain(db_session)
    resp = await client.post(
        "/api/v1/cms/learning-objectives",
        json={
            "objective_key": f"obj-{uuid.uuid4().hex[:8]}",
            "concept_id": str(concept.id),
            "title": "Calculate electrostatic force using Coulomb's law",
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 403


async def test_objective_family_blueprint_coverage_flow(client, register_user, db_session):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    subject, chapter, topic, concept = await _concept_chain(db_session)
    suffix = uuid.uuid4().hex[:8]

    obj = await client.post(
        "/api/v1/cms/learning-objectives",
        json={
            "objective_key": f"obj-scale-{suffix}",
            "concept_id": str(concept.id),
            "title": "Determine how electrostatic force scales with charge and distance",
            "description": "Apply inverse-square and product of charges.",
            "learning_level": "apply",
        },
        headers=csrf_headers(client),
    )
    assert obj.status_code == 201, obj.text
    objective_id = obj.json()["data"]["id"]

    # Idempotent objective
    obj2 = await client.post(
        "/api/v1/cms/learning-objectives",
        json={
            "objective_key": f"obj-scale-{suffix}",
            "concept_id": str(concept.id),
            "title": "Determine how electrostatic force scales with charge and distance",
        },
        headers=csrf_headers(client),
    )
    assert obj2.status_code == 200
    assert obj2.json()["meta"]["idempotent"] is True

    fam = await client.post(
        "/api/v1/cms/question-families",
        json={
            "family_key": f"phys-ratio-{suffix}",
            "name": "Ratio / scaling",
            "description": "Proportional reasoning on physical quantities",
            "applicable_subject_codes": ["PHYSICS"],
            "cognitive_intent": "scale quantities under parameter change",
            "difficulty_min": "easy",
            "difficulty_max": "hard",
            "question_format": "MCQ_4",
        },
        headers=csrf_headers(client),
    )
    assert fam.status_code == 201, fam.text
    family_id = fam.json()["data"]["id"]

    # Chemistry family incompatible with Physics blueprint
    chem_fam = await client.post(
        "/api/v1/cms/question-families",
        json={
            "family_key": f"chem-eq-{suffix}",
            "name": "Equilibrium reasoning",
            "applicable_subject_codes": ["CHEMISTRY"],
            "cognitive_intent": "Le Chatelier shifts",
            "question_format": "MCQ_4",
        },
        headers=csrf_headers(client),
    )
    assert chem_fam.status_code == 201, chem_fam.text

    bad_bp = await client.post(
        "/api/v1/cms/question-blueprints",
        json={
            "blueprint_key": f"bp-bad-{suffix}",
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(concept.id),
            "learning_objective_id": objective_id,
            "question_family_id": chem_fam.json()["data"]["id"],
            "difficulty": "medium",
            "target_count": 20,
            "provenance_tier": "ai",
            "constraints": {
                "question_format": "MCQ_4",
                "correct_option_count": 1,
                "explanation_required": True,
            },
        },
        headers=csrf_headers(client),
    )
    assert bad_bp.status_code == 400
    assert bad_bp.json()["errors"][0]["code"] == "BLUEPRINT_VALIDATION_FAILED"

    # False official provenance rejected at schema
    bad_prov = await client.post(
        "/api/v1/cms/question-blueprints",
        json={
            "blueprint_key": f"bp-nta-{suffix}",
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(concept.id),
            "learning_objective_id": objective_id,
            "question_family_id": family_id,
            "difficulty": "medium",
            "target_count": 10,
            "provenance_tier": "official_source",
        },
        headers=csrf_headers(client),
    )
    assert bad_prov.status_code == 422

    # Hierarchy gap: random concept UUID
    gap = await client.post(
        "/api/v1/cms/question-blueprints",
        json={
            "blueprint_key": f"bp-gap-{suffix}",
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(uuid.uuid4()),
            "learning_objective_id": objective_id,
            "question_family_id": family_id,
            "difficulty": "medium",
            "target_count": 5,
            "provenance_tier": "human",
        },
        headers=csrf_headers(client),
    )
    assert gap.status_code == 400
    assert gap.json()["errors"][0]["code"] == "HIERARCHY_GAP"

    bp = await client.post(
        "/api/v1/cms/question-blueprints",
        json={
            "blueprint_key": f"bp-coulomb-scale-{suffix}",
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(concept.id),
            "learning_objective_id": objective_id,
            "question_family_id": family_id,
            "difficulty": "medium",
            "target_count": 20,
            "provenance_tier": "ai",
            "constraints": {
                "question_format": "MCQ_4",
                "correct_option_count": 1,
                "explanation_required": True,
                "reasoning": "charge_and_distance_scaling",
            },
        },
        headers=csrf_headers(client),
    )
    assert bp.status_code == 201, bp.text
    blueprint = bp.json()["data"]
    assert blueprint["generation_eligible"] is True
    assert blueprint["blueprint_version"] == 1
    blueprint_id = blueprint["id"]

    # Idempotent blueprint (same key)
    bp_again = await client.post(
        "/api/v1/cms/question-blueprints",
        json={
            "blueprint_key": f"bp-coulomb-scale-{suffix}",
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(concept.id),
            "learning_objective_id": objective_id,
            "question_family_id": family_id,
            "difficulty": "medium",
            "target_count": 20,
            "provenance_tier": "ai",
        },
        headers=csrf_headers(client),
    )
    assert bp_again.status_code == 200
    assert bp_again.json()["data"]["id"] == blueprint_id

    # New version
    bp_v2 = await client.post(
        "/api/v1/cms/question-blueprints",
        json={
            "blueprint_key": f"bp-coulomb-scale-{suffix}",
            "new_version": True,
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(concept.id),
            "learning_objective_id": objective_id,
            "question_family_id": family_id,
            "difficulty": "medium",
            "target_count": 25,
            "provenance_tier": "human",
            "constraints": {
                "question_format": "MCQ_4",
                "correct_option_count": 1,
                "explanation_required": True,
            },
        },
        headers=csrf_headers(client),
    )
    assert bp_v2.status_code == 201, bp_v2.text
    assert bp_v2.json()["data"]["blueprint_version"] == 2
    assert bp_v2.json()["data"]["provenance_tier"] == "human"

    # Validate endpoint
    val = await client.post(
        f"/api/v1/cms/question-blueprints/{bp_v2.json()['data']['id']}/validate",
        headers=csrf_headers(client),
    )
    assert val.status_code == 200, val.text
    assert val.json()["data"]["verdict"] == "GREEN"

    # Coverage slice + report
    slice_resp = await client.post(
        "/api/v1/cms/coverage-slices",
        json={
            "slice_key": f"cov-phys-{suffix}",
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(concept.id),
            "difficulty": "medium",
            "question_family_id": family_id,
            "target_count": 50,
        },
        headers=csrf_headers(client),
    )
    assert slice_resp.status_code == 201, slice_resp.text

    cov = await client.get(f"/api/v1/cms/content-coverage?subject_id={subject.id}")
    assert cov.status_code == 200, cov.text
    rows = cov.json()["data"]
    match = [r for r in rows if r["slice_key"] == f"cov-phys-{suffix}"]
    assert match
    row = match[0]
    assert row["target"] == 50
    assert "published" in row
    assert "existing" in row
    assert "planned" in row
    assert row["published"] <= row["existing"]
    assert row["generated"] == 0

    # Attach to batch + job with blueprint (no generation)
    batch = await client.post(
        "/api/v1/cms/content-batches",
        json={
            "batch_key": f"batch-p2-{suffix}",
            "name": "P2 planning batch",
            "subject_id": str(subject.id),
            "concept_id": str(concept.id),
            "target_count": 25,
            "source_tier": "ai",
            "source_type": "AI",
        },
        headers=csrf_headers(client),
    )
    assert batch.status_code == 201, batch.text
    batch_id = batch.json()["data"]["id"]

    attach = await client.post(
        f"/api/v1/cms/content-batches/{batch_id}/blueprints",
        json={"blueprint_id": bp_v2.json()["data"]["id"], "requested_count": 25},
        headers=csrf_headers(client),
    )
    assert attach.status_code == 201, attach.text

    job = await client.post(
        f"/api/v1/cms/content-batches/{batch_id}/jobs",
        json={
            "job_key": f"gen-bp-{suffix}",
            "job_type": "GENERATE",
            "requested_count": 25,
            "blueprint_id": bp_v2.json()["data"]["id"],
        },
        headers=csrf_headers(client),
    )
    assert job.status_code == 201, job.text
    assert job.json()["data"]["blueprint_id"] == bp_v2.json()["data"]["id"]
    assert job.json()["data"]["blueprint_version"] == 2


async def test_invalid_difficulty_out_of_family_range(client, register_user, db_session):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    subject, chapter, topic, concept = await _concept_chain(db_session)
    suffix = uuid.uuid4().hex[:8]

    obj = await client.post(
        "/api/v1/cms/learning-objectives",
        json={
            "objective_key": f"obj-easy-{suffix}",
            "concept_id": str(concept.id),
            "title": "Identify Coulomb's law formula structure",
        },
        headers=csrf_headers(client),
    )
    assert obj.status_code == 201, obj.text

    fam = await client.post(
        "/api/v1/cms/question-families",
        json={
            "family_key": f"phys-direct-{suffix}",
            "name": "Direct concept",
            "applicable_subject_codes": ["PHYSICS"],
            "cognitive_intent": "recall definition",
            "difficulty_min": "easy",
            "difficulty_max": "medium",
            "question_format": "MCQ_4",
        },
        headers=csrf_headers(client),
    )
    assert fam.status_code == 201, fam.text

    hard = await client.post(
        "/api/v1/cms/question-blueprints",
        json={
            "blueprint_key": f"bp-hard-{suffix}",
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(concept.id),
            "learning_objective_id": obj.json()["data"]["id"],
            "question_family_id": fam.json()["data"]["id"],
            "difficulty": "hard",
            "target_count": 5,
            "provenance_tier": "human",
        },
        headers=csrf_headers(client),
    )
    assert hard.status_code == 400
    assert "DIFFICULTY_OUT_OF_FAMILY_RANGE" in hard.json()["errors"][0]["message"]
