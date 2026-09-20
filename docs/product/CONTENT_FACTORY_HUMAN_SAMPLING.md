# NEET Content Factory — Human Sampling Guide

**Status:** FACTORY-P5 · 2026-09-01  
Companion to `CONTENT_FACTORY_SAMPLING.md` (policy) and `CONTENT_FACTORY_P5_IMPLEMENTATION.md` (engineering).

---

## What humans review

| Stream | Who | Purpose |
|--------|-----|---------|
| GREEN sample | Stratified draw | Operational check that the pipeline is sane — **not** a statistical claim about all items |
| YELLOW | 100% | Risk / uncertainty |
| RED | 100% | Quarantine / exception |

Sample ACCEPT ≠ “all generated questions are scientifically correct.”

---

## Decision model

| Decision | Effect |
|----------|--------|
| ACCEPT | Factory ACCEPTED + `ecaep_submit_eligible` — still DRAFT |
| CORRECTION_REQUIRED | Note + reasons; fix via CMS edit |
| REJECT | Note + reasons; retained for audit |

Never auto DRAFT→IN_REVIEW / APPROVED / PUBLISHED.

---

## Checklist

A Scientific · B Answer · C Distractors · D NEET · E Explanation · F Mapping · G Difficulty · H Language · I Provenance  

Evidence only — not an approve button.

---

## UI

`/admin/factory-review` — queue + packet.  
ECAEP remains `/admin/ai-review` and `/admin/content/[id]`.

---

## Metrics (honest)

Dashboard shows reviewed/accepted/pending by class and failure-reason counts.  
Do **not** label these as scientific accuracy.
