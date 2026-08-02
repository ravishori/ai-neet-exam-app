import uuid

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContentVersionKnowledgeUnit(Base):
    """Full lineage for a generated ContentVersion — one row per Knowledge
    Unit that contributed to it. See ADR-0025: MCQ/Flashcard always have
    exactly one row here (mirrored on ContentVersion.knowledge_unit_id as
    a convenience column); Concept Note/Revision Sheet routinely have
    several, which this table is the only complete record of.

    knowledge_unit_id has no ON DELETE action (defaults to RESTRICT) —
    Knowledge Units are never deleted in this project (only marked
    FAILED/superseded), so this should never actually block a delete; it
    exists so a lineage row can't silently disappear if that ever changes.
    """

    __tablename__ = "content_version_knowledge_units"
    __table_args__ = {"schema": "cms"}

    content_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_versions.id", ondelete="CASCADE"), primary_key=True
    )
    knowledge_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge.knowledge_units.id"), primary_key=True
    )
    knowledge_unit_version: Mapped[int] = mapped_column(Integer, nullable=False)

    content_version: Mapped["ContentVersion"] = relationship(back_populates="knowledge_unit_refs")
