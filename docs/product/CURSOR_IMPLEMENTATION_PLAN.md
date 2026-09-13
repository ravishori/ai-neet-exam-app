# CURSOR IMPLEMENTATION PLAN — TALOS

**Purpose:** Dependency-aware waves for future Cursor prompts.  
**Rule:** Do **not** implement these waves in the audit session. Execute **one wave per dedicated prompt**.  
**Preserve:** API contracts (unless wave explicitly approves change), DB architecture, auth/security model, NEET question data, AI Gateway shape, Design System, working flows.

---

## Global Definition of Done (every wave)

| Gate | Requirement |
|------|-------------|
| Functional | User journey works end-to-end on staging or local with real DB |
| Backend | Business logic complete for wave scope |
| Database | Migrations only via Alembic; no hand-edit prod |
| API | Envelope contract preserved; OpenAPI/manual check |
| Frontend | Loading / empty / error states; Design System consistency |
| Security | No secrets in logs; CSRF on mutations; permission checks |
| Testing | Automated tests for new paths; regression suite subset green |
| Observability | Errors carry `traceId` / `errorId` |
| Documentation | Update gap register status + relevant docs |
| Production | Mark PRODUCTION READY only after deploy verification |

---

## WAVE-P0-1 — Doc & marketing truthfulness

| Field | Content |
|-------|---------|
| **Status** | **DONE (docs)** — 2026-08-31. Landing `page.tsx` **not** edited (WAVE prompt forbade frontend application code). |
| **Objective** | Align README + roadmap + product docs with SP0–SP9 reality |
| **Features** | README rewrite; CLAUDE.md; architecture roadmap; web README; MARKETING_TRUTHFULNESS |
| **Dependencies** | None |
| **Files changed** | `README.md`, `CLAUDE.md`, `docs/architecture/roadmap.md`, `apps/web/README.md`, `docs/product/*` |
| **Deferred** | `apps/web/src/app/(public)/page.tsx` — see `MARKETING_TRUTHFULNESS.md` |
| **DB / API** | None |
| **UI** | Docs only this wave |
| **Security** | None |
| **Acceptance** | Root README no longer claims “SP0 in progress”; product posture honest |
| **DoD** | Docs match product audit; FE landing still inconsistent until follow-up |
| **Regression** | None (docs only) |

---

## WAVE-P0-2 — SMTP + auth email verification (staging)

| Field | Content |
|-------|---------|
| **Objective** | Make forgot/reset/verify/OTP emails deliver in staging |
| **Features** | Configure SMTP_*; verify Mailpit→real SMTP path; ops checklist |
| **Dependencies** | Infra secrets |
| **Files** | `.env.example` notes, `docs/deploy/*`, email_service (config only unless bugs) |
| **DB** | None |
| **API** | Existing auth email endpoints |
| **UI** | Existing auth pages |
| **Security** | Tokens never in prod logs |
| **Tests** | Existing auth + security tests |
| **Acceptance** | Reset email received; link works; prod log redaction verified |
| **Regression** | Auth flows |

---

## WAVE-P0-3 — Critical path E2E smoke

| Field | Content |
|-------|---------|
| **Objective** | Playwright (or agreed E2E) for login → practice → submit; admin publish smoke |
| **Features** | Minimal E2E suite in CI |
| **Dependencies** | Test DB + seeded published questions |
| **Files** | `apps/web` e2e config; CI workflow |
| **DB** | Seed fixtures |
| **API** | None new |
| **UI** | Exercises existing |
| **Security** | Test secrets isolated |
| **Tests** | New E2E |
| **Acceptance** | CI job green on main |
| **Regression** | CI time |

---

## WAVE-P0-4 — Content publish campaign (process + tooling)

| Field | Content |
|-------|---------|
| **Objective** | Move Phase D drafts + backlog through ECAEP to PUBLISHED with quality bar |
| **Features** | Reviewer checklist; bulk review UX polish if needed; coverage dashboard use |
| **Dependencies** | Human SMEs; **no auto-publish** |
| **Files** | Possibly admin content UX; `docs/architecture/ecaep.md` checklist |
| **DB** | Status transitions only |
| **API** | Existing CMS |
| **UI** | Admin content |
| **Security** | Permission-gated publish |
| **Tests** | CMS workflow tests |
| **Acceptance** | Product-agreed published counts per subject; explanations present |
| **Regression** | Do not publish low-quality AI drafts blindly |
| **Note** | Primarily editorial; Cursor assists tooling only |
| **Phase 3.2 (2026-09-13)** | Inventory truth + ECAEP queue APIs + readiness reporting restored/hardened. **No mass-publish.** Revalidate via `scripts/content_readiness_inventory.py`. Full 180 mock still blocked on subject allocation. |

---

## WAVE-P0-5 — Practice/recs published-availability

| Field | Content |
|-------|---------|
| **Objective** | Recommendations and Practice Now never target zero-published concepts |
| **Features** | Filter recs; clear FE errors (partially done); dashboard copy |
| **Dependencies** | G-001 helps but filter required regardless |
| **Files** | `learning/services/recommendation_service.py`, dashboard, practice |
| **DB** | Query filters |
| **API** | Possibly meta `availableQuestionCount` |
| **UI** | Disable/CTA when unavailable |
| **Security** | None special |
| **Tests** | Learning + assessment tests |
| **Acceptance** | No 422 surprise without UI explanation |
| **Regression** | Dashboard widgets |

---

## WAVE-P1-1 — MFA / TOTP student UI

| Field | Content |
|-------|---------|
| **Objective** | Productize Wave C APIs |
| **Features** | Settings enroll/confirm/disable; login MFA step-up; recovery codes display once |
| **Dependencies** | ENCRYPTION_KEY; WAVE-P0-2 optional |
| **Files** | `(auth)/login`, `student/settings`, `features/auth/api.ts` |
| **DB** | Existing Wave C tables |
| **API** | Existing `/totp/*`, `/mfa/verify` |
| **UI** | New flows; DS-aligned |
| **Security** | CSRF; never log secrets |
| **Tests** | Vitest + API tests already; add FE tests |
| **Acceptance** | User with TOTP cannot get session cookies without MFA |
| **Regression** | Login for non-MFA users unchanged |

---

## WAVE-P1-2 — Bookmark library

| Field | Content |
|-------|---------|
| **Objective** | List and open bookmarked questions |
| **Features** | `GET` bookmarks API; `/student/bookmarks` page; nav link |
| **Dependencies** | Existing toggle |
| **Files** | `learning` API/repo; web student route |
| **DB** | Read `question_bookmarks` |
| **API** | New list endpoint (additive) |
| **UI** | New page |
| **Security** | user-scoped only |
| **Tests** | API + FE |
| **Acceptance** | Toggle → appears in list → question detail |
| **Regression** | Attempt bookmark badges |

---

## WAVE-P1-3 — AI degraded-mode + cost guardrails

| Field | Content |
|-------|---------|
| **Objective** | Honest AI UX; prevent runaway cost |
| **Features** | FE banner when FallbackProvider; per-user daily call caps; admin visibility |
| **Dependencies** | Gateway logging |
| **Files** | `ai/gateway`, tutor UI, coach shell, analytics |
| **DB** | Possibly usage counters in Redis |
| **API** | Meta flags |
| **UI** | Degraded notices |
| **Security** | No key leakage |
| **Tests** | AI module tests |
| **Acceptance** | Without API key, UI shows degraded; with key, caps enforced |
| **Regression** | Tutor happy path |

---

## WAVE-P1-4 — AI evaluation harness (minimal)

| Field | Content |
|-------|---------|
| **Objective** | Golden-question set for tutor groundedness / format |
| **Features** | Offline eval script or pytest markers; CI optional job |
| **Dependencies** | Sample KUs + published questions |
| **Files** | `apps/backend` tests/evals |
| **DB** | Fixtures |
| **API** | None |
| **UI** | None |
| **Security** | No prod keys in CI if possible |
| **Tests** | New eval suite |
| **Acceptance** | Documented score thresholds; failures visible |
| **Regression** | CI flakiness — start non-blocking |

---

## WAVE-P1-5 — Premium entitlement policy

| Field | Content |
|-------|---------|
| **Objective** | Define and enforce what `is_premium` unlocks |
| **Features** | Gate selected AI or mock volume; clear upsell |
| **Dependencies** | Product decision |
| **Files** | commerce deps, AI/assessment routers, profile UI |
| **DB** | Existing orders |
| **API** | Permission checks |
| **UI** | Locked states |
| **Security** | Server-side enforce only |
| **Tests** | Commerce + gated routes |
| **Acceptance** | Non-premium cannot call gated APIs |
| **Regression** | Free practice remains usable |

---

## WAVE-P2-1 — Student analytics depth

| Field | Content |
|-------|---------|
| **Objective** | Chapter/topic breakdown, time metrics if instrumented |
| **Features** | Server aggregates; DS charts |
| **Dependencies** | Enough attempts (content) |
| **Files** | analytics or learning APIs; student analytics page |
| **DB** | Queries on attempts/answers |
| **API** | Additive student analytics endpoints |
| **UI** | Extend scorecard |
| **Tests** | Analytics tests |
| **Acceptance** | Matches attempt truth |
| **Regression** | Admin analytics unchanged |

---

## WAVE-P2-2 — Ingestion Phase A/B DoD closeout

| Field | Content |
|-------|---------|
| **Objective** | Meet ADR-0030/31 DoD; monitoring |
| **Features** | Validation reports; failure alerts |
| **Dependencies** | StudyMaterial corpus access |
| **Files** | ingestion services, admin UI, runbook |
| **DB** | source documents/jobs |
| **Tests** | ingestion suite |
| **Acceptance** | Roadmap flags flip to DoD complete with evidence |
| **Regression** | Pilot data integrity |

---

## WAVE-P2-3 — Notifications MVP (email-first)

| Field | Content |
|-------|---------|
| **Objective** | Revision-due and study-plan reminder emails |
| **Features** | Scheduler or cron job; templates; prefs |
| **Dependencies** | SMTP; mastery revision; user prefs |
| **Files** | new `notifications` module (or system jobs) |
| **DB** | prefs + outbox optional |
| **API** | prefs endpoints |
| **UI** | settings toggles |
| **Security** | no PII in logs |
| **Tests** | template + scheduler unit |
| **Acceptance** | Opt-in user receives reminder |
| **Regression** | Email volume / spam |

---

## WAVE-P2-4 — MFA OTP email step-up (optional)

| Field | Content |
|-------|---------|
| **Objective** | Wire OTP purposes into sensitive actions |
| **Dependencies** | WAVE-P0-2, WAVE-P1-1 |
| **Acceptance** | Sensitive action requires verified OTP |

---

## WAVE-P3-1 — Flashcard SRS

| Field | Content |
|-------|---------|
| **Objective** | SM-2 or fixed-interval SRS on published flashcards |
| **Dependencies** | Substantial published flashcard corpus |
| **DB** | New review state tables (Alembic) |
| **Do not start** until content threshold met |

---

## WAVE-P3-2 — Vector RAG (innovation)

| Field | Content |
|-------|---------|
| **Objective** | Embeddings + retrieval for tutor grounding |
| **Dependencies** | KU quality, cost model, ADR amendment |
| **Risk** | High cost + hallucination if weak chunks |
| **Gate** | Explicit product approval |

---

## WAVE-P10 — Security ops cutover

| Field | Content |
|-------|---------|
| **Objective** | ENCRYPTION_KEY, ALERT_EMAIL, HSTS verified; optional RLS staging experiment |
| **Dependencies** | WAVE-P0-2, WAVE-P1-1 |
| **Files** | deploy runbooks, `database/rls_least_privilege.sql` (careful) |
| **Acceptance** | security-audit → evidence-based upgrade; no false GREEN |

---

## WAVE-P12 — Production go-live

| Field | Content |
|-------|---------|
| **Objective** | Coolify deploy + `VERIFICATION_CHECKLIST` signed |
| **Dependencies** | P0 content threshold decision, P0 SMTP, P0 E2E, security YELLOW acceptable with known risks |
| **Acceptance** | Public staging/prod health; backup/rollback drilled |

---

## Suggested next Cursor prompt

**Content Factory FACTORY-P3.1 (multi-provider AI Gateway) is complete** — see `CONTENT_FACTORY_P3_1_MULTI_PROVIDER.md` / `CONTENT_FACTORY_ROADMAP.md`.

Provider infrastructure is ready for controlled evaluation (do not claim a provider is “best” yet).

Recommended next (ops, not a redesign wave):

1. **Controlled ~100-question cross-provider pilot** — configure ONE provider at a time (`FACTORY_PROVIDER_MODE=fixed`) with credentials/budget; run `scripts/run_factory_p3_pilot.py`; then P4 QA + P5 sampling. Prefer OpenAI/Gemini/Mistral/Anthropic A/B on the **same** blueprints.
2. **Human ECAEP** — review/approve/publish PHY-01–10 (`IN_REVIEW`) and remaining Batch A via Editorial Review, or
3. **WAVE-P0-2** — SMTP / ops gates.

Do not auto-publish. Do not scale to 1,000 until P4/P5 pilot evidence is reviewed. Quality × coverage × traceability > raw count.
