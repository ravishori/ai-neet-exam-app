"""pyq: create staging schema (sources/import_batches/source_files/questions/
answer_assertions/duplicate_candidates/qa_reviews/promotion_log)

Schema-only. No data migration, no PYQ import. Staged questions never enter
cms.content_items directly — promotion is a separate, explicit, gated write
via the existing ContentWorkflowService.create_item() path (not part of this
migration). See docs/architecture (PYQ staging architecture) for the full
design rationale, state machines, and promotion contract.

Revision ID: b7c8d9e0f1a2
Revises: a2b3c4d5e6f7
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b7c8d9e0f1a2"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS pyq")

    # 1. pyq.sources — root of provenance chain (one row per authoritative source)
    op.create_table(
        "sources",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("authority_type", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("source_key", name="uq_pyq_sources_source_key"),
        schema="pyq",
    )

    # 2. pyq.import_batches — one row per extraction run; idempotent by (source, stage, zip hash)
    op.create_table(
        "import_batches",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_stage", sa.String(40), nullable=False),
        sa.Column("zip_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("manifest_path", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["pyq.sources.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_pyq_import_batches_status",
        ),
        sa.UniqueConstraint(
            "source_id", "pipeline_stage", "zip_sha256", name="uq_pyq_import_batches_source_stage_sha"
        ),
        schema="pyq",
    )

    # 3. pyq.source_files — one row per paper PDF within a batch
    op.create_table(
        "source_files",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("batch_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paper_id", sa.String(64), nullable=False),
        sa.Column("paper_code", sa.String(80), nullable=True),
        sa.Column("exam_year", sa.String(4), nullable=True),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["pyq.import_batches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("batch_id", "paper_id", name="uq_pyq_source_files_batch_paper"),
        schema="pyq",
    )
    op.create_index("ix_pyq_source_files_exam_year", "source_files", ["exam_year"], schema="pyq")

    # 4. pyq.questions — raw + normalized staged question; raw fields never overwritten
    op.create_table(
        "questions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_file_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("extraction_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("staging_id", sa.String(64), nullable=False),
        sa.Column("question_hash", sa.String(64), nullable=False),
        sa.Column("normalized_question_hash", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(30), nullable=True),
        sa.Column("class_level", sa.String(2), nullable=True),
        sa.Column("raw_stem", sa.Text(), nullable=False),
        sa.Column("raw_options", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("normalized_stem", sa.Text(), nullable=True),
        sa.Column("normalized_options", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="EXTRACTED"),
        sa.Column("state", sa.String(30), nullable=False, server_default="EXTRACTED"),
        sa.Column("concept_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_file_id"], ["pyq.source_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["academic.concepts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "source_file_id", "question_number", "extraction_version",
            name="uq_pyq_questions_file_number_version",
        ),
        sa.UniqueConstraint("staging_id", name="uq_pyq_questions_staging_id"),
        sa.CheckConstraint(
            "state IN ('EXTRACTED','NORMALIZED','ANSWER_PENDING','ANSWER_VERIFIED',"
            "'ANSWER_CONFLICT','DEDUPE_CHECKED','QA_PENDING','QA_APPROVED',"
            "'QA_REJECTED','PROMOTION_ELIGIBLE','PROMOTED','BLOCKED')",
            name="ck_pyq_questions_state",
        ),
        schema="pyq",
    )
    op.create_index("ix_pyq_questions_state", "questions", ["state"], schema="pyq")
    op.create_index(
        "ix_pyq_questions_normalized_question_hash", "questions", ["normalized_question_hash"], schema="pyq"
    )
    op.create_index("ix_pyq_questions_question_hash", "questions", ["question_hash"], schema="pyq")

    # 5. pyq.answer_assertions — multiple answer-key claims per question, one per source
    op.create_table(
        "answer_assertions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("question_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asserted_option", sa.String(1), nullable=False),
        sa.Column("assertion_source", sa.String(80), nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="ASSERTED"),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["pyq.questions.id"], ondelete="CASCADE"),
        sa.CheckConstraint("asserted_option IN ('A','B','C','D')", name="ck_pyq_answer_assertions_option"),
        sa.CheckConstraint(
            "verification_status IN ('ASSERTED','VERIFIED','DISPUTED')",
            name="ck_pyq_answer_assertions_status",
        ),
        sa.UniqueConstraint("question_id", "assertion_source", name="uq_pyq_answer_assertions_question_source"),
        schema="pyq",
    )

    # 6. pyq.duplicate_candidates — staged<->staged or staged<->production match evidence
    op.create_table(
        "duplicate_candidates",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("question_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matched_question_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_content_item_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("classification", sa.String(30), nullable=False, server_default="CANDIDATE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["pyq.questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_question_id"], ["pyq.questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_content_item_id"], ["cms.content_items.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "classification IN ('CANDIDATE','EXACT_HASH','LIKELY','QA_CONFIRMED','QA_REJECTED_NOT_DUPLICATE')",
            name="ck_pyq_duplicate_candidates_classification",
        ),
        sa.CheckConstraint(
            "(matched_question_id IS NOT NULL)::int + (matched_content_item_id IS NOT NULL)::int = 1",
            name="ck_pyq_duplicate_candidates_one_target",
        ),
        schema="pyq",
    )
    op.create_index("ix_pyq_duplicate_candidates_question_id", "duplicate_candidates", ["question_id"], schema="pyq")

    # 7. pyq.qa_reviews — human verification decision on a staged question
    op.create_table(
        "qa_reviews",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("question_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["pyq.questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["identity.users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("decision IN ('APPROVED','REJECTED','NEEDS_INFO')", name="ck_pyq_qa_reviews_decision"),
        schema="pyq",
    )
    op.create_index("ix_pyq_qa_reviews_question_id", "qa_reviews", ["question_id"], schema="pyq")

    # 8. pyq.promotion_log — immutable record of promotion/rejection outcome
    op.create_table(
        "promotion_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("question_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_item_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["pyq.questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["content_item_id"], ["cms.content_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["identity.users.id"]),
        sa.UniqueConstraint("question_id", name="uq_pyq_promotion_log_question"),
        schema="pyq",
    )


def downgrade() -> None:
    op.drop_table("promotion_log", schema="pyq")

    op.drop_index("ix_pyq_qa_reviews_question_id", table_name="qa_reviews", schema="pyq")
    op.drop_table("qa_reviews", schema="pyq")

    op.drop_index("ix_pyq_duplicate_candidates_question_id", table_name="duplicate_candidates", schema="pyq")
    op.drop_table("duplicate_candidates", schema="pyq")

    op.drop_table("answer_assertions", schema="pyq")

    op.drop_index("ix_pyq_questions_question_hash", table_name="questions", schema="pyq")
    op.drop_index("ix_pyq_questions_normalized_question_hash", table_name="questions", schema="pyq")
    op.drop_index("ix_pyq_questions_state", table_name="questions", schema="pyq")
    op.drop_table("questions", schema="pyq")

    op.drop_index("ix_pyq_source_files_exam_year", table_name="source_files", schema="pyq")
    op.drop_table("source_files", schema="pyq")

    op.drop_table("import_batches", schema="pyq")

    op.drop_table("sources", schema="pyq")

    op.execute("DROP SCHEMA IF EXISTS pyq CASCADE")
