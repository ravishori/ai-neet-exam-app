import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.modules.ingestion.models import IngestionJob
from app.modules.ingestion.repositories.ingestion_repository import IngestionRepository
from app.modules.ingestion.schemas.ingestion import StartIngestionJobRequest
from app.modules.ingestion.services.ingestion_pipeline_service import IngestionPipelineService
from app.modules.system.services.audit_service import AuditService, request_context
from app.shared.responses import envelope

logger = get_logger("ingestion")
router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"], dependencies=[Depends(get_current_user)])

# Real PDF upload (PR 1 of the vertical-slice roadmap — Architecture Blueprint
# v1.0 §12 Phase 1). Uploaded files never overwrite the developer-managed
# StudyMaterial tree; they land in their own subdirectory instead.
UPLOAD_SUBDIR = "Uploads"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB — generous for a textbook chapter, bounded against abuse
PDF_MAGIC = b"%PDF-"
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _resolve_and_guard_path(raw_path: str) -> str:
    """Rejects anything outside STUDY_MATERIAL_DIR — this endpoint reads
    arbitrary files off disk by path, so path traversal is a real risk
    even though it's already gated behind content.create (ADR-0022)."""
    settings = get_settings()
    study_material_root = Path(settings.study_material_dir).resolve()
    resolved = Path(raw_path).resolve()
    if study_material_root not in resolved.parents and resolved != study_material_root:
        raise AppError("file_path must be inside the configured study material directory", code="INVALID_PATH", status_code=400)
    if not resolved.is_file():
        raise NotFoundError(f"File not found: {resolved}")
    return str(resolved)


def _safe_upload_filename(original_filename: str) -> str:
    """A random prefix guarantees uniqueness (two uploads of "chapter3.pdf"
    must not collide); stripping to a safe character set is defense in
    depth against a malicious filename, even though the prefix alone
    already prevents path traversal from ever reaching a real directory
    boundary."""
    base = Path(original_filename).name  # strip any directory components
    safe = _UNSAFE_FILENAME_CHARS.sub("_", base) or "upload.pdf"
    return f"{uuid.uuid4().hex}_{safe}"


async def _save_uploaded_pdf(file: UploadFile) -> str:
    header = await file.read(len(PDF_MAGIC))
    if header != PDF_MAGIC:
        raise AppError("Uploaded file is not a valid PDF", code="INVALID_FILE_TYPE", status_code=400)

    settings = get_settings()
    upload_dir = Path(settings.study_material_dir) / UPLOAD_SUBDIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_dir / _safe_upload_filename(file.filename or "upload.pdf")

    written = 0
    with open(dest_path, "wb") as out:
        out.write(header)
        written += len(header)
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                out.close()
                dest_path.unlink(missing_ok=True)
                raise AppError(
                    f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit",
                    code="FILE_TOO_LARGE",
                    status_code=400,
                )
            out.write(chunk)

    return str(dest_path)


def _job(job: IngestionJob) -> dict:
    return {
        "id": str(job.id),
        "source_file_path": job.source_file_path,
        "original_filename": job.original_filename,
        "status": job.status,
        "stage_detail": job.stage_detail,
        "error_message": job.error_message,
        "sections_detected": job.sections_detected,
        "questions_generated": job.questions_generated,
        "questions_deduped": job.questions_deduped,
        "flashcards_generated": job.flashcards_generated,
        "notes_generated": job.notes_generated,
        "revision_sheets_generated": job.revision_sheets_generated,
        "knowledge_units_created": job.knowledge_units_created,
        "knowledge_units_rejected": job.knowledge_units_rejected,
        "visual_assets_detected": job.visual_assets_detected,
        "visual_assets_needing_review": job.visual_assets_needing_review,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


async def _run_pipeline_in_background(job_id: uuid.UUID, author_id: uuid.UUID) -> None:
    """Opens its own session — the request-scoped one from Depends(get_db)
    is torn down once the response is sent, long before this runs."""
    async with AsyncSessionLocal() as session:
        pipeline = IngestionPipelineService(session)
        await pipeline.run(job_id=job_id, author_id=author_id)


@router.post(
    "/jobs",
    dependencies=[Depends(require_permission("content.create")), Depends(verify_csrf)],
)
async def start_ingestion_job(
    payload: StartIngestionJobRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resolved_path = _resolve_and_guard_path(payload.file_path)
    pipeline = IngestionPipelineService(db)
    job = await pipeline.start_job(file_path=resolved_path, chapter_code=payload.chapter_code)

    if job.status != "COMPLETED":
        background_tasks.add_task(_run_pipeline_in_background, job.id, user.id)

    return envelope(success=True, data=_job(job), status_code=202)


@router.post(
    "/upload",
    dependencies=[Depends(require_permission("content.create")), Depends(verify_csrf)],
)
async def upload_ingestion_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    chapter_code: str = Form(..., min_length=1, max_length=80),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Real PDF upload — see Architecture Blueprint v1.0 §12 Phase 1. The
    pre-existing path-based /jobs endpoint required a file already placed
    on the server's filesystem by a developer; this endpoint is the actual
    product-facing "upload a PDF" flow, saving the file itself before
    handing off to the same start_job/background-run path used by /jobs."""
    saved_path = await _save_uploaded_pdf(file)
    pipeline = IngestionPipelineService(db)
    job = await pipeline.start_job(file_path=saved_path, chapter_code=chapter_code, original_filename=file.filename)

    if job.status != "COMPLETED":
        background_tasks.add_task(_run_pipeline_in_background, job.id, user.id)

    return envelope(success=True, data=_job(job), status_code=202)


@router.get("/jobs", dependencies=[Depends(require_permission("content.create"))])
async def list_ingestion_jobs(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    repo = IngestionRepository(db)
    jobs, total = await repo.list_jobs_paginated(status=status, limit=limit, offset=offset)
    return envelope(success=True, data=[_job(j) for j in jobs], meta={"total": total, "limit": limit, "offset": offset})


@router.get("/jobs/{job_id}", dependencies=[Depends(require_permission("content.create"))])
async def get_ingestion_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = IngestionRepository(db)
    job = await repo.get_job(job_id)
    if not job:
        raise NotFoundError("Ingestion job not found")
    return envelope(success=True, data=_job(job))


@router.get("/jobs/{job_id}/detail", dependencies=[Depends(require_permission("content.create"))])
async def get_ingestion_job_detail(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Admin Portal (PR11) Module 4 — the drill-down view: which sections,
    knowledge units, and visual assets a job actually produced."""
    from app.modules.knowledge.repositories.knowledge_repository import KnowledgeRepository

    repo = IngestionRepository(db)
    job = await repo.get_job(job_id)
    if not job:
        raise NotFoundError("Ingestion job not found")

    sections = await repo.list_sections_for_job(job_id)
    visual_assets = await repo.list_visual_assets_for_job(job_id)
    knowledge_units = await KnowledgeRepository(db).list_for_job(job_id)

    return envelope(
        success=True,
        data={
            **_job(job),
            "sections": [
                {"id": str(s.id), "heading": s.heading, "source_page": s.source_page, "matched_concept_id": str(s.matched_concept_id) if s.matched_concept_id else None}
                for s in sections
            ],
            "knowledge_units": [
                {"id": str(u.id), "summary": u.summary, "validation_status": u.validation_status} for u in knowledge_units
            ],
            "visual_assets": [
                {"id": str(a.id), "asset_type": a.asset_type, "review_status": a.review_status, "source_page": a.source_page}
                for a in visual_assets
            ],
        },
    )


def _visual_asset(asset) -> dict:
    return {
        "id": str(asset.id),
        "job_id": str(asset.job_id),
        "knowledge_unit_id": str(asset.knowledge_unit_id) if asset.knowledge_unit_id else None,
        "source_page": asset.source_page,
        "width_px": asset.width_px,
        "height_px": asset.height_px,
        "asset_type": asset.asset_type,
        "detection_method": asset.detection_method,
        "review_status": asset.review_status,
        "vision_description": asset.vision_description,
        "approved_at": asset.approved_at,
        "approved_by": str(asset.approved_by) if asset.approved_by else None,
        "rejection_reason": asset.rejection_reason,
        "has_image": bool(asset.storage_path),
    }


class RejectVisualAssetRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


_ASSET_CONTENT_TYPE_BY_SUFFIX = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


@router.get("/visual-assets/{asset_id}/image", dependencies=[Depends(require_permission("visual_assets.review"))])
async def get_visual_asset_image_for_review(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Admin-only image stream for the review queue — deliberately NOT
    gated on review_status == VERIFIED like knowledge_router.py's
    student-facing image endpoint, since a reviewer needs to see an
    AUTO_DETECTED/NEEDS_MANUAL_BBOX asset's image *before* approving it."""
    from fastapi.responses import FileResponse

    repo = IngestionRepository(db)
    asset = await repo.get_visual_asset(asset_id)
    if not asset or not asset.storage_path:
        raise NotFoundError("Visual asset not found")

    settings = get_settings()
    assets_root = Path(settings.visual_assets_dir).resolve()
    resolved = Path(asset.storage_path).resolve()
    if assets_root not in resolved.parents and resolved != assets_root:
        raise AppError("Visual asset storage_path is outside the configured directory", code="INVALID_PATH", status_code=500)
    if not resolved.is_file():
        raise NotFoundError("Visual asset file is missing on disk")

    content_type = _ASSET_CONTENT_TYPE_BY_SUFFIX.get(resolved.suffix.lower(), "application/octet-stream")
    return FileResponse(resolved, media_type=content_type)


@router.get("/visual-assets", dependencies=[Depends(require_permission("visual_assets.review"))])
async def list_visual_assets(
    review_status: str | None = None,
    asset_type: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Admin Portal (PR11) Module 5 — Visual Asset Review queue."""
    repo = IngestionRepository(db)
    assets, total = await repo.list_visual_assets_paginated(
        review_status=review_status, asset_type=asset_type, limit=limit, offset=offset
    )
    return envelope(success=True, data=[_visual_asset(a) for a in assets], meta={"total": total, "limit": limit, "offset": offset})


@router.post(
    "/visual-assets/{asset_id}/approve",
    dependencies=[Depends(require_permission("visual_assets.review")), Depends(verify_csrf)],
)
async def approve_visual_asset(
    asset_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    repo = IngestionRepository(db)
    asset = await repo.get_visual_asset(asset_id)
    if not asset:
        raise NotFoundError("Visual asset not found")

    asset.review_status = "VERIFIED"
    asset.approved_at = datetime.now(UTC)
    asset.approved_by = user.id
    asset.rejection_reason = None
    await repo.commit()

    await AuditService(db).log(
        actor_user_id=user.id,
        action="visual_asset.approve",
        entity_type="visual_asset",
        entity_id=asset_id,
        **request_context(request),
    )
    return envelope(success=True, data=_visual_asset(asset))


@router.post(
    "/visual-assets/{asset_id}/reject",
    dependencies=[Depends(require_permission("visual_assets.review")), Depends(verify_csrf)],
)
async def reject_visual_asset(
    asset_id: uuid.UUID,
    payload: RejectVisualAssetRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = IngestionRepository(db)
    asset = await repo.get_visual_asset(asset_id)
    if not asset:
        raise NotFoundError("Visual asset not found")

    asset.review_status = "REJECTED"
    asset.approved_at = datetime.now(UTC)
    asset.approved_by = user.id
    asset.rejection_reason = payload.reason
    await repo.commit()

    await AuditService(db).log(
        actor_user_id=user.id,
        action="visual_asset.reject",
        entity_type="visual_asset",
        entity_id=asset_id,
        metadata={"reason": payload.reason},
        **request_context(request),
    )
    return envelope(success=True, data=_visual_asset(asset))
