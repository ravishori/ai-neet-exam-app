"""cms: full-text search index on content_items (PR 3)

Adds search_text (plain concatenated text) and search_vector (weighted
tsvector) to cms.content_items, a GIN index for ranked full-text search, and
a GIN trigram index on search_text for the pg_trgm typo-tolerant fallback.

Both columns are populated for every currently-PUBLISHED QUESTION as part of
this migration. This is index population, not data backfill: search_text/
search_vector are 100% mechanically derived from data that already exists on
those rows (stem/options/explanation/academic names), the same way any index
built against an existing table covers its existing rows for free — it does
not invent or infer any new fact about historical rows, so it doesn't
conflict with this project's "never backfill" precedent for genuinely new
facts (e.g. original_filename, approval timestamps).

Revision ID: 9a1e4c7d2b63
Revises: 6e2b8d4a1f97
Create Date: 2026-08-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = '9a1e4c7d2b63'
down_revision = '6e2b8d4a1f97'
branch_labels = None
depends_on = None


# Shared by the one-time backfill below and app.modules.cms.repositories.search_repository
# (kept in sync manually — see the module docstring there).
_REINDEX_SQL = """
WITH item_data AS (
    SELECT
        ci.id AS item_id,
        cv.body ->> 'stem' AS stem,
        cv.body ->> 'explanation' AS explanation,
        (SELECT string_agg(opt ->> 'text', ' ') FROM jsonb_array_elements(cv.body -> 'options') AS opt) AS options_text,
        concept.name AS concept_name,
        topic.name AS topic_name,
        chapter.name AS chapter_name,
        subject.name AS subject_name,
        ku.summary AS ku_summary
    FROM cms.content_items ci
    JOIN cms.content_versions cv ON cv.id = ci.current_version_id
    LEFT JOIN academic.concepts concept ON concept.id = ci.concept_id
    LEFT JOIN academic.topics topic ON topic.id = concept.topic_id
    LEFT JOIN academic.chapters chapter ON chapter.id = topic.chapter_id
    LEFT JOIN academic.subjects subject ON subject.id = chapter.subject_id
    LEFT JOIN knowledge.knowledge_units ku ON ku.id = cv.knowledge_unit_id
    WHERE ci.content_type = 'QUESTION' AND ci.status = 'PUBLISHED' AND ci.current_version_id IS NOT NULL
)
UPDATE cms.content_items ci
SET
    search_text = concat_ws(' ',
        item_data.stem, item_data.options_text, item_data.explanation,
        item_data.concept_name, item_data.topic_name, item_data.chapter_name,
        item_data.subject_name, item_data.ku_summary
    ),
    search_vector =
        setweight(to_tsvector('english', coalesce(item_data.stem, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(item_data.options_text, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(item_data.explanation, '') || ' ' || coalesce(item_data.concept_name, '') || ' ' || coalesce(item_data.ku_summary, '')), 'C') ||
        setweight(to_tsvector('english', coalesce(item_data.chapter_name, '') || ' ' || coalesce(item_data.topic_name, '') || ' ' || coalesce(item_data.subject_name, '')), 'D')
FROM item_data
WHERE ci.id = item_data.item_id
"""


def upgrade() -> None:
    op.add_column("content_items", sa.Column("search_text", sa.Text(), nullable=True), schema="cms")
    op.add_column("content_items", sa.Column("search_vector", TSVECTOR(), nullable=True), schema="cms")

    op.create_index(
        "ix_content_items_search_vector",
        "content_items",
        ["search_vector"],
        schema="cms",
        postgresql_using="gin",
    )
    op.create_index(
        "ix_content_items_search_text_trgm",
        "content_items",
        ["search_text"],
        schema="cms",
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )

    op.execute(_REINDEX_SQL)


def downgrade() -> None:
    op.drop_index("ix_content_items_search_text_trgm", table_name="content_items", schema="cms")
    op.drop_index("ix_content_items_search_vector", table_name="content_items", schema="cms")
    op.drop_column("content_items", "search_text", schema="cms")
    op.drop_column("content_items", "search_vector", schema="cms")
