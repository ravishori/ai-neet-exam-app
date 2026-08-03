"""pr11: question solving experience — bookmarks, notes, reports, attempt-answer extensions

Adds three additive columns to assessment.attempt_answers (confidence,
marked_for_review, time_spent_seconds — all nullable/defaulted, existing rows
and callers unaffected) and three new tables:

- learning.question_bookmarks — one row per (user, question) save-for-later flag
- learning.question_notes — one running note per (user, question)
- cms.content_reports — student-submitted content-quality flags ("Report Issue")

No backfill: these are all genuinely new facts (a student did/didn't bookmark
a question, wrote a note, spent N seconds) that don't exist for historical
rows, so existing rows are simply left NULL/absent, consistent with this
project's non-backfill precedent for new facts.

Revision ID: 7c3f9e1a4d82
Revises: 9a1e4c7d2b63
Create Date: 2026-08-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '7c3f9e1a4d82'
down_revision = '9a1e4c7d2b63'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attempt_answers", sa.Column("confidence", sa.String(10), nullable=True), schema="assessment")
    op.add_column(
        "attempt_answers",
        sa.Column("marked_for_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="assessment",
    )
    op.add_column("attempt_answers", sa.Column("time_spent_seconds", sa.Integer(), nullable=True), schema="assessment")

    op.create_table(
        "question_bookmarks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "content_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cms.content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "content_item_id", name="uq_question_bookmark_user_question"),
        schema="learning",
    )

    op.create_table(
        "question_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "content_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cms.content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "content_item_id", name="uq_question_note_user_question"),
        schema="learning",
    )

    op.create_table(
        "content_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "content_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cms.content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "content_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cms.content_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reported_by", UUID(as_uuid=True), sa.ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="cms",
    )


def downgrade() -> None:
    op.drop_table("content_reports", schema="cms")
    op.drop_table("question_notes", schema="learning")
    op.drop_table("question_bookmarks", schema="learning")
    op.drop_column("attempt_answers", "time_spent_seconds", schema="assessment")
    op.drop_column("attempt_answers", "marked_for_review", schema="assessment")
    op.drop_column("attempt_answers", "confidence", schema="assessment")
