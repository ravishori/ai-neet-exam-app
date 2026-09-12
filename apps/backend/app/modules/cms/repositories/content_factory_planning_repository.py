"""FACTORY-P2 planning persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.cms.models.content_factory_planning import (
    ContentBatchBlueprint,
    CoverageSlice,
    LearningObjective,
    QuestionBlueprint,
    QuestionFamily,
)
from app.modules.cms.models.content_item import ContentItem
from app.modules.cms.models.content_version import ContentVersion


class ContentFactoryPlanningRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, obj) -> None:
        self.session.add(obj)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    # --- Learning objectives ---

    async def get_objective_by_key(self, key: str) -> LearningObjective | None:
        result = await self.session.execute(
            select(LearningObjective).where(
                LearningObjective.objective_key == key,
                LearningObjective.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_objective(self, objective_id: uuid.UUID) -> LearningObjective | None:
        result = await self.session.execute(
            select(LearningObjective).where(
                LearningObjective.id == objective_id,
                LearningObjective.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_objectives(
        self,
        *,
        concept_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[LearningObjective], int]:
        filters = [LearningObjective.deleted_at.is_(None)]
        if concept_id:
            filters.append(LearningObjective.concept_id == concept_id)
        total = (await self.session.execute(select(func.count(LearningObjective.id)).where(*filters))).scalar_one()
        result = await self.session.execute(
            select(LearningObjective)
            .where(*filters)
            .order_by(LearningObjective.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    # --- Families ---

    async def get_family_by_key(self, key: str) -> QuestionFamily | None:
        result = await self.session.execute(
            select(QuestionFamily).where(
                QuestionFamily.family_key == key,
                QuestionFamily.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_family(self, family_id: uuid.UUID) -> QuestionFamily | None:
        result = await self.session.execute(
            select(QuestionFamily).where(
                QuestionFamily.id == family_id,
                QuestionFamily.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_families(
        self,
        *,
        subject_code: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[QuestionFamily], int]:
        filters = [QuestionFamily.deleted_at.is_(None)]
        if subject_code:
            filters.append(QuestionFamily.applicable_subject_codes.contains([subject_code.upper()]))
        total = (await self.session.execute(select(func.count(QuestionFamily.id)).where(*filters))).scalar_one()
        result = await self.session.execute(
            select(QuestionFamily)
            .where(*filters)
            .order_by(QuestionFamily.name.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    # --- Blueprints ---

    async def get_blueprint(self, blueprint_id: uuid.UUID) -> QuestionBlueprint | None:
        result = await self.session.execute(
            select(QuestionBlueprint)
            .options(
                selectinload(QuestionBlueprint.learning_objective),
                selectinload(QuestionBlueprint.question_family),
            )
            .where(QuestionBlueprint.id == blueprint_id, QuestionBlueprint.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_blueprint_by_key_version(self, key: str, version: int) -> QuestionBlueprint | None:
        result = await self.session.execute(
            select(QuestionBlueprint)
            .options(
                selectinload(QuestionBlueprint.learning_objective),
                selectinload(QuestionBlueprint.question_family),
            )
            .where(
                QuestionBlueprint.blueprint_key == key,
                QuestionBlueprint.blueprint_version == version,
                QuestionBlueprint.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def latest_blueprint_version(self, key: str) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(QuestionBlueprint.blueprint_version), 0)).where(
                QuestionBlueprint.blueprint_key == key,
                QuestionBlueprint.deleted_at.is_(None),
            )
        )
        return int(result.scalar_one())

    async def list_blueprints(
        self,
        *,
        concept_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[QuestionBlueprint], int]:
        filters = [QuestionBlueprint.deleted_at.is_(None)]
        if concept_id:
            filters.append(QuestionBlueprint.concept_id == concept_id)
        if subject_id:
            filters.append(QuestionBlueprint.subject_id == subject_id)
        if status:
            filters.append(QuestionBlueprint.status == status)
        total = (await self.session.execute(select(func.count(QuestionBlueprint.id)).where(*filters))).scalar_one()
        result = await self.session.execute(
            select(QuestionBlueprint)
            .options(
                selectinload(QuestionBlueprint.learning_objective),
                selectinload(QuestionBlueprint.question_family),
            )
            .where(*filters)
            .order_by(QuestionBlueprint.blueprint_key.asc(), QuestionBlueprint.blueprint_version.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def sum_planned_targets(
        self,
        *,
        subject_id: uuid.UUID,
        concept_id: uuid.UUID | None = None,
        difficulty: str | None = None,
        family_id: uuid.UUID | None = None,
    ) -> int:
        filters = [
            QuestionBlueprint.deleted_at.is_(None),
            QuestionBlueprint.is_active.is_(True),
            QuestionBlueprint.status.in_(("DRAFT", "ACTIVE")),
            QuestionBlueprint.subject_id == subject_id,
        ]
        if concept_id:
            filters.append(QuestionBlueprint.concept_id == concept_id)
        if difficulty:
            filters.append(QuestionBlueprint.difficulty == difficulty)
        if family_id:
            filters.append(QuestionBlueprint.question_family_id == family_id)
        result = await self.session.execute(select(func.coalesce(func.sum(QuestionBlueprint.target_count), 0)).where(*filters))
        return int(result.scalar_one())

    # --- Coverage slices ---

    async def get_slice_by_key(self, key: str) -> CoverageSlice | None:
        result = await self.session.execute(
            select(CoverageSlice).where(CoverageSlice.slice_key == key, CoverageSlice.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_slice(self, slice_id: uuid.UUID) -> CoverageSlice | None:
        result = await self.session.execute(
            select(CoverageSlice).where(CoverageSlice.id == slice_id, CoverageSlice.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_slices(
        self,
        *,
        subject_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CoverageSlice], int]:
        filters = [CoverageSlice.deleted_at.is_(None), CoverageSlice.is_active.is_(True)]
        if subject_id:
            filters.append(CoverageSlice.subject_id == subject_id)
        total = (await self.session.execute(select(func.count(CoverageSlice.id)).where(*filters))).scalar_one()
        result = await self.session.execute(
            select(CoverageSlice)
            .where(*filters)
            .order_by(CoverageSlice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def count_questions_for_concept(
        self,
        concept_id: uuid.UUID,
        *,
        difficulty: str | None = None,
        published_only: bool = False,
    ) -> int:
        filters = [
            ContentItem.content_type == "QUESTION",
            ContentItem.deleted_at.is_(None),
            ContentItem.concept_id == concept_id,
        ]
        if published_only:
            filters.append(ContentItem.status == "PUBLISHED")
        if difficulty:
            # Difficulty lives on version body JSONB
            filters.append(ContentItem.latest_version_id.is_not(None))
            q = (
                select(func.count(ContentItem.id))
                .join(ContentVersion, ContentVersion.id == ContentItem.latest_version_id)
                .where(*filters, ContentVersion.body["difficulty"].astext == difficulty)
            )
        else:
            q = select(func.count(ContentItem.id)).where(*filters)
        return int((await self.session.execute(q)).scalar_one())

    async def get_batch_blueprint_link(
        self, batch_id: uuid.UUID, blueprint_id: uuid.UUID
    ) -> ContentBatchBlueprint | None:
        result = await self.session.execute(
            select(ContentBatchBlueprint).where(
                ContentBatchBlueprint.batch_id == batch_id,
                ContentBatchBlueprint.blueprint_id == blueprint_id,
                ContentBatchBlueprint.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()
