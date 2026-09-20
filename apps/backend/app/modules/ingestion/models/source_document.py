"""NEET StudyMaterial source document registry (ADR-0030)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase

if TYPE_CHECKING:
    from app.modules.ingestion.models.ingestion_job import IngestionJob
    from app.modules.ingestion.models.source_academic_mapping import SourceAcademicMapping

# NEET-UG subjects only — Maths is explicitly out of scope (ADR-0030).
NEET_SUBJECT_CODES = ("PHYSICS", "CHEMISTRY", "BIOLOGY")
CLASS_LEVELS = ("11", "12")
SOURCE_INGESTION_STATUSES = ("DISCOVERED", "QUEUED", "INGESTED", "FAILED")


class SourceDocument(Base, AuditedBase):
    """First-class registry row for one NEET source PDF under StudyMaterial.

    Canonical content identity is checksum_sha256. relative_source_path is
    relative to Settings.study_material_dir — never treat the absolute Windows
    path as the identity key.
    """

    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("checksum_sha256", name="uq_source_documents_checksum_sha256"),
        Index("ix_source_documents_relative_path", "relative_source_path"),
        Index("ix_source_documents_subject_class", "subject_code", "class_level"),
        Index("ix_source_documents_ingestion_status", "ingestion_status"),
        {"schema": "ingestion"},
    )

    relative_source_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, default="pdf")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Dev-only absolute path convenience; null / unused in production storage.
    absolute_source_path_dev: Mapped[str | None] = mapped_column(String(2000))
    # Future production object-storage key; unused in Phase A local discovery.
    storage_key: Mapped[str | None] = mapped_column(String(1000))
    class_level: Mapped[str] = mapped_column(String(2), nullable=False)  # "11" | "12"
    subject_code: Mapped[str] = mapped_column(String(20), nullable=False)  # PHYSICS|CHEMISTRY|BIOLOGY
    title: Mapped[str | None] = mapped_column(String(500))
    publisher: Mapped[str | None] = mapped_column(String(100))
    edition: Mapped[str | None] = mapped_column(String(100))
    page_count: Mapped[int | None] = mapped_column(Integer)
    ingestion_status: Mapped[str] = mapped_column(String(20), nullable=False, default="DISCOVERED")
    notes: Mapped[str | None] = mapped_column(Text)

    jobs: Mapped[list[IngestionJob]] = relationship(
        back_populates="source_document",
        foreign_keys="IngestionJob.source_document_id",
    )
    academic_mapping: Mapped[SourceAcademicMapping | None] = relationship(
        back_populates="source_document",
        foreign_keys="SourceAcademicMapping.source_document_id",
        uselist=False,
    )
