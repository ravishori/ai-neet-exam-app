"""ingestion: source_academic_mappings (ADR-0031 Phase B)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-24 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_academic_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", UUID(as_uuid=True), nullable=True),
        sa.Column("mapping_status", sa.String(length=20), nullable=False, server_default="UNMAPPED"),
        sa.Column("academic_subject_code", sa.String(length=20), nullable=True),
        sa.Column("chapter_code", sa.String(length=80), nullable=True),
        sa.Column("ncert_chapter_number", sa.Integer(), nullable=True),
        sa.Column("pilot_ready", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("mapping_notes", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["source_document_id"], ["ingestion.source_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["academic.chapters.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("source_document_id", name="uq_source_academic_mappings_source_document_id"),
        schema="ingestion",
    )
    op.create_index(
        "ix_source_academic_mappings_status",
        "source_academic_mappings",
        ["mapping_status"],
        schema="ingestion",
    )
    op.create_index(
        "ix_source_academic_mappings_chapter_code",
        "source_academic_mappings",
        ["chapter_code"],
        schema="ingestion",
    )


def downgrade() -> None:
    op.drop_index("ix_source_academic_mappings_chapter_code", table_name="source_academic_mappings", schema="ingestion")
    op.drop_index("ix_source_academic_mappings_status", table_name="source_academic_mappings", schema="ingestion")
    op.drop_table("source_academic_mappings", schema="ingestion")
