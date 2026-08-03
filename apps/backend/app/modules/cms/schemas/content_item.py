from datetime import datetime

from pydantic import BaseModel, Field


class ContentItemCreateRequest(BaseModel):
    content_type: str
    concept_id: str | None = None
    micro_competency_id: str | None = None
    title: str = Field(max_length=300)
    slug: str = Field(max_length=320)
    tags: list[str] = Field(default_factory=list)
    language: str = "en"
    body: dict


class ContentItemUpdateRequest(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    body: dict
    change_summary: str | None = None


class ReviewDecisionRequest(BaseModel):
    decision: str  # approve | request_changes
    comment: str | None = None


class ContentReportRequest(BaseModel):
    reason: str  # WRONG_ANSWER | UNCLEAR | TYPO | OFFENSIVE | OTHER
    comment: str | None = Field(default=None, max_length=1000)


class ContentVersionResponse(BaseModel):
    id: str
    version_no: int
    body: dict
    workflow_state: str
    ai_check_report: dict | None
    change_summary: str | None
    authored_by: str | None
    authored_at: datetime


class ContentItemResponse(BaseModel):
    id: str
    content_type: str
    concept_id: str | None
    micro_competency_id: str | None
    title: str
    slug: str
    tags: list[str]
    language: str
    status: str
    current_version: ContentVersionResponse | None
    latest_version: ContentVersionResponse | None


class ContentReviewResponse(BaseModel):
    id: str
    reviewer_id: str | None
    decision: str
    comment: str | None
    reviewed_at: datetime
