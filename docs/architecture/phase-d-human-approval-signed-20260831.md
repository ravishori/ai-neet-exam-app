# Phase-D Human Approval — Signed Decision

**Status:** APPROVED FOR PHASE D.5B CONTROLLED APPLICATION

**Reviewer:** Ravi  
**Date:** 31 August 2026  
**Pilot:** `phase-d-30-mcq-authorized-20260825`  
**Authority:** `docs/architecture/phase-d-human-approval-manifest-20260831.md` (+ `.json`)

**This document records human decisions only.**  
It does **not** apply database changes. Phase D.5B must execute only the exact approved scope below.

---

## Global constraints (binding)

| # | Decision |
|---|----------|
| 9 | All 21 previously approved original questions — **KEEP UNCHANGED** |
| 10 | All 30 questions — **REMAIN DRAFT** |
| 11 | ECAEP submission — **NOT YET AUTHORIZED** |
| 12 | Publication — **NOT AUTHORIZED** |

**Additional condition:** Only the exact changes contained in the approved Phase-D manifest (as amended by this signed decision for `c7a54ae9`) may be applied. No additional content, metadata, taxonomy, provenance, workflow, or publication changes are authorized.

---

## Decision matrix — 9 flagged items

| ID | Decision | Scope notes |
|----|----------|-------------|
| `85fee888` | **APPROVE REPLACE** | Photorespiration pathway consequences; answer **B**; per manifest proposal |
| `c7a54ae9` | **APPROVE WITH MODIFICATION** | Ohm scaling REPLACE; **fixed-R condition made explicit** (see §Modification below); answer **A** |
| `7b80d6db` | **APPROVE REVISE** | Wording/sign-convention clarity; retain answer **A** |
| `ade9900b` | **APPROVE** (body REVISE + metadata) | Remap to `ohms-law` / `ohms-law-concept` |
| `87f621ab` | **APPROVE REVISE** | Remaining proposed revision — as in manifest |
| `863f1289` | **APPROVE REVISE** | Remaining proposed revision — as in manifest |
| `a42a3589` | **APPROVE REVISE** | Remaining proposed revision — as in manifest |
| `e6b9fb1e` | **APPROVE** body KEEP as proposed | Taxonomy remap **after** `limiting-factors` is created in D.5B |
| `8d50e829` | **APPROVE** body REVISE | Taxonomy remap **after** `limiting-factors` is created in D.5B |

“Remaining five proposed revisions” in the signer’s list maps to: `8d50e829`, `87f621ab`, `863f1289`, `ade9900b` (body), `a42a3589` — each APPROVE as above (with `ade9900b` metadata also APPROVE; Blackman remaps gated on taxonomy create).

---

## Taxonomy decision

| Item | Decision |
|------|----------|
| Concept `limiting-factors` — Limiting Factors (Blackman's Law) | **APPROVE NEW CONCEPT** |
| Parent | `factors-affecting-photosynthesis` / chapter `photosynthesis` / BOTANY |
| Create in D.5A? | No — create only in controlled D.5B |
| Remap `e6b9fb1e`, `8d50e829` | Authorized **only after** concept exists |

---

## Modification — `c7a54ae9` (binding for D.5B)

Manifest proposal stem (superseded):

> Ohm's law is written as V = RI. If the potential difference across a conductor is doubled while the current through it is halved, the resistance R of the conductor:

**Human-approved modified stem** (fixed-R / ratio condition explicit):

> Ohm's law gives R = V/I. Without treating R as a fixed material property that independently forces both changes, if a situation is described in which V becomes 2V and I becomes I/2, the value of the ratio V/I:

**Options / answer / difficulty** — unchanged from manifest proposal:

| Field | Approved value |
|-------|----------------|
| A | becomes four times the original value. |
| B | becomes twice the original value. |
| C | remains unchanged. |
| D | becomes one-fourth of the original value. |
| Correct | **A** |
| Difficulty | easy |

**Approved explanation** (aligned to explicit ratio wording):

> From Ohm's law, R = V/I. If V → 2V and I → I/2, then (V/I)' = (2V)/(I/2) = 4(V/I). The question asks how this ratio changes under those stated V and I values; it does not assert that a fixed ohmic resistor simultaneously experiences both changes as independent physical constraints. B undercounts. C would require V/I constant. D inverts the ratio.

Concept / topic / provenance: unchanged from manifest (`ohms-law` / `ohms-law-concept`).

---

## D.5B authorized work package (summary)

When Phase D.5B is explicitly executed:

1. Create taxonomy concept `limiting-factors` under approved parent.
2. Remap `e6b9fb1e` and `8d50e829` `concept_id` → new concept (after create).
3. Apply body REVISE/REPLACE for approved items via `ContentWorkflowService.update_draft` + **mandatory KU copy**; `current_version_id` unchanged; status remains **DRAFT**.
4. Apply `ade9900b` `concept_id` → `ohms-law-concept` (`9071ef5d-b62f-4159-91b6-90436a7705e6`).
5. Apply `c7a54ae9` using **modified** stem/explanation above (not the superseded manifest stem).
6. Leave 21 originals untouched.
7. Do **not** submit ECAEP; do **not** publish.

---

## Safety (this signing step)

```text
Database writes = 0
MCQ modifications = 0
Taxonomy modifications = 0
ECAEP actions = 0
Publication = 0
```

---

## Sign-off

```text
Human approval status:
APPROVED FOR PHASE D.5B CONTROLLED APPLICATION

Reviewer: Ravi
Date: 31 August 2026
```

Await explicit Phase D.5B apply instruction before any database writes.
