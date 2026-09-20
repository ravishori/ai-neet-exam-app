# Device compatibility matrix — Practice Now / student shell

**Last updated:** 2026-09-02 (Phase 2)  
**Rule:** Do not mark PASS unless actually tested. Use PASS / FAIL / BLOCKED / NOT TESTED.

## Playwright Chromium matrix (automated)

Harness: `apps/web/e2e/` · Config: `apps/web/playwright.config.ts`  
Evidence run: **10 passed** (2026-09-02) against `http://127.0.0.1:3001` + API `127.0.0.1:8000`.

| Class | Device/Viewport | Browser | Orientation | Practice Now | Practice | Result | A11y | Status |
| ----- | --------------- | ------- | ----------- | ------------ | -------- | ------ | ---- | ------ |
| Mobile | 390×844 | Chromium | Portrait | PASS | PASS | PASS | PASS (axe critical/serious=0) | PASS |
| Mobile | 390×844 → landscape swap | Chromium | Landscape | PASS (smoke) | — | — | — | PASS |
| Mobile | 360×640 | Chromium | Portrait + landscape | PASS (smoke/overflow) | — | — | — | PASS |
| Mobile | 430×932 | Chromium | Portrait + landscape | PASS (smoke/overflow) | — | — | — | PASS |
| Tablet | 768×1024 | Chromium | Portrait | PASS | PASS | PASS | PASS | PASS |
| Laptop | 1366×768 | Chromium | Landscape | PASS | PASS | PASS | PASS | PASS |
| Desktop | 1920×1080 | Chromium | Landscape | PASS | PASS | PASS | PASS | PASS |

Critical-path coverage (not every smoke size): Practice Now CTA → attempt → option select → next (when enabled) → submit → Score → axe.

## Real devices / native browsers

| Class | Device/Viewport | Browser | Orientation | Practice Now | Practice | Result | A11y | Status |
| ----- | --------------- | ------- | ----------- | ------------ | -------- | ------ | ---- | ------ |
| Mobile | Android phone | Chrome | Portrait | | | | | NOT TESTED |
| Mobile | Android phone | Chrome | Landscape | | | | | NOT TESTED |
| Mobile | iPhone | Safari | Portrait | | | | | NOT TESTED |
| Mobile | iPhone | Safari | Landscape | | | | | NOT TESTED |
| Tablet | Android tablet | Chrome | Portrait | | | | | NOT TESTED |
| Tablet | iPad | Safari | Portrait | | | | | NOT TESTED |
| Tablet | iPad | Safari | Landscape | | | | | NOT TESTED |
| Desktop | Edge | Edge | Landscape | | | | | NOT TESTED |
| Desktop | Firefox | Firefox | Landscape | | | | | NOT TESTED |
| Desktop | Safari/macOS | Safari | Landscape | | | | | NOT TESTED |

Procedure: `docs/testing/real-device-test-procedure.md`

## Other evidence

| Channel | Status |
| ------- | ------ |
| Cursor browser (Phase 1 desktop flow) | PASS (Practice Now live) |
| API scoring script `verify_practice_scoring.py` | PASS (11 Q delivered; independent score match) |
| Phase-D 30-question pilot | BLOCKED (DRAFT; not published via ECAEP) |

## Notes

- Chromium viewport emulation ≠ real Android/iOS Safari. Real-device rows stay NOT TESTED.
- WebKit/Firefox Playwright projects not installed in this lab.
- Port 3000 host process was sticky/corrupt during Phase 2; matrix ran on **3001** with CORS including `127.0.0.1:3001`.
