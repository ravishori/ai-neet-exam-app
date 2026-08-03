"""Integration test: TutorService.explain_question() (PR 8) — a focused,
question-specific walkthrough distinct from explain()'s full concept-teaching
template. Same "route through KnowledgeService, mock the gateway" convention
as test_tutor_service.py."""
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.modules.academic.models import Concept
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.gateway.base import AIResponse
from app.modules.ai.services.tutor_service import TutorService
from app.modules.cms.models import ContentItem, ContentVersion

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept(db_session) -> Concept:
    result = await db_session.execute(select(Concept).limit(1))
    return result.scalar_one()


def _mock_response(text: str, *, is_fallback: bool = False) -> AIResponse:
    return AIResponse(text=text, model="test-model", prompt_tokens=10, completion_tokens=10, is_fallback=is_fallback)


async def _published_question(db_session, concept_id) -> uuid.UUID:
    """Builds a PUBLISHED question directly via the ORM — this module's
    tests operate below the HTTP layer (mocking AIGateway), so there's no
    client/csrf fixture in scope the way the cms router tests have."""
    item = ContentItem(
        content_type="QUESTION",
        concept_id=concept_id,
        title="Explain-question test",
        slug=f"explain-question-test-{uuid.uuid4().hex[:10]}",
        language="en",
        status="PUBLISHED",
    )
    db_session.add(item)
    await db_session.flush()

    version = ContentVersion(
        content_item_id=item.id,
        version_no=1,
        body={
            "stem": "What is the SI unit of electric current?",
            "options": [{"label": "A", "text": "Ampere"}, {"label": "B", "text": "Volt"}, {"label": "C", "text": "Ohm"}, {"label": "D", "text": "Watt"}],
            "correct_option": "A",
            "explanation": "Current is measured in amperes.",
            "difficulty": "easy",
        },
        workflow_state="PUBLISHED",
        authored_at=datetime.now(UTC),
    )
    db_session.add(version)
    await db_session.flush()

    item.current_version_id = version.id
    item.latest_version_id = version.id
    await db_session.commit()
    return item.id


async def test_explain_question_returns_grounded_answer(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    concept.summary = "Concept summary text."
    await db_session.commit()
    question_id = await _published_question(db_session, concept.id)

    captured_prompt = {}

    async def fake_generate(self, **kwargs):
        captured_prompt["system_prompt"] = kwargs["system_prompt"]
        captured_prompt["user_prompt"] = kwargs["user_prompt"]
        return _mock_response("## Why the correct answer is right\nBecause SI defines it that way.")

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = TutorService(db_session)
    result = await service.explain_question(question_id=question_id, user_id=uuid.uuid4())

    assert result["answer"].startswith("## Why the correct answer is right")
    assert result["concept_name"] == concept.name
    assert result["is_fallback"] is False
    # No stray keys from explain()'s response shape — a different action, a
    # deliberately smaller response contract.
    assert "cited_published_notes" not in result
    assert "knowledge_units_cited" not in result

    # The actual question content reached the model, not just the concept.
    assert "What is the SI unit of electric current?" in captured_prompt["user_prompt"]
    assert "Ampere" in captured_prompt["user_prompt"]
    assert "Correct answer: A" in captured_prompt["user_prompt"]
    # Uses the question-specific template, not explain()'s concept-teaching one.
    assert "Practice MCQs" not in captured_prompt["system_prompt"]
    assert "Why the correct answer is right" in captured_prompt["system_prompt"]


async def test_explain_question_propagates_fallback_flag(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    question_id = await _published_question(db_session, concept.id)

    async def fake_generate(self, **kwargs):
        return _mock_response("Fallback answer.", is_fallback=True)

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = TutorService(db_session)
    result = await service.explain_question(question_id=question_id, user_id=uuid.uuid4())
    assert result["is_fallback"] is True


async def test_explain_question_404s_for_draft_question(db_session):
    concept = await _any_concept(db_session)
    item = ContentItem(
        content_type="QUESTION", concept_id=concept.id, title="Draft", slug=f"draft-{uuid.uuid4().hex[:8]}",
        language="en", status="DRAFT",
    )
    db_session.add(item)
    await db_session.commit()

    service = TutorService(db_session)
    with pytest.raises(NotFoundError):
        await service.explain_question(question_id=item.id, user_id=uuid.uuid4())


async def test_explain_question_404s_for_nonexistent_question(db_session):
    service = TutorService(db_session)
    with pytest.raises(NotFoundError):
        await service.explain_question(question_id=uuid.uuid4(), user_id=uuid.uuid4())


async def test_explain_question_endpoint_requires_authentication(client):
    resp = await client.post("/api/v1/ai/tutor/explain-question", json={"question_id": str(uuid.uuid4())})
    assert resp.status_code == 401
