import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase

# PENDING (created, gates not yet run) -> PASSED | FAILED
# No RETRY state in this PR — a FAILED unit is not automatically re-attempted
# (Continuous Improvement / re-validation priority is a later-stage concern
# per the AI Content Lifecycle Specification, not this one). See ADR-0024.
VALIDATION_STATUSES = ("PENDING", "PASSED", "FAILED")


class KnowledgeUnit(Base, AuditedBase):
    """The smallest independently-citable, versioned piece of verified
    knowledge extracted from a source document — see ADR-0024 and the AI
    Content Lifecycle Specification, Section 2.

    (id, version) is the stable address everything else references, the
    same pattern already proven by cms.ContentItem/ContentVersion.
    """

    __tablename__ = "knowledge_units"
    __table_args__ = (
        Index("ix_knowledge_units_concept", "concept_id"),
        Index("ix_knowledge_units_content_hash", "content_hash"),
        {"schema": "knowledge"},
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 of structured_facts

    structured_facts: Mapped[list] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    source_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion.ingestion_sections.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.concepts.id", ondelete="CASCADE"), nullable=False
    )

    extraction_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    validation_detail: Mapped[str | None] = mapped_column(Text)  # human-readable gate failure reason, if any

    # Points from an old version to the version that replaced it. No ORM
    # relationship object yet — nothing in this PR navigates the chain;
    # that's re-validation/regeneration territory (PR 2+, per ADR-0024).
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge.knowledge_units.id", ondelete="SET NULL")
    )
