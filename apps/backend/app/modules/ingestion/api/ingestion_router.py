import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
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
from app.shared.responses import envelope

logger = get_logger("ingestion")
router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"], dependencies=[Depends(get_current_user)])


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


def _job(job: IngestionJob) -> dict:
    return {
        "id": str(job.id),
        "source_file_path": job.source_file_path,
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


@router.get("/jobs", dependencies=[Depends(require_permission("content.create"))])
async def list_ingestion_jobs(db: AsyncSession = Depends(get_db)):
    repo = IngestionRepository(db)
    jobs = await repo.list_jobs()
    return envelope(success=True, data=[_job(j) for j in jobs])


@router.get("/jobs/{job_id}", dependencies=[Depends(require_permission("content.create"))])
async def get_ingestion_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = IngestionRepository(db)
    job = await repo.get_job(job_id)
    if not job:
        raise NotFoundError("Ingestion job not found")
    return envelope(success=True, data=_job(job))
