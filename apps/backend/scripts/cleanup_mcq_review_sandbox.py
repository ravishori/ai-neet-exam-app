#!/usr/bin/env python3
"""Cleanup expired P2.3 Human Gold Review Sandbox sessions."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/backend"))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.modules.cms.models.review_sandbox import (
    ReviewSandboxAuditEvent,
    ReviewSandboxSession,
)


async def cleanup_expired(*, dry_run: bool = False) -> dict[str, int]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    expired_count = deleted_sessions = 0
    async with factory() as session:
        now_rows = (
            await session.execute(
                select(ReviewSandboxSession).where(
                    ReviewSandboxSession.status.in_(["ACTIVE", "COMPLETED"]),
                    ReviewSandboxSession.expires_at <= __import__("datetime").datetime.now(__import__("datetime").UTC),
                )
            )
        ).scalars().all()
        expired_count = len(now_rows)
        if dry_run:
            await engine.dispose()
            return {"would_expire": expired_count, "deleted": 0}
        for sess in now_rows:
            sess.status = "EXPIRED"
            await session.execute(delete(ReviewSandboxAuditEvent).where(ReviewSandboxAuditEvent.session_id == sess.id))
            await session.delete(sess)
            deleted_sessions += 1
        await session.commit()
    await engine.dispose()
    return {"expired": expired_count, "deleted": deleted_sessions}


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup expired review sandbox sessions")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true", help="Run sandbox cleanup tests via pytest")
    args = parser.parse_args()
    if args.test:
        import subprocess

        py = ROOT / "apps/backend/.venv/Scripts/python.exe"
        if not py.exists():
            py = Path(sys.executable)
        r = subprocess.run(
            [str(py), "-m", "pytest", "app/modules/cms/tests/test_human_gold_sandbox.py", "-q"],
            cwd=ROOT / "apps/backend",
        )
        return r.returncode
    result = asyncio.run(cleanup_expired(dry_run=args.dry_run))
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
