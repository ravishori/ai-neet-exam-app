import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.academic.models import Concept
from app.modules.ai.models import StudyPlan
from app.modules.assessment.models import Attempt, AttemptAnswer
from app.modules.cms.models import ContentItem


class AIRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_concept(self, concept_id: uuid.UUID) -> Concept | None:
        result = await self.session.execute(select(Concept).where(Concept.id == concept_id))
        return result.scalar_one_or_none()

    async def get_published_notes(self, concept_id: uuid.UUID) -> list[str]:
        result = await self.session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.concept_id == concept_id, ContentItem.content_type == "CONCEPT_NOTE", ContentItem.status == "PUBLISHED")
        )
        notes = []
        for item in result.scalars().all():
            for v in item.versions:
                if v.id == item.current_version_id and v.body.get("summary"):
                    notes.append(v.body["summary"])
        return notes

    async def get_weak_concept_names(self, user_id: uuid.UUID, limit: int = 10) -> list[str]:
        result = await self.session.execute(
            select(Concept.name)
            .join(ContentItem, ContentItem.concept_id == Concept.id)
            .join(AttemptAnswer, AttemptAnswer.content_item_id == ContentItem.id)
            .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
            .where(Attempt.user_id == user_id, AttemptAnswer.is_correct.is_(False))
            .distinct()
            .limit(limit)
        )
        return list(result.scalars().all())

    def add_study_plan(self, plan: StudyPlan) -> None:
        self.session.add(plan)

    async def commit(self) -> None:
        await self.session.commit()

    async def get_latest_study_plan(self, user_id: uuid.UUID) -> StudyPlan | None:
        result = await self.session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user_id).order_by(StudyPlan.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()
