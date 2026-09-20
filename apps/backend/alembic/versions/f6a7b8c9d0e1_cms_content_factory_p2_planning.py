"""FACTORY-P2: learning objectives, families, blueprints, coverage slices

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-01 01:00:00.000000

Does not modify content_items / content_versions / reviews / ECAEP statuses.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_objectives",
        sa.Column("objective_key", sa.String(length=120), nullable=False),
        sa.Column("concept_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("learning_level", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["concept_id"], ["academic.concepts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("objective_key", name="uq_cms_learning_objectives_key"),
        schema="cms",
    )
    op.create_index("ix_cms_learning_objectives_concept_id", "learning_objectives", ["concept_id"], schema="cms")
    op.create_index("ix_cms_learning_objectives_is_active", "learning_objectives", ["is_active"], schema="cms")

    op.create_table(
        "question_families",
        sa.Column("family_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("applicable_subject_codes", postgresql.ARRAY(sa.String(length=30)), nullable=False),
        sa.Column("cognitive_intent", sa.String(length=200), nullable=False),
        sa.Column("difficulty_min", sa.String(length=20), nullable=False),
        sa.Column("difficulty_max", sa.String(length=20), nullable=False),
        sa.Column("question_format", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_key", name="uq_cms_question_families_key"),
        schema="cms",
    )
    op.create_index("ix_cms_question_families_is_active", "question_families", ["is_active"], schema="cms")

    op.create_table(
        "question_blueprints",
        sa.Column("blueprint_key", sa.String(length=120), nullable=False),
        sa.Column("blueprint_version", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("chapter_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.Column("concept_id", sa.UUID(), nullable=False),
        sa.Column("learning_objective_id", sa.UUID(), nullable=False),
        sa.Column("question_family_id", sa.UUID(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance_tier", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("generation_eligible", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["academic.subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["chapter_id"], ["academic.chapters.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["topic_id"], ["academic.topics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["concept_id"], ["academic.concepts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["learning_objective_id"], ["cms.learning_objectives.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["question_family_id"], ["cms.question_families.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blueprint_key", "blueprint_version", name="uq_cms_blueprints_key_version"),
        schema="cms",
    )
    op.create_index("ix_cms_question_blueprints_concept_id", "question_blueprints", ["concept_id"], schema="cms")
    op.create_index("ix_cms_question_blueprints_status", "question_blueprints", ["status"], schema="cms")
    op.create_index("ix_cms_question_blueprints_family_id", "question_blueprints", ["question_family_id"], schema="cms")
    op.create_index(
        "ix_cms_question_blueprints_objective_id", "question_blueprints", ["learning_objective_id"], schema="cms"
    )
    op.create_index("ix_cms_question_blueprints_eligible", "question_blueprints", ["generation_eligible"], schema="cms")

    op.create_table(
        "coverage_slices",
        sa.Column("slice_key", sa.String(length=160), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("chapter_id", sa.UUID(), nullable=True),
        sa.Column("topic_id", sa.UUID(), nullable=True),
        sa.Column("concept_id", sa.UUID(), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("question_family_id", sa.UUID(), nullable=True),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["academic.subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["chapter_id"], ["academic.chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["academic.topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["concept_id"], ["academic.concepts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["question_family_id"], ["cms.question_families.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slice_key", name="uq_cms_coverage_slices_key"),
        schema="cms",
    )
    op.create_index("ix_cms_coverage_slices_subject_id", "coverage_slices", ["subject_id"], schema="cms")
    op.create_index("ix_cms_coverage_slices_concept_id", "coverage_slices", ["concept_id"], schema="cms")
    op.create_index("ix_cms_coverage_slices_family_id", "coverage_slices", ["question_family_id"], schema="cms")

    op.create_table(
        "content_batch_blueprints",
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("blueprint_id", sa.UUID(), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["cms.content_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blueprint_id"], ["cms.question_blueprints.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "blueprint_id", name="uq_cms_batch_blueprint"),
        schema="cms",
    )
    op.create_index("ix_cms_batch_blueprints_batch_id", "content_batch_blueprints", ["batch_id"], schema="cms")
    op.create_index("ix_cms_batch_blueprints_blueprint_id", "content_batch_blueprints", ["blueprint_id"], schema="cms")

    # P3 contract: GenerationJob may target a concrete blueprint version.
    op.add_column(
        "generation_jobs",
        sa.Column("blueprint_id", sa.UUID(), nullable=True),
        schema="cms",
    )
    op.add_column(
        "generation_jobs",
        sa.Column("blueprint_version", sa.Integer(), nullable=True),
        schema="cms",
    )
    op.create_foreign_key(
        "fk_cms_generation_jobs_blueprint_id",
        "generation_jobs",
        "question_blueprints",
        ["blueprint_id"],
        ["id"],
        source_schema="cms",
        referent_schema="cms",
        ondelete="SET NULL",
    )
    op.create_index("ix_cms_generation_jobs_blueprint_id", "generation_jobs", ["blueprint_id"], schema="cms")


def downgrade() -> None:
    op.drop_index("ix_cms_generation_jobs_blueprint_id", table_name="generation_jobs", schema="cms")
    op.drop_constraint("fk_cms_generation_jobs_blueprint_id", "generation_jobs", schema="cms", type_="foreignkey")
    op.drop_column("generation_jobs", "blueprint_version", schema="cms")
    op.drop_column("generation_jobs", "blueprint_id", schema="cms")

    op.drop_index("ix_cms_batch_blueprints_blueprint_id", table_name="content_batch_blueprints", schema="cms")
    op.drop_index("ix_cms_batch_blueprints_batch_id", table_name="content_batch_blueprints", schema="cms")
    op.drop_table("content_batch_blueprints", schema="cms")

    op.drop_index("ix_cms_coverage_slices_family_id", table_name="coverage_slices", schema="cms")
    op.drop_index("ix_cms_coverage_slices_concept_id", table_name="coverage_slices", schema="cms")
    op.drop_index("ix_cms_coverage_slices_subject_id", table_name="coverage_slices", schema="cms")
    op.drop_table("coverage_slices", schema="cms")

    op.drop_index("ix_cms_question_blueprints_eligible", table_name="question_blueprints", schema="cms")
    op.drop_index("ix_cms_question_blueprints_objective_id", table_name="question_blueprints", schema="cms")
    op.drop_index("ix_cms_question_blueprints_family_id", table_name="question_blueprints", schema="cms")
    op.drop_index("ix_cms_question_blueprints_status", table_name="question_blueprints", schema="cms")
    op.drop_index("ix_cms_question_blueprints_concept_id", table_name="question_blueprints", schema="cms")
    op.drop_table("question_blueprints", schema="cms")

    op.drop_index("ix_cms_question_families_is_active", table_name="question_families", schema="cms")
    op.drop_table("question_families", schema="cms")

    op.drop_index("ix_cms_learning_objectives_is_active", table_name="learning_objectives", schema="cms")
    op.drop_index("ix_cms_learning_objectives_concept_id", table_name="learning_objectives", schema="cms")
    op.drop_table("learning_objectives", schema="cms")
