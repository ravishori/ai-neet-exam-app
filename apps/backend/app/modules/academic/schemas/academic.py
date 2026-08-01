from pydantic import BaseModel


class ExamResponse(BaseModel):
    id: str
    code: str
    name: str
    description: str | None


class SubjectResponse(BaseModel):
    id: str
    exam_id: str
    code: str
    name: str
    display_order: int


class ChapterResponse(BaseModel):
    id: str
    subject_id: str
    code: str
    name: str
    display_order: int
    neet_weightage_percent: float | None


class TopicResponse(BaseModel):
    id: str
    chapter_id: str
    code: str
    name: str
    display_order: int


class ConceptResponse(BaseModel):
    id: str
    topic_id: str
    code: str
    name: str
    summary: str | None
    ncert_reference: str | None
    difficulty: str
    display_order: int


class ConceptTreeResponse(ConceptResponse):
    pass


class TopicTreeResponse(TopicResponse):
    concepts: list[ConceptTreeResponse]


class ChapterTreeResponse(ChapterResponse):
    topics: list[TopicTreeResponse]


class SubjectTreeResponse(SubjectResponse):
    chapters: list[ChapterTreeResponse]
