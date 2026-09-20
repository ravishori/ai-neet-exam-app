# BACKEND-RUNTIME-001 — Backend :8000 availability

**Verdict: GREEN** (2026-09-14)

## Diagnosis

| Hypothesis | Result |
|---|---|
| A. Not started | **YES** — no listener / no uvicorn before this task |
| B. Crashing on startup | No — clean start |
| C. Wrong port | No — documented `:8000` |
| D. Env blocked | No — existing `.env` sufficient |
| E. DB blocked | No — Postgres `:5432` already up |
| F. Import/runtime error | No |
| G. Port occupied | No — port was free |

Root cause: **backend process was simply not running.** Dependencies (Postgres, Redis, `.venv`, `.env`) were already available.

## Startup command (documented)

```text
cd apps/backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

(README equivalent: `py -3.11 -m uvicorn app.main:app --reload --port 8000`)

## Process / port

- Uvicorn PID: **15840** (shell PID 19968)
- Listening: **127.0.0.1:8000**

## Health

- `GET /health` → `{"status":"ok"}` success
- `GET /ready` → `database: true`, `redis: true`

## Database / Redis

- Postgres `:5432` listening (pre-existing)
- Redis `:6379` listening (pre-existing)
- Ready probe confirms both

## API smoke

| Endpoint | Result |
|---|---|
| `POST /api/v1/auth/register` | 201 |
| `POST /api/v1/auth/login` | 200 |
| `GET /api/v1/auth/me` | 200 |
| `GET /api/v1/learning/mastery/overview` | 200 |
| `GET /api/v1/learning/revision/due` | 200 |
| `POST /api/v1/assessments/practice` | 201 (5 questions delivered) |
| `GET /api/v1/attempts` | 200 |
| `GET /api/v1/subjects` | 200 (Physics/Chemistry/Botany/Zoology) |
| OpenAPI path count | 148 |

## Files changed

None (ops start only). Audit artifact: this file + JSON companion.

## Frontend

`:3001` untouched and still HTTP 200. No `next dev`. No A6–A12 / BUILD changes. No ECAEP/Practice/Mock/AuthZ/DB schema/data mutations beyond normal register creating one new student user for smoke (`backend-runtime-001@example.com`).

## Note

Register smoke created a normal identity user via the public API (not a schema/data remediation). No content/question mutation.
