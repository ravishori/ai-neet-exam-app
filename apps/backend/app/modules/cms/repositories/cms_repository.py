import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.cms.models import ContentItem, ContentReview, ContentVersion, ContentVersionKnowledgeUnit


class CmsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add_item(self, item: ContentItem) -> None:
        self.session.add(item)

    def add_version(self, version: ContentVersion) -> None:
        self.session.add(version)

    def add_review(self, review: ContentReview) -> None:
        self.session.add(review)

    def add_knowledge_unit_ref(self, ref: ContentVersionKnowledgeUnit) -> None:
        self.session.add(ref)

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

    async def list_questions(
        self,
        *,
        scope_type: str | None = None,
        scope_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ContentItem], int]:
        """Published questions only, optionally narrowed to one Subject/Chapter/Topic/Concept.

        Mirrors the scope-join pattern in assessment_repository.published_question_ids_for_scope,
        extended with a TOPIC level for the question browser's filter UI.
        """
        from app.modules.academic.models import Chapter, Concept, Topic

        base = select(ContentItem).where(ContentItem.content_type == "QUESTION", ContentItem.status == "PUBLISHED")
        count_query = select(func.count(ContentItem.id)).where(
            ContentItem.content_type == "QUESTION", ContentItem.status == "PUBLISHED"
        )

        if scope_type == "CONCEPT":
            base = base.where(ContentItem.concept_id == scope_id)
            count_query = count_query.where(ContentItem.concept_id == scope_id)
        elif scope_type == "TOPIC":
            base = base.join(Concept, Concept.id == ContentItem.concept_id).where(Concept.topic_id == scope_id)
            count_query = count_query.join(Concept, Concept.id == ContentItem.concept_id).where(Concept.topic_id == scope_id)
        elif scope_type == "CHAPTER":
            base = (
                base.join(Concept, Concept.id == ContentItem.concept_id)
                .join(Topic, Topic.id == Concept.topic_id)
                .where(Topic.chapter_id == scope_id)
            )
            count_query = (
                count_query.join(Concept, Concept.id == ContentItem.concept_id)
                .join(Topic, Topic.id == Concept.topic_id)
                .where(Topic.chapter_id == scope_id)
            )
        elif scope_type == "SUBJECT":
            base = (
                base.join(Concept, Concept.id == ContentItem.concept_id)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .where(Chapter.subject_id == scope_id)
            )
            count_query = (
                count_query.join(Concept, Concept.id == ContentItem.concept_id)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .where(Chapter.subject_id == scope_id)
            )
        # scope_type None: no extra filter, browse everything published

        total = (await self.session.execute(count_query)).scalar_one()
        base = base.options(selectinload(ContentItem.versions)).order_by(ContentItem.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(base)
        return list(result.scalars().unique().all()), total

    async def academic_names_for_concepts(self, concept_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
        """Batch-load Concept/Topic/Chapter/Subject names for a page of questions.

        One extra query per page rather than joining names into the paginated
        question query itself, which would otherwise mix ORM entity + scalar
        columns and complicate the limit/offset pagination above.
        """
        from app.modules.academic.models import Chapter, Concept, Subject, Topic

        if not concept_ids:
            return {}
        result = await self.session.execute(
            select(
                Concept.id,
                Concept.name.label("concept_name"),
                Topic.id.label("topic_id"),
                Topic.name.label("topic_name"),
                Chapter.id.label("chapter_id"),
                Chapter.name.label("chapter_name"),
                Subject.id.label("subject_id"),
                Subject.name.label("subject_name"),
            )
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(Concept.id.in_(concept_ids))
        )
        return {
            row.id: {
                "concept": {"id": str(row.id), "name": row.concept_name},
                "topic": {"id": str(row.topic_id), "name": row.topic_name},
                "chapter": {"id": str(row.chapter_id), "name": row.chapter_name},
                "subject": {"id": str(row.subject_id), "name": row.subject_name},
            }
            for row in result.all()
        }

    async def visual_assets_for_knowledge_units(self, knowledge_unit_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
        """Question images (PR 7) — reuses the existing VisualAsset.knowledge_unit_id
        FK (ADR-0026) and ContentVersion.knowledge_unit_id (ADR-0025) rather than
        adding a new column: a question generated from exactly one KnowledgeUnit
        already links to it, and a VisualAsset detected alongside that same KU
        already links to it too. Only VERIFIED assets — review_status carries the
        approve/reject decision, and nothing here should surface an unreviewed or
        rejected crop to a student.
        """
        from app.modules.ingestion.models.visual_asset import VisualAsset

        if not knowledge_unit_ids:
            return {}
        result = await self.session.execute(
            select(VisualAsset).where(
                VisualAsset.knowledge_unit_id.in_(knowledge_unit_ids), VisualAsset.review_status == "VERIFIED"
            )
        )
        by_ku: dict[uuid.UUID, list[dict]] = {}
        for asset in result.scalars().all():
            by_ku.setdefault(asset.knowledge_unit_id, []).append(
                {
                    "id": str(asset.id),
                    "asset_type": asset.asset_type,
                    "alt_text": asset.vision_description,
                    "width_px": asset.width_px,
                    "height_px": asset.height_px,
                }
            )
        return by_ku

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
