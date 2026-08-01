import uuid

from sqlalchemy import ARRAY, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
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
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(320), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)

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
