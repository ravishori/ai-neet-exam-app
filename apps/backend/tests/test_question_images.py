"""Integration tests: question images (PR 7).

Reuses the existing VisualAsset.knowledge_unit_id / ContentVersion.knowledge_unit_id
FKs (ADR-0025/ADR-0026) rather than a new column — see cms_repository.py's
visual_assets_for_knowledge_units() docstring.
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _publish_question(client, concept_id: str) -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Image test question",
            "slug": f"image-test-question-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": {
                "stem": "What does the diagram show?",
                "options": [{"label": "A", "text": "x"}, {"label": "B", "text": "y"}],
                "correct_option": "A",
                "explanation": "n/a",
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


async def _link_question_to_knowledge_unit(db_session, *, question_id: str, concept_id: str) -> uuid.UUID:
    """Sets the *singular* ContentVersion.knowledge_unit_id FK a real
    ingestion run populates when exactly one KU contributed (ADR-0025) —
    what visual_assets_for_knowledge_units() actually joins against."""
    from app.modules.cms.models import ContentItem, ContentVersion
    from app.modules.ingestion.models import IngestionJob, IngestionSection
    from app.modules.knowledge.models import KnowledgeUnit

    job = IngestionJob(source_file_path="test.pdf", file_checksum=uuid.uuid4().hex, status="STRUCTURING")
    db_session.add(job)
    await db_session.flush()

    section = IngestionSection(
        job_id=job.id,
        heading="Test section",
        source_page=1,
        raw_text="Some source text.",
        matched_concept_id=uuid.UUID(concept_id),
    )
    db_session.add(section)
    await db_session.flush()

    unit = KnowledgeUnit(
        version=1,
        content_hash=uuid.uuid4().hex,
        structured_facts=["A fact."],
        summary="A summary.",
        source_section_id=section.id,
        concept_id=uuid.UUID(concept_id),
        extraction_confidence=0.95,
        validation_status="PASSED",
    )
    db_session.add(unit)
    await db_session.flush()

    item = await db_session.get(ContentItem, uuid.UUID(question_id))
    version = await db_session.get(ContentVersion, item.current_version_id)
    version.knowledge_unit_id = unit.id
    version.knowledge_unit_version = 1
    await db_session.commit()
    return unit.id


async def _create_visual_asset(db_session, *, job_id, knowledge_unit_id, review_status: str, with_real_file: bool) -> tuple[uuid.UUID, Path | None]:
    from app.core.config import get_settings
    from app.modules.ingestion.models.visual_asset import VisualAsset

    file_path = None
    storage_path = None
    if with_real_file:
        settings = get_settings()
        assets_dir = Path(settings.visual_assets_dir)
        assets_dir.mkdir(parents=True, exist_ok=True)
        file_path = assets_dir / f"test-{uuid.uuid4().hex}.png"
        # Minimal valid PNG signature + IHDR-less body is not required —
        # FileResponse only needs real bytes on disk, not a decodable image.
        file_path.write_bytes(b"\x89PNG\r\n\x1a\nTEST-IMAGE-BYTES")
        storage_path = str(file_path)

    asset = VisualAsset(
        job_id=job_id,
        knowledge_unit_id=knowledge_unit_id,
        source_page=1,
        asset_type="diagram",
        detection_method="manual",
        review_status=review_status,
        storage_path=storage_path,
        vision_description="A labeled circuit diagram.",
        width_px=400,
        height_px=300,
    )
    db_session.add(asset)
    await db_session.commit()
    return asset.id, file_path


async def test_verified_image_appears_on_browse_and_detail(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)
    ku_id = await _link_question_to_knowledge_unit(db_session, question_id=question_id, concept_id=concept_id)

    from app.modules.ingestion.models import IngestionJob

    job_result = await db_session.execute(select(IngestionJob.id).limit(1))
    job_id = job_result.scalars().first()

    asset_id, file_path = await _create_visual_asset(
        db_session, job_id=job_id, knowledge_unit_id=ku_id, review_status="VERIFIED", with_real_file=True
    )
    try:
        detail = await client.get(f"/api/v1/cms/questions/{question_id}")
        assert detail.status_code == 200, detail.text
        images = detail.json()["data"]["images"]
        assert len(images) == 1
        assert images[0]["id"] == str(asset_id)
        assert images[0]["alt_text"] == "A labeled circuit diagram."

        browse = await client.get("/api/v1/cms/questions", params={"scope_type": "CONCEPT", "scope_id": concept_id})
        assert browse.status_code == 200, browse.text
        matched = next(q for q in browse.json()["data"] if q["id"] == question_id)
        assert len(matched["images"]) == 1
    finally:
        if file_path:
            file_path.unlink(missing_ok=True)


async def test_unverified_visual_asset_never_appears(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)
    ku_id = await _link_question_to_knowledge_unit(db_session, question_id=question_id, concept_id=concept_id)

    from app.modules.ingestion.models import IngestionJob

    job_result = await db_session.execute(select(IngestionJob.id).limit(1))
    job_id = job_result.scalars().first()

    await _create_visual_asset(
        db_session, job_id=job_id, knowledge_unit_id=ku_id, review_status="AUTO_DETECTED", with_real_file=False
    )

    detail = await client.get(f"/api/v1/cms/questions/{question_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["images"] == []


async def test_image_endpoint_serves_verified_asset(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)
    ku_id = await _link_question_to_knowledge_unit(db_session, question_id=question_id, concept_id=concept_id)

    from app.modules.ingestion.models import IngestionJob

    job_result = await db_session.execute(select(IngestionJob.id).limit(1))
    job_id = job_result.scalars().first()

    asset_id, file_path = await _create_visual_asset(
        db_session, job_id=job_id, knowledge_unit_id=ku_id, review_status="VERIFIED", with_real_file=True
    )
    try:
        resp = await client.get(f"/api/v1/knowledge/visual-assets/{asset_id}/image")
        assert resp.status_code == 200, resp.text
        assert resp.content == b"\x89PNG\r\n\x1a\nTEST-IMAGE-BYTES"
        assert resp.headers["content-type"] == "image/png"
    finally:
        if file_path:
            file_path.unlink(missing_ok=True)


async def test_image_endpoint_404s_for_unverified_asset(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)
    ku_id = await _link_question_to_knowledge_unit(db_session, question_id=question_id, concept_id=concept_id)

    from app.modules.ingestion.models import IngestionJob

    job_result = await db_session.execute(select(IngestionJob.id).limit(1))
    job_id = job_result.scalars().first()

    asset_id, file_path = await _create_visual_asset(
        db_session, job_id=job_id, knowledge_unit_id=ku_id, review_status="REJECTED", with_real_file=True
    )
    try:
        resp = await client.get(f"/api/v1/knowledge/visual-assets/{asset_id}/image")
        assert resp.status_code == 404
    finally:
        if file_path:
            file_path.unlink(missing_ok=True)


async def test_image_endpoint_requires_authentication(client):
    resp = await client.get(f"/api/v1/knowledge/visual-assets/{uuid.uuid4()}/image")
    assert resp.status_code == 401


async def test_image_endpoint_rejects_path_outside_visual_assets_dir(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    question_id = await _publish_question(client, concept_id)
    ku_id = await _link_question_to_knowledge_unit(db_session, question_id=question_id, concept_id=concept_id)

    from app.modules.ingestion.models import IngestionJob
    from app.modules.ingestion.models.visual_asset import VisualAsset

    job_result = await db_session.execute(select(IngestionJob.id).limit(1))
    job_id = job_result.scalars().first()

    asset = VisualAsset(
        job_id=job_id,
        knowledge_unit_id=ku_id,
        source_page=1,
        asset_type="diagram",
        detection_method="manual",
        review_status="VERIFIED",
        storage_path="/etc/passwd",
    )
    db_session.add(asset)
    await db_session.commit()

    resp = await client.get(f"/api/v1/knowledge/visual-assets/{asset.id}/image")
    assert resp.status_code == 500  # rejected as outside the configured directory, not silently served
