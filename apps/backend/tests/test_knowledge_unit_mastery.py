"""Integration test: Knowledge-Unit-grained mastery (ADR-0028 Phase D).

Publishes a real question via the CMS API (same pattern as
test_assessment_and_mastery.py), manually establishes the Knowledge Unit
lineage a real ingestion run would have created (ADR-0025's
content_version_knowledge_units), then drives a real practice attempt
through the actual HTTP submit flow — the same recompute_for_content_items
hook every other mastery test already exercises — and verifies
knowledge_unit_mastery is populated exactly like ConceptMastery already is.
"""
import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _publish_question(client, concept_id: str, *, correct_option: str = "B") -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "KU mastery test question",
            "slug": f"ku-mastery-test-question-{concept_id[:8]}",
            "language": "en",
            "body": {
                "stem": "1 + 1 = ?",
                "options": [
                    {"label": "A", "text": "1"},
                    {"label": "B", "text": "2"},
                    {"label": "C", "text": "3"},
                    {"label": "D", "text": "11"},
                ],
                "correct_option": correct_option,
                "explanation": "Basic arithmetic.",
                "difficulty": "easy",
            },
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


async def _link_question_to_a_new_knowledge_unit(db_session, *, question_id: str, concept_id: str) -> uuid.UUID:
    """Establishes the ADR-0025 lineage a real ingestion run would have
    created — a KnowledgeUnit plus the join row connecting it to the
    question's current ContentVersion."""
    from app.modules.cms.models import ContentItem
    from app.modules.cms.models.content_version_knowledge_unit import ContentVersionKnowledgeUnit
    from app.modules.ingestion.models import IngestionJob, IngestionSection
    from app.modules.knowledge.models import KnowledgeUnit

    job = IngestionJob(source_file_path="test.pdf", file_checksum=uuid.uuid4().hex, status="STRUCTURING")
    db_session.add(job)
    await db_session.flush()

    section = IngestionSection(
        job_id=job.id,
        heading="3.4 OHM'S LAW",
        source_page=3,
        raw_text="Ohm's law relates voltage and current.",
        matched_concept_id=uuid.UUID(concept_id),
    )
    db_session.add(section)
    await db_session.flush()

    unit = KnowledgeUnit(
        version=1,
        content_hash=uuid.uuid4().hex,
        structured_facts=["Ohm's law relates voltage and current."],
        summary="Ohm's law summary.",
        source_section_id=section.id,
        concept_id=uuid.UUID(concept_id),
        extraction_confidence=0.95,
        validation_status="PASSED",
    )
    db_session.add(unit)
    await db_session.flush()

    item = await db_session.get(ContentItem, uuid.UUID(question_id))
    db_session.add(
        ContentVersionKnowledgeUnit(
            content_version_id=item.current_version_id, knowledge_unit_id=unit.id, knowledge_unit_version=1
        )
    )
    await db_session.commit()
    return unit.id


async def test_correct_answer_updates_knowledge_unit_mastery(client, db_session, register_user):
    from app.modules.learning.models import KnowledgeUnitMastery

    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id, correct_option="B")
    knowledge_unit_id = await _link_question_to_a_new_knowledge_unit(
        db_session, question_id=question_id, concept_id=concept_id
    )

    generate = await client.post(
        "/api/v1/assessments/practice", json={"scope_type": "CONCEPT", "scope_id": concept_id}, headers=csrf_headers(client)
    )
    assessment_id = generate.json()["data"]["id"]
    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    attempt_id = start.json()["data"]["id"]
    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": question_id, "selected_option": "B"},
        headers=csrf_headers(client),
    )
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text

    result = await db_session.execute(
        select(KnowledgeUnitMastery).where(
            KnowledgeUnitMastery.user_id == uuid.UUID(user["id"]),
            KnowledgeUnitMastery.knowledge_unit_id == knowledge_unit_id,
        )
    )
    row = result.scalar_one()
    assert row.attempts_count == 1
    assert row.correct_count == 1
    assert row.mastery_level == "LEARNING"  # below MASTERY_ATTEMPT_FLOOR of 3


async def test_answering_a_question_with_no_knowledge_unit_lineage_is_a_no_op_for_ku_mastery(
    client, db_session, register_user
):
    """Non-interference check: a question published the ordinary way (no
    ingestion, no Knowledge Unit link — the vast majority of existing
    content) must not create a spurious knowledge_unit_mastery row, and
    ConceptMastery must keep working exactly as before this ADR."""
    from app.modules.learning.models import ConceptMastery, KnowledgeUnitMastery

    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id, correct_option="B")
    # Deliberately no _link_question_to_a_new_knowledge_unit call.

    generate = await client.post(
        "/api/v1/assessments/practice", json={"scope_type": "CONCEPT", "scope_id": concept_id}, headers=csrf_headers(client)
    )
    assessment_id = generate.json()["data"]["id"]
    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    attempt_id = start.json()["data"]["id"]
    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": question_id, "selected_option": "B"},
        headers=csrf_headers(client),
    )
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text

    ku_rows = (
        await db_session.execute(
            select(KnowledgeUnitMastery).where(KnowledgeUnitMastery.user_id == uuid.UUID(user["id"]))
        )
    ).scalars().all()
    assert ku_rows == []

    concept_row = (
        await db_session.execute(
            select(ConceptMastery).where(
                ConceptMastery.user_id == uuid.UUID(user["id"]), ConceptMastery.concept_id == uuid.UUID(concept_id)
            )
        )
    ).scalar_one()
    assert concept_row.attempts_count == 1
    assert concept_row.correct_count == 1
