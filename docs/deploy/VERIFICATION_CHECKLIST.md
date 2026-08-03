# Deployment verification checklist

Run through this after every first deploy, and skim the "Redeploy"
subset after every subsequent one. Pairs with `docs/deploy/RUNBOOK.md`
(the how) and `docs/deploy/ROLLBACK.md` (what to do if any item fails
and can't be fixed forward quickly).

## Infrastructure
- [ ] `ssh root@<VPS_IP>` succeeds; `ufw status` shows only 22/80/443 open.
- [ ] `docker compose version` and `docker --version` both run on the VPS.
- [ ] Coolify's own dashboard (`http://<VPS_IP>:8000` or its configured
      domain) is reachable and you're logged in as the admin account you
      created, not a default/shared login.

## Domain + DNS
- [ ] `dig <your-domain>` (or `nslookup`) resolves to `<VPS_IP>`.
- [ ] The domain is assigned to the `web` service inside the Coolify
      resource (Coolify dashboard → resource → domains).

## HTTPS / SSL
- [ ] `https://<your-domain>/` loads without a browser certificate
      warning.
- [ ] The certificate issuer is Let's Encrypt, not self-signed — check
      via the browser's padlock → certificate details, or:
      `curl -vI https://<your-domain>/ 2>&1 | grep -i "issuer"`
- [ ] `http://<your-domain>/` redirects to `https://` (Coolify's "Force
      HTTPS" is enabled).

## Environment variables
- [ ] Every variable in `infrastructure/docker/.env.production.example`
      is set in Coolify's environment panel with a **real** value, not a
      placeholder — spot-check `JWT_SECRET` is not one of the two known
      dev placeholders `app/core/config.py` explicitly rejects.
- [ ] `NEXT_PUBLIC_API_URL` was set correctly **before** the `web` image
      was built (it's baked in at build time — changing it later requires
      a rebuild, not just a restart).

## PostgreSQL
- [ ] `docker compose -f infrastructure/docker/docker-compose.prod.yml ps postgres`
      shows the container `healthy`, not just `running`.
- [ ] `alembic upgrade head` (run once per section 9 of `RUNBOOK.md`)
      completed without error.
- [ ] `docker compose ... exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c '\dn'`
      lists all eight expected schemas (`identity, academic, cms,
      assessment, ai, analytics, commerce, system`) plus `knowledge` and
      `ingestion` from later ADRs.

## Persistent storage
- [ ] `docker volume ls` shows all four: `postgres_data`, `redis_data`,
      `study_material_data`, `visual_assets_data`.
- [ ] Upload a real PDF through the ingestion admin UI, then
      `docker compose ... exec backend ls /data/studymaterial/Uploads`
      shows the file landed there (not silently failed on a permissions
      error — confirms the Dockerfile's pre-created, `app`-owned mount
      points actually took effect).
- [ ] **The real test:** redeploy (or `docker compose restart backend`)
      and confirm the same file is still listed afterward — proves it's
      on the named volume, not the container's ephemeral layer.

## Health checks
- [ ] `docker compose ... ps` shows `postgres`, `redis`, `backend`, `web`
      all `healthy` (not `starting` stuck, not `unhealthy`).
- [ ] `curl https://<your-domain>/health` →
      `{"success": true, "data": {"status": "ok"}}`
- [ ] `curl https://<your-domain>/ready` → `database: true, redis: true`

## Application smoke test
- [ ] The frontend home page loads over HTTPS.
- [ ] Register a new test account, log in, log out — full auth
      round-trip.
- [ ] Browse to a subject/chapter/concept page and confirm content
      renders.
- [ ] As an admin user, open `/admin` and confirm the dashboard loads
      (RBAC guard is active, not bypassed).

## CI/CD (once the repo has a Git remote — see `docs/deploy/CI_CD.md`)
- [ ] A push to `main` triggers `ci.yml` and it goes green.
- [ ] `deploy.yml` runs after CI succeeds and the Coolify webhook fires
      (check Coolify's deployment log for a new deploy triggered at the
      right time, not just triggered by the earlier manual step).

## Redeploy-only subset (after the first deploy, run just these)
- [ ] `docker compose ... ps` — all four services `healthy` again post-redeploy.
- [ ] `/health` and `/ready` both still green.
- [ ] Any new migration has been applied (`alembic upgrade head`).
- [ ] Persistent-storage spot check above still passes (file from before
      the redeploy is still there).
