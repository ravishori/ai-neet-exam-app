# Deploy runbook — Hetzner + Coolify

Per ADR-0006. **Nothing in this document has been executed against a real
server.** No Hetzner VPS, domain, or Coolify instance is reachable from
the environment this was written in — there is no SSH access, no API
token, no DNS control here. Every command below is correct and ready to
run, but treat the first real attempt as a dry run: watch each step's
output before trusting it, exactly as this runbook has always said.

## Prerequisites
- A Hetzner Cloud account (or any provider that gives you a plain Ubuntu
  24.04 VPS with root/sudo access).
- A domain you control, able to add a DNS A record.
- This repo pushed to a Git remote Coolify can pull from (none is
  configured yet — see `docs/deploy/CI_CD.md`).
- Real values for every variable in
  `infrastructure/docker/.env.production.example` — none of the dev
  defaults in `apps/backend/.env.example` are valid here.

---

## 1. Provision the VPS

Create a Hetzner Cloud server: **Ubuntu 24.04**, at minimum a CX22 (2
vCPU / 4GB RAM) — this stack runs Postgres, Redis, and two app
containers on one box. Note the server's public IPv4 address; the rest
of this guide calls it `<VPS_IP>`.

```bash
ssh root@<VPS_IP>
apt update && apt upgrade -y
```

**Basic server prep** (firewall only — this app's own hardening is
covered elsewhere: ADR-0006 rate limiting, security headers):
```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

## 2. Install Docker + Docker Compose

```bash
curl -fsSL https://get.docker.com | sh
docker compose version   # confirms the Compose v2 plugin is present
```

## 3. Install Coolify

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

This installs Coolify itself in Docker on the same VPS. Once it
finishes, Coolify prints a URL — open `http://<VPS_IP>:8000` in a
browser and complete the first-run setup (create the admin account).
Coolify manages its own reverse proxy (Traefik) for every project it
runs, including the eventual HTTPS termination for this app — no
Nginx/Traefik config is needed in this repo (ADR-0006).

## 4. Domain + DNS

In your DNS provider, add an **A record** pointing your domain (e.g.
`neet.example.com`) at `<VPS_IP>`. Wait for it to propagate
(`dig neet.example.com` should return `<VPS_IP>`) before continuing —
Let's Encrypt's HTTP-01 challenge in step 7 needs the domain to already
resolve to this server.

## 5. Point Coolify at this repo

Coolify dashboard → **New Resource** → **Docker Compose** → paste the
Git remote URL → set the compose file path to
`infrastructure/docker/docker-compose.prod.yml`.

## 6. Environment variables

Copy every variable from `infrastructure/docker/.env.production.example`
into Coolify's environment panel for this resource, filled in with real
values (not committed anywhere — the compose file only references
`${VAR}` names):

| Variable | Required | Notes |
|---|---|---|
| `POSTGRES_USER` | yes | not `trinetra_app` — that's the dev default |
| `POSTGRES_PASSWORD` | yes | generate fresh, e.g. `openssl rand -base64 32` |
| `POSTGRES_DB` | yes | e.g. `trinetra_db` |
| `JWT_SECRET` | yes | ≥32 random chars — `app/core/config.py` refuses to start in `production` without one, and rejects known dev placeholders |
| `CORS_ORIGINS` | yes | the real frontend origin(s), comma-separated |
| `NEXT_PUBLIC_API_URL` | yes | the public backend URL — baked into the `web` image at **build** time, so must be set before Coolify builds it |
| `ANTHROPIC_API_KEY` | no | omit and the AI Gateway runs in fallback mode (ADR-0014) |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | no | omit and commerce order-creation returns `PAYMENT_GATEWAY_NOT_CONFIGURED` (ADR-0018) |

`STUDY_MATERIAL_DIR` and `VISUAL_ASSETS_DIR` are **not** set here — the
compose file hardcodes them to the container paths its own volumes
mount at (`/data/studymaterial`, `/data/visualassets`); see section 8.

Not wired up: outbound email (SMTP). Password-reset/verification emails
only work against the dev-only Mailpit container in `docker-compose.yml`
— in this prod compose they silently go nowhere. Pre-existing gap
(`email_service.py` has no SMTP backend), not introduced by this deploy.

## 7. HTTPS / SSL

In the Coolify resource, assign your domain to the `web` service (the
one Coolify should route public traffic to) and enable **"Force HTTPS"**.
Coolify provisions a Let's Encrypt certificate automatically via its
Traefik proxy — no certbot, no manual cert handling, nothing to
configure in this repo. Certificate renewal is automatic (Traefik
re-issues before expiry).

If you need the backend directly reachable too (e.g. for a mobile
client hitting the API on a separate subdomain), assign a second domain
to the `backend` service the same way — otherwise route `/api/*` through
the frontend's own proxying, whichever this app's `NEXT_PUBLIC_API_URL`
convention expects.

## 8. Persistent storage

Four named volumes, declared in `docker-compose.prod.yml`, survive
container recreation/redeploys:

| Volume | Mounted at | What it holds |
|---|---|---|
| `postgres_data` | `/var/lib/postgresql/data` | the database |
| `redis_data` | `/data` (redis container) | Redis's own persistence, if enabled |
| `study_material_data` | `/data/studymaterial` (backend) | uploaded PDFs (ADR-0022) |
| `visual_assets_data` | `/data/visualassets` (backend) | detected/cropped visual assets (ADR-0026) |

Coolify manages these as regular Docker named volumes on the host —
nothing further to configure. They are **not** touched by a redeploy or
rollback (see `docs/deploy/ROLLBACK.md`); only deleting the resource in
Coolify or `docker volume rm` removes them.

## 9. First deploy

1. Trigger a deploy in Coolify. It builds `postgres`, `redis`, `backend`,
   `web` from `docker-compose.prod.yml`.
2. Run the migration once `backend` is healthy:
   ```bash
   docker compose -f infrastructure/docker/docker-compose.prod.yml exec backend alembic upgrade head
   ```
3. Confirm (see `docs/deploy/VERIFICATION_CHECKLIST.md` for the full list):
   - `https://<your-domain>/health` → `{"success": true, "data": {"status": "ok"}}`
   - `https://<your-domain>/ready` → `database: true, redis: true`
   - The padlock/certificate is valid (Let's Encrypt, not self-signed).
   - The frontend loads and a fresh registration + login round-trips.

## 10. Health checks

`docker-compose.prod.yml` defines a Docker-level healthcheck for every
service (`postgres`: `pg_isready`, `redis`: `redis-cli ping`, `backend`:
hits its own `/health` endpoint, `web`: hits `/`). `backend` and `web`
both `depends_on` their dependencies with `condition: service_healthy`,
so Compose won't start the app before Postgres/Redis are actually ready
— not just "container started," but "accepting connections."

Coolify surfaces these same healthcheck statuses in its dashboard per
service; a service stuck "unhealthy" is the first thing to check before
digging into logs.

## 11. Redeploys
Coolify rebuilds the changed image(s) and restarts with `restart:
unless-stopped` already in place. Run `alembic upgrade head` again after
any deploy that includes a new migration — it's not automatic.

## 12. Rollback
See `docs/deploy/ROLLBACK.md` for both the Coolify-native and
git-revert-based procedures, plus the explicit note that neither touches
the database or the persistent volumes above.
