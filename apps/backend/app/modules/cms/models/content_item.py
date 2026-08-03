import uuid

from sqlalchemy import ARRAY, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase

# CONCEPT_NOTE | QUESTION | FLASHCARD | DIAGRAM | VIDEO_REF | FORMULA_SHEET
# DRAFT | AI_CHECKED | IN_REVIEW | CHANGES_REQUESTED | APPROVED | PUBLISHED | ARCHIVED


class ContentItem(Base, AuditedBase):
    __tablename__ = "content_items"
    __table_args__ = {"schema": "cms"}

    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.concepts.id", ondelete="SET NULL"), nullable=True
    )
    # One optional micro-competency this QUESTION tests — see ADR-0021.
    # Nullable/optional: existing and future untagged questions stay valid.
    micro_competency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.micro_competencies.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(320), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)

    # Search index (PR 3) — maintained by SearchRepository.reindex_item(),
    # called whenever a QUESTION is published. NULL for draft/unpublished
    # rows and for content_types search doesn't cover yet. search_text is
    # the plain-text source for the pg_trgm typo-tolerant fallback and for
    # ts_headline snippets; search_vector is the weighted tsvector the GIN
    # index and ts_rank actually query against.
    search_text: Mapped[str | None] = mapped_column(Text)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_versions.id", use_alter=True, name="fk_current_version"), nullable=True
    )
    latest_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_versions.id", use_alter=True, name="fk_latest_version"), nullable=True
    )

    versions: Mapped[list["ContentVersion"]] = relationship(
        back_populates="content_item",
        foreign_keys="ContentVersion.content_item_id",
        cascade="all, delete-orphan",
        order_by="ContentVersion.version_no",
    )
