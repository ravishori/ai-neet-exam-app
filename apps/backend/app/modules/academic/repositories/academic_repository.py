import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.academic.models import Chapter, Concept, Exam, MicroCompetency, Subject, Topic


class AcademicRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_exams(self) -> list[Exam]:
        result = await self.session.execute(select(Exam).where(Exam.is_active.is_(True)))
        return list(result.scalars().all())

    async def list_subjects(self, exam_id: uuid.UUID | None = None) -> list[Subject]:
        query = select(Subject).order_by(Subject.display_order)
        if exam_id:
            query = query.where(Subject.exam_id == exam_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_subject(self, subject_id: uuid.UUID) -> Subject | None:
        result = await self.session.execute(select(Subject).where(Subject.id == subject_id))
        return result.scalar_one_or_none()

    async def get_subject_tree(self, subject_id: uuid.UUID) -> Subject | None:
        result = await self.session.execute(
            select(Subject)
            .options(selectinload(Subject.chapters).selectinload(Chapter.topics).selectinload(Topic.concepts))
            .where(Subject.id == subject_id)
        )
        return result.scalar_one_or_none()

    async def list_chapters(self, subject_id: uuid.UUID) -> list[Chapter]:
        result = await self.session.execute(
            select(Chapter).where(Chapter.subject_id == subject_id).order_by(Chapter.display_order)
        )
        return list(result.scalars().all())

    async def get_chapter(self, chapter_id: uuid.UUID) -> Chapter | None:
        result = await self.session.execute(select(Chapter).where(Chapter.id == chapter_id))
        return result.scalar_one_or_none()

    async def list_topics(self, chapter_id: uuid.UUID) -> list[Topic]:
        result = await self.session.execute(
            select(Topic).where(Topic.chapter_id == chapter_id).order_by(Topic.display_order)
        )
        return list(result.scalars().all())

    async def get_topic(self, topic_id: uuid.UUID) -> Topic | None:
        result = await self.session.execute(select(Topic).where(Topic.id == topic_id))
        return result.scalar_one_or_none()

    async def list_concepts(self, topic_id: uuid.UUID) -> list[Concept]:
        result = await self.session.execute(
            select(Concept).where(Concept.topic_id == topic_id).order_by(Concept.display_order)
        )
        return list(result.scalars().all())

    async def get_concept(self, concept_id: uuid.UUID) -> Concept | None:
        result = await self.session.execute(select(Concept).where(Concept.id == concept_id))
        return result.scalar_one_or_none()

    async def list_micro_competencies(self, concept_id: uuid.UUID) -> list[MicroCompetency]:
        result = await self.session.execute(
            select(MicroCompetency).where(MicroCompetency.concept_id == concept_id).order_by(MicroCompetency.display_order)
        )
        return list(result.scalars().all())

    async def add_micro_competency(self, micro_competency: MicroCompetency) -> None:
        self.session.add(micro_competency)
        await self.session.commit()
