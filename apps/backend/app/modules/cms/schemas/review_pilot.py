from datetime import datetime

from pydantic import BaseModel


class RecordPilotEventRequest(BaseModel):
    pilot_id: str
    content_item_id: str
    decision: str  # APPROVED | CHANGES_REQUESTED | SKIPPED | FLAGGED
    review_started_at: datetime
    decision_submitted_at: datetime
    review_duration_seconds: float
    subject: str | None = None
    class_level: str | None = None
    chapter: str | None = None
    batch_id: str | None = None
    risk_bucket: str | None = None
    reason: str | None = None
    note: str | None = None
