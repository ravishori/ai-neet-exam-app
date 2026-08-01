"""Seed all modules. Run from apps/backend: python scripts/seed.py"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.modules.academic.seed import seed_academic  # noqa: E402
from app.modules.cms.seed import seed_cms  # noqa: E402
from app.modules.identity.seed import seed_identity  # noqa: E402


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_identity(session)
        await seed_academic(session)
        await seed_cms(session)


if __name__ == "__main__":
    asyncio.run(main())
