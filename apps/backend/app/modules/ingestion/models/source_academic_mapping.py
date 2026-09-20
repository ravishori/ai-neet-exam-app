"""SourceDocument → academic Chapter mapping (ADR-0031 Phase B)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase

if TYPE_CHECKING:
    from app.modules.academic.models.chapter import Chapter
    from app.modules.ingestion.models.source_document import SourceDocument

MAPPING_STATUSES = ("MAPPED", "UNMAPPED")


class SourceAcademicMapping(Base, AuditedBase):
    """Deterministic bridge from a registered NEET source PDF to academic.chapters.

    One row per SourceDocument. UNMAPPED rows record that no confident academic
    chapter link exists — the system must not guess or invent chapters.
    """

    __tablename__ = "source_academic_mappings"
    __table_args__ = (
        UniqueConstraint("source_document_id", name="uq_source_academic_mappings_source_document_id"),
        Index("ix_source_academic_mappings_status", "mapping_status"),
        Index("ix_source_academic_mappings_chapter_code", "chapter_code"),
        {"schema": "ingestion"},
    )

    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion.source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic.chapters.id", ondelete="SET NULL"),
        nullable=True,
    )
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNMAPPED")
    # Academic subject (PHYSICS/CHEMISTRY/BOTANY/ZOOLOGY) — not filesystem BIOLOGY.
    academic_subject_code: Mapped[str | None] = mapped_column(String(20))
    chapter_code: Mapped[str | None] = mapped_column(String(80))
    ncert_chapter_number: Mapped[int | None] = mapped_column(Integer)
    # True only when mapped chapter has a seeded topic/concept tree AND the
    # on-disk PDF body matches chapter content markers (Phase B.1).
    pilot_ready: Mapped[bool] = mapped_column(default=False, nullable=False)
    mapping_notes: Mapped[str | None] = mapped_column(String(500))

    source_document: Mapped[SourceDocument] = relationship(
        back_populates="academic_mapping",
        foreign_keys=[source_document_id],
    )
    chapter: Mapped[Chapter | None] = relationship(
        "Chapter",
        foreign_keys=[chapter_id],
    )
