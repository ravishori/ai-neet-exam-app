"""Quick verification for flashcard seed V1 browse totals."""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import text

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.cms.repositories.cms_repository import CmsRepository


async def main() -> None:
    async with AsyncSessionLocal() as s:
        repo = CmsRepository(s)
        items, total = await repo.list_flashcards(limit=12, offset=0)
        items2, _ = await repo.list_flashcards(limit=12, offset=12)
        print("page1", len(items), "page2", len(items2), "total", total)
        assert total >= 300
        assert len(items) == 12
        assert len(items2) == 12

        async def subject_total(code: str) -> int:
            sid = (
                await s.execute(
                    text("SELECT id FROM academic.subjects WHERE code=:c AND deleted_at IS NULL"),
                    {"c": code},
                )
            ).scalar_one()
            _, t = await repo.list_flashcards(scope_type="SUBJECT", scope_id=uuid.UUID(str(sid)), limit=20, offset=0)
            return t

        phy = await subject_total("PHYSICS")
        chem = await subject_total("CHEMISTRY")
        bot = await subject_total("BOTANY")
        zoo = await subject_total("ZOOLOGY")
        print("physics", phy, "chemistry", chem, "botany", bot, "zoology", zoo, "biology", bot + zoo)


if __name__ == "__main__":
    asyncio.run(main())
