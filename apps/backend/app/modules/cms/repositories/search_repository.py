"""Raw-SQL-backed search queries for cms.content_items (PR 3).

Two tiers, both against the same denormalized search_text/search_vector
columns (see alembic/versions/9a1e4c7d2b63_cms_search_fts_and_trgm.py):

- search_fulltext: PostgreSQL FTS via the GIN(search_vector) index,
  websearch_to_tsquery + ts_rank. Primary path.
- search_fuzzy: pg_trgm similarity via the GIN(search_text gin_trgm_ops)
  index. Fallback only, for typo tolerance — SearchService calls this
  when search_fulltext returns nothing.

No SQL leaks past this file — SearchService consumes plain dicts.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Shared by reindex_item/reindex_all_published below and by the one-time
# backfill in the migration (kept in sync manually — same formula, just a
# different WHERE clause).
_REINDEX_CTE = """
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
    WHERE ci.content_type = 'QUESTION' AND ci.current_version_id IS NOT NULL
    {item_filter}
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

# Joined once, reused by both search tiers so a result row always carries
# enough to build the same response shape (academic names, matched_fields).
_RESULT_JOIN = """
    FROM cms.content_items ci
    JOIN cms.content_versions cv ON cv.id = ci.current_version_id
    LEFT JOIN academic.concepts concept ON concept.id = ci.concept_id
    LEFT JOIN academic.topics topic ON topic.id = concept.topic_id
    LEFT JOIN academic.chapters chapter ON chapter.id = topic.chapter_id
    LEFT JOIN academic.subjects subject ON subject.id = chapter.subject_id
    LEFT JOIN knowledge.knowledge_units ku ON ku.id = cv.knowledge_unit_id
"""

_RESULT_COLUMNS = """
    ci.id, cv.body, ci.tags, ci.language, ci.concept_id,
    concept.id AS concept_id_j, concept.name AS concept_name,
    topic.id AS topic_id_j, topic.name AS topic_name,
    chapter.id AS chapter_id_j, chapter.name AS chapter_name,
    subject.id AS subject_id_j, subject.name AS subject_name
"""


def _scope_filter(scope_type: str | None, scope_id: uuid.UUID | None) -> tuple[str, dict]:
    if not scope_type or not scope_id:
        return "", {}
    column = {
        "SUBJECT": "subject.id",
        "CHAPTER": "chapter.id",
        "TOPIC": "topic.id",
        "CONCEPT": "concept.id",
    }.get(scope_type)
    if not column:
        return "", {}
    return f" AND {column} = :scope_id", {"scope_id": str(scope_id)}


def _common_filters(
    *,
    scope_type: str | None,
    scope_id: uuid.UUID | None,
    difficulty: str | None,
    pyq_year: int | None,
    content_type: str,
) -> tuple[str, dict]:
    clause, params = _scope_filter(scope_type, scope_id)
    params["content_type"] = content_type
    clause += " AND ci.content_type = :content_type AND ci.status = 'PUBLISHED'"
    if difficulty:
        clause += " AND cv.body ->> 'difficulty' = :difficulty"
        params["difficulty"] = difficulty
    if pyq_year:
        clause += " AND (cv.body ->> 'pyq_year')::int = :pyq_year"
        params["pyq_year"] = pyq_year
    return clause, params


class SearchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def reindex_item(self, item_id: uuid.UUID) -> None:
        sql = _REINDEX_CTE.format(item_filter="AND ci.id = :item_id")
        await self.session.execute(text(sql), {"item_id": str(item_id)})
        await self.session.commit()

    async def reindex_all_published(self) -> int:
        """Bulk (re)index every currently-PUBLISHED question — used for the
        migration backfill and available as an admin catch-up operation if
        search_text/search_vector ever drift (e.g. a question's academic
        assignment changes after publish, which nothing else currently
        triggers a reindex for)."""
        sql = _REINDEX_CTE.format(item_filter="AND ci.status = 'PUBLISHED'")
        result = await self.session.execute(text(sql))
        await self.session.commit()
        return result.rowcount

    async def search_fulltext(
        self,
        *,
        query: str,
        scope_type: str | None,
        scope_id: uuid.UUID | None,
        difficulty: str | None,
        pyq_year: int | None,
        content_type: str,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        clause, params = _common_filters(
            scope_type=scope_type, scope_id=scope_id, difficulty=difficulty, pyq_year=pyq_year, content_type=content_type
        )
        params["query"] = query

        sql = f"""
            SELECT
                {_RESULT_COLUMNS},
                ts_rank(ci.search_vector, websearch_to_tsquery('english', :query)) AS rank,
                ts_headline(
                    'english', coalesce(cv.body ->> 'stem', ''), websearch_to_tsquery('english', :query),
                    'MaxFragments=1, MaxWords=25, MinWords=5, StartSel=<mark>, StopSel=</mark>, HighlightAll=true'
                ) AS stem_snippet,
                ts_headline(
                    'english', coalesce(ci.search_text, ''), websearch_to_tsquery('english', :query),
                    'MaxFragments=1, MaxWords=25, MinWords=5, StartSel=<mark>, StopSel=</mark>'
                ) AS full_snippet,
                to_tsvector('english', coalesce(cv.body ->> 'stem', '')) @@ websearch_to_tsquery('english', :query) AS matched_stem,
                to_tsvector('english', coalesce((SELECT string_agg(opt ->> 'text', ' ') FROM jsonb_array_elements(cv.body -> 'options') AS opt), ''))
                    @@ websearch_to_tsquery('english', :query) AS matched_options,
                to_tsvector('english', coalesce(cv.body ->> 'explanation', '')) @@ websearch_to_tsquery('english', :query) AS matched_explanation,
                to_tsvector('english', coalesce(concept.name, '')) @@ websearch_to_tsquery('english', :query) AS matched_concept,
                to_tsvector('english', coalesce(topic.name, '')) @@ websearch_to_tsquery('english', :query) AS matched_topic,
                to_tsvector('english', coalesce(chapter.name, '')) @@ websearch_to_tsquery('english', :query) AS matched_chapter,
                to_tsvector('english', coalesce(subject.name, '')) @@ websearch_to_tsquery('english', :query) AS matched_subject,
                to_tsvector('english', coalesce(ku.summary, '')) @@ websearch_to_tsquery('english', :query) AS matched_knowledge_unit
            {_RESULT_JOIN}
            WHERE ci.search_vector @@ websearch_to_tsquery('english', :query)
            {clause}
            ORDER BY rank DESC, ci.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"""
            SELECT count(*) {_RESULT_JOIN}
            WHERE ci.search_vector @@ websearch_to_tsquery('english', :query)
            {clause}
        """

        count_params = dict(params)
        params["limit"] = limit
        params["offset"] = offset

        total = (await self.session.execute(text(count_sql), count_params)).scalar_one()
        rows = (await self.session.execute(text(sql), params)).mappings().all()
        return [dict(r) for r in rows], total

    async def search_fuzzy(
        self,
        *,
        query: str,
        scope_type: str | None,
        scope_id: uuid.UUID | None,
        difficulty: str | None,
        pyq_year: int | None,
        content_type: str,
        limit: int,
        offset: int,
        threshold: float = 0.35,
    ) -> tuple[list[dict], int]:
        """pg_trgm fallback — typo-tolerant, ranked by trigram similarity.
        Only called by SearchService when search_fulltext finds nothing.

        Uses word_similarity()/the `<%` operator rather than plain
        similarity(): similarity() compares two whole strings, so a short
        query against search_text's large concatenated blob would score
        near zero even on a perfect word match, since the score is
        normalized by the union of both strings' trigrams. word_similarity
        instead finds the best-matching *substring* of search_text, which is
        what "does this misspelled word appear in this long field" actually
        means. `<%` (rather than calling word_similarity() in WHERE) is what
        lets the GIN(search_text gin_trgm_ops) index accelerate this —
        pg_trgm indexes support %, <%, and %> directly; a bare function call
        in WHERE would force a sequential scan. The threshold is set via
        SET LOCAL so it's explicit per-call rather than relying on the
        pg_trgm.word_similarity_threshold session default.
        """
        clause, params = _common_filters(
            scope_type=scope_type, scope_id=scope_id, difficulty=difficulty, pyq_year=pyq_year, content_type=content_type
        )
        params["query"] = query

        sql = f"""
            SELECT
                {_RESULT_COLUMNS},
                word_similarity(:query, coalesce(ci.search_text, '')) AS rank,
                (:query <% coalesce(cv.body ->> 'stem', '')) AS matched_stem,
                (:query <% coalesce((SELECT string_agg(opt ->> 'text', ' ') FROM jsonb_array_elements(cv.body -> 'options') AS opt), '')) AS matched_options,
                (:query <% coalesce(cv.body ->> 'explanation', '')) AS matched_explanation,
                (:query <% coalesce(concept.name, '')) AS matched_concept,
                (:query <% coalesce(topic.name, '')) AS matched_topic,
                (:query <% coalesce(chapter.name, '')) AS matched_chapter,
                (:query <% coalesce(subject.name, '')) AS matched_subject,
                (:query <% coalesce(ku.summary, '')) AS matched_knowledge_unit
            {_RESULT_JOIN}
            WHERE :query <% coalesce(ci.search_text, '')
            {clause}
            ORDER BY rank DESC, ci.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"""
            SELECT count(*) {_RESULT_JOIN}
            WHERE :query <% coalesce(ci.search_text, '')
            {clause}
        """

        count_params = dict(params)
        params["limit"] = limit
        params["offset"] = offset

        # SET LOCAL can't take a bind parameter over the wire protocol; safe to
        # interpolate directly since `threshold` is an internal float default,
        # never sourced from request input.
        await self.session.execute(text(f"SET LOCAL pg_trgm.word_similarity_threshold = {float(threshold)}"))
        # Benchmarked at ~5000 rows: Postgres's cost estimator for `<%`
        # underestimates the trigram index's benefit here and picks a seq
        # scan (~345ms) over the GIN(search_text gin_trgm_ops) index
        # (~11ms) — a ~30x gap. Forcing it is safe because this tier only
        # ever runs this one query, as a low-QPS fallback after tier 1
        # finds nothing, scoped to this transaction alone via SET LOCAL.
        await self.session.execute(text("SET LOCAL enable_seqscan = off"))
        total = (await self.session.execute(text(count_sql), count_params)).scalar_one()
        rows = (await self.session.execute(text(sql), params)).mappings().all()
        return [dict(r) for r in rows], total
