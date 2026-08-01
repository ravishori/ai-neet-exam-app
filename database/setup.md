# Database bootstrap

Two steps. Step 1 needs a superuser and runs once per environment; step 2 is
the normal, repeatable path for every schema change after that.

## 1. Roles + database (superuser, one-time)

```bash
psql -U postgres -h localhost -f database/init.sql
psql -U postgres -h localhost -c "CREATE DATABASE trinetra_db OWNER trinetra_app;"
```

Dev passwords are in `init.sql` as placeholders (`trinetra_dev_pw`, etc.) —
fine for local dev, must be replaced before any shared/staging environment.

## 2. Extensions + schemas (repeatable)

```bash
cd apps/backend
alembic upgrade head
```

Migration `0001` creates `uuid-ossp`, `citext`, `pg_trgm`, and the eight
schemas (`identity, academic, cms, assessment, ai, analytics, commerce,
system`). This is the reproducible path — `database/schema_init.sql` is kept
only as a manual reference/fallback.

## Known local gaps (this machine, 2026-08-01)

- `pgcrypto` fails to load (`pgcrypto.dll` procedure not found) on this
  Postgres 18 install. Not blocking — Argon2 hashing happens in application
  code (`argon2-cffi`), not in Postgres.
- `pgvector` isn't installed at all. Not needed until Sprint 5 (AI Gateway /
  embeddings) — install it then via the pgvector Windows build or Docker.
