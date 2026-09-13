# MASTER FEATURE AUDIT — TALOS (AI NEET Exam Preparation)

**Audit date:** 2026-08-31  
**Mode:** READ-ONLY (no application code, schema, or infra changes)  
**Repo:** `D:\ravishori\AI Neet Exam App`  
**Evidence sources:** code (`apps/backend`, `apps/web`), Alembic (26 migrations, head `d4e5f6a7b8c9`), live local DB `trinetra_db` inventory query, tests, ADRs, `docs/architecture/roadmap.md`, security docs Waves A–C.

**Conflict order (canonical):** Working code → ADRs → deploy docs → blueprint → BRD.docx (vision only).

---

## Executive completion scores (evidence-based)

| Metric | Score | Methodology |
|--------|------:|-------------|
| Overall feature completion | **52%** | ~100 inventoried capabilities; COMPLETE=1.0, PARTIAL=0.55, BASIC=0.35, STUB/NOT=0; weighted average across domains A–S |
| Core MVP completion | **68%** | Frozen SP0–SP9 + CLAUDE.md v1 (identity, academic browse, ECAEP, assessment, 4 AI agents, mastery, recs, admin analytics, commerce, admin). Code largely present; content/SMTP/prod/MFA-UI subtract |
| Advanced capability completion | **12%** | SRS flashcards, vector RAG, notifications, adaptive engine, rank/percentile, Digital Twin, 12-agent OS |
| Security readiness | **62%** | Waves A–C implemented in backend; MFA/OTP **API without UI**; SMTP/ENCRYPTION_KEY/ALERT_EMAIL unverified in deploy; RLS not enforced → YELLOW |
| Production readiness | **30%** | Compose/CI/Coolify docs exist; production deploy **not verified in-repo**; secrets/SMTP/content insufficient |
| QA confidence | **58%** | Strong pytest integration suite; thin Vitest; **no Playwright/E2E**; no load/perf suite |
| Content readiness | **~25%** | Inventory is **DB-derived** (revalidate via `scripts/content_readiness_inventory.py`). Phase 3.1/3.2: ~1.4k+ PUBLISHED questions exist, but Chemistry/Zoology published pools and NCERT verification remain insufficient for claiming full NEET mock readiness. Do **not** cite the historical “11 PUBLISHED / 2 flashcards” snapshot as current. Flashcards published count is also DB-derived (hundreds in recent audits — revalidate). Large **unmapped DRAFT** backlog must not be mass-published. |
| AI maturity | **48%** | Real Claude gateway + 4 agents + fallback; lexical grounding (not vector RAG); no eval harness / hallucination suite |

**Overall product verdict:** Engineering scaffold for a NEET learning OS is **substantially built** (SP0–SP9 code). The product is **not pilot-ready for serious aspirants** primarily due to **published content scarcity**, **unverified production ops**, and **engagement/AI depth gaps**.

---

## Definition of Done (used in this audit)

A capability is **COMPLETE** only if: Functional E2E path exists **and** Backend + DB + API + Frontend (if user-facing) are wired.  
**PRODUCTION READY** additionally requires: security review, tests, observability, staging/prod verification.  
Documentation alone, a table, an API without UI, or a UI without published content → **not COMPLETE**.

---

## A. Identity & Account

| Capability | Status | BE | DB | API | FE | UX | Test | Sec | Obs | Docs | Prod | Evidence |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Registration | 🟢 COMPLETE | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 3 | 4 | 2 | `auth_router` + `(auth)/register` |
| Login / logout / refresh | 🟢 COMPLETE | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 3 | 4 | 2 | cookies + CSRF |
| Password reset / change | 🟡 PARTIAL | 4 | 4 | 4 | 4 | 3 | 3 | 4 | 3 | 4 | 1 | FE present; SMTP delivery REQUIRES INFRA |
| Email verification | 🟡 PARTIAL | 4 | 4 | 4 | 4 | 3 | 2 | 3 | 2 | 4 | 1 | Informational; not login gate |
| Email OTP | 🟠 BASIC | 4 | 4 | 4 | 0 | 0 | 3 | 4 | 3 | 4 | 1 | API Wave C; **no FE** |
| TOTP MFA + recovery | 🟡 PARTIAL | 4 | 4 | 4 | 0 | 0 | 4 | 4 | 3 | 4 | 1 | API Wave C; **login ignores `mfaRequired` in UI** |
| Session management UI | ⚪ NOT | 2 | 3 | 0 | 0 | 0 | 0 | 2 | 1 | 2 | 0 | rotate/revoke server-side only |
| Account lockout | 🟢 COMPLETE | 4 | 4 | 4 | 2 | 2 | 3 | 4 | 3 | 4 | 2 | 5 fails / 15 min |
| Profile | 🟢 COMPLETE | 4 | 4 | 4 | 4 | 3 | 2 | 3 | 2 | 3 | 2 | `/student/profile` |
| Settings | 🟠 BASIC | 3 | 3 | 3 | 3 | 2 | 1 | 2 | 1 | 2 | 1 | language only |
| RBAC roles/permissions | 🟢 COMPLETE | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 2 | 4 | 2 | admin users + seed roles |

**Maturity note:** Backend auth is strong; **MFA/OTP are not productized in the web app**.

---

## B. Academic Structure

| Capability | Status | Evidence |
|---|---|---|
| Exam→Subject→Chapter→Topic→Concept→Micro-competency | 🟢 COMPLETE (seeded read model) | models + `academic_router` GET tree; NEET seed |
| Academic browsing (student) | 🟢 COMPLETE | `/student/subjects` … `/concepts/[id]` |
| Academic administration CRUD | 🟡 PARTIAL | Micro-competency create only; hierarchy not full admin CRUD |
| Content coverage matrix | 🟢 COMPLETE | `/admin/coverage` + CMS coverage API |

Scores (typical): BE 4 · DB 4 · API 3 · FE 4 · UX 3 · Test 3 · Sec 3 · Obs 2 · Docs 4 · Prod 2

---

## C. Question Bank / CMS (ECAEP)

| Capability | Status | Evidence |
|---|---|---|
| Create / edit / version / review / publish / archive | 🟢 COMPLETE | `content_workflow_service` + admin content UI |
| Difficulty / explanation fields | 🟢 COMPLETE (schema) | `content_bodies.py` QUESTION body |
| Subject/topic/concept mapping | 🟢 COMPLETE | via `concept_id` |
| Search (published FTS) | 🟡 PARTIAL | question FTS only; admin reindex |
| Reporting / AI review queue | 🟢 COMPLETE | admin routes |
| Provenance (ingestion linkage) | 🟡 PARTIAL | source docs + jobs; editorial DoD incomplete |
| DIAGRAM / VIDEO_REF product depth | 🟠 BASIC | schemas exist; no rich student media product |

**Live content (`trinetra_db`, 2026-08-31):**

| Type | DRAFT | IN_REVIEW | PUBLISHED |
|------|------:|----------:|----------:|
| QUESTION | 78 | 1 | **11** |
| FLASHCARD | 12 | 0 | **2** |
| CONCEPT_NOTE | 7 | 0 | **6** |
| FORMULA_SHEET | 8 | 0 | 0 |

Published questions by subject: Physics 6, Zoology 3, Botany 1, Chemistry 1.

---

## D. NEET Examination Engine

| Capability | Status | Evidence |
|---|---|---|
| Practice generation + attempt | 🟢 COMPLETE | API + `/student/practice` + runner |
| Mock + full mock | 🟡 PARTIAL | Engine exists; **degrades** with thin published inventory; full 180-Q NEET **not content-ready** |
| Timed exam, palette, flag, confidence, submit, review | 🟢 COMPLETE | attempt runner UI + models |
| Attempt history | 🟡 PARTIAL | list page thinner UX |
| Reattempt / adaptive selection | 🔵 ADVANCED / ⚪ | no true adaptive engine |
| Rank/percentile | ⚪ NOT | explicitly not claimed in student analytics copy |

---

## E. Learning & Mastery

| Capability | Status | Evidence |
|---|---|---|
| Concept / micro / KU mastery | 🟡 PARTIAL | recompute on submit; rule-based levels |
| Recommendations | 🟡 PARTIAL | due → weak → new (not ML) |
| Revision due | 🟡 PARTIAL | concept schedule; not flashcard SRS |
| Progress dashboards | 🟢 COMPLETE (MVP) | student dashboard + analytics DS |

---

## F. Flashcards

| Capability | Status | Evidence |
|---|---|---|
| Browse / flip / filter | 🟠 BASIC→COMPLETE browse | `/student/flashcards` + CMS list |
| Decks / SRS / grading / schedule | ⚪ NOT | no SRS APIs |
| Published inventory | 🟡 PARTIAL | Count is **DB-derived** — revalidate with inventory script; historical “2 published” snapshot is stale |

---

## G. Bookmarks & Personal Study

| Capability | Status | Evidence |
|---|---|---|
| Toggle bookmark on question | 🟡 PARTIAL | API + question panel |
| Bookmark list / collections | ⚪ NOT | **no** list API or `/student/bookmarks` |
| Per-question notes | 🟡 PARTIAL | get/put/delete API; limited discovery UI |

---

## H. Analytics

| Capability | Status | Evidence |
|---|---|---|
| Student scorecard (accuracy, trends, weak subjects) | 🟡 PARTIAL→COMPLETE MVP | client-side from mastery + attempts; **not** admin analytics API |
| Admin assessment + AI usage | 🟠 BASIC | 2 endpoints + `/admin/analytics` |
| Rank, speed norms, cohort | ⚪ / 🔵 | absent |
| Content quality KPIs | 🟠 BASIC | coverage + AI review; limited |

---

## I. AI (v1 four agents only)

| Agent / capability | Implementation class | Evidence |
|---|---|---|
| AI Gateway | **Real** (+ FallbackProvider) | `ai/gateway/` |
| Tutor explain | **Real** / fallback text | `/api/v1/ai/tutor/*` + coach shell |
| Question Generator | **Real** → CMS draft | admin content generate |
| Study Planner | **Real** → persisted plan | study-plan page |
| Evaluator (AI check on submit) | **Real** / fallback report | ECAEP submit path |
| Mentor / Digital Twin / 12-agent | ⚫ DEPRECATED for v1 | ADR-0007 / CLAUDE.md |
| Vector RAG retrieval | ⚪ NOT | lexical grounding only |
| AI Study Coach UI | 🟡 PARTIAL | dock + study plan; not full chat OS |
| Eval benchmarks / red-team | ⚪ NOT | unit tests only |

---

## J. Knowledge / “RAG”

| Capability | Status | Evidence |
|---|---|---|
| Knowledge Units CRUD/browse | 🟡 PARTIAL | admin + limited student asset serve |
| Grounding check | 🟠 BASIC | string/fact overlap — **not embeddings** |
| Embeddings / vector search | ⚪ NOT | pgvector in Docker image ≠ app usage |
| Provenance / publish KU | 🟡 PARTIAL | pipeline present; editorial DoD open |

---

## K. Content Ingestion

| Capability | Status | Evidence |
|---|---|---|
| PDF discover / map / job / upload | 🟡 PARTIAL | admin ingestion UI + APIs; Phase A/B **not DoD complete** |
| MCQ / flashcard / note generation | 🟡 PARTIAL | pilot path; scaled 600 blocked |
| Visual asset review | 🟢 COMPLETE (MVP) | admin queue |
| Hindi translation | 🟣 STUB | `NotImplementedTranslationService` |
| Retry / monitoring | 🟡 PARTIAL | jobs poll; limited ops alerting |

---

## L. Admin / CMS

Admin portal largely **COMPLETE (MVP)** for: dashboard, content ECAEP, AI review, search, users/roles, audit logs, coverage, ingestion, knowledge units, visual assets, analytics.  
Role gate: client layout + API permissions (middleware cookie-presence only).

---

## M. Notifications

| Channel | Status |
|---|---|
| Transactional email | 🟡 PARTIAL (abstraction; SMTP infra) |
| Security alert email | 🟠 BASIC (Wave C; needs ALERT_EMAIL) |
| In-app / push / SMS / study reminders | ⚪ NOT |

---

## N. Search

Published question FTS + admin reindex: **🟡 PARTIAL**. No global multi-entity search.

---

## O. Security (incl. Waves A–C)

| Control | Status |
|---|---|
| JWT cookies, CSRF, Argon2, lockout, RBAC | 🟢 COMPLETE |
| Rate limits (auth recovery fail-closed) | 🟢 COMPLETE |
| Error IDs, redaction, Integrity mapping, headers | 🟢 COMPLETE |
| OTP/TOTP APIs | 🟡 PARTIAL (no FE) |
| SMTP / ENCRYPTION_KEY / ALERT ops | 🔴 BLOCKED on infra |
| PostgreSQL RLS / least-privilege runtime | 🔴 BLOCKED / REQUIRES INFRA |
| Dependency / Next upgrade | tracked separately — do not blind-upgrade |

Overall security posture: **YELLOW** (`docs/security-audit.md`).

---

## P. Observability

| Capability | Status |
|---|---|
| Structlog + correlation + errorId | 🟢 COMPLETE |
| Health / live / ready | 🟢 COMPLETE |
| OTel metrics/traces | ⚪ NOT |
| AI cost logging | 🟡 PARTIAL (gateway logs; admin AI usage) |
| Critical email alerts | 🟠 BASIC |

---

## Q. DevOps

Docker Compose (dev/prod-shaped), Alembic, GitHub workflows (ci/security/deploy/codeql/…) present.  
Coolify/Hetzner production execution: **UNVERIFIED**. Root README stale vs roadmap.

---

## R. QA

| Layer | Status |
|---|---|
| Backend pytest (auth, CMS, assessment, ingestion, security waves…) | 🟢 strong |
| Frontend Vitest | 🟠 BASIC (few component tests) |
| E2E / load / a11y / AI eval | ⚪ NOT |

---

## S. UX / Design System (Phases 1–4)

| Surface | Status |
|---|---|
| Tokens, DS components, dashboard, practice/mock, analytics, coach shell, admin pass | 🟢 COMPLETE as restyles wired to APIs |
| Marketing landing | 🟠 SHELL / stale roadmap copy |
| Dark mode / theme toggle | 🟢 COMPLETE |
| Loading/empty consistency | 🟡 PARTIAL |
| Bookmarks page / MFA UI | ⚪ missing |

---

## Cross-check summary (Docs → Code → DB → API → UI → Tests)

| Claim | Docs | Code | DB | API | UI | Tests | Verdict |
|---|---|---|---|---|---|---|---|
| SP0–SP9 done | roadmap ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Engineering done; **content/prod not** |
| Full NEET mock ready | implied engine | ✅ | ❌ 11 pub Q | ✅ | ✅ | ✅ | **Not product-ready** |
| TOTP MFA | security docs ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | Partial |
| Vector RAG | BRD vision | ❌ | pgvector unused | ❌ | ❌ | ❌ | Not implemented |
| Premium gating | commerce ADR | order ✅ | ✅ | status ✅ | pay UI ✅ | ✅ | **No entitlement checks** |
| Notifications | BRD | ❌ | ❌ | ❌ | ❌ | ❌ | Not implemented |

---

## Architectural debt & duplication (report only)

1. ~~Stale root `README.md` (SP0 in progress)~~ — fixed WAVE-P0-1.  
2. Marketing `(public)/page.tsx` still shows CMS/Assessment/AI as “planned” (FE not in WAVE-P0-1 scope; see `MARKETING_TRUTHFULNESS.md`).  
3. `AI_CHECKED` mentioned in comments but not durable status.  
4. Premium payment without feature gating.  
5. Bookmarks toggle without list surface.  
6. Flashcard “revision” in roadmap language vs concept-mastery revision only (no SRS).  
7. Multiple GH workflows overlapping with deploy docs that claim “never run”.  
8. CLAUDE.md still says identity “once it exists”.  
9. Knowledge “grounding” easily confused with RAG.  
10. Fallback AI text dangerous if mistaken for production Claude quality.

---

## Related docs

- Gap register: `docs/product/FEATURE_GAP_REGISTER.md`  
- Roadmap: `docs/product/MASTER_ROADMAP.md`  
- Cursor waves: `docs/product/CURSOR_IMPLEMENTATION_PLAN.md`
