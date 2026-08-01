import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.modules.cms.models import ContentItem, ContentVersion
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.schemas.content_item import ContentItemCreateRequest, ContentItemUpdateRequest, ReviewDecisionRequest
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/cms", tags=["cms"])


def _version(v: ContentVersion | None) -> dict | None:
    if not v:
        return None
    return {
        "id": str(v.id),
        "version_no": v.version_no,
        "body": v.body,
        "workflow_state": v.workflow_state,
        "ai_check_report": v.ai_check_report,
        "change_summary": v.change_summary,
        "authored_by": str(v.authored_by) if v.authored_by else None,
        "authored_at": v.authored_at,
    }


def _item(item: ContentItem) -> dict:
    by_id = {v.id: v for v in item.versions}
    return {
        "id": str(item.id),
        "content_type": item.content_type,
        "concept_id": str(item.concept_id) if item.concept_id else None,
        "title": item.title,
        "slug": item.slug,
        "tags": item.tags,
        "language": item.language,
        "status": item.status,
        "created_by": str(item.created_by) if item.created_by else None,
        "current_version": _version(by_id.get(item.current_version_id)),
        "latest_version": _version(by_id.get(item.latest_version_id)),
    }


def _can_edit(item: ContentItem, user: User) -> bool:
    return "SUPER_ADMIN" in user.role_codes or "ADMIN" in user.role_codes or item.created_by == user.id


@router.post("/content-items", dependencies=[Depends(require_permission("content.create")), Depends(verify_csrf)])
async def create_content_item(
    payload: ContentItemCreateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    service = ContentWorkflowService(db)
    concept_id = uuid.UUID(payload.concept_id) if payload.concept_id else None
    item = await service.create_item(
        content_type=payload.content_type,
        concept_id=concept_id,
        title=payload.title,
        slug=payload.slug,
        tags=payload.tags,
        language=payload.language,
        body=payload.body,
        author_id=user.id,
    )
    return envelope(success=True, data=_item(item), status_code=201)


@router.get("/content-items", dependencies=[Depends(require_permission("content.create"))])
async def list_content_items(
    content_type: str | None = None,
    concept_id: uuid.UUID | None = None,
    status: str | None = None,
    mine: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = CmsRepository(db)
    items = await repo.list_items(content_type=content_type, concept_id=concept_id, status=status)
    if mine:
        items = [i for i in items if i.created_by == user.id]
    return envelope(success=True, data=[_item(i) for i in items])


@router.get("/content-items/{item_id}", dependencies=[Depends(require_permission("content.create"))])
async def get_content_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = CmsRepository(db)
    item = await repo.get_item(item_id)
    if not item:
        raise NotFoundError("Content item not found")
    return envelope(success=True, data=_item(item))


@router.get("/content-items/{item_id}/versions", dependencies=[Depends(require_permission("content.create"))])
async def list_content_versions(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = CmsRepository(db)
    versions = await repo.list_versions(item_id)
    return envelope(success=True, data=[_version(v) for v in versions])


@router.patch("/content-items/{item_id}", dependencies=[Depends(require_permission("content.edit_own_draft")), Depends(verify_csrf)])
async def update_content_item(
    item_id: uuid.UUID, payload: ContentItemUpdateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    repo = CmsRepository(db)
    existing = await repo.get_item(item_id)
    if not existing:
        raise NotFoundError("Content item not found")
    if not _can_edit(existing, user):
        raise PermissionDeniedError("You can only edit your own drafts")

    service = ContentWorkflowService(db)
    item = await service.update_draft(item_id, body=payload.body, change_summary=payload.change_summary, author_id=user.id)
    return envelope(success=True, data=_item(item))


@router.post(
    "/content-items/{item_id}/submit",
    dependencies=[Depends(require_permission("content.submit_for_review")), Depends(verify_csrf)],
)
async def submit_content_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = ContentWorkflowService(db)
    item = await service.submit_for_review(item_id)
    return envelope(success=True, data=_item(item))


@router.post("/content-items/{item_id}/review", dependencies=[Depends(require_permission("content.review")), Depends(verify_csrf)])
async def review_content_item(
    item_id: uuid.UUID, payload: ReviewDecisionRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    service = ContentWorkflowService(db)
    item = await service.review(item_id, reviewer_id=user.id, decision=payload.decision, comment=payload.comment)
    return envelope(success=True, data=_item(item))


@router.post("/content-items/{item_id}/publish", dependencies=[Depends(require_permission("content.publish")), Depends(verify_csrf)])
async def publish_content_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = ContentWorkflowService(db)
    item = await service.publish(item_id)
    return envelope(success=True, data=_item(item))


@router.post("/content-items/{item_id}/archive", dependencies=[Depends(require_permission("content.archive")), Depends(verify_csrf)])
async def archive_content_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = ContentWorkflowService(db)
    item = await service.archive(item_id)
    return envelope(success=True, data=_item(item))


@router.get("/coverage", dependencies=[Depends(require_permission("content.create"))])
async def get_coverage(db: AsyncSession = Depends(get_db)):
    repo = CmsRepository(db)
    return envelope(success=True, data=await repo.coverage())


@router.get("/concepts/{concept_id}/published", dependencies=[Depends(get_current_user)])
async def get_published_content_for_concept(
    concept_id: uuid.UUID,
    language: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Student-facing: every authenticated user can read published content — no editorial permission needed.

    Defaults to the caller's preferred_language (ADR-0019); falls back to
    English with `language_fallback: true` in meta if nothing's been
    translated for this concept yet, rather than returning an empty list.
    """
    requested_language = language or user.preferred_language
    repo = CmsRepository(db)
    items = await repo.list_items(concept_id=concept_id, status="PUBLISHED", language=requested_language)

    language_fallback = False
    if not items and requested_language != "en":
        items = await repo.list_items(concept_id=concept_id, status="PUBLISHED", language="en")
        language_fallback = True

    return envelope(
        success=True,
        data=[_item(i) for i in items],
        meta={"language": requested_language, "language_fallback": language_fallback},
    )
