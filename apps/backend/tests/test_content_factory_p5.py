"""FACTORY-P5 human sampling / exception review tests — no live Anthropic."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select, text

from app.modules.ai.gateway.base import AIProvider, AIResponse
from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService
from app.modules.cms.services.content_factory_human_review_service import ContentFactoryHumanReviewService
from app.modules.cms.services.content_factory_qa_service import ContentFactoryQAService, ContentFactorySamplingService
from conftest import csrf_headers


def _mcq(*, stem: str, difficulty: str = "medium") -> dict:
    return {
        "stem": stem,
        "options": [
            {"label": "A", "text": "Alpha option text unique"},
            {"label": "B", "text": "Beta option text unique"},
            {"label": "C", "text": "Gamma option text unique"},
            {"label": "D", "text": "Delta option text unique"},
        ],
        "correct_option": "A",
        "explanation": "Option A is correct because it matches the learning objective reasoning required here.",
        "difficulty": difficulty,
    }


class ScriptedProvider(AIProvider):
    def __init__(self, responses: list[AIResponse]):
        self._responses = list(responses)

    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        return self._responses.pop(0)


def _resp(body: dict) -> AIResponse:
    return AIResponse(
        text=json.dumps(body),
        model="mock-claude",
        prompt_tokens=10,
        completion_tokens=20,
        is_fallback=False,
        cost_usd=0.001,
    )


async def _seed(client, db_session, suffix: str):
    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    subject = (await db_session.execute(select(Subject).where(Subject.code == "PHYSICS"))).scalar_one()
    concept, topic, chapter = (
        await db_session.execute(
            select(Concept, Topic, Chapter)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .where(Chapter.subject_id == subject.id)
            .limit(1)
        )
    ).one()
    obj = await client.post(
        "/api/v1/cms/learning-objectives",
        json={
            "objective_key": f"p5-obj-{suffix}",
            "concept_id": str(concept.id),
            "title": "Apply Ohm's law to compute current from voltage and resistance",
        },
        headers=csrf_headers(client),
    )
    assert obj.status_code in (200, 201), obj.text
    fam = await client.post(
        "/api/v1/cms/question-families",
        json={
            "family_key": f"p5-fam-{suffix}",
            "name": "Formula application",
            "applicable_subject_codes": ["PHYSICS"],
            "cognitive_intent": "apply formula",
            "difficulty_min": "easy",
            "difficulty_max": "hard",
            "question_format": "MCQ_4",
        },
        headers=csrf_headers(client),
    )
    assert fam.status_code in (200, 201), fam.text
    bp = await client.post(
        "/api/v1/cms/question-blueprints",
        json={
            "blueprint_key": f"p5-bp-{suffix}",
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(concept.id),
            "learning_objective_id": obj.json()["data"]["id"],
            "question_family_id": fam.json()["data"]["id"],
            "difficulty": "medium",
            "target_count": 10,
            "provenance_tier": "ai",
            "constraints": {
                "question_format": "MCQ_4",
                "correct_option_count": 1,
                "explanation_required": True,
                "neet_ug_2026": {
                    "subject": "PHYSICS",
                    "unit_number": 12,
                    "unit_name": "CURRENT ELECTRICITY",
                    "topic_id": "PHYSICS:U12:T01",
                },
            },
        },
        headers=csrf_headers(client),
    )
    assert bp.status_code in (200, 201), bp.text
    batch = await client.post(
        "/api/v1/cms/content-batches",
        json={
            "batch_key": f"p5-batch-{suffix}",
            "name": "P5 test batch",
            "subject_id": str(subject.id),
            "concept_id": str(concept.id),
            "target_count": 5,
            "source_type": "AI",
            "source_tier": "ai",
        },
        headers=csrf_headers(client),
    )
    assert batch.status_code in (200, 201), batch.text
    return {"blueprint_id": bp.json()["data"]["id"], "batch_id": batch.json()["data"]["id"]}


async def _pipeline(db_session, seeded, actor, stems, suffix):
    provider = ScriptedProvider([_resp(_mcq(stem=s)) for s in stems])
    await ContentFactoryGenerationService(db_session, provider=provider).generate_for_batch(
        uuid.UUID(seeded["batch_id"]),
        blueprint_id=uuid.UUID(seeded["blueprint_id"]),
        target_count=len(stems),
        actor_id=actor,
        job_key=f"p5-gen-{suffix}",
        sync_cap=True,
    )
    await ContentFactoryQAService(db_session).run_batch_qa(
        uuid.UUID(seeded["batch_id"]),
        actor_id=actor,
        job_key=f"p5-qa-{suffix}",
    )
    return await ContentFactorySamplingService(db_session).create_sample(
        uuid.UUID(seeded["batch_id"]),
        actor_id=actor,
        seed=99,
        sample_key=f"p5-sample-{suffix}",
        green_size=len(stems),
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_student_denied_factory_review(client, register_user):
    await register_user(client)
    resp = await client.get("/api/v1/cms/factory-review/dashboard")
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_green_decisions_and_no_ecaep_mutation(client, register_user, db_session):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed(client, db_session, suffix)
    actor = uuid.UUID(user["id"])
    stems = [f"P5 ohm stem {suffix} {i}?" for i in range(3)]
    sample = await _pipeline(db_session, seeded, actor, stems, suffix)
    assert sample["green_sample_size"] >= 1

    sample2 = await ContentFactorySamplingService(db_session).create_sample(
        uuid.UUID(seeded["batch_id"]),
        actor_id=actor,
        seed=99,
        sample_key=f"p5-sample-{suffix}",
        green_size=len(stems),
    )
    assert sample2["idempotent"] is True
    assert sample["selected_candidate_ids"] == sample2["selected_candidate_ids"]

    hr = ContentFactoryHumanReviewService(db_session)
    queue = await hr.list_queue(batch_id=uuid.UUID(seeded["batch_id"]), needs_review=True)
    assert queue["total"] >= 1
    fri_id = uuid.UUID(queue["items"][0]["factory_review_item_id"])
    content_item_id = queue["items"][0]["content_item_id"]
    status_before = (
        await db_session.execute(
            text("SELECT status FROM cms.content_items WHERE id = CAST(:id AS uuid)"),
            {"id": content_item_id},
        )
    ).scalar_one()
    assert status_before == "DRAFT"

    packet = await hr.get_review_packet(fri_id)
    assert packet["automated_qa"]["scientific_certification"] is False
    assert "NOT scientific certification" in packet["automated_qa"]["label"]

    from app.core.exceptions import AppError

    with pytest.raises(AppError):
        await hr.submit_decision(fri_id, decision="REJECT", actor_id=actor, checklist={"language": True})

    result = await hr.submit_decision(
        fri_id,
        decision="ACCEPT",
        actor_id=actor,
        checklist={"scientific_correctness": True, "correct_answer": True},
    )
    assert result["ecaep_submit_eligible"] is True
    assert result["review_status"] == "ACCEPTED"

    status_after = (
        await db_session.execute(
            text("SELECT status FROM cms.content_items WHERE id = CAST(:id AS uuid)"),
            {"id": content_item_id},
        )
    ).scalar_one()
    assert status_after == "DRAFT"

    queue2 = await hr.list_queue(batch_id=uuid.UUID(seeded["batch_id"]), needs_review=True)
    if queue2["items"]:
        fri2 = uuid.UUID(queue2["items"][0]["factory_review_item_id"])
        await hr.submit_decision(
            fri2,
            decision="CORRECTION_REQUIRED",
            actor_id=actor,
            checklist={"explanation": False},
            failure_reasons=["POOR_EXPLANATION"],
            reviewer_note="Explanation needs revision for NEET clarity.",
        )

    dash = await hr.dashboard(batch_id=uuid.UUID(seeded["batch_id"]))
    assert dash["green_accepted"] >= 1

    api = await client.get("/api/v1/cms/factory-review/dashboard")
    assert api.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_red_quarantine_excluded_from_green_sample(client, register_user, db_session):
    user = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed(client, db_session, suffix)
    actor = uuid.UUID(user["id"])

    good = _mcq(stem=f"P5 good stem {suffix}?")
    bad = _mcq(stem=f"Official NTA question current {suffix}?")
    bad["explanation"] = "This is an NTA official question copied from NCERT for this stem."
    provider = ScriptedProvider([_resp(good), _resp(bad)])
    await ContentFactoryGenerationService(db_session, provider=provider).generate_for_batch(
        uuid.UUID(seeded["batch_id"]),
        blueprint_id=uuid.UUID(seeded["blueprint_id"]),
        target_count=2,
        actor_id=actor,
        job_key=f"p5-mix-{suffix}",
        sync_cap=True,
    )
    qa = await ContentFactoryQAService(db_session).run_batch_qa(
        uuid.UUID(seeded["batch_id"]),
        actor_id=actor,
        job_key=f"p5-qamix-{suffix}",
    )
    assert qa["RED"] >= 1
    sample = await ContentFactorySamplingService(db_session).create_sample(
        uuid.UUID(seeded["batch_id"]),
        actor_id=actor,
        seed=7,
        sample_key=f"p5-mix-sample-{suffix}",
        green_size=5,
    )
    assert len(sample["red_candidate_ids"]) >= 1
    assert set(sample["selected_candidate_ids"]).isdisjoint(set(sample["red_candidate_ids"]))

    queue = await ContentFactoryHumanReviewService(db_session).list_queue(
        batch_id=uuid.UUID(seeded["batch_id"]), selection_class="RED"
    )
    assert queue["total"] >= 1
    for row in queue["items"]:
        assert row["selection_class"] == "RED"
