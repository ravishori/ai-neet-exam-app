"""FACTORY-P4: qa_results, question_fingerprints, review_samples + candidate QA columns

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-01 02:00:00.000000

Does not modify existing question bodies or ECAEP statuses.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_candidates", sa.Column("qa_classification", sa.String(length=10), nullable=True), schema="cms")
    op.add_column(
        "generation_candidates",
        sa.Column("qa_quarantined", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="cms",
    )
    op.add_column("generation_candidates", sa.Column("latest_qa_result_id", sa.UUID(), nullable=True), schema="cms")
    op.add_column("generation_candidates", sa.Column("option_stem_hash", sa.String(length=64), nullable=True), schema="cms")
    op.create_index("ix_cms_gen_candidates_qa_classification", "generation_candidates", ["qa_classification"], schema="cms")
    op.create_index("ix_cms_gen_candidates_batch_status", "generation_candidates", ["batch_id", "status"], schema="cms")
    op.create_index("ix_cms_gen_candidates_option_stem_hash", "generation_candidates", ["option_stem_hash"], schema="cms")

    op.create_table(
        "qa_results",
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("content_version_id", sa.UUID(), nullable=True),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("qa_job_id", sa.UUID(), nullable=True),
        sa.Column("qa_run_id", sa.UUID(), nullable=True),
        sa.Column("generation_run_id", sa.UUID(), nullable=True),
        sa.Column("blueprint_id", sa.UUID(), nullable=True),
        sa.Column("blueprint_version", sa.Integer(), nullable=True),
        sa.Column("qa_version", sa.String(length=40), nullable=False),
        sa.Column("evaluation_no", sa.Integer(), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("classification", sa.String(length=10), nullable=False),
        sa.Column("gate_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failed_checks", postgresql.ARRAY(sa.String(length=80)), nullable=False),
        sa.Column("warnings", postgresql.ARRAY(sa.String(length=80)), nullable=False),
        sa.Column("duplicate_class", sa.String(length=40), nullable=False),
        sa.Column("duplicate_of_item_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
        sa.Column("duplicate_of_candidate_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
        sa.Column("sampling_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("quarantine", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("scientific_certification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "disclaimer",
            sa.Text(),
            nullable=False,
            server_default="AUTOMATED_QA_ONLY — not scientifically certified; not approved; not publishable",
        ),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["cms.generation_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_item_id"], ["cms.content_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["content_version_id"], ["cms.content_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["batch_id"], ["cms.content_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["qa_job_id"], ["cms.generation_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["qa_run_id"], ["cms.generation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["generation_run_id"], ["cms.generation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["blueprint_id"], ["cms.question_blueprints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "qa_version", "evaluation_no", name="uq_cms_qa_results_candidate_version_eval"),
        schema="cms",
    )
    op.create_index("ix_cms_qa_results_batch_id", "qa_results", ["batch_id"], schema="cms")
    op.create_index("ix_cms_qa_results_candidate_id", "qa_results", ["candidate_id"], schema="cms")
    op.create_index("ix_cms_qa_results_classification", "qa_results", ["classification"], schema="cms")
    op.create_index("ix_cms_qa_results_qa_version", "qa_results", ["qa_version"], schema="cms")
    op.create_index(
        "uq_cms_qa_results_latest",
        "qa_results",
        ["candidate_id", "qa_version"],
        unique=True,
        schema="cms",
        postgresql_where=sa.text("is_latest IS TRUE AND deleted_at IS NULL"),
    )

    op.create_table(
        "question_fingerprints",
        sa.Column("content_item_id", sa.UUID(), nullable=False),
        sa.Column("content_version_id", sa.UUID(), nullable=False),
        sa.Column("concept_id", sa.UUID(), nullable=True),
        sa.Column("stem_hash", sa.String(length=64), nullable=False),
        sa.Column("option_stem_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["content_item_id"], ["cms.content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_version_id"], ["cms.content_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["academic.concepts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_item_id", name="uq_cms_question_fingerprints_item"),
        schema="cms",
    )
    op.create_index("ix_cms_question_fingerprints_stem_hash", "question_fingerprints", ["stem_hash"], schema="cms")
    op.create_index(
        "ix_cms_question_fingerprints_option_stem_hash", "question_fingerprints", ["option_stem_hash"], schema="cms"
    )
    op.create_index(
        "ix_cms_question_fingerprints_concept_stem",
        "question_fingerprints",
        ["concept_id", "stem_hash"],
        schema="cms",
    )

    op.create_table(
        "review_samples",
        sa.Column("sample_key", sa.String(length=120), nullable=False),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("green_sample_size", sa.Integer(), nullable=False),
        sa.Column("selected_candidate_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("yellow_candidate_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("red_candidate_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("selection_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("strata_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "note",
            sa.Text(),
            nullable=False,
            server_default="Sampling eligibility only — does not approve, publish, or scientifically certify",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["cms.content_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sample_key", name="uq_cms_review_samples_sample_key"),
        schema="cms",
    )
    op.create_index("ix_cms_review_samples_batch_id", "review_samples", ["batch_id"], schema="cms")


def downgrade() -> None:
    op.drop_index("ix_cms_review_samples_batch_id", table_name="review_samples", schema="cms")
    op.drop_table("review_samples", schema="cms")
    op.drop_index("ix_cms_question_fingerprints_concept_stem", table_name="question_fingerprints", schema="cms")
    op.drop_index("ix_cms_question_fingerprints_option_stem_hash", table_name="question_fingerprints", schema="cms")
    op.drop_index("ix_cms_question_fingerprints_stem_hash", table_name="question_fingerprints", schema="cms")
    op.drop_table("question_fingerprints", schema="cms")
    op.drop_index("uq_cms_qa_results_latest", table_name="qa_results", schema="cms")
    op.drop_index("ix_cms_qa_results_qa_version", table_name="qa_results", schema="cms")
    op.drop_index("ix_cms_qa_results_classification", table_name="qa_results", schema="cms")
    op.drop_index("ix_cms_qa_results_candidate_id", table_name="qa_results", schema="cms")
    op.drop_index("ix_cms_qa_results_batch_id", table_name="qa_results", schema="cms")
    op.drop_table("qa_results", schema="cms")
    op.drop_index("ix_cms_gen_candidates_option_stem_hash", table_name="generation_candidates", schema="cms")
    op.drop_index("ix_cms_gen_candidates_batch_status", table_name="generation_candidates", schema="cms")
    op.drop_index("ix_cms_gen_candidates_qa_classification", table_name="generation_candidates", schema="cms")
    op.drop_column("generation_candidates", "option_stem_hash", schema="cms")
    op.drop_column("generation_candidates", "latest_qa_result_id", schema="cms")
    op.drop_column("generation_candidates", "qa_quarantined", schema="cms")
    op.drop_column("generation_candidates", "qa_classification", schema="cms")
