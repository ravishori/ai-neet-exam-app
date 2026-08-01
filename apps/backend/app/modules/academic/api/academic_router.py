import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.academic.models import Chapter, Concept, Exam, Subject, Topic
from app.modules.academic.repositories.academic_repository import AcademicRepository
from app.modules.identity.dependencies import get_current_user
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1", tags=["academic"], dependencies=[Depends(get_current_user)])


def _exam(e: Exam) -> dict:
    return {"id": str(e.id), "code": e.code, "name": e.name, "description": e.description}


def _subject(s: Subject) -> dict:
    return {
        "id": str(s.id),
        "exam_id": str(s.exam_id),
        "code": s.code,
        "name": s.name,
        "display_order": s.display_order,
    }


def _chapter(c: Chapter) -> dict:
    return {
        "id": str(c.id),
        "subject_id": str(c.subject_id),
        "code": c.code,
        "name": c.name,
        "display_order": c.display_order,
        "neet_weightage_percent": float(c.neet_weightage_percent) if c.neet_weightage_percent is not None else None,
    }


def _topic(t: Topic) -> dict:
    return {"id": str(t.id), "chapter_id": str(t.chapter_id), "code": t.code, "name": t.name, "display_order": t.display_order}


def _concept(co: Concept) -> dict:
    return {
        "id": str(co.id),
        "topic_id": str(co.topic_id),
        "code": co.code,
        "name": co.name,
        "summary": co.summary,
        "ncert_reference": co.ncert_reference,
        "difficulty": co.difficulty,
        "display_order": co.display_order,
    }


def _subject_tree(s: Subject) -> dict:
    return {
        **_subject(s),
        "chapters": [
            {
                **_chapter(c),
                "topics": [
                    {**_topic(t), "concepts": [_concept(co) for co in t.concepts]}
                    for t in c.topics
                ],
            }
            for c in s.chapters
        ],
    }


@router.get("/exams")
async def list_exams(db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    exams = await repo.list_exams()
    return envelope(success=True, data=[_exam(e) for e in exams])


@router.get("/subjects")
async def list_subjects(db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    subjects = await repo.list_subjects()
    return envelope(success=True, data=[_subject(s) for s in subjects])


@router.get("/subjects/{subject_id}")
async def get_subject(subject_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    subject = await repo.get_subject(subject_id)
    if not subject:
        raise NotFoundError("Subject not found")
    return envelope(success=True, data=_subject(subject))


@router.get("/subjects/{subject_id}/chapters")
async def list_subject_chapters(subject_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    chapters = await repo.list_chapters(subject_id)
    return envelope(success=True, data=[_chapter(c) for c in chapters])


@router.get("/subjects/{subject_id}/tree")
async def get_subject_tree(subject_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    subject = await repo.get_subject_tree(subject_id)
    if not subject:
        raise NotFoundError("Subject not found")
    return envelope(success=True, data=_subject_tree(subject))


@router.get("/chapters/{chapter_id}")
async def get_chapter(chapter_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    chapter = await repo.get_chapter(chapter_id)
    if not chapter:
        raise NotFoundError("Chapter not found")
    return envelope(success=True, data=_chapter(chapter))


@router.get("/chapters/{chapter_id}/topics")
async def list_chapter_topics(chapter_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    topics = await repo.list_topics(chapter_id)
    return envelope(success=True, data=[_topic(t) for t in topics])


@router.get("/topics/{topic_id}")
async def get_topic(topic_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    topic = await repo.get_topic(topic_id)
    if not topic:
        raise NotFoundError("Topic not found")
    return envelope(success=True, data=_topic(topic))


@router.get("/topics/{topic_id}/concepts")
async def list_topic_concepts(topic_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    concepts = await repo.list_concepts(topic_id)
    return envelope(success=True, data=[_concept(co) for co in concepts])


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = AcademicRepository(db)
    concept = await repo.get_concept(concept_id)
    if not concept:
        raise NotFoundError("Concept not found")
    return envelope(success=True, data=_concept(concept))
