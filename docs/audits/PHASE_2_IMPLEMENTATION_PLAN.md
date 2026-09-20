# Phase-2 Implementation Plan (2026-09-02)

## Confirmed state
- Branch: `main` (large uncommitted working tree including Phase-1 Practice Now work)
- Practice Now: `useStartPractice` present; live-tested in Phase 1
- Published pool: **11** QUESTIONS
- Phase-D pilot (`phase-d-30-mcq-authorized-20260825`): **35 DRAFT**, **0 PUBLISHED**
- ECAEP: DRAFT → IN_REVIEW → APPROVED → PUBLISHED (human approve + `content.publish`)
- Playwright: not installed
- Build blocker: `Button asChild` in admin pages (Base UI has no `asChild`)

## Decisions
1. **Do NOT publish** Phase-D drafts → Gate B (30/30) = **BLOCKED**
2. Establish Playwright viewport matrix + critical Practice Now E2E against **available published pool**
3. Independent scoring verification script
4. Fix `asChild` build errors
5. Incremental premium UX + error boundary
6. Lighthouse mobile measurement
7. axe accessibility in Playwright
8. Real-device procedure doc (NOT TESTED)
9. Update audits honestly → expect **YELLOW** until Gate B + real devices pass

## Out of scope
- Silent publish / content mutation
- Regenerating replacement MCQs
- Schema migrations
