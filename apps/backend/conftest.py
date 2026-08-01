"""Integration test infrastructure — see ADR-0020.

Points the whole test run at a dedicated trinetra_test_db (never the dev
database) *before* any app module is imported, since app.core.database
creates its engine at import time from app.core.config.get_settings().
"""

import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_test_db"
os.environ["DATABASE_URL_SYNC"] = "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_test_db"

import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

get_settings.cache_clear()

from app.main import app  # noqa: E402
from app.modules.academic.seed import seed_academic  # noqa: E402
from app.modules.identity.seed import seed_identity  # noqa: E402

TEST_DATABASE_URL = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_test_db"

# Every test module needs `pytestmark = pytest.mark.asyncio(loop_scope="session")`
# at its top (see tests/test_smoke.py) — asyncio_default_fixture_loop_scope in
# pytest.ini only controls *fixtures*; pytest-asyncio reads the test's own loop
# scope from this marker during collection (pytest_generate_tests), which runs
# before any conftest hook could inject the marker programmatically. Without a
# matching scope, a test function gets its own function-scoped loop while
# session-scoped fixtures (like _seed_reference_data) run on the session loop,
# and awaiting a connection across that mismatch raises "Task ... attached to
# a different loop" the moment a test actually touches the database.


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _seed_reference_data() -> AsyncGenerator[None, None]:
    """Roles/permissions + a real NEET curriculum, seeded once per test run."""
    seed_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with AsyncSession(bind=seed_engine) as session:
        await seed_identity(session)
        await seed_academic(session)
    await seed_engine.dispose()
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """One SAVEPOINT-isolated session per test — commits inside application
    code end/restart the savepoint, never the outer transaction, which is
    rolled back here so no test leaves data behind for the next one.

    Uses its own freshly-created engine (NullPool, disposed at teardown)
    rather than the app's shared module-level engine — asyncpg ties a
    connection to the asyncio task context that created it, and reusing one
    engine's pool across the different task contexts anyio's structured
    concurrency creates (inside httpx's ASGITransport) raises "attached to a
    different loop" even within a single real event loop. A fresh engine per
    test sidesteps it entirely.
    """
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


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """httpx client hitting the real FastAPI app in-process (ASGITransport —
    no network port, so none of the stale-listener issues this project hit
    all session with real uvicorn processes apply to tests)."""
    from app.core.database import get_db

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def csrf_headers(client: AsyncClient) -> dict[str, str]:
    """Read the double-submit CSRF cookie and echo it as a header, exactly
    like apps/web/src/lib/api-client.ts does for every mutating request."""
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


@pytest_asyncio.fixture
async def register_user():
    """Factory fixture: register + log in a user, return (user_data, headers-ready client).

    Usage: user = await register_user(client, role_codes=["ADMIN"])
    """

    async def _register(ac: AsyncClient, *, role_codes: list[str] | None = None, db_session: AsyncSession | None = None):
        email = f"test-{uuid.uuid4().hex[:12]}@example.com"
        password = "TestPassword!234"
        resp = await ac.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "first_name": "Test"},
        )
        assert resp.status_code == 201, resp.text
        user_id = resp.json()["data"]["id"]

        if role_codes and db_session is not None:
            from sqlalchemy import select

            from app.modules.identity.models.role import Role, UserRole

            for code in role_codes:
                result = await db_session.execute(select(Role).where(Role.code == code))
                role = result.scalar_one()
                db_session.add(UserRole(user_id=uuid.UUID(user_id), role_id=role.id))
            await db_session.commit()

            # Re-login so the access token/roles reflect the newly granted roles.
            await ac.post("/api/v1/auth/logout")
            resp = await ac.post("/api/v1/auth/login", json={"email": email, "password": password})
            assert resp.status_code == 200, resp.text

        return {"id": user_id, "email": email, "password": password}

    return _register
