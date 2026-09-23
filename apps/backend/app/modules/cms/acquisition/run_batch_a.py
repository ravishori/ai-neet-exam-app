"""Run Batch A acquisition against the configured DATABASE_URL (dev only).

Usage (from apps/backend, with venv):
  .venv\\Scripts\\python.exe -m app.modules.cms.acquisition.run_batch_a

Refuses non-trinetra_db databases. Never publishes.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.modules.academic.models  # noqa: F401
import app.modules.cms.models  # noqa: F401

# Ensure FK metadata for content_versions.knowledge_unit_id is registered.
import app.modules.knowledge.models  # noqa: F401
import app.modules.system.models  # noqa: F401
from app.modules.cms.acquisition.batch_a_acquisition_service import BatchAAcquisitionService
from app.modules.identity.models.user import User

ALLOWED_DB_NAMES = {"trinetra_db"}


async def _main() -> int:
    # Force development inventory DB — never test/prod for this CLI.
    url = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        dbname = (await session.execute(text("select current_database()"))).scalar()
        print(f"database={dbname}")
        if dbname not in ALLOWED_DB_NAMES:
            print(f"Refusing to run Batch A on database {dbname!r} (allowed: {sorted(ALLOWED_DB_NAMES)})")
            await engine.dispose()
            return 2

        user = (await session.execute(select(User).order_by(User.created_at.asc()).limit(1))).scalar_one_or_none()
        if not user:
            print("No user found to attribute authorship — aborting.")
            await engine.dispose()
            return 3

        before = dict(
            (
                await session.execute(
                    text(
                        "select status, count(*)::int from cms.content_items "
                        "where content_type='QUESTION' and deleted_at is null group by status"
                    )
                )
            ).all()
        )
        print("before", before)

        report = await BatchAAcquisitionService(session).run(author_id=user.id, actor_user_id=user.id)
        print(
            json.dumps(
                {
                    "created": report["created"],
                    "skipped_duplicate": report["skipped_duplicate"],
                    "rejected": report["rejected"],
                    "distributions": report["distributions"],
                    "hierarchy": report["hierarchy"],
                },
                indent=2,
            )
        )

        after = dict(
            (
                await session.execute(
                    text(
                        "select status, count(*)::int from cms.content_items "
                        "where content_type='QUESTION' and deleted_at is null group by status"
                    )
                )
            ).all()
        )
        print("after", after)
        published_before = before.get("PUBLISHED", 0)
        published_after = after.get("PUBLISHED", 0)
        if published_after != published_before:
            print("ERROR: PUBLISHED count changed — abort signal")
            await engine.dispose()
            return 4

        repo_docs = Path(__file__).resolve().parents[6] / "docs" / "product" / "_batch_a_run_report.json"
        repo_docs.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print("wrote", repo_docs)

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
