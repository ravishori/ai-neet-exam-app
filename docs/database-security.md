# Database security — TALOS

**Status:** Operator guidance. Role cutover is **REQUIRES INFRASTRUCTURE** — do not apply casually to a live owning `trinetra_app` role without a staged cutover plan.

## Current model

- Schemas: `identity`, `academic`, `cms`, `assessment`, `ai`, `analytics`, `commerce`, `system`.
- Bootstrap roles in `database/init.sql`: `trinetra_app` (app), `trinetra_migration` (DDL), `trinetra_readonly` (SELECT).
- Runtime app connection today typically uses `trinetra_app`, which also **owns** schemas — so PostgreSQL RLS would not constrain the table owner unless `FORCE ROW LEVEL SECURITY` is used.

## Least-privilege target (production)

1. Keep ownership on `trinetra_migration` (or a dedicated owner role that is not used by the API).
2. Grant `trinetra_app` only `USAGE` + DML on application schemas; no `CREATE`/`DROP`.
3. Run Alembic as `trinetra_migration` only.
4. Use `trinetra_readonly` for analytics/BI.

See optional operator script: `database/rls_least_privilege.sql` (not applied by app startup).

## Row Level Security (future)

RLS is useful when the DB role is shared and policies must enforce `user_id` boundaries. TALOS MVP enforces tenancy/ownership in the application layer (`get_current_user` + repository filters). Enabling RLS without rewriting session `SET` of `app.user_id` will not help and can break migrations.

Recommended sequence (later sprint):

1. Non-owner runtime role.
2. Policies on student-owned tables (`assessment.*` attempts, etc.).
3. `SET LOCAL app.current_user_id` in a request dependency.
4. Integration tests that assert denied cross-user SELECT.

## Soft delete

Business tables use `deleted_at`. Prefer repository filters that exclude soft-deleted rows; do not rely on RLS alone for soft-delete semantics.
