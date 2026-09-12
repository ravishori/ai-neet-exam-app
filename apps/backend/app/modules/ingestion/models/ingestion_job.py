from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase

if TYPE_CHECKING:
    from app.modules.ingestion.models.ingestion_section import IngestionSection
    from app.modules.ingestion.models.source_document import SourceDocument

# PENDING -> EXTRACTING -> MATCHING -> STRUCTURING -> GENERATING -> COMPLETED
#                                                                 \-> FAILED (any stage)
# STRUCTURING (ADR-0024) creates Knowledge Units from matched sections.
# GENERATING (ADR-0025) now reads only PASSED Knowledge Units, never raw
# section text directly — a section/concept/chapter with no PASSED unit
# is skipped, not silently generated from raw text.
# Visual asset detection (ADR-0026) runs during EXTRACTING, alongside text
# extraction — it doesn't get its own status, the same way section-splitting
# doesn't.
JOB_STATUSES = ("PENDING", "EXTRACTING", "MATCHING", "STRUCTURING", "GENERATING", "COMPLETED", "FAILED")


class IngestionJob(Base, AuditedBase):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index("ix_ingestion_jobs_checksum", "file_checksum"),
        Index("ix_ingestion_jobs_status", "status"),
        Index("ix_ingestion_jobs_pilot_run_id", "pilot_run_id"),
        {"schema": "ingestion"},
    )

    source_file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Original client-supplied filename (e.g. "Physics Chapter 3.pdf") — for
    # display in the admin UI's job list, since source_file_path is a
    # server-generated safe path, not something a human recognizes. Nullable:
    # jobs created via the pre-existing path-based endpoint have none.
    original_filename: Mapped[str | None] = mapped_column(String(500))
    file_checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 hex
    # Optional link to the NEET StudyMaterial registry (ADR-0030). Nullable so
    # existing path-based and upload-based jobs remain valid without a registry
    # row. When set, provenance is SourceDocument → IngestionJob → …
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion.source_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.subjects.id", ondelete="SET NULL")
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.chapters.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    stage_detail: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    sections_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_deduped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flashcards_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revision_sheets_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    knowledge_units_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    knowledge_units_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generation_skipped_no_knowledge_unit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visual_assets_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visual_assets_needing_review: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Phase D pilot (ADR-0032): when set, generation targets exactly this many MCQs
    # for the chapter job and records pilot_run_id for idempotent re-runs.
    target_mcq_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pilot_run_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    sections: Mapped[list[IngestionSection]] = relationship(
        back_populates="job", order_by="IngestionSection.source_page", cascade="all, delete-orphan"
    )
    source_document: Mapped[SourceDocument | None] = relationship(
        back_populates="jobs",
        foreign_keys=[source_document_id],
    )
