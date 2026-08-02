import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContentVersion(Base):
    __tablename__ = "content_versions"
    __table_args__ = {"schema": "cms"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    workflow_state: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    ai_check_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text)
    authored_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Traceability (ADR-0025) — nullable because content predating this PR,
    # and content not generated from a Knowledge Unit, has none of this.
    # knowledge_unit_id/_version are populated only when exactly one
    # Knowledge Unit contributed to this version; when more than one did
    # (Concept Note/Revision Sheet aggregating several sections), the full
    # set lives in content_version_knowledge_units instead and these two
    # columns stay NULL rather than naming one arbitrarily.
    knowledge_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge.knowledge_units.id", ondelete="SET NULL")
    )
    knowledge_unit_version: Mapped[int | None] = mapped_column(Integer)
    model_used: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    confidence_score: Mapped[float | None] = mapped_column(Float)
    generation_cost_usd: Mapped[float | None] = mapped_column(Float)

    content_item: Mapped["ContentItem"] = relationship(
        back_populates="versions", foreign_keys=[content_item_id]
    )
    reviews: Mapped[list["ContentReview"]] = relationship(back_populates="content_version", cascade="all, delete-orphan")
    knowledge_unit_refs: Mapped[list["ContentVersionKnowledgeUnit"]] = relationship(
        back_populates="content_version", cascade="all, delete-orphan"
    )
