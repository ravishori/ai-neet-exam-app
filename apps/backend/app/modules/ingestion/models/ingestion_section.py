import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase


class IngestionSection(Base, AuditedBase):
    """One detected heading-delimited section of a source PDF — kept for
    audit/citation (which page/paragraph a generated question came from),
    not just as pipeline scratch state."""

    __tablename__ = "ingestion_sections"
    __table_args__ = {"schema": "ingestion"}

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion.ingestion_jobs.id", ondelete="CASCADE"), nullable=False
    )
    heading: Mapped[str] = mapped_column(String(300), nullable=False)
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    matched_concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.concepts.id", ondelete="SET NULL")
    )
    questions_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Language metadata (ADR-0027) — nullable: historical rows created
    # before this ADR have none, same non-backfill precedent as every prior
    # additive column in this project (e.g. ADR-0025's traceability
    # columns). Populated for every row created from this point forward.
    language_code: Mapped[str | None] = mapped_column(String(10))  # "en" | "hi" | "mixed"
    language_name: Mapped[str | None] = mapped_column(String(20))  # "English" | "Hindi" | "Mixed"
    language_confidence: Mapped[float | None] = mapped_column(Float)

    job: Mapped["IngestionJob"] = relationship(back_populates="sections")
