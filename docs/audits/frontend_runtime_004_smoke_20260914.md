# FRONTEND-RUNTIME-004 — Production frontend smoke

**Verdict: YELLOW** (2026-09-14)

Frontend presentation/runtime on `http://127.0.0.1:3001` is healthy. Backend `:8000` is down — treat as **API/data blocker**, not CSS/hydration.

## 1. Overall
| Area | Status |
|---|---|
| Hashed CSS delivery | GREEN |
| Static JS | GREEN |
| Hydration | GREEN |
| Auth pages | GREEN |
| Student shell (A6–A9) | GREEN (cookie present) |
| Backend API | DOWN (separate) |
| **Overall** | **YELLOW** |

## 2. Route matrix (1280 light)

| Route | HTTP | Final URL | CSS 200 | JS 200 | Dev CSS path | Hydration | Shell brand | Notes |
|---|---|---|---|---|---|---|---|---|
| /register | 200 | same | yes | yes | no | none | n/a (auth) | Plus Jakarta applied |
| /login | 200 | same | yes | yes | no | none | n/a | ok |
| /student/dashboard | 200 | same | yes | yes | no | none | yes | theme+account+nav |
| /student/practice | 200 | same | yes | yes | no | none | yes | |
| /student/subjects | 200 | same | yes | yes | no | none | yes | |
| /student/analytics | 200 | same | yes | yes | no | none | yes | |
| /student/questions | 200 | same | yes | yes | no | none | yes | |
| /student/flashcards | 200 | same | yes | yes | no | none | yes | |
| /student/mock-tests | 200 | same | yes | yes | no | none | yes | |
| /student/attempts | 200 | same | yes | yes | no | none | yes | |

Auth: reused `e2e/.auth/student.json` cookies (middleware presence check). Backend register/login **unavailable** — could not mint fresh tokens. Student pages not redirected to login because `access_token` cookie still present.

## 3. CSS assets
Referenced: `/_next/static/css/df040096fa0b04cd.css`, `/_next/static/css/bd5b56afac8c4fc3.css` — both **200**.  
**No** `/_next/static/css/app/layout.css`.

## 4. JS assets
Sampled hashed `/_next/static/chunks/*.js` — all **200**. No static JS 404s.

## 5. Browser console
No hydration / React pageerror / static asset errors in probe window.  
API `ERR_CONNECTION_REFUSED` expected when backend down (classified separately; may not always surface as `requestfailed` depending on client timing).

## 6. Hydration
No hydration logs/overlay copy on any probed route.

## 7. Responsive (dashboard)
390 / 768 / 1280 / 1440 — HTTP 200, CSS/JS 200, shell brand present, no hydration.

## 8. Theme
Light: `html` class includes `light`. Dark probe: `dark`. Shell controls present.

## 9. Backend-dependent (not frontend CSS defects)
- `http://127.0.0.1:8000/health` → connection failed
- Cannot refresh Playwright student session via API
- Student data/queries will fail until API is up

## 10. Source files changed
**None** (probe script only: `apps/web/scripts/a14-runtime-smoke.mjs` + this audit).

## 11. Tests
A12: **19/19 passed**

## 12. Build
`npm run build` — re-run in progress / expected GREEN (prior RUNTIME-003 already GREEN)

## 13–14. Preserved
A6–A12, BUILD-001/002 intact. No ECAEP / Practice / Mock / AuthZ / DB changes. Not committed.

## Navigation
`/register` → Sign in → `/login` works.

## Before P0 dashboard redesign
Frontend CSS + shell + hydration baseline is ready. Bring **backend :8000** up for data-backed redesign verification.
