# Phase D.4.1 — Independent Second Review

**Banner:** INDEPENDENT REVIEW — NO DATABASE CHANGES — NO ECAEP ACTION — NO PUBLICATION

**Reviewer role:** Independent NEET assessment / NCERT SME / taxonomy / quality auditor  
**Pilot:** `phase-d-30-mcq-authorized-20260825`  
**Date:** 2026-08-31  
**Database writes:** `0`

Treat prior Phase-D reports as proposals and audit evidence only — not approved changes.

---

## Final verdict

```text
Independent verdict:     AMBER
Taxonomy:                NEW CONCEPT REQUIRED
Revision plan:           APPROVED FOR HUMAN DECISION
Database writes:         0
```

**AMBER** means: scientifically and structurally suitable for **human ECAEP review**, with documented open items (taxonomy gap; answer-key position skew; one pedagogical caveat on the Ohm ratio stem). It does **not** mean ECAEP-approved or publishable.

---

## Live pilot check (read-only)

| Check | Result |
|-------|--------|
| Pilot questions | 30 |
| Subjects | 10 BOTANY / 10 CHEMISTRY / 10 PHYSICS (per D.3 matrix) |
| DRAFT | 30 |
| PUBLISHED | 0 |

---

## Independent review of the 9 flagged items

| ID | Previous action | Independent finding | Scientific status | NCERT status | Recommendation |
|----|-----------------|---------------------|-------------------|--------------|----------------|
| `e6b9fb1e` | KEEP | AGREE — independently verified. Blackman definition is correct; concept tag `photorespiration` is wrong. | PASS | PASS (§11.10) | KEEP (body); taxonomy remap after seed |
| `8d50e829` | REVISE | AGREE — clearer stem; answer A still correct; difficulty hard→medium appropriate. Taxonomy gap remains. | PASS | PASS (§11.10) | REVISE |
| `85fee888` | REPLACE | AGREE — live item is near-duplicate of `10d4d997` (same LO: RuBP+O₂ products). Proposed replacement tests pathway energetics/products-of-pathway, not product pair. Answer **B** independently defensible. | PASS | PASS (§11.9) | REPLACE |
| `87f621ab` | REVISE | AGREE — science unchanged (C); stem less theatrical; medium difficulty fair. | PASS | PASS (VSEPR→VB bridge) | REVISE |
| `863f1289` | REVISE | AGREE — NCERT 3p–4s gap reason; answer B; shortened stem improves parse. | PASS | PASS (§4.6.3) | REVISE |
| `ade9900b` | REVISE | AGREE on body clarity and math (I=2 A; q=−4 C → I=−2 A). AGREE Kirchhoff tag is wrong. Remap to topic `ohms-law` (“Electric Current and Ohm's Law”) is justified; concept `ohms-law-concept` is best available but coarse (summary is V=IR; item is I=dq/dt). | PASS | PASS (§3.2) | REVISE (+ metadata) |
| `c7a54ae9` | REPLACE | AGREE replace unit trivia. Algebra: R=V/I → (2V)/(I/2)=4R → **A**. Substantially better assessment value. Soft caveat: for fixed ohmic R, V×2 cannot coexist with I÷2; stem is ratio-style NEET convention. Optional human polish: ask about V/I explicitly. | PASS (ratio reading) | PASS (§3.4 scope) | REPLACE (optional stem polish) |
| `7b80d6db` | REVISE | AGREE after independent derivation (below). Proposed wording makes only A defensible. | PASS | PASS (Kirchhoff cell labelling) | REVISE |
| `a42a3589` | REVISE | AGREE — conceptual drift ≪ thermal (~10⁻⁵); answer A; easy difficulty OK. Slightly softer NEET discrimination remains acceptable for pilot. | PASS | PASS (Example 3.1) | REVISE |

---

## Botany near-duplicate (`10d4d997` vs `85fee888`)

| Dimension | `10d4d997` (retain) | `85fee888` live | `85fee888` proposed |
|-----------|---------------------|-----------------|---------------------|
| LO | Oxygenation **products** of RuBP+O₂ | Same products LO | Pathway **consequences** (no sugar/ATP/NADPH; CO₂ release; ATP use) |
| Cognitive | Recall of product pair | Same | Conceptual pathway outcome |
| Correct | A (PGA + phosphoglycolate) | A (same text) | **B** |
| Source | §11.9 photorespiration | §11.9 | §11.9 |

**Independent conclusion:** Live pair is **genuinely redundant**. Proposed replacement is **not** a paraphrase of `10d4d997`.

**Answer B check (NCERT):** Photorespiratory pathway yields neither sugars nor ATP/NADPH; CO₂ is released with utilisation of ATP. B matches. A invents sugar/NADPH synthesis; C reverses energetics; D misstates C4 role.

```text
NEAR-DUPLICATE = CONFIRMED (live)
REPLACE OBJECTIVE = DISTINCT — AGREE
ANSWER B = DEFENSIBLE — AGREE
```

---

## Kirchhoff independent derivation (`7b80d6db`)

| Element | Independent value |
|---------|-------------------|
| Current direction | I labelled **P → N** (positive → negative through the cell) |
| Polarity | P = positive terminal; N = negative terminal |
| Potential traversal | Given NCERT labelling: V(P) − V(N) = ε + Ir |
| Internal resistance | +Ir when current is marked entering the positive terminal (charging / load) |
| Equation | V(N) − V(P) = −(ε + Ir) = **−ε − Ir** |
| Answer | **A** |
| Other options | B matches opposite labelling (discharge ε−Ir); C/D wrong signs |

Proposed stem states the NCERT formula explicitly → single defensible key. Residual ambiguity of the original is adequately removed.

```text
REVISE REQUIRED (for clarity) — yes, as proposed
Further REVISE beyond proposal — no
```

---

## Ohm replacement (`c7a54ae9`)

```text
V → 2V
I → I/2
R' = V'/I' = (2V)/(I/2) = 4R
Correct = A
```

Better than SI-unit recall for NEET discrimination. Within NCERT Ohm’s-law algebra. Soft pedagogical note for human: ratio wording preferred over implying a fixed conductor simultaneously doubles V and halves I.

---

## Metadata (`ade9900b`)

| Tag | Fit |
|-----|-----|
| Live `kirchhoffs-laws` / `kcl-kvl` | **Incorrect** — no loop/junction law; §3.2 current definition |
| Proposed `ohms-law` / `ohms-law-concept` | **Better** — topic is “Electric Current and Ohm's Law”; no finer current-definition concept exists |
| Ideal (not in seed) | Dedicated “electric current / I=dq/dt” concept |

Remap is semantic, not convenience. Residual coarseness of `ohms-law-concept` is acceptable under current seed.

---

## Blackman taxonomy

| Test | Independent result |
|------|-------------------|
| Distinct from `photorespiration`? | **Yes** — Blackman/limiting factors (§11.10) ≠ RuBisCO oxygenation pathway (§11.9) |
| Fits parent topic `factors-affecting-photosynthesis`? | **Yes** |
| NCERT support? | **Yes** — Blackman’s Law of Limiting Factors |
| Reusable? | **Yes** — high NEET density |
| Fragmentation? | **Low** — sibling under existing topic |
| Naming (`limiting-factors` kebab-case)? | **Matches** seed peers |

### Taxonomy decision

```text
NEW CONCEPT REQUIRED
```

| Field | Recommendation |
|-------|----------------|
| name | Limiting Factors (Blackman's Law) |
| code | `limiting-factors` |
| parent | `factors-affecting-photosynthesis` → `photosynthesis` → BOTANY |
| definition | Rate of a multi-factor process is set by the factor nearest its minimal value (Blackman, 1905); covers external (light, CO₂, temperature, water) and internal (leaf traits, chlorophyll, internal CO₂) limiters for photosynthesis. |
| NCERT | Class 11 Biology Ch 11 §11.10 |
| why insufficient | Only concept under topic is `photorespiration`, whose summary and NCERT section do not cover Blackman. |
| future use | Blackman definition, limiting-factor scenarios, light/CO₂/temp curves, chlorophyll as internal limiter |

**Do not create the concept in this review.**

---

## Versioning strategy review

Proposed pattern:

```text
ContentWorkflowService.update_draft
→ new content_versions (version_no + 1)
→ latest_version_id → new
→ current_version_id unchanged
→ status DRAFT
→ copy KU join rows (+ singular knowledge_unit_id/_version)
```

| Claim | Independent check vs code |
|-------|---------------------------|
| `update_draft` creates new version | AGREE — verified in `content_workflow_service.py` |
| Does not set `current_version_id` | AGREE — only `publish` sets it |
| Status stays DRAFT | AGREE |
| Admin uses latest | AGREE — CMS item payload exposes `latest_version` |
| Student needs PUBLISHED + current | AGREE — search/browse filter `status='PUBLISHED'` |

### Critical: KU copy required?

```text
YES — REQUIRED
```

**Evidence (repository, not generic CMS):** `CmsRepository._pilot_run_item_ids_subquery` joins:

```text
ContentItem → ContentVersion (latest_version_id)
  → content_version_knowledge_units
  → knowledge_units → ingestion_sections → ingestion_jobs.pilot_run_id
```

If D.5 calls `update_draft` without copying KU rows onto the new latest version, revised items **drop out of** `pilot_run_id` filters and lineage audits. Singular `ContentVersion.knowledge_unit_id` is also used for visual-asset attachment and search KU text — must be mirrored when a single KU exists.

### Hidden risks

1. **KU omission** → silent pilot membership loss (highest risk).
2. **Stale `current_version_id` on DRAFT** after edit is correct per publish semantics; admin must not assume current==latest for unrepaired tooling.
3. **`concept_id` on item** — remap is not versioned; body history won’t show old concept on old versions.
4. No public PATCH for `concept_id` alone — D.5 needs an explicit controlled path.

---

## Final 30 set review (proposed)

| Gate | Result |
|------|--------|
| 10/10/10 subjects | PASS |
| Exact duplicates | PASS (0) |
| Near duplicates | PASS after `85fee888` REPLACE |
| Conceptual redundancy | ACCEPTABLE |
| Difficulty 12/6/12 | ACCEPTABLE for pilot |
| Cognitive mix | ACCEPTABLE (not recall-only) |
| Answer keys A22/B7/C1/D0 | **WARNING** — do not force rebalance; human may note for later bank hygiene |
| Metadata | WARNING until Blackman remap |
| NCERT coverage | PASS for scoped chapters |
| Distractors | PASS on reviewed flagged set |
| Educational coherence | **YES** for a three-chapter pilot |

---

## ECAEP readiness

```text
AMBER
```

**Why AMBER (not GREEN):** two items still mis-tagged until `limiting-factors` exists; answer-position skew; Ohm ratio stem soft caveat.  
**Why not RED:** no P0/P1 scientific failures found on independent review of the nine; duplicates resolved by proposed REPLACE; Kirchhoff key independently confirmed.

```text
Technically suitable for human ECAEP review.
≠ ECAEP approved.
≠ Publication authorized.
```

---

## Disagreement register

| Issue | Cursor finding | Independent finding | Agreement? | Resolution needed |
|-------|----------------|---------------------|------------|-------------------|
| `c7a54ae9` proposed stem | Fully clean Ohm application | Algebra correct; soft fixed-R / simultaneous V↑ I↓ tension if read literally | **PARTIAL** | Human: accept as NEET-ratio style **or** polish stem to “V/I becomes…” |
| `ade9900b` → `ohms-law-concept` | Fully accurate remap | Correct topic; concept is best-available but coarse vs I=dq/dt | **PARTIAL** | Accept remap under current seed; optional future concept for current definition |
| Blackman taxonomy | NEW CONCEPT REQUIRED | Same | AGREE | Human approve seed |
| KU copy on draft update | Required | Required — pilot filter joins latest→KU | AGREE | Must be in D.5 |
| Overall ECAEP color | AMBER (D.3) | AMBER | AGREE | — |

No substantive disagreement that blocks sending the package to human decision. Soft PARTIAL items belong on the human checklist, not automatic FURTHER REVISION REQUIRED for the whole plan.

---

## Human approval checklist

Before any database application, a human must explicitly:

1. Approve/reject taxonomy concept `limiting-factors`
2. Approve/reject `85fee888` replacement (pathway consequences; answer B)
3. Approve/reject `c7a54ae9` replacement (and optional stem polish)
4. Approve/reject `7b80d6db` wording revision (answer A retained)
5. Approve/reject remaining revisions (`8d50e829`, `87f621ab`, `863f1289`, `ade9900b`, `a42a3589`)
6. Approve/reject metadata changes (`ade9900b` remap; Blackman remap only after seed)
7. Approve versioning/application strategy (`update_draft` + **mandatory KU copy** + `current_version_id` unchanged + DRAFT preserved)

This review does **not** make those decisions.

---

## Safety

```text
Database modified = NO
MCQs modified = NO
Taxonomy modified = NO
ECAEP submitted = NO
Questions published = NO
```
