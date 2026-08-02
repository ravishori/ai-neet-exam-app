import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase

# PENDING -> EXTRACTING -> MATCHING -> GENERATING -> COMPLETED
#                                                  \-> FAILED (any stage)
JOB_STATUSES = ("PENDING", "EXTRACTING", "MATCHING", "GENERATING", "COMPLETED", "FAILED")


class IngestionJob(Base, AuditedBase):
    __tablename__ = "ingestion_jobs"
    __table_args__ = {"schema": "ingestion"}

    source_file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 hex
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

    sections: Mapped[list["IngestionSection"]] = relationship(
        back_populates="job", order_by="IngestionSection.source_page", cascade="all, delete-orphan"
    )
