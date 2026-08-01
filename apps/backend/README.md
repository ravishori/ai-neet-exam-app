# Trinetra backend

FastAPI, modular monolith. See root `CLAUDE.md` and `docs/decisions/` before
adding a module.

## Local setup (native — no Docker required)

> Use **Python 3.11**, not whatever 3.14 the system default might be —
> `asyncpg`/`pydantic-core`/`argon2-cffi` don't reliably have prebuilt
> Windows wheels for 3.14 yet.

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then follow `database/setup.md` (roles/db, then `alembic upgrade head`).

```bash
py -3.11 -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/health, http://localhost:8000/ready, and
http://localhost:8000/docs.

## Adding a module

Copy the shape every module in this backend follows:

```
app/modules/<name>/
  api/            FastAPI routers — thin, no business logic
  services/       business rules, called by api/
  repositories/   the only layer that talks to SQLAlchemy
  models/         SQLAlchemy models (schema-qualified, e.g. identity.users)
  schemas/        Pydantic request/response models
  tests/
```

Register the module's models in `alembic/env.py` (import so they attach to
`Base.metadata`) and its router in `app/main.py`.
