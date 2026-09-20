"""CMS test fixtures — mirrors root conftest for --confcutdir runs."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_test_db",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_test_db",
)

TEST_DATABASE_URL = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_test_db"


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _cms_seed_reference_data() -> AsyncGenerator[None, None]:
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.modules.academic.seed import seed_academic
    from app.modules.identity.seed import seed_identity

    seed_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with AsyncSession(bind=seed_engine) as session:
        await seed_identity(session)
        await seed_academic(session)
    await seed_engine.dispose()
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        await session.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(sync_session, transaction):
            if transaction.nested and not transaction._parent.nested:
                sync_session.begin_nested()

        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await test_engine.dispose()
