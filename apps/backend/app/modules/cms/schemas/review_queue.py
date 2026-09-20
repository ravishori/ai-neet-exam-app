from pydantic import BaseModel

from app.modules.cms.models.review_queue import DEFAULT_SESSION_SIZE


class CreateReviewSessionRequest(BaseModel):
    session_size: int = DEFAULT_SESSION_SIZE
    subject_id: str | None = None
    class_level: str | None = None
    chapter_id: str | None = None
    topic_id: str | None = None
    batch_id: str | None = None
    risk_bucket: str | None = None  # RED | AMBER | GREEN
