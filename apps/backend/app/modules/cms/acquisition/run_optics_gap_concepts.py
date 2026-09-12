"""WAVE-P0-11A — close Optics hierarchy gaps on development trinetra_db only.

Usage (from apps/backend):
  .venv\\Scripts\\python.exe -m app.modules.cms.acquisition.run_optics_gap_concepts

Never modifies CMS questions. Rolls back if fingerprints change or DB ≠ trinetra_db.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

import app.modules.academic.models  # noqa: F401
import app.modules.cms.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
import app.modules.system.models  # noqa: F401
from app.modules.cms.acquisition.optics_gap_concepts import (
    PHY_PILOT_IDS,
    audit_optics_hierarchy,
    ensure_optics_gap_concepts,
)
from app.modules.cms.models import ContentItem

ALLOWED_DB = "trinetra_db"


def _body_fingerprint(body: dict | None) -> str:
    raw = json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def fingerprint_phy(session: AsyncSession) -> dict[str, dict[str, Any]]:
    ids = [uuid.UUID(i) for i in PHY_PILOT_IDS]
    result = await session.execute(
        select(ContentItem).options(selectinload(ContentItem.versions)).where(ContentItem.id.in_(ids))
    )
    out: dict[str, dict[str, Any]] = {}
    for item in result.scalars().unique().all():
        by_id = {v.id: v for v in item.versions}
        latest = by_id.get(item.latest_version_id)
        body = latest.body if latest else {}
        out[str(item.id)] = {
            "status": item.status,
            "concept_id": str(item.concept_id) if item.concept_id else None,
            "title": item.title,
            "version": item.version,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "body_sha256": _body_fingerprint(body if isinstance(body, dict) else {}),
            "model_used": latest.model_used if latest else None,
            "difficulty": (body or {}).get("difficulty") if isinstance(body, dict) else None,
            "correct_option": (body or {}).get("correct_option") if isinstance(body, dict) else None,
        }
    return out


async def _main() -> int:
    url = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        dbname = (await session.execute(text("select current_database()"))).scalar()
        print(f"database={dbname}")
        if dbname != ALLOWED_DB:
            print(f"Refusing: expected {ALLOWED_DB!r}, got {dbname!r}")
            await engine.dispose()
            return 2

        print("=== PRE-AUDIT (read-only) ===")
        pre_audit = await audit_optics_hierarchy(session)
        print(json.dumps({"gap_status": pre_audit["gap_status"], "count": len(pre_audit["concepts"])}, indent=2))

        before = await fingerprint_phy(session)
        if len(before) != 10:
            print(f"Refusing: expected 10 PHY fingerprints, got {len(before)}")
            await engine.dispose()
            return 3

        try:
            report = await ensure_optics_gap_concepts(session)
            await session.flush()
            after = await fingerprint_phy(session)
            if before != after:
                await session.rollback()
                print("ROLLBACK: PHY question fingerprints changed unexpectedly")
                print(json.dumps({"before": before, "after": after}, indent=2, default=str))
                await engine.dispose()
                return 4
            await session.commit()
        except Exception as exc:
            await session.rollback()
            print(f"ROLLBACK: {exc}")
            await engine.dispose()
            return 5

        post_audit = await audit_optics_hierarchy(session)
        print("=== RESULT ===")
        print(
            json.dumps(
                {
                    "created": report["created"],
                    "already_existed": report["already_existed"],
                    "gap_status_after": post_audit["gap_status"],
                    "existing_gap_ids": post_audit["existing_gap_ids"],
                    "phy_fingerprints_unchanged": True,
                    "future_question_mapping": report["future_question_mapping"],
                },
                indent=2,
            )
        )
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
