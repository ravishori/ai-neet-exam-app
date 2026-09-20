# FEATURE GAP REGISTER — TALOS

**Date:** 2026-08-31 · **Audit-only** · Evidence: code + local `trinetra_db` inventory

Priority: **P0** before meaningful pilot · **P1** core MVP product · **P2** important enhancement · **P3** advanced/future

| ID | Domain | Capability | Current Status | Evidence | Missing | Priority | Dependencies |
| -- | ------ | ---------- | -------------- | -------- | ------- | -------- | ------------ |
| G-001 | Content | Published question inventory | 🟡 PARTIAL | Inventory **DB-derived** — revalidate (`scripts/content_readiness_inventory.py`). Historical “11 PUBLISHED” is stale. Full 180 mock still blocked on subject allocation (esp. Zoology). | SME review + selective publish; never mass-publish unmapped drafts | P0 | CMS + SMEs |
| G-031 | Content | NEET Content Factory (batch/jobs/QA/sampling) | 🟡 PARTIAL | P1–P5 code DONE; live ~100 gen→QA→human review BLOCKED (Anthropic credits); next ops pilot then P6 certify | FACTORY-P6…P8 | P1 | ECAEP preserved; factory review ≠ approve/publish |
| G-002 | Content | Full NEET mock readiness | 🔴 BLOCKED | Engine needs ~180 published; have 11 | Physics/Chem/Bio depth | P0 | G-001 |
| G-003 | Content | Published flashcards / notes | 🟠 BASIC | 2 FC / 6 notes published | Editorial publish | P0 | CMS |
| G-004 | Assessment | Practice reliability | 🟢 COMPLETE (thin-content) | WAVE-P0-5: recs filter + UX; still needs published volume for value | Human publish campaign | P0 | G-001 |
| G-005 | Identity | MFA/OTP product UI | 🟡 PARTIAL | Wave C APIs + tests; login FE has no `mfaRequired` handling | Settings enroll + login step-up UI | P1 | ENCRYPTION_KEY, SMTP optional |
| G-006 | Ops | SMTP delivery | 🔴 BLOCKED | `email_service` abstraction | Production SMTP + WEB_APP_URL | P0 | Infra |
| G-007 | Ops | Production deploy verification | 🔴 BLOCKED | Coolify docs UNVERIFIED | Staging deploy, secrets, health | P0 | Docker/CI |
| G-008 | Security | RLS / DB least privilege | 🔴 BLOCKED | docs + optional SQL only | Role cutover plan | P2 | DBA |
| G-009 | Commerce | Premium entitlement gating | 🟠 BASIC | Orders + `is_premium` unused | Gate AI/premium features | P1 | Product policy |
| G-010 | Learning | Bookmark library | ⚪ NOT | Toggle only | List API + `/student/bookmarks` | P1 | learning module |
| G-011 | Learning | Flashcard SRS | ⚪ NOT | Browse only | Decks, grades, schedule | P2 | mastery, content |
| G-012 | Analytics | Student depth (chapter/topic/speed) | 🟡 PARTIAL | Client scorecard | Server aggregates, time-on-question | P2 | assessment events |
| G-013 | Analytics | Admin engagement KPIs | 🟠 BASIC | 2 endpoints | Cohort, content quality, funnels | P2 | analytics |
| G-014 | AI | Evaluation / hallucination harness | ⚪ NOT | Unit tests only | Golden sets, groundedness metrics | P1 | AI gateway logs |
| G-015 | AI | Vector RAG | ⚪ NOT | Lexical grounding | Embeddings, retrieval, citations UX | P3 | KU quality, cost |
| G-016 | AI | Coach as full tutor product | 🟡 PARTIAL | Dock + explain APIs | Session history, multimodal, safety UX | P2 | Tutor |
| G-017 | Knowledge | KU publish → student consumption | 🟡 PARTIAL | 69 KUs; limited student surface | Publish pipeline + UI | P1 | ingestion DoD |
| G-018 | Ingestion | Phase A/B DoD | 🟡 PARTIAL | Roadmap: implemented not DoD | Sign-off, monitoring | P1 | StudyMaterial |
| G-019 | Ingestion | Hindi translation | 🟣 STUB | NotImplemented | Provider decision | P3 | ADR-0019 |
| G-020 | Notifications | In-app / push / reminders | ⚪ NOT | None | Product design + module | P2 | identity, plans |
| G-021 | Search | Global / multi-type search | 🟡 PARTIAL | Question FTS | Concepts, KUs, notes | P2 | FTS indexes |
| G-022 | Academic | Admin hierarchy CRUD | 🟡 PARTIAL | Seed + micro create | Safe admin editors | P2 | academic |
| G-023 | UX | Marketing / README freshness | 🟡 PARTIAL | WAVE-P0-1: README/roadmap/product docs aligned; landing `page.tsx` still stale | FE marketing copy wave | P1 | docs done; UI pending |
| G-024 | QA | E2E critical journeys | ⚪ NOT | No Playwright | Login→practice→submit; admin publish | P0 | CI |
| G-025 | QA | Frontend test depth | 🟠 BASIC | Few Vitest files | DS + auth + attempt | P1 | vitest |
| G-026 | Observability | OTel / APM | ⚪ NOT | logs + ids only | Exporters, dashboards | P2 | infra |
| G-027 | Security | Audit log completeness | 🟡 PARTIAL | admin audit list | Authz events coverage audit | P2 | system |
| G-028 | Assessment | Adaptive practice | 🔵 ADVANCED | Fixed generation | Item response / mastery-driven pick | P3 | mastery data volume |
| G-029 | Product | Rank/percentile | 🔵 ADVANCED | Explicitly absent | Needs cohort data | P3 | users |
| G-030 | Scope | Digital Twin / 12 agents / multi-tenant | ⚫ DO NOT BUILD (v1) | ADR-0007 | — | — | After v1 + content |

---

## Content gap detail (local DB)

| Subject | DRAFT Q | PUBLISHED Q | Mock-ready? |
|---------|--------:|------------:|-------------|
| Physics | 38 | 6 | No |
| Chemistry | 30 | 1 | No |
| Botany | 10 | 1 | No |
| Zoology | 0 | 3 | No |
| **Total** | **78** | **11** | **No full paper** |

**Supports today:** light concept practice on a few published concepts; demo of exam UX.  
**Does not support:** daily multi-chapter practice, subject tests, full NEET mocks, adaptive claims, serious revision loops.

**Knowledge units:** 69 rows — pipeline capacity exists; student-facing published learning corpus still thin.

---

## AI-specific gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| No groundedness / citation UX in student tutor | P1 | Knowledge service has lexical check; tutor may still hallucinate |
| FallbackProvider can look “alive” without Claude | P0 ops | Must surface degraded mode in UI/ops |
| No cost budgets / per-user caps | P1 | Gateway logs exist; no enforcement |
| No prompt version registry | P2 | prompts in code |
| No red-team / safety eval suite | P1 | Student trust risk |
| No vector retrieval | P3 | Deferred intentionally vs BRD |

---

## Dependency highlights

```
G-001 published content
  ├─ blocks G-002 full mock, G-004 reliable practice, G-011 SRS value, G-012 analytics signal
  └─ depends on CMS reviewers + Phase D/E editorial process

G-006 SMTP
  └─ blocks trustworthy reset/verify/OTP emails

G-007 production verify
  └─ blocks any PRODUCTION READY label

G-005 MFA UI
  └─ depends on G-006 optional + ENCRYPTION_KEY
```
