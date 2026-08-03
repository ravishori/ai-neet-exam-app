import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.cms.repositories.search_repository import SearchRepository
from app.modules.cms.services.search_service import SearchService
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.modules.system.services.audit_service import AuditService, request_context
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/cms", tags=["search"])


def _resolve_scope(
    subject_id: uuid.UUID | None, chapter_id: uuid.UUID | None, topic_id: uuid.UUID | None, concept_id: uuid.UUID | None
) -> tuple[str | None, uuid.UUID | None]:
    """Most-specific wins — same convention as the question browser (PR 2).
    A question has exactly one concept -> topic -> chapter -> subject, so
    passing more than one of these is redundant, not a real AND filter."""
    if concept_id:
        return "CONCEPT", concept_id
    if topic_id:
        return "TOPIC", topic_id
    if chapter_id:
        return "CHAPTER", chapter_id
    if subject_id:
        return "SUBJECT", subject_id
    return None, None


@router.get("/search", dependencies=[Depends(require_permission("questions.read"))])
async def search_questions(
    q: str = Query(..., min_length=1, max_length=200),
    subject_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
    concept_id: uuid.UUID | None = None,
    difficulty: str | None = None,
    pyq_year: int | None = None,
    content_type: str = "QUESTION",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    scope_type, scope_id = _resolve_scope(subject_id, chapter_id, topic_id, concept_id)
    service = SearchService(db)
    result = await service.search(
        query=q,
        scope_type=scope_type,
        scope_id=scope_id,
        difficulty=difficulty,
        pyq_year=pyq_year,
        content_type=content_type,
        limit=limit,
        offset=offset,
    )
    return envelope(
        success=True,
        data=result.data,
        meta={
            "total": result.total,
            "limit": result.limit,
            "offset": result.offset,
            "search_mode": result.search_mode,
            "query": result.query,
        },
    )


@router.post("/search/reindex", dependencies=[Depends(require_permission("search.admin")), Depends(verify_csrf)])
async def reindex_search(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Admin Portal (PR11) Module 7 — exposes SearchRepository.reindex_all_published(),
    which already existed as "an admin catch-up operation if search_text/
    search_vector ever drift" (its own docstring) but had no endpoint."""
    repo = SearchRepository(db)
    count = await repo.reindex_all_published()

    await AuditService(db).log(
        actor_user_id=user.id,
        action="search.reindex",
        metadata={"reindexed_count": count},
        **request_context(request),
    )
    return envelope(success=True, data={"reindexed_count": count})
