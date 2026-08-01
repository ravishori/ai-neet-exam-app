import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.cms.models import ContentItem, ContentReview, ContentVersion


class CmsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add_item(self, item: ContentItem) -> None:
        self.session.add(item)

    def add_version(self, version: ContentVersion) -> None:
        self.session.add(version)

    def add_review(self, review: ContentReview) -> None:
        self.session.add(review)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def get_item(self, item_id: uuid.UUID) -> ContentItem | None:
        result = await self.session.execute(
            select(ContentItem).options(selectinload(ContentItem.versions)).where(ContentItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def list_items(
        self,
        *,
        content_type: str | None = None,
        concept_id: uuid.UUID | None = None,
        status: str | None = None,
        language: str | None = None,
    ) -> list[ContentItem]:
        query = select(ContentItem).options(selectinload(ContentItem.versions)).order_by(ContentItem.created_at.desc())
        if content_type:
            query = query.where(ContentItem.content_type == content_type)
        if concept_id:
            query = query.where(ContentItem.concept_id == concept_id)
        if status:
            query = query.where(ContentItem.status == status)
        if language:
            query = query.where(ContentItem.language == language)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_version(self, version_id: uuid.UUID) -> ContentVersion | None:
        result = await self.session.execute(select(ContentVersion).where(ContentVersion.id == version_id))
        return result.scalar_one_or_none()

    async def list_versions(self, item_id: uuid.UUID) -> list[ContentVersion]:
        result = await self.session.execute(
            select(ContentVersion).where(ContentVersion.content_item_id == item_id).order_by(ContentVersion.version_no)
        )
        return list(result.scalars().all())

    async def coverage(self) -> list[dict]:
        """Per-concept content completeness — concept x content_type grid."""
        from app.modules.academic.models import Chapter, Concept, Subject, Topic

        result = await self.session.execute(
            select(
                Concept.id,
                Concept.name,
                Subject.name.label("subject_name"),
                Chapter.name.label("chapter_name"),
            )
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .order_by(Subject.display_order, Chapter.display_order, Concept.display_order)
        )
        concepts = result.all()

        published = await self.session.execute(
            select(ContentItem.concept_id, ContentItem.content_type).where(ContentItem.status == "PUBLISHED")
        )
        published_by_concept: dict[uuid.UUID, set[str]] = {}
        for concept_id, content_type in published.all():
            if concept_id:
                published_by_concept.setdefault(concept_id, set()).add(content_type)

        return [
            {
                "concept_id": str(c.id),
                "concept_name": c.name,
                "subject_name": c.subject_name,
                "chapter_name": c.chapter_name,
                "published_content_types": sorted(published_by_concept.get(c.id, set())),
            }
            for c in concepts
        ]
