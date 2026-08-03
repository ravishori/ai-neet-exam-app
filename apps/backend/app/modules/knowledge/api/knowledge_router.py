import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.modules.identity.dependencies import require_permission
from app.modules.ingestion.models.visual_asset import VisualAsset
from app.modules.knowledge.models import KnowledgeUnit
from app.modules.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _unit_summary(unit: KnowledgeUnit, concept_name: str | None = None) -> dict:
    return {
        "id": str(unit.id),
        "version": unit.version,
        "summary": unit.summary,
        "concept_id": str(unit.concept_id),
        "concept_name": concept_name,
        "extraction_confidence": unit.extraction_confidence,
        "validation_status": unit.validation_status,
        "validation_detail": unit.validation_detail,
        "superseded_by": str(unit.superseded_by) if unit.superseded_by else None,
        "created_at": unit.created_at,
    }

_CONTENT_TYPE_BY_SUFFIX = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


@router.get("/visual-assets/{asset_id}/image", dependencies=[Depends(require_permission("questions.read"))])
async def get_visual_asset_image(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Streams a detected visual asset's image file — question content, so
    gated the same as browsing/searching questions (PR2/PR3), not a separate
    permission. Only ever serves VERIFIED assets: review_status carries the
    approve/reject decision (ADR-0026/ADR-0028), and nothing here should let
    a student see an unreviewed or rejected crop."""
    result = await db.execute(select(VisualAsset).where(VisualAsset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset or asset.review_status != "VERIFIED" or not asset.storage_path:
        raise NotFoundError("Visual asset not found")

    settings = get_settings()
    assets_root = Path(settings.visual_assets_dir).resolve()
    resolved = Path(asset.storage_path).resolve()
    if assets_root not in resolved.parents and resolved != assets_root:
        raise AppError("Visual asset storage_path is outside the configured directory", code="INVALID_PATH", status_code=500)
    if not resolved.is_file():
        raise NotFoundError("Visual asset file is missing on disk")

    content_type = _CONTENT_TYPE_BY_SUFFIX.get(resolved.suffix.lower(), "application/octet-stream")
    return FileResponse(resolved, media_type=content_type)


@router.get("/units", dependencies=[Depends(require_permission("knowledge.manage"))])
async def list_knowledge_units(
    validation_status: str | None = None,
    concept_id: uuid.UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Admin Portal (PR11) Module 3 — first-ever list view over
    KnowledgeUnit; previously every consumer only fetched units scoped to a
    single concept (AI Tutor, content generation)."""
    from app.modules.academic.models import Concept

    repo = KnowledgeRepository(db)
    units, total = await repo.list_paginated(validation_status=validation_status, concept_id=concept_id, limit=limit, offset=offset)

    concept_ids = {u.concept_id for u in units}
    names: dict[uuid.UUID, str] = {}
    if concept_ids:
        result = await db.execute(select(Concept.id, Concept.name).where(Concept.id.in_(concept_ids)))
        names = dict(result.all())

    return envelope(
        success=True,
        data=[_unit_summary(u, names.get(u.concept_id)) for u in units],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/units/{unit_id}", dependencies=[Depends(require_permission("knowledge.manage"))])
async def get_knowledge_unit(unit_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.modules.academic.models import Concept
    from app.modules.ingestion.models import IngestionSection

    repo = KnowledgeRepository(db)
    unit = await repo.get(unit_id)
    if not unit:
        raise NotFoundError("Knowledge unit not found")

    concept = await db.get(Concept, unit.concept_id)
    section = await db.get(IngestionSection, unit.source_section_id)
    visual_assets = await repo.get_visual_assets_for_knowledge_unit(unit_id)
    chain = await repo.get_supersede_chain(unit_id)

    return envelope(
        success=True,
        data={
            **_unit_summary(unit, concept.name if concept else None),
            "structured_facts": unit.structured_facts,
            "source_section": {
                "id": str(section.id),
                "heading": section.heading,
                "source_page": section.source_page,
            }
            if section
            else None,
            "visual_assets": [
                {"id": str(a.id), "asset_type": a.asset_type, "review_status": a.review_status} for a in visual_assets
            ],
            "supersede_chain": [str(u.id) for u in chain if u.id != unit_id],
        },
    )
