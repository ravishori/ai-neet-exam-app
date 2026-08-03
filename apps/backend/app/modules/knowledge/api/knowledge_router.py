import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.modules.identity.dependencies import require_permission
from app.modules.ingestion.models.visual_asset import VisualAsset

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

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
