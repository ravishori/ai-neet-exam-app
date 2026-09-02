"""Shared Physics acquisition helpers — legacy firewall + dedupe hashes (read-only on legacy)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cms.acquisition.physics_t6d_constants import LEGACY_BATCH
from app.modules.cms.services.factory_candidate_validation import stem_hash

LEGACY_FINGERPRINT_EXPECTED = "937c60a9aaa5dcbedfa9b5bc569d45a0"


async def legacy_fingerprint(session: AsyncSession) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE concept_id IS NULL) AS null_c,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                       md5(string_agg(id::text || ':' || COALESCE(concept_id::text, 'null') || ':' || status, '|' ORDER BY id::text)) AS fp
                FROM cms.content_items
                WHERE :b = ANY(tags) OR slug LIKE 'legacy-phy11-%'
                """
            ),
            {"b": LEGACY_BATCH},
        )
    ).mappings().one()
    return dict(row)


async def assert_legacy_invariant(session: AsyncSession, before: dict, after: dict) -> list[str]:
    errors: list[str] = []
    if int(after.get("total", -1)) != int(before.get("total", -2)):
        errors.append("LEGACY_TOTAL_CHANGED")
    if int(after.get("null_c", -1)) != int(before.get("null_c", -2)):
        errors.append("LEGACY_NULL_CONCEPT_CHANGED")
    if int(after.get("published", -1)) != int(before.get("published", -2)):
        errors.append("LEGACY_PUBLISHED_CHANGED")
    if after.get("fp") != before.get("fp"):
        errors.append("LEGACY_FINGERPRINT_CHANGED")
    return errors


async def physics_stem_hashes_for_dedupe(
    session: AsyncSession,
    *,
    exclude_batch_slug: str,
) -> set[str]:
    """Stem hashes for duplicate gate — includes legacy + T6-D + all other Physics (read-only)."""
    rows = (
        await session.execute(
            text(
                """
                SELECT cv.body->>'stem' AS stem
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type = 'QUESTION'
                  AND ci.deleted_at IS NULL
                  AND NOT (ci.slug LIKE :exclude_slug)
                  AND cv.body ? 'stem'
                """
            ),
            {"exclude_slug": exclude_batch_slug},
        )
    ).scalars().all()
    return {stem_hash(s) for s in rows if s}


async def batch_inventory(session: AsyncSession, *, batch_slug: str, batch_tag: str) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                       COUNT(*) FILTER (WHERE status = 'DRAFT') AS draft,
                       COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                       COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved
                FROM cms.content_items
                WHERE content_type = 'QUESTION'
                  AND deleted_at IS NULL
                  AND (slug LIKE :slug OR :tag = ANY(tags))
                """
            ),
            {"slug": batch_slug, "tag": batch_tag},
        )
    ).mappings().one()
    return dict(row)
