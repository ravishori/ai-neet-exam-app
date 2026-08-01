"""Seed roles + permissions. Run from apps/backend: python scripts/seed.py"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.modules.identity.seed import seed_identity  # noqa: E402


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_identity(session)


if __name__ == "__main__":
    asyncio.run(main())
