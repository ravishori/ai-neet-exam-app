"""Deterministic CMS integrity fingerprints for T6-F2 DoD evidence.

Read-oriented helpers. Fingerprints hash identity + status + body content —
not volatile timestamps — so idempotent no-ops compare cleanly.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cms.acquisition.physics_t6f2_constants import BATCH_ID, LEGACY_BATCH, T6D_BATCH_ID


async def fingerprint_batch(session: AsyncSession, *, batch_tag: str) -> dict[str, Any]:
    """Content fingerprint for a tagged question batch (e.g. T6-D / T6-F1)."""
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                       COUNT(*) FILTER (WHERE status = 'DRAFT') AS draft,
                       md5(
                         coalesce(
                           string_agg(
                             ci.id::text
                               || '|' || ci.slug
                               || '|' || ci.status
                               || '|' || coalesce(ci.concept_id::text, 'null')
                               || '|' || md5(coalesce(cv.body::text, ''))
                               || '|' || coalesce(array_to_string(ci.tags, ','), ''),
                             E'\\n' ORDER BY ci.id::text
                           ),
                           ''
                         )
                       ) AS content_fp
                FROM cms.content_items ci
                LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type = 'QUESTION'
                  AND ci.deleted_at IS NULL
                  AND :b = ANY(ci.tags)
                """
            ),
            {"b": batch_tag},
        )
    ).mappings().one()
    return dict(row)


async def fingerprint_protected_cms(session: AsyncSession) -> dict[str, Any]:
    """CMS questions that T6-F2 must not mutate (everything except the F1 batch)."""
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                       md5(
                         coalesce(
                           string_agg(
                             ci.id::text
                               || '|' || ci.slug
                               || '|' || ci.status
                               || '|' || coalesce(ci.concept_id::text, 'null')
                               || '|' || md5(coalesce(cv.body::text, ''))
                               || '|' || coalesce(array_to_string(ci.tags, ','), ''),
                             E'\\n' ORDER BY ci.id::text
                           ),
                           ''
                         )
                       ) AS content_fp
                FROM cms.content_items ci
                LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type = 'QUESTION'
                  AND ci.deleted_at IS NULL
                  AND NOT (
                    :f1 = ANY(ci.tags)
                    OR ci.slug LIKE :f1_slug
                  )
                """
            ),
            {"f1": BATCH_ID, "f1_slug": f"{BATCH_ID}-q%"},
        )
    ).mappings().one()
    return dict(row)


async def fingerprint_t6f1_published(session: AsyncSession) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       md5(
                         coalesce(
                           string_agg(
                             ci.id::text
                               || '|' || ci.slug
                               || '|' || ci.status
                               || '|' || md5(coalesce(cv.body::text, '')),
                             E'\\n' ORDER BY ci.id::text
                           ),
                           ''
                         )
                       ) AS content_fp
                FROM cms.content_items ci
                LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type = 'QUESTION'
                  AND ci.deleted_at IS NULL
                  AND :b = ANY(ci.tags)
                  AND ci.status = 'PUBLISHED'
                """
            ),
            {"b": BATCH_ID},
        )
    ).mappings().one()
    return dict(row)


async def _row_canon_map(session: AsyncSession, *, where_sql: str, params: dict[str, Any]) -> dict[str, str]:
    """Map content_item id → canonical content string for diffing."""
    rows = (
        await session.execute(
            # B608 false positive: where_sql is always one of 2 hardcoded
            # SQL-fragment literals from this module's own call sites
            # (collect_integrity_snapshot), containing only bind
            # placeholders (:b, :f1, :f1_slug). Actual values are never
            # interpolated here — they are passed via `params` below.
            text(
                f"""
                SELECT ci.id::text AS id,
                       ci.id::text
                         || '|' || ci.slug
                         || '|' || ci.status
                         || '|' || coalesce(ci.concept_id::text, 'null')
                         || '|' || md5(coalesce(cv.body::text, ''))
                         || '|' || coalesce(array_to_string(ci.tags, ','), '') AS canon
                FROM cms.content_items ci
                LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type = 'QUESTION'
                  AND ci.deleted_at IS NULL
                  AND ({where_sql})
                """  # nosec B608
            ),
            params,
        )
    ).mappings().all()
    return {str(r["id"]): str(r["canon"]) for r in rows}


async def collect_integrity_snapshot(session: AsyncSession) -> dict[str, Any]:
    t6d = await fingerprint_batch(session, batch_tag=T6D_BATCH_ID)
    legacy = await fingerprint_batch(session, batch_tag=LEGACY_BATCH)
    protected = await fingerprint_protected_cms(session)
    t6f1 = await fingerprint_t6f1_published(session)
    t6d_rows = await _row_canon_map(session, where_sql=":b = ANY(ci.tags)", params={"b": T6D_BATCH_ID})
    protected_rows = await _row_canon_map(
        session,
        where_sql="NOT (:f1 = ANY(ci.tags) OR ci.slug LIKE :f1_slug)",
        params={"f1": BATCH_ID, "f1_slug": f"{BATCH_ID}-q%"},
    )
    return {
        "t6d": t6d,
        "legacy": legacy,
        "t6f1_published": t6f1,
        "protected_non_f1_cms": protected,
        "t6d_row_canons": t6d_rows,
        "protected_row_canons": protected_rows,
        "batch_ids": {
            "t6f1": BATCH_ID,
            "t6d": T6D_BATCH_ID,
            "legacy": LEGACY_BATCH,
        },
        "historical_pre_f2_deep_immutability": "NOT RETROACTIVELY VERIFIABLE",
        "note": (
            "Fingerprints cover id|slug|status|concept_id|body_md5|tags. "
            "Timestamps excluded. Pre-T6-F2 historical fingerprints were not "
            "captured at publish time."
        ),
    }


def diff_row_canons(before: dict[str, str], after: dict[str, str]) -> dict[str, int]:
    before_ids = set(before)
    after_ids = set(after)
    added = after_ids - before_ids
    deleted = before_ids - after_ids
    shared = before_ids & after_ids
    changed = {i for i in shared if before[i] != after[i]}
    return {
        "changed_rows": len(changed),
        "added_rows": len(added),
        "deleted_rows": len(deleted),
        "unexpected_updates": len(changed),
        "unexpected_inserts": len(added),
        "unexpected_deletes": len(deleted),
        "unexpected_status_or_content_changes": len(changed),
    }
