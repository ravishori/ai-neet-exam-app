# Deploy runbook — Coolify on Hetzner

Per ADR-0006. This is the artifact side of "deploy" — no live server was
reachable from the environment this was built in, so nothing here has
actually been run against a real Hetzner VPS yet. Treat first use as a
dry run: watch each step's output before trusting it.

## Prerequisites
- A Hetzner VPS (or any Docker host) with Coolify installed.
- This repo pushed somewhere Coolify can pull from (a Git remote).
- Real values for every secret in the table below — none of the dev
  defaults in `apps/backend/.env.example` are valid here.

## 1. Point Coolify at the compose file
Coolify project → new resource → "Docker Compose" → repo URL, and set
the compose file path to `infrastructure/docker/docker-compose.prod.yml`.
Coolify handles the reverse proxy / TLS termination itself (ADR-0006) —
no Nginx/Traefik config needed in this repo.

## 2. Environment variables
Set these in Coolify's environment panel for the resource (not committed
anywhere — `docker-compose.prod.yml` only references `${VAR}` names):

| Variable | Required | Notes |
|---|---|---|
| `POSTGRES_USER` | yes | new value, not `trinetra_app` (that's the dev default) |
| `POSTGRES_PASSWORD` | yes | real secret, generate fresh |
| `POSTGRES_DB` | yes | e.g. `trinetra_db` |
| `JWT_SECRET` | yes | ≥32 random chars — `app/core/config.py` refuses to start in `production` without one (rejects known dev placeholders too) |
| `CORS_ORIGINS` | yes | the real frontend origin(s), comma-separated |
| `NEXT_PUBLIC_API_URL` | yes | the public backend URL — baked into the frontend at **build** time, not runtime (Next.js inlines `NEXT_PUBLIC_*`), so this must be set before the `web` image is built |
| `ANTHROPIC_API_KEY` | no | omit and the AI Gateway runs in fallback mode (ADR-0014) — a real deploy without this serves fake AI answers, which is a product decision, not a crash |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | no | omit and commerce order-creation returns `PAYMENT_GATEWAY_NOT_CONFIGURED` (ADR-0018) — no fake payments, ever |

Not wired up yet, independent of this deploy: outbound email (SMTP).
Password-reset and verification emails currently only work against the
dev-only Mailpit container in `docker-compose.yml` — in this prod
compose they silently go nowhere. That's a pre-existing gap (`email_service.py`
has no SMTP backend), not something introduced by this sprint.

## 3. First deploy
1. Coolify builds and starts `postgres`, `redis`, `backend`, `web`.
2. Run the migration once the `backend` container is healthy:
   ```bash
   docker compose -f infrastructure/docker/docker-compose.prod.yml exec backend alembic upgrade head
   ```
3. Confirm:
   - `https://<your-domain>/health` → `{"success": true, "data": {"status": "ok"}}`
   - `https://<your-domain>/ready` → `database: true, redis: true`
   - The frontend loads and a fresh registration + login round-trips.

## 4. Redeploys
Coolify rebuilds the changed image(s) and restarts with `restart:
unless-stopped` already in place. Run `alembic upgrade head` again after
any deploy that includes a new migration — it's not automatic.

## 5. Rollback
Coolify keeps previous image builds; redeploying a prior commit rebuilds
from that commit. There is no automated DB migration rollback — `alembic
downgrade` is available per-migration if a schema change needs reverting,
but treat it as a manual, deliberate step, not part of a routine rollback.
