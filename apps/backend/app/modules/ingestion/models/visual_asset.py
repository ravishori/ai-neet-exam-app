import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase

ASSET_TYPES = ("image", "diagram", "table", "equation", "chemical_structure")

# Stated honestly per ADR-0026 — not hidden. "embedded_image" (pixel-exact,
# via PyMuPDF's get_image_rects) and "vector_cluster" (proximity-merge over
# get_drawings() paths, reliable only for isolated multi-option grids) are
# both real, proven this session. "manual" means a human/agent placed the
# bounding_box directly — not a fallback to be ashamed of.
DETECTION_METHODS = ("embedded_image", "vector_cluster", "manual")

# NEEDS_MANUAL_BBOX is the answer to "never discard a diagram" — a row
# always exists, even when detection can't isolate a clean box (recorded
# with bounding_box=None rather than a wrong guess or a dropped page).
REVIEW_STATUSES = ("AUTO_DETECTED", "VERIFIED", "NEEDS_MANUAL_BBOX", "REJECTED")


class VisualAsset(Base, AuditedBase):
    """One detected visual element (image, diagram, table, equation, or
    chemical structure) from a source PDF page — see ADR-0026. Deliberately
    independent of IngestionSection (a visual element is often detected
    before or without any section match) and optionally cited by a
    KnowledgeUnit once one actually references it."""

    __tablename__ = "visual_assets"
    __table_args__ = (
        Index("ix_visual_assets_job", "job_id"),
        Index("ix_visual_assets_review_status", "review_status"),
        {"schema": "ingestion"},
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion.ingestion_jobs.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion.ingestion_sections.id", ondelete="SET NULL")
    )
    knowledge_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge.knowledge_units.id", ondelete="RESTRICT")
    )

    source_page: Mapped[int] = mapped_column(Integer, nullable=False)
    # {"x0":.., "y0":.., "x1":.., "y1":.., "unit": "pdf_points_72dpi"} — None
    # when review_status is NEEDS_MANUAL_BBOX and no box has been placed yet.
    bounding_box: Mapped[dict | None] = mapped_column(JSONB)
    render_dpi: Mapped[int | None] = mapped_column(Integer)
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)

    asset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(20), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="AUTO_DETECTED")

    storage_path: Mapped[str | None] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64))  # sha256 hex of the crop file
    vision_description: Mapped[str | None] = mapped_column(Text)
    ocr_text: Mapped[str | None] = mapped_column(Text)

    # Approval timestamps (ADR-0028 Phase C) — added onto the *existing*
    # review_status workflow above, deliberately not a second, parallel
    # status enum: VisualAsset represents content *detected* from a source
    # PDF, never AI-*generated*, so a "Pending/Generating/Generated" state
    # machine doesn't describe anything real about this row. review_status
    # already carries the approve/reject decision (VERIFIED/REJECTED); these
    # columns record *when* and *by whom* and, for a rejection, *why* —
    # information review_status alone can't hold.
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="SET NULL")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    job: Mapped["IngestionJob"] = relationship()
