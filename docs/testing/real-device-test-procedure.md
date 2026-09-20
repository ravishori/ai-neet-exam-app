# Real-device test procedure — Practice Now / student shell

**Purpose:** Honest physical-device verification. Do **not** mark PASS without executing this procedure on the named device.

## Prerequisites

- Backend API running (`:8000`)
- Web app reachable from the device (LAN URL or tunnel — `localhost` only works on the host machine)
- A student account
- Published questions available in the practice pool

## Procedure (per device)

1. Record device model, OS version, browser + version, date/time, tester name.
2. Open the student dashboard (portrait).
3. Confirm **Practice now** is visible without horizontal scroll.
4. Tap **Practice now**; confirm loading feedback.
5. Confirm question text + options A–D are readable and tappable.
6. Select an option; confirm selected state.
7. Tap Next (if available); confirm progress updates.
8. Rotate to landscape; confirm controls remain usable (no obscured sticky bars).
9. Submit; confirm score/result readable.
10. Attach screenshot evidence paths in the matrix row.

## Result codes

| Code | Meaning |
|------|---------|
| PASS | Steps 3–9 succeeded |
| FAIL | Functional or layout failure with notes |
| BLOCKED | Device/network/app unavailable |
| NOT TESTED | Not executed |

## Lab log (fill when tested)

| Date | Device | OS | Browser | Orientation | Result | Evidence | Notes |
|------|--------|----|---------|-------------|--------|----------|-------|
| | Android phone | | Chrome | Portrait | NOT TESTED | | |
| | Android phone | | Chrome | Landscape | NOT TESTED | | |
| | iPhone | | Safari | Portrait | NOT TESTED | | |
| | iPhone | | Safari | Landscape | NOT TESTED | | |
| | Android tablet | | Chrome | Portrait | NOT TESTED | | |
| | iPad | | Safari | Portrait | NOT TESTED | | |
| | iPad | | Safari | Landscape | NOT TESTED | | |

## Current environment limitation

This Cursor agent environment does **not** have physical Android/iPhone/iPad access. Automated Chromium viewport emulation is **not** a substitute for real-device PASS.
