"""WAVE-P0-11B: SME PHY edit payloads validate; update_draft preserves provenance."""

from __future__ import annotations

import uuid

from helpers_publishable_question import publishable_question_body

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.cms.acquisition.batch_a_acquisition_service import BatchAAcquisitionService
from app.modules.cms.acquisition.batch_a_catalog import BATCH_A_QUESTIONS
from app.modules.cms.acquisition.phy_sme_edits import PHY_SME_EDITS
from app.modules.cms.models import ContentItem
from app.modules.cms.schemas.content_bodies import assert_body_publishable
from app.modules.cms.services.content_workflow_service import ContentWorkflowService

pytestmark = pytest.mark.asyncio(loop_scope="session")


def test_all_phy_sme_payloads_structurally_valid():
    assert len(PHY_SME_EDITS) == 10
    labels = {e["label"] for e in PHY_SME_EDITS}
    assert labels == {f"PHY-{i:02d}" for i in range(1, 11)}
    for edit in PHY_SME_EDITS:
        assert_body_publishable("QUESTION", edit["body"])


async def test_update_draft_preserves_model_used(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    catalog = [
        {
            **BATCH_A_QUESTIONS[0],
            "source_key": f"sme-edit-{uuid.uuid4().hex[:8]}",
            "stem": f"Preserve provenance stem {uuid.uuid4().hex}?",
            "title": "Provenance preserve test",
        }
    ]
    report = await BatchAAcquisitionService(db_session).run(author_id=author_id, questions=catalog)
    await db_session.commit()
    item_id = uuid.UUID(report["created_items"][0]["id"])

    item = (
        await db_session.execute(
            select(ContentItem).options(selectinload(ContentItem.versions)).where(ContentItem.id == item_id)
        )
    ).scalar_one()
    latest = {v.id: v for v in item.versions}[item.latest_version_id]
    assert latest.model_used == "human-authored-batch-a"

    body = {
        "stem": "Updated stem for provenance test?",
        "options": [
            {"label": "A", "text": "One"},
            {"label": "B", "text": "Two"},
            {"label": "C", "text": "Three"},
            {"label": "D", "text": "Four"},
        ],
        "correct_option": "B",
        "explanation": "Updated explanation retaining provenance.",
        "difficulty": "easy",
    }
    updated = await ContentWorkflowService(db_session).update_draft(
        item_id,
        body=body,
        change_summary="test provenance preserve",
        author_id=author_id,
        title="Updated title",
        commit=True,
    )
    assert updated.status == "DRAFT"
    # Expire so relationship reload includes the new version row
    db_session.expire_all()
    refreshed = (
        await db_session.execute(
            select(ContentItem).options(selectinload(ContentItem.versions)).where(ContentItem.id == item_id)
        )
    ).scalar_one()
    latest2 = next(v for v in refreshed.versions if v.id == refreshed.latest_version_id)
    assert latest2.model_used == "human-authored-batch-a"
    assert latest2.prompt_version == latest.prompt_version
    assert latest2.version_no == latest.version_no + 1
    assert refreshed.title == "Updated title"
