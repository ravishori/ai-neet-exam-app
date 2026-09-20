# NEET Content Factory — QA, Sampling & Certification Strategy

**Status:** Strategy + **P4 QA** + **P5 human sampling UX** · 2026-09-01  
**Constraint:** Human editorial judgement remains final for release decisions; automation never auto-approves or auto-publishes.

See also: `CONTENT_FACTORY_P4_IMPLEMENTATION.md`, `CONTENT_FACTORY_P5_IMPLEMENTATION.md`, `CONTENT_FACTORY_HUMAN_SAMPLING.md`.

---

## 1. Quality tiers (question + batch)

| Tier | Meaning | Typical action |
|------|---------|----------------|
| **GREEN** | All critical deterministic gates pass; no known hard duplicate | Eligible for **GREEN sampling pool only** |
| **YELLOW** | Possible duplicate, soft metadata, short explanation, etc. | **100% human-review eligibility** |
| **RED** | Structural/consistency/safety/hard duplicate/hierarchy/blueprint fail | Factory quarantine — blocked from GREEN sample & certify |

Store tiers on **QAResult** + `GenerationCandidate.qa_classification` (authoritative for factory). Roll up batch counters via QA summary API.  
**ECAEP `ContentItem.status` is unchanged** (items stay DRAFT).

**Mandatory distinction:** AUTOMATED QA ≠ SCIENTIFIC VALIDATION.  
`scientific_certification` is always false on QAResult.

---

## 2. Automated QA gates (P4 = `factory_qa_v1`)

| Gate | Focus | P4 |
|------|-------|----|
| A Structure | QuestionBody / 4 options / answer | Deterministic RED |
| B Blueprint | Pin, hierarchy match, difficulty, family | Deterministic RED |
| C Hierarchy | subject→chapter→topic→concept | Deterministic RED |
| D Provenance | model, prompt, lineage; forbid official claims | RED / soft YELLOW |
| E Answer | Deterministic contradiction only | RED; no science claim |
| F Duplicate | DB fingerprints (exact/normalized/option-stem) | RED / YELLOW |
| G Safety | Injection, secrets, NTA/NCERT impersonation | RED |

**Semantic dedupe:** `SEMANTIC_DEDUPE_NOT_AVAILABLE` (no pgvector in P4).

**Rule:** Deterministic critical fails → RED. Soft signals → YELLOW. No AI judge in P4.

---

## 3. AI model roles (cost-aware)

| Role | P4 | Later |
|------|----|-------|
| Generator | P3 only | — |
| Validator / Judge | **Disabled** | P5/P6 assistive only |
| Evaluator (`ai_check`) | Unchanged ECAEP assist | Never certifies science |

Fallback must never be logged as “authoritative validation passed.”

---

## 4. Human review at scale — sampling (P4 prep / P5 UX)

| Stream | P4/P5 |
|--------|-----|
| Stratified GREEN | `ReviewSample` + seed → Factory Review UX |
| 100% YELLOW | Listed + human decisions |
| RED quarantine list | Listed; excluded from GREEN sample |

Sample size guidance: \(n=\min(N,\max(n_{min},\lceil k\sqrt{N}\rceil))\). P5 records checklist/decisions without ECAEP auto-transitions.

---

## 5. Certification (P6 — not P4)

Batch CERTIFIED ≠ question APPROVED/PUBLISHED. Requires `content.factory.certify` + evidence package.

---

## 6. Definition of Done (P4)

- [x] Persistent versioned QAResult
- [x] Deterministic gates A–G
- [x] DB-backed dedupe indexes/fingerprints
- [x] Explainable GREEN/YELLOW/RED
- [x] Sampling eligibility reproducible
- [x] No auto-approve / auto-publish
- [x] P1–P3 regression green
- [ ] Live ~100 generate→QA (blocked on Anthropic credits; commands documented)
