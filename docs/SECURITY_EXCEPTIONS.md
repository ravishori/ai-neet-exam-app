# Documented Security Exceptions

## EX-2026-09-23-001 — PostCSS HIGH (4 advisories), bundled inside Next.js 15.x

**Status:** ACCEPTED RISK
**Reviewed:** 2026-09-23 (updated — coverage extended from 2 to 4 advisories after `npm audit` on PR #48 reported the full current set)
**Review-by date:** Next scheduled Next.js major-version evaluation, or within 90 days, whichever is sooner.

### Findings

| Field | CVE-2026-45623 | CVE-2026-73646 | (no CVE number verified) | (no CVE number verified) |
|---|---|---|---|---|
| Advisory | [GHSA-6g55-p6wh-862q](https://github.com/advisories/GHSA-6g55-p6wh-862q) | [GHSA-r28c-9q8g-f849](https://github.com/advisories/GHSA-r28c-9q8g-f849) | [GHSA-fxqj-rqcc-2cmp](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp) | [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93) |
| Summary | Arbitrary file read via attacker-controlled `sourceMappingURL` in CSS comments | Path traversal in previous-source-map auto-loading, discloses arbitrary `.map` file contents | Incomplete fix of GHSA-6g55-p6wh-862q — `sourceMappingURL` still reads arbitrary `.map` files when `from` is unset | XSS via unescaped `</style>` in PostCSS's CSS stringify output |
| Package | `postcss` | `postcss` | `postcss` | `postcss` |
| Installed version | 8.4.31 | 8.4.31 | 8.4.31 | 8.4.31 |
| Fixed version | 8.5.12 | 8.5.18 | (see GHSA-6g55-p6wh-862q fix) | (see advisory) |
| Severity | HIGH | HIGH | HIGH | HIGH (npm audit block header) / part of npm's reported "1 moderate, 1 high" split across this package's 4 advisories |

All 4 advisories were reported together by `npm audit --audit-level=high` (the exact CI-enforced command in `security.yml`) under a single `postcss <=8.5.22` package entry, first observed complete on PR #48 (`8da91d1`) once the Bandit B314 fix let the Enterprise Security job reach the `npm audit` step for the first time. The first 2 (CVE-2026-45623, CVE-2026-73646) were already covered by this exception's original 2026-09-23 entry, including filling in `GHSA-r28c-9q8g-f849` as the previously-unrecorded advisory ID for CVE-2026-73646. The remaining 2 (`GHSA-fxqj-rqcc-2cmp`, `GHSA-qx2v-qp2m-jg93`) are newly added to this document in this update; no CVE number was independently verified for either in this pass — they are tracked here by GHSA ID only.

### Dependency path

```
apps/web (this app)
└─ next@15.5.26
   └─ postcss@8.4.31   (bundled inside next's own node_modules — not a direct
                         or even a normally-resolvable transitive dependency;
                         next pins this internally for its own build pipeline)
```

Verified via `npm ls postcss`: every *other* postcss consumer in this project
(`@tailwindcss/postcss`, `vite`, `shadcn`) already resolves to `postcss@8.5.25`
(patched). Only Next.js's own internal copy is stuck on 8.4.31.

### Runtime relevance / exploitability / reachability

**Build-time only, not reachable at runtime.** Both advisories' own text states the
precondition explicitly: *"reachable from any pipeline that runs **untrusted CSS**
through PostCSS (CMS themes, user-uploaded styles, browser-extension/userstyle
processors, ...)"* (CVE-2026-45623) and requires *"untrusted CSS processed...
through `result.map`"* (CVE-2026-73646).

In this application, PostCSS runs exactly once per deploy, inside `next build`,
processing only this repository's own CSS source files (`globals.css`, Tailwind
config, component-level CSS). **ai-neet-exam-app has no feature — checked
exhaustively across this entire engagement — that accepts user-uploaded CSS,
custom themes, or any other externally-supplied stylesheet at runtime.** No
student, admin, or API surface ever passes external input into a PostCSS
`process()` call. The precondition all 3 input-side advisories (CVE-2026-45623 /
GHSA-6g55-p6wh-862q, CVE-2026-73646 / GHSA-r28c-9q8g-f849, and the incomplete-fix
follow-up GHSA-fxqj-rqcc-2cmp) require to be exploitable does not exist in this
application's actual usage.

**`GHSA-qx2v-qp2m-jg93` (XSS via unescaped `</style>` in stringify output) —
output-side, separately verified.** This advisory requires the *opposite* data
flow from the 3 above: application code takes PostCSS's generated CSS text and
re-embeds it into an HTML `<style>` context without escaping. A dedicated,
read-only investigation confirmed this precondition is also absent:
- Zero `dangerouslySetInnerHTML` usages anywhere under `apps/web/src` (the
  standard React mechanism for injecting a raw string into the DOM).
- Zero dynamic `<style>` JSX usages anywhere under `apps/web/src`.
- PostCSS is configured only through `@tailwindcss/postcss`
  (`apps/web/postcss.config.mjs`) — no other plugin or invocation exists.
- PostCSS runs only during `next build`, as part of the standard Next.js
  pipeline described above.
- The generated CSS is emitted as static `.css` assets and served through
  Next.js's own asset/`<link>` handling — application code never stringifies
  PostCSS's output back into an HTML response itself.
- No CSS-upload, theme-customization, or other runtime CSS-injection feature
  was identified (consistent with the exhaustive feature review already
  performed for the input-side advisories above).

Therefore the unescaped HTML/`<style>` output path this advisory requires is
not present in this application, by the same architecture-review methodology
already applied to the input-side findings.

### Whether a non-major fix exists

**No.** Checked directly against npm's registry: the current stable Next.js 15.x
line (`next@15.5.26`, the newest 15.x release, npm dist-tag `backport`) still
bundles `postcss@8.4.31`. The bundled postcss version only advances to
`8.5.23` (patched) in `next@16.3.6` (current `latest` dist-tag) — a major
version. There is no 15.x patch release that carries the fix.

### Why not upgraded now

A Next.js 14→... wait, 15→16 major upgrade is a breaking-change framework
migration (routing/rendering internals, React version compatibility, etc.) that
requires a full regression pass across the entire frontend (43 test files, all
student/admin routes, the newly-added monetization UI, Playwright suite) — not
safely completable within this hardening pass without risking a real production
regression for a vulnerability class that is not reachable in this app's actual
architecture.

### Mitigation in place

1. Confirmed via architecture review (this document) that no code path passes
   externally-supplied CSS into PostCSS (input side, covers the 3 sourceMappingURL/
   path-traversal advisories) and no code path re-embeds PostCSS's output into
   HTML unescaped (output side, covers `GHSA-qx2v-qp2m-jg93`).
2. All *other* postcss consumers in the dependency tree are already patched
   (8.5.25) — only Next's internal copy is affected.
3. CRITICAL count is 0 across the entire application (backend and frontend) —
   this exception covers HIGH-severity, build-time-only findings exclusively.
4. Tracked here for the next Next.js major-version evaluation cycle.

### Decision

**ACCEPTED RISK** — 0 CRITICAL, 4 HIGH advisories (all against the same
Next-bundled `postcss@8.4.31`) with confirmed non-reachability on both the
input side and the output side, and no available non-breaking fix. Re-evaluate
when Next.js 16 stabilizes far enough for a scoped, tested migration, or if
this application ever adds a feature that processes externally-supplied CSS or
re-embeds generated CSS into HTML without using Next's standard asset pipeline
(at which point this exception is void and must be re-reviewed immediately).
