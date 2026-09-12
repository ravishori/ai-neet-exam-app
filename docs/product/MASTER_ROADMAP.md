# MASTER PRODUCT ROADMAP — TALOS

**Date:** 2026-08-31 · Derived from repository evidence (not BRD fantasy scope)  
**Principle:** Content and reliability before AI sophistication. Preserve modular monolith, ECAEP, 4-agent AI Gateway, Design System, auth model.

---

## Current baseline

- **Engineering:** SP0–SP9 implemented in code (see `docs/architecture/roadmap.md`).
- **Product blocker:** **11 published questions** locally; full NEET mock and daily practice not content-viable.
- **Security:** Waves A–C backend shipped; posture **YELLOW**.
- **Production:** Documented Coolify path; **UNVERIFIED**.

---

## Phase map (adjusted to evidence)

| Phase | Name | Objective | Status vs repo |
|------:|------|-----------|----------------|
| 0 | Audit & Baseline | Authoritative inventory + gaps | **Done** — `docs/product/` + WAVE-P0-1 README/roadmap alignment (landing UI copy still stale; see MARKETING_TRUTHFULNESS) |
| 1 | Foundation / Reliability | SMTP, staging, health, stale docs, E2E smoke | Mostly missing ops |
| 2 | Core NEET Learning Content | Publish quality MCQs/notes/flashcards via ECAEP | **Critical path** |
| 3 | Examination Engine Hardening | Practice/mock reliability + UX polish under real content | Engine exists; needs content |
| 4 | Personalization & Mastery | Recs filter by published availability; bookmark library; revision UX | Partial |
| 5 | AI Learning Intelligence | Eval harness, cost caps, coach UX, safer grounding | Agents exist; maturity low |
| 6 | Analytics & Student Intelligence | Deeper student + admin KPIs | Basic |
| 7 | Content & Knowledge Platform | Ingestion DoD, KU publish, search expansion | Partial |
| 8 | Notifications & Engagement | Reminders after content/practice work | Not started |
| 9 | Advanced Learning / SRS | Flashcard SRS, adaptive practice | Not started |
| 10 | Security & Production Hardening | MFA UI, RLS cutover, secrets, alerts verified | Partial (API-only MFA) |
| 11 | E2E QA / Performance | Playwright, load on attempt submit | Thin |
| 12 | Production Deployment | Coolify live + runbook proof | Unverified |
| 13 | Advanced / Future | RAG, Digital Twin, 12 agents, multi-tenant, native | **Explicitly deferred** |

---

## Recommended build sequence (dependency-aware)

```
Phase 0 Audit + doc truth (WAVE-P0-1 docs done; landing UI copy pending explicit FE wave)
    ↓
Phase 1 Reliability (SMTP + staging + E2E smoke)
    ↓
Phase 2 Content publish pipeline (human review; Phase D sign-off; scale inventory)
    ↓
Phase 3 Exam engine under real content (practice/mock acceptance; no silent empty)
    ↓
Phase 4 Mastery/recs/bookmarks (value compounds with content)
    ↓
Phase 5 AI quality & safety (eval, caps, coach)
    ↓
Phase 6 Analytics depth
    ↓
Phase 7 Ingestion/KU DoD + search
    ↓
Phase 10 Security productization (MFA UI) ∥ Phase 11 QA ∥ Phase 12 Prod
    ↓
Phase 8 Notifications (only after daily active practice exists)
    ↓
Phase 9 SRS / adaptive
    ↓
Phase 13 Future innovation (only with users + data + content)
```

**Why this order:** Without published content, practice/mock/AI/analytics cannot deliver aspirant value. Without SMTP/staging, auth recovery and “production ready” claims are false. AI sophistication without eval + content is expensive theater.

---

## Priority scoring rubric

`Priority Score = 0.25·StudentValue + 0.15·BusinessValue + 0.20·DependencyCriticality + 0.15·SecurityImpact + 0.10·(5−Complexity) + 0.15·RiskReduction`  
(each 1–5; higher = do sooner)

| Theme | Score | Why |
|-------|------:|-----|
| Publish content (G-001/2/3) | **4.7** | Unlocks entire product; low code risk, high process effort |
| SMTP + staging (G-006/7) | **4.5** | Auth trust + release honesty |
| E2E smoke (G-024) | **4.2** | Protects regressions while content scales |
| Practice/recs published filter (G-004) | **4.0** | Prevents broken aspirant journeys |
| MFA UI (G-005) | **3.6** | Security completeness; after ENCRYPTION_KEY |
| Bookmark library (G-010) | **3.4** | High student value, small scope |
| AI eval harness (G-014) | **3.5** | Safety/cost before scaling Claude |
| Premium gating (G-009) | **3.2** | Business; needs policy |
| Notifications | **2.4** | Premature without habit loops |
| Vector RAG / Digital Twin | **1.5** | Conflicts with frozen scope / cost |

---

## What we should NOT build yet

See also executive section in chat / plan doc. Summary:

1. **12-agent orchestrator, Mentor, Digital Twin** — ADR-0007.  
2. **Multi-tenancy / org threading** — reserved table only.  
3. **Native mobile apps**.  
4. **Vector RAG platform** until KU quality + cost model exist.  
5. **Competitor feature cloning** (live classes, social feed, gamification sprawl).  
6. **Blind Next.js major upgrades** as part of product waves.  
7. **Flashcard SRS** before ≥ hundreds published cards.  
8. **Rank/percentile** before meaningful cohort size.  
9. **SMS OTP gateway** until email OTP productized.  
10. **Microservices split** — contradicts ADR-0001.

---

## Phase acceptance (high level)

| Phase | Exit criteria |
|------:|---------------|
| 1 | Staging URL healthy; SMTP reset works; smoke E2E green; README/marketing not lying |
| 2 | ≥ N published questions per subject (product-set N; suggest interim **≥50/subject** before “daily practice”; **≥45/subject** before claiming full mock) |
| 3 | Practice/mock journeys never silent-fail; full mock only offered when inventory allows |
| 4 | Recs only point at practicable concepts; bookmarks list works |
| 5 | Degraded AI mode visible; eval suite in CI; cost logged per user/day |
| 12 | Coolify deploy + VERIFICATION_CHECKLIST signed; security still YELLOW→GREEN only with evidence |

---

## Linkage

- Inventory: `MASTER_FEATURE_AUDIT.md`  
- Gaps: `FEATURE_GAP_REGISTER.md`  
- Executable Cursor waves: `CURSOR_IMPLEMENTATION_PLAN.md`  
- Legacy sprint log: `docs/architecture/roadmap.md` (do not contradict without evidence)
