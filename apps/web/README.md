# Trinetra web

Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui + NEET AI
Design System primitives. Single app, route-grouped — see ADR-0008 (no
separate admin frontend).

**Status:** Student and admin learning surfaces are substantially wired to
the FastAPI backend. The public landing page copy is **stale** relative to
SP0–SP9 (tracked in `docs/product/MARKETING_TRUTHFULNESS.md`). The product
is under active development — not a finished content-complete NEET platform.

## Primary routes (implemented)

### Public / auth
- `/` — landing (copy outdated; see marketing truthfulness doc)
- `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`

### Student
- `/student/dashboard`, `/student/subjects` … concept tree
- `/student/questions`, `/student/flashcards`
- `/student/practice`, `/student/mock-tests`, `/student/attempts`
- `/student/analytics`, `/student/study-plan`, `/student/profile`, `/student/settings`

### Admin (role-gated in layout; API enforces permissions)
- `/admin` dashboard, `/admin/content`, `/admin/ingestion`, `/admin/knowledge-units`
- `/admin/visual-assets`, `/admin/ai-review`, `/admin/search`, `/admin/users`
- `/admin/coverage`, `/admin/analytics`, `/admin/audit-logs`

Authoritative capability status: `docs/product/MASTER_FEATURE_AUDIT.md`.

## Local setup

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. Backend should be on `NEXT_PUBLIC_API_URL`
(default `http://localhost:8000`).

## Tests

```bash
npm test
```

Vitest covers a small set of components/helpers. **No Playwright E2E suite**
yet (product gap G-024).

## Adding shadcn/ui components

```bash
npx shadcn@latest add <component>
```
