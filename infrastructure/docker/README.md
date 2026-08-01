# Docker Compose — prod-parity local dev

Not required if you already have Postgres 17+/Redis natively (see
`database/setup.md` and each app's own README) — this exists for anyone
who doesn't, and to keep a production-shaped stack around for reference.

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

Then:
1. `docker compose exec backend alembic upgrade head` (first run only)
2. Backend: http://localhost:8000/docs — Web: http://localhost:3000
3. Mailpit UI (dev email testing): http://localhost:8025

Not included in v1: Nginx and MinIO. Neither is needed yet — content is
external URLs/references in v1 (ECAEP, ADR-0009), and there's no
reverse-proxy requirement until production deploy (Coolify handles that
directly — ADR-0006).
