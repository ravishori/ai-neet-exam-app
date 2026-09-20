"""FACTORY-P1 safety: question inventory checksum on a named database."""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_URL = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"


async def checksum(url: str) -> dict:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        counts = (
            await conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                           COUNT(*) FILTER (WHERE status = 'DRAFT') AS draft,
                           COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                           COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
                           COUNT(*) FILTER (WHERE status = 'ARCHIVED') AS archived,
                           COUNT(*) FILTER (WHERE status = 'CHANGES_REQUESTED') AS changes_requested
                    FROM cms.content_items
                    WHERE content_type = 'QUESTION' AND deleted_at IS NULL
                    """
                )
            )
        ).mappings().one()
        item_cs = (
            await conn.execute(
                text(
                    """
                    SELECT md5(
                        string_agg(
                            id::text || ':' || status || ':' ||
                            coalesce(current_version_id::text, '') || ':' ||
                            coalesce(latest_version_id::text, ''),
                            '|' ORDER BY id
                        )
                    ) AS checksum
                    FROM cms.content_items
                    WHERE content_type = 'QUESTION' AND deleted_at IS NULL
                    """
                )
            )
        ).scalar()
        version = (
            await conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS versions,
                           md5(
                               string_agg(
                                   cv.id::text || ':' || cv.version_no::text || ':' ||
                                   md5(cv.body::text) || ':' || cv.workflow_state,
                                   '|' ORDER BY cv.id
                               )
                           ) AS body_checksum
                    FROM cms.content_versions cv
                    JOIN cms.content_items ci ON ci.id = cv.content_item_id
                    WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
                    """
                )
            )
        ).mappings().one()
        reviews = (
            await conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS review_count
                    FROM cms.content_reviews cr
                    JOIN cms.content_versions cv ON cv.id = cr.content_version_id
                    JOIN cms.content_items ci ON ci.id = cv.content_item_id
                    WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
                    """
                )
            )
        ).scalar()
    await engine.dispose()
    return {
        "counts": dict(counts),
        "item_checksum": item_cs,
        "versions": dict(version),
        "review_count": reviews,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--label", default="snapshot")
    args = parser.parse_args()
    result = asyncio.run(checksum(args.url))
    print(json.dumps({"label": args.label, **result}, indent=2, default=str))


if __name__ == "__main__":
    main()
