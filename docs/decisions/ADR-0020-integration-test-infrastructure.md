# ADR-0020: Integration test infrastructure — dedicated test DB, transactional isolation

## Status
Accepted

## Context
Every automated test written across SP0–SP9 and the Phase 2 work since has
been a pure-function unit test (`compute_mastery`, `safe_percent`,
`verify_payment_signature`, ...). All 40 of them pass without touching a
database, an HTTP layer, or a permission check. Every actual regression
this session caught in those areas — the suspended-user-can-still-log-in
bug, the `RoleRepository.list` naming footgun, the stale-relationship bug
after a bulk role update — was caught by hand, via curl and browser
click-through, not by a test that would catch it again automatically next
time. This ADR adds the missing layer: real integration tests against the
actual FastAPI app, over a real Postgres database.

## Decision

**A dedicated `trinetra_test_db`, never the dev database.** Created once
(`CREATE DATABASE trinetra_test_db OWNER trinetra_app`) and migrated with
the real Alembic history (`alembic upgrade head` against it), so tests run
against the actual deployed schema — not an ORM-regenerated approximation
that could silently diverge from what migrations actually produce.

**`conftest.py` at the backend root** sets `DATABASE_URL`/`DATABASE_URL_SYNC`
to the test database *before* importing any app module — `app.core.database`
creates its engine at import time from `get_settings()`, so the environment
override has to land first or the test suite would quietly point at the
dev database.

**Per-test isolation via SAVEPOINT, not per-test truncation.** Each test
gets a connection wrapped in an outer transaction plus a nested
SAVEPOINT-backed session; `session.commit()` calls inside application code
(there are many — every service in this codebase commits directly) end and
restart the SAVEPOINT via the standard SQLAlchemy
`after_transaction_end`-listener recipe, never the outer transaction. The
outer transaction rolls back at the end of every test regardless of how
many internal commits happened, so tests never leak data into each other —
confirmed by running the suite twice in a row against a fixed email address
and confirming zero rows persist in `trinetra_test_db` afterward.

**Reference data (roles/permissions, the NEET curriculum) is seeded once
per test *session*, for real** — via the existing `seed_identity` /
`seed_academic` functions, committed for real (not rolled back) since it's
shared baseline data every test can assume exists, exactly like the dev
database. Both are already idempotent, so re-running the suite doesn't
duplicate rows.

**httpx `AsyncClient` + `ASGITransport`, no real server process.** Tests
call the FastAPI app in-process — no port, no `uvicorn` subprocess. This
was also a deliberate escape from the repeated "phantom listener on a
port that Windows tools can't see or kill" problem hit constantly across
Sprints 7–9 during manual curl verification; in-process testing has no
port at all.

**Two bugs in this codebase surfaced *while building the test
infrastructure itself*, before a single real test assertion was written:**

1. **`RequestContextMiddleware` / `SecurityHeadersMiddleware` were
   `starlette.middleware.base.BaseHTTPMiddleware` subclasses.** That base
   class runs the downstream app in a separate anyio task per request,
   which trips asyncpg's per-connection event-loop-affinity check the
   moment a test exercises a database-touching endpoint through
   `ASGITransport` — `RuntimeError: ... attached to a different loop`.
   Rewritten as plain ASGI middleware (`__call__(self, scope, receive,
   send)`, wrapping `send` to inject headers) — no task-group indirection,
   and arguably the more correct pattern for Starlette middleware
   regardless of testing.
2. **`asyncio_default_fixture_loop_scope` in `pytest.ini` only governs
   fixture loop scope, not test-function loop scope**, despite the
   similar-sounding name — confirmed by reading `pytest_asyncio`'s own
   source (`_preprocess_async_fixtures` only iterates fixture defs). A
   session-scoped fixture and a function-scoped test loop then fight over
   the same asyncpg connection and produce the exact same "different
   loop" error from a different angle. Every test module needs its own
   `pytestmark = pytest.mark.asyncio(loop_scope="session")` — a
   `pytest_generate_tests`-time marker that a `conftest.py` hook can't
   inject after the fact, since collection-time marker resolution happens
   before `pytest_collection_modifyitems` runs.

Neither of these would have been found without actually trying to get a
real request through the real middleware stack against a real database —
exactly the gap pure-function tests can't close.

## What's covered, what isn't
This ADR is infrastructure. Coverage itself is built out across the next
few sprints of test-writing (auth/permission boundaries, ECAEP workflow
transitions, assessment scoring, mastery recompute, the commerce guard
rail) — not exhaustive endpoint-by-endpoint coverage, prioritized at the
flows this session found real bugs in or that are cheapest to regress
silently.

## Consequences
Running the suite requires `trinetra_test_db` to exist and be migrated —
documented in `database/setup.md` alongside the existing dev-database
bootstrap steps. CI (whenever it exists) needs the same one-time setup.
The fixed per-test overhead (opening a connection, two nested
transactions) is small relative to what it replaces: manual curl/browser
verification repeated by hand every sprint, which this doesn't eliminate
for UI-facing changes but does for backend regressions.
