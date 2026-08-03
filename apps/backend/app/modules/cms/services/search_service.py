"""Question search (PR 3) — orchestrates the two-tier repository, redacts
answers, and shapes results. The only thing api/search_router.py talks to;
no SQL crosses this boundary.

Tier 1, always tried first: PostgreSQL full-text search (search_fulltext) —
websearch_to_tsquery + ts_rank against the GIN(search_vector) index.
Tier 2, only when tier 1 finds zero rows: pg_trgm word-similarity fallback
(search_fuzzy) for typo tolerance ("photosyntesis" -> "photosynthesis").
pg_trgm is never tried first and never blended into tier 1's ranking.

Future pgvector path: a third tier (search_semantic) can be added the same
way — same call signature, same SearchResult shape, selected the same way
tier 2 is (e.g. when tiers 1+2 both come up empty, or blended via reciprocal
rank fusion once there's a real need). Nothing here assumes ts_rank is the
only kind of score: `rank` is a plain float and `search_mode` is already a
string tag ("fulltext" | "fuzzy") a future "semantic" value slots into
without changing the response contract.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cms.repositories.search_repository import SearchRepository

_MATCHED_FIELD_COLUMNS = {
    "matched_stem": "stem",
    "matched_options": "options",
    "matched_explanation": "explanation",
    "matched_concept": "concept",
    "matched_topic": "topic",
    "matched_chapter": "chapter",
    "matched_subject": "subject",
    "matched_knowledge_unit": "knowledge_unit",
}


@dataclass
class SearchResult:
    data: list[dict]
    total: int
    limit: int
    offset: int
    search_mode: str  # "fulltext" | "fuzzy" | "empty"
    query: str
    filters: dict = field(default_factory=dict)


def _named_ref(id_col, name_col) -> dict | None:
    return {"id": str(id_col), "name": name_col} if id_col else None


def _matched_fields(row: dict) -> list[str]:
    return [label for col, label in _MATCHED_FIELD_COLUMNS.items() if row.get(col)]


_MARK_SPLIT = re.compile(r"(<mark>.*?</mark>)")


def _snippet_segments(snippet: str) -> list[dict]:
    """Parse ts_headline's <mark>/</mark> wrapper into {text, highlighted}
    segments the frontend renders as React elements — never as raw HTML.
    ts_headline only wraps matched substrings, it doesn't escape the
    surrounding source text, so passing its output straight into
    dangerouslySetInnerHTML would let anything stored in a question stem
    (even from trusted ingestion/admin content — defense in depth) inject
    markup. Structured segments sidestep that entirely."""
    segments = []
    for part in _MARK_SPLIT.split(snippet):
        if not part:
            continue
        if part.startswith("<mark>") and part.endswith("</mark>"):
            segments.append({"text": part[len("<mark>") : -len("</mark>")], "highlighted": True})
        else:
            segments.append({"text": part, "highlighted": False})
    return segments


def _snippet(row: dict) -> list[dict]:
    stem_snippet = row.get("stem_snippet") or ""
    if "<mark>" in stem_snippet:
        return _snippet_segments(stem_snippet)
    full_snippet = row.get("full_snippet") or ""
    if "<mark>" in full_snippet:
        return _snippet_segments(full_snippet)
    # Fuzzy-tier rows (and any fulltext edge case with no headline-able
    # match, e.g. a match only in a JSONB field ts_headline wasn't run
    # against) fall back to the plain stem — no highlight, since nothing
    # matched verbatim.
    body = row.get("body") or {}
    return [{"text": body.get("stem") or "", "highlighted": False}]


def _to_public_result(row: dict) -> dict:
    body = row["body"] or {}
    return {
        "id": str(row["id"]),
        "stem": body.get("stem"),
        "options": body.get("options", []),
        "difficulty": body.get("difficulty"),
        "bloom_level": body.get("bloom_level"),
        "pyq_year": body.get("pyq_year"),
        "tags": row.get("tags") or [],
        "language": row.get("language"),
        "concept": _named_ref(row.get("concept_id_j"), row.get("concept_name")),
        "topic": _named_ref(row.get("topic_id_j"), row.get("topic_name")),
        "chapter": _named_ref(row.get("chapter_id_j"), row.get("chapter_name")),
        "subject": _named_ref(row.get("subject_id_j"), row.get("subject_name")),
        "rank": float(row["rank"]) if row.get("rank") is not None else 0.0,
        "snippet": _snippet(row),
        "matched_fields": _matched_fields(row),
        # correct_option/explanation are deliberately never included here —
        # same redaction contract as PR 2's question browser.
    }


class SearchService:
    def __init__(self, session: AsyncSession):
        self.repo = SearchRepository(session)

    async def search(
        self,
        *,
        query: str,
        scope_type: str | None = None,
        scope_id=None,
        difficulty: str | None = None,
        pyq_year: int | None = None,
        content_type: str = "QUESTION",
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResult:
        filters = {
            "scope_type": scope_type,
            "scope_id": str(scope_id) if scope_id else None,
            "difficulty": difficulty,
            "pyq_year": pyq_year,
            "content_type": content_type,
        }

        rows, total = await self.repo.search_fulltext(
            query=query,
            scope_type=scope_type,
            scope_id=scope_id,
            difficulty=difficulty,
            pyq_year=pyq_year,
            content_type=content_type,
            limit=limit,
            offset=offset,
        )
        if total > 0:
            return SearchResult(
                data=[_to_public_result(r) for r in rows],
                total=total,
                limit=limit,
                offset=offset,
                search_mode="fulltext",
                query=query,
                filters=filters,
            )

        rows, total = await self.repo.search_fuzzy(
            query=query,
            scope_type=scope_type,
            scope_id=scope_id,
            difficulty=difficulty,
            pyq_year=pyq_year,
            content_type=content_type,
            limit=limit,
            offset=offset,
        )
        return SearchResult(
            data=[_to_public_result(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
            search_mode="fuzzy" if total > 0 else "empty",
            query=query,
            filters=filters,
        )

    async def reindex_item(self, item_id) -> None:
        await self.repo.reindex_item(item_id)

    async def reindex_all_published(self) -> int:
        return await self.repo.reindex_all_published()
