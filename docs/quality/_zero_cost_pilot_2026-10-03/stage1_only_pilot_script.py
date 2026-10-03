"""Zero-cost, Stage-1-only pilot. Reuses resolve_batch() unmodified -- never
constructs a Gemini provider, never calls resolve_stage2_batch. Commits
per page, same as the existing resolver."""
import asyncio, sys
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from scripts.resolve_pyq_answers import _load_ku_index, resolve_batch, ResolveReport

async def main(max_total: int):
    async with AsyncSessionLocal() as session:
        idx = await _load_ku_index(session)
        rows = (await session.execute(
            text("SELECT id, raw_stem, raw_options FROM pyq.questions WHERE state='ANSWER_PENDING' ORDER BY id LIMIT :lim"),
            {"lim": max_total},
        )).all()
        report = ResolveReport()
        await resolve_batch(session, idx, rows, report, apply=True)
        await session.commit()
        print(report.__dict__)

if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1])))
