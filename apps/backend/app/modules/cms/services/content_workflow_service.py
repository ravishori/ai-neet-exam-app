import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.cms.models import ContentItem, ContentReview, ContentVersion, ContentVersionKnowledgeUnit
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.repositories.search_repository import SearchRepository
from app.modules.cms.schemas.content_bodies import CONTENT_TYPES, assert_body_publishable
from app.modules.cms.services.ai_check_service import run_ai_check
from app.modules.cms.services.publication_gates import assert_question_publishable

logger = get_logger("cms")

# Actual v1 path (AI_CHECKED does not persist as item.status):
# DRAFT -> IN_REVIEW -> APPROVED -> PUBLISHED -> ARCHIVED
#                  \-> CHANGES_REQUESTED -> DRAFT (after edit)
# Publish re-validates body; QUESTION also requires concept_id.


class ContentWorkflowError(AppError):
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_WORKFLOW_TRANSITION", status_code=409)


class ContentWorkflowService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CmsRepository(session)

    async def create_item(
        self,
        *,
        content_type: str,
        concept_id: uuid.UUID | None,
        title: str,
        slug: str,
        tags: list[str],
        language: str,
        body: dict,
        author_id: uuid.UUID,
        micro_competency_id: uuid.UUID | None = None,
        knowledge_unit_refs: list[tuple[uuid.UUID, int]] | None = None,
        model_used: str | None = None,
        prompt_version: str | None = None,
        confidence_score: float | None = None,
        generation_cost_usd: float | None = None,
    ) -> ContentItem:
        """knowledge_unit_refs is the full set of (knowledge_unit_id, version)
        pairs this content was generated from — see ADR-0025. When there is
        exactly one, it's also mirrored onto the version's singular
        knowledge_unit_id/knowledge_unit_version columns for easy querying;
        with more than one, those two columns stay NULL and the join rows
        below are the only complete record."""
        if content_type not in CONTENT_TYPES:
            raise AppError(f"Unknown content_type: {content_type}", code="INVALID_CONTENT_TYPE", status_code=400)
        validated_body = assert_body_publishable(content_type, body)

        item = ContentItem(
            content_type=content_type,
            concept_id=concept_id,
            micro_competency_id=micro_competency_id,
            title=title,
            slug=slug,
            tags=tags,
            language=language,
            status="DRAFT",
            created_by=author_id,
        )
        self.repo.add_item(item)
        await self.repo.flush()

        refs = knowledge_unit_refs or []
        version = ContentVersion(
            content_item_id=item.id,
            version_no=1,
            body=validated_body,
            workflow_state="DRAFT",
            authored_by=author_id,
            authored_at=datetime.now(UTC),
            knowledge_unit_id=refs[0][0] if len(refs) == 1 else None,
            knowledge_unit_version=refs[0][1] if len(refs) == 1 else None,
            model_used=model_used,
            prompt_version=prompt_version,
            confidence_score=confidence_score,
            generation_cost_usd=generation_cost_usd,
        )
        self.repo.add_version(version)
        await self.repo.flush()

        for unit_id, unit_version in refs:
            self.repo.add_knowledge_unit_ref(
                ContentVersionKnowledgeUnit(
                    content_version_id=version.id, knowledge_unit_id=unit_id, knowledge_unit_version=unit_version
                )
            )

        item.latest_version_id = version.id
        await self.repo.commit()
        logger.info("content_created", item_id=str(item.id), content_type=content_type)
        return await self.repo.get_item(item.id)

    async def update_draft(self, item_id: uuid.UUID, *, body: dict, change_summary: str | None, author_id: uuid.UUID) -> ContentItem:
        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status not in ("DRAFT", "CHANGES_REQUESTED"):
            raise ContentWorkflowError(f"Cannot edit content in state {item.status}")

        validated_body = assert_body_publishable(item.content_type, body)
        next_version_no = max((v.version_no for v in item.versions), default=0) + 1
        by_id = {v.id: v for v in item.versions}
        previous = by_id.get(item.latest_version_id)

        version = ContentVersion(
            content_item_id=item.id,
            version_no=next_version_no,
            body=validated_body,
            workflow_state="DRAFT",
            authored_by=author_id,
            authored_at=datetime.now(UTC),
            change_summary=change_summary,
            # Preserve truthful provenance lineage across draft edits
            knowledge_unit_id=previous.knowledge_unit_id if previous else None,
            knowledge_unit_version=previous.knowledge_unit_version if previous else None,
            model_used=previous.model_used if previous else None,
            prompt_version=previous.prompt_version if previous else None,
            confidence_score=previous.confidence_score if previous else None,
            generation_cost_usd=previous.generation_cost_usd if previous else None,
        )
        self.repo.add_version(version)
        await self.repo.flush()

        item.latest_version_id = version.id
        item.status = "DRAFT"
        await self.repo.commit()
        logger.info("content_draft_updated", item_id=str(item.id), version_no=next_version_no)
        return await self.repo.get_item(item.id)

    async def submit_for_review(self, item_id: uuid.UUID) -> ContentItem:
        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status != "DRAFT":
            raise ContentWorkflowError(f"Cannot submit content in state {item.status}")

        latest = await self.repo.get_version(item.latest_version_id)
        if not latest:
            raise AppError("Content version not found", code="NOT_FOUND", status_code=404)
        # Structural gate before entering the human review queue.
        assert_body_publishable(item.content_type, latest.body)
        if item.content_type == "QUESTION" and not item.concept_id:
            raise AppError(
                "QUESTION must be mapped to a concept before review.",
                code="MISSING_ACADEMIC_MAPPING",
                status_code=422,
            )

        report = await run_ai_check(self.session, content_type=item.content_type, body=latest.body)
        latest.ai_check_report = report
        latest.workflow_state = "IN_REVIEW"  # AI_CHECKED is instantaneous in v1 — see ai_check_service.py
        item.status = "IN_REVIEW"
        await self.repo.commit()
        logger.info("content_submitted", item_id=str(item.id))
        return await self.repo.get_item(item.id)

    async def review(self, item_id: uuid.UUID, *, reviewer_id: uuid.UUID, decision: str, comment: str | None) -> ContentItem:
        if decision not in ("approve", "request_changes"):
            raise AppError("decision must be 'approve' or 'request_changes'", code="INVALID_DECISION", status_code=400)

        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status != "IN_REVIEW":
            raise ContentWorkflowError(f"Cannot review content in state {item.status}")

        latest = await self.repo.get_version(item.latest_version_id)
        self.repo.add_review(
            ContentReview(content_version_id=latest.id, reviewer_id=reviewer_id, decision=decision, comment=comment)
        )

        if decision == "approve":
            latest.workflow_state = "APPROVED"
            item.status = "APPROVED"
        else:
            latest.workflow_state = "CHANGES_REQUESTED"
            item.status = "CHANGES_REQUESTED"

        await self.repo.commit()
        logger.info("content_reviewed", item_id=str(item.id), decision=decision)
        return await self.repo.get_item(item.id)

    async def publish(self, item_id: uuid.UUID) -> ContentItem:
        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status != "APPROVED":
            raise ContentWorkflowError(f"Cannot publish content in state {item.status}")

        latest = await self.repo.get_version(item.latest_version_id)
        if not latest:
            raise AppError("Content version not found", code="NOT_FOUND", status_code=404)

        # WAVE-P0-4 + T6-E-FIX: structural + scientific + NCERT + taxonomy +
        # duplicate + provenance gates — server-side; no frontend-only bypass.
        assert_body_publishable(item.content_type, latest.body)
        if item.content_type == "QUESTION":
            await assert_question_publishable(
                self.session,
                item_id=item.id,
                status=item.status,
                content_type=item.content_type,
                concept_id=item.concept_id,
                body=latest.body,
                tags=list(item.tags or []),
                model_used=latest.model_used,
                knowledge_unit_id=latest.knowledge_unit_id,
            )

        latest.workflow_state = "PUBLISHED"
        item.status = "PUBLISHED"
        item.current_version_id = latest.id
        await self.repo.commit()

        if item.content_type == "QUESTION":
            # PR 3 — search_text/search_vector only ever exist for PUBLISHED
            # questions, mirroring the browse endpoint's PUBLISHED-only rule.
            await SearchRepository(self.session).reindex_item(item.id)

        logger.info("content_published", item_id=str(item.id))
        return await self.repo.get_item(item.id)

    async def archive(self, item_id: uuid.UUID) -> ContentItem:
        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status != "PUBLISHED":
            raise ContentWorkflowError(f"Cannot archive content in state {item.status}")

        item.status = "ARCHIVED"
        if item.current_version_id:
            current = await self.repo.get_version(item.current_version_id)
            current.workflow_state = "ARCHIVED"
        await self.repo.commit()
        logger.info("content_archived", item_id=str(item.id))
        return await self.repo.get_item(item.id)
