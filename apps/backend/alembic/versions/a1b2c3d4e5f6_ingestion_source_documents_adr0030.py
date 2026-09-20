"""ingestion: source_documents registry + optional job FK (ADR-0030)

Revision ID: a1b2c3d4e5f6
Revises: 7c3f9e1a4d82
Create Date: 2026-08-24 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "a1b2c3d4e5f6"
down_revision = "7c3f9e1a4d82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("relative_source_path", sa.String(length=1000), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False, server_default="pdf"),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("absolute_source_path_dev", sa.String(length=2000), nullable=True),
        sa.Column("storage_key", sa.String(length=1000), nullable=True),
        sa.Column("class_level", sa.String(length=2), nullable=False),
        sa.Column("subject_code", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("publisher", sa.String(length=100), nullable=True),
        sa.Column("edition", sa.String(length=100), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("ingestion_status", sa.String(length=20), nullable=False, server_default="DISCOVERED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("checksum_sha256", name="uq_source_documents_checksum_sha256"),
        schema="ingestion",
    )
    op.create_index(
        "ix_source_documents_relative_path",
        "source_documents",
        ["relative_source_path"],
        schema="ingestion",
    )
    op.create_index(
        "ix_source_documents_subject_class",
        "source_documents",
        ["subject_code", "class_level"],
        schema="ingestion",
    )
    op.create_index(
        "ix_source_documents_ingestion_status",
        "source_documents",
        ["ingestion_status"],
        schema="ingestion",
    )

    op.add_column(
        "ingestion_jobs",
        sa.Column("source_document_id", UUID(as_uuid=True), nullable=True),
        schema="ingestion",
    )
    op.create_foreign_key(
        "fk_ingestion_jobs_source_document_id",
        "ingestion_jobs",
        "source_documents",
        ["source_document_id"],
        ["id"],
        source_schema="ingestion",
        referent_schema="ingestion",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_ingestion_jobs_source_document_id",
        "ingestion_jobs",
        ["source_document_id"],
        schema="ingestion",
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_source_document_id", table_name="ingestion_jobs", schema="ingestion")
    op.drop_constraint("fk_ingestion_jobs_source_document_id", "ingestion_jobs", schema="ingestion", type_="foreignkey")
    op.drop_column("ingestion_jobs", "source_document_id", schema="ingestion")

    op.drop_index("ix_source_documents_ingestion_status", table_name="source_documents", schema="ingestion")
    op.drop_index("ix_source_documents_subject_class", table_name="source_documents", schema="ingestion")
    op.drop_index("ix_source_documents_relative_path", table_name="source_documents", schema="ingestion")
    op.drop_table("source_documents", schema="ingestion")
