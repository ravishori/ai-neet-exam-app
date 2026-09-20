# Production Seed V2 — Publication Authorization (Exact Active 100)

**Verdict: GREEN**  
**Captured:** 2026-09-03T19:13:48.615936+00:00

## PRE-FLIGHT
- Exact allowlist: **100** · SHA-256 `a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978`
- Subjects: Physics 35 / Chemistry 35 / Botany 15 / Zoology 15
- All DRAFT · NCERT SOURCE_TEXT_VERIFIED · FAIL=0 · REVIEW=0
- Historical superseded excluded: **8**
- Protected populations fingerprint captured
- Publication gates (evaluate as APPROVED): **100/100 PASS**

## PUBLICATION AUTHORIZATION
- Path: DRAFT → APPROVED (atomic SQL exact allowlist) → PUBLISHED (`ContentWorkflowService.publish`)
- Authorized/published: **100**
- ECAEP: **0** · submit_for_review skipped (ECAEP-adjacent)

## POST-PUBLICATION AUDIT
- Exact-set equality: **True**
- Extra V2 publications: **0**
- Missing: **0** · Superseded published: **0**
- Core content unchanged: **True** · NCERT retained: **True**
- Published global delta: **100** (expected 100)

## PROTECTED POPULATIONS
- V1 published: **30** (expected 30)
- T6-D / T6-F2 / legacy unchanged: **True**
- V1 practice firewall: **unchanged** (no SEED_V2 practice wiring)

## Four numerical replacements
- physics-10: `2e43ef71-d72a-423a-b9be-2e44c51de8b1` → PUBLISHED
- physics-11: `5b4f381e-0dee-4118-b237-fbaabbe1d0f5` → PUBLISHED
- physics-20: `f60e3124-8aa0-4ff6-b3e1-f8ad81eadce9` → PUBLISHED
- physics-34: `b98e5873-8352-4bb6-9a30-368e2f0ce6f7` → PUBLISHED

## Graphical
- physics-05: `9c51f8a1-bf72-4ca0-bcfd-e0aa5cb8ee53` → PUBLISHED (SVG≠NCERT)
- physics-21: `1633f068-f0df-4ff5-ac0c-57be4417f29e` → PUBLISHED (SVG≠NCERT)
- zoology-12: `ca0e7a05-38bb-4e12-a52d-4fd4c7a26b07` → PUBLISHED (SVG≠NCERT)

## VERDICT
**GREEN** — V2 publication authorization CLOSED/GREEN

## LIMITATIONS
- Per-UUID ContentWorkflowService.publish commits (same pattern as V1 exact-30); approval was a single SQL transaction; publish failure triggers full cohort rollback to DRAFT
- submit_for_review skipped (ECAEP-adjacent AI check); approval mirrors review(approve) end-state
- V1 practice firewall unchanged — V2 practice entry is a separate future task
- CERTIFIED_WITH_LIMITATION / page_verified=false limitations from NCERT re-run remain
- Numerical remediation artifact was AMBER (soft semantic); NCERT re-run GREEN authorized publication
- zoology-15 is a documented deterministic rematerialization (`deterministic_distractor_rewrite`), not Gemini; remaining 99 are `fixed:gemini`

---
**STOP** — Do not start V2 practice rollout or 1,000-question generation.
