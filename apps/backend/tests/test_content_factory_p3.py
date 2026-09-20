"""FACTORY-P3 generation tests — mocked AI Gateway only (no live Claude)."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select, text

from app.modules.ai.gateway.base import AIProvider, AIResponse
from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService
from app.modules.cms.services.factory_candidate_validation import parse_mcq_json, stem_hash, validate_candidate_body
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _mcq(*, stem: str, difficulty: str = "medium", correct: str = "A") -> dict:
    return {
        "stem": stem,
        "options": [
            {"label": "A", "text": "Alpha option text"},
            {"label": "B", "text": "Beta option text"},
            {"label": "C", "text": "Gamma option text"},
            {"label": "D", "text": "Delta option text"},
        ],
        "correct_option": correct,
        "explanation": f"Option {correct} is correct because it matches the learning objective reasoning required.",
        "difficulty": difficulty,
    }


class ScriptedProvider(AIProvider):
    def __init__(self, responses: list[AIResponse | Exception]):
        self._responses = list(responses)
        self.calls = 0

    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        self.calls += 1
        if not self._responses:
            raise RuntimeError("No scripted responses left")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _resp(body: dict, *, model: str = "mock-claude", fallback: bool = False) -> AIResponse:
    return AIResponse(
        text=json.dumps(body),
        model=model,
        prompt_tokens=10,
        completion_tokens=20,
        is_fallback=fallback,
        cost_usd=0.001,
    )


async def _concept_chain(db_session):
    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    subject = (await db_session.execute(select(Subject).where(Subject.code == "PHYSICS"))).scalar_one()
    result = await db_session.execute(
        select(Concept, Topic, Chapter)
        .join(Topic, Topic.id == Concept.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .where(Chapter.subject_id == subject.id)
        .limit(1)
    )
    concept, topic, chapter = result.one()
    return subject, chapter, topic, concept


async def _seed_eligible_blueprint(client, db_session, suffix: str):
    subject, chapter, topic, concept = await _concept_chain(db_session)
    obj = await client.post(
        "/api/v1/cms/learning-objectives",
        json={
            "objective_key": f"p3-obj-{suffix}",
            "concept_id": str(concept.id),
            "title": "Apply Ohm's law to compute current from voltage and resistance",
        },
        headers=csrf_headers(client),
    )
    assert obj.status_code in (200, 201), obj.text
    fam = await client.post(
        "/api/v1/cms/question-families",
        json={
            "family_key": f"p3-fam-{suffix}",
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
            "blueprint_key": f"p3-bp-{suffix}",
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
                "reasoning": "V=IR",
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
            "batch_key": f"p3-batch-{suffix}",
            "name": "P3 test batch",
            "subject_id": str(subject.id),
            "concept_id": str(concept.id),
            "target_count": 5,
            "source_type": "AI",
            "source_tier": "ai",
        },
        headers=csrf_headers(client),
    )
    assert batch.status_code in (200, 201), batch.text
    return {
        "subject": subject,
        "concept": concept,
        "blueprint_id": bp.json()["data"]["id"],
        "batch_id": batch.json()["data"]["id"],
        "user_id": None,
    }


async def test_validation_helpers():
    ok, errs = validate_candidate_body(_mcq(stem="What is Ohm's law?"), expected_difficulty="medium")
    assert errs == [] and ok is not None
    bad, errs2 = validate_candidate_body(
        _mcq(stem="x", correct="A") | {"explanation": "Option B is correct because reasons."},
        expected_difficulty="medium",
    )
    assert bad is None
    assert "ANSWER_EXPLANATION_CONTRADICTION" in errs2 or "EXPLANATION_TOO_SHORT" in errs2 or "SCHEMA" in errs2[0]
    with pytest.raises(ValueError):
        parse_mcq_json("```json\n{}\n```")
    assert stem_hash("Hello  World!") == stem_hash("hello world")


async def test_student_cannot_generate(client, register_user):
    await register_user(client)
    resp = await client.post(
        f"/api/v1/cms/content-batches/{uuid.uuid4()}/generate",
        json={"blueprint_id": str(uuid.uuid4()), "target_count": 1},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 403


async def test_generate_valid_malformed_duplicate_budget(client, register_user, db_session):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_eligible_blueprint(client, db_session, suffix)

    stem1 = f"Unique factory stem one {suffix}?"
    stem2 = f"Unique factory stem two {suffix}?"
    provider = ScriptedProvider(
        [
            _resp(_mcq(stem=stem1)),
            AIResponse(text="not-json", model="mock-claude", prompt_tokens=1, completion_tokens=1),
            _resp(_mcq(stem=stem1)),  # duplicate
            _resp(_mcq(stem=stem2)),
        ]
    )
    service = ContentFactoryGenerationService(db_session, provider=provider)
    result = await service.generate_for_batch(
        uuid.UUID(seeded["batch_id"]),
        blueprint_id=uuid.UUID(seeded["blueprint_id"]),
        target_count=2,
        actor_id=uuid.UUID(user["id"]),
        job_key=f"p3-job-{suffix}",
        sync_cap=True,
    )
    assert result["created"] == 2
    assert result["failed_parse"] >= 1
    assert result["duplicate"] >= 1
    assert result["attempted"] >= 4
    assert len(result["content_item_ids"]) == 2

    # All DRAFT
    for item_id in result["content_item_ids"]:
        status = (
            await db_session.execute(
                text("SELECT status FROM cms.content_items WHERE id = :id"),
                {"id": item_id},
            )
        ).scalar_one()
        assert status == "DRAFT"
        model_used = (
            await db_session.execute(
                text(
                    """
                    SELECT cv.model_used, cv.prompt_version
                    FROM cms.content_versions cv
                    JOIN cms.content_items ci ON ci.latest_version_id = cv.id
                    WHERE ci.id = :id
                    """
                ),
                {"id": item_id},
            )
        ).one()
        assert model_used[0] == "mock-claude"
        assert model_used[1] == "neet_mcq_factory_v2"

    # Existing PUBLISHED count unchanged in this transaction scope — spot-check no non-DRAFT factory tags
    non_draft = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE 'factory-p3' = ANY(tags) AND status <> 'DRAFT'
                """
            )
        )
    ).scalar_one()
    assert non_draft == 0


async def test_fallback_stops_generation(client, register_user, db_session):
    user = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_eligible_blueprint(client, db_session, suffix)
    provider = ScriptedProvider(
        [_resp(_mcq(stem=f"fallback test {suffix}"), fallback=True)]
    )
    service = ContentFactoryGenerationService(db_session, provider=provider)
    result = await service.generate_for_batch(
        uuid.UUID(seeded["batch_id"]),
        blueprint_id=uuid.UUID(seeded["blueprint_id"]),
        target_count=1,
        actor_id=uuid.UUID(user["id"]),
        job_key=f"p3-fb-{suffix}",
        sync_cap=True,
    )
    assert result["created"] == 0
    assert result["failed_provider"] >= 1
    assert result["stop_reason"] == "FALLBACK_PROVIDER"


async def test_provider_transient_then_success(client, register_user, db_session):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_eligible_blueprint(client, db_session, suffix)
    provider = ScriptedProvider([RuntimeError("provider down"), _resp(_mcq(stem=f"after fail {suffix}"))])
    service = ContentFactoryGenerationService(db_session, provider=provider)
    result = await service.generate_for_batch(
        uuid.UUID(seeded["batch_id"]),
        blueprint_id=uuid.UUID(seeded["blueprint_id"]),
        target_count=1,
        actor_id=uuid.UUID(user["id"]),
        job_key=f"p3-pf-{suffix}",
        sync_cap=True,
    )
    assert result["created"] == 1
    assert result["failed_provider"] >= 1


async def test_provider_credit_blocked_stops(client, register_user, db_session):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_eligible_blueprint(client, db_session, suffix)
    provider = ScriptedProvider(
        [RuntimeError("Error code: 400 - Your credit balance is too low to access the Anthropic API")]
    )
    service = ContentFactoryGenerationService(db_session, provider=provider)
    result = await service.generate_for_batch(
        uuid.UUID(seeded["batch_id"]),
        blueprint_id=uuid.UUID(seeded["blueprint_id"]),
        target_count=3,
        actor_id=uuid.UUID(user["id"]),
        job_key=f"p3-credit-{suffix}",
        sync_cap=True,
    )
    assert result["created"] == 0
    assert result["failed_provider"] == 1
    assert result["stop_reason"] == "PROVIDER_BLOCKED"
    assert provider.calls == 1


async def test_ineligible_blueprint_blocked(client, register_user, db_session):
    from app.core.exceptions import AppError

    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_eligible_blueprint(client, db_session, suffix)
    await db_session.execute(
        text(
            "UPDATE cms.question_blueprints SET generation_eligible = false, status = 'DRAFT' WHERE id = CAST(:id AS uuid)"
        ),
        {"id": seeded["blueprint_id"]},
    )
    await db_session.commit()
    service = ContentFactoryGenerationService(db_session, provider=ScriptedProvider([]))
    with pytest.raises(AppError) as exc:
        await service.generate_for_batch(
            uuid.UUID(seeded["batch_id"]),
            blueprint_id=uuid.UUID(seeded["blueprint_id"]),
            target_count=1,
            actor_id=uuid.UUID(user["id"]),
            job_key=f"p3-inel-{suffix}",
            sync_cap=True,
        )
    assert exc.value.code == "BLUEPRINT_NOT_ELIGIBLE"
