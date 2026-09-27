# Documented Security Exceptions

## EX-2026-09-23-001 — PostCSS HIGH (2 CVEs), bundled inside Next.js 15.x

**Status:** ACCEPTED RISK
**Reviewed:** 2026-09-23
**Review-by date:** Next scheduled Next.js major-version evaluation, or within 90 days, whichever is sooner.

### Findings

| Field | CVE-2026-45623 | CVE-2026-73646 |
|---|---|---|
| Advisory | [GHSA-6g55-p6wh-862q](https://github.com/postcss/postcss/security/advisories/GHSA-6g55-p6wh-862q) | GHSA (path traversal, previous-map) |
| Summary | Arbitrary file read via attacker-controlled `sourceMappingURL` in CSS comments | Path traversal in previous-source-map auto-loading, discloses arbitrary `.map` file contents |
| Package | `postcss` | `postcss` |
| Installed version | 8.4.31 | 8.4.31 |
| Fixed version | 8.5.12 | 8.5.18 |
| Severity | HIGH | HIGH |

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
`process()` call. The precondition both CVEs require to be exploitable does not
exist in this application's actual usage.

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
   externally-supplied CSS to PostCSS.
2. All *other* postcss consumers in the dependency tree are already patched
   (8.5.25) — only Next's internal copy is affected.
3. CRITICAL count is 0 across the entire application (backend and frontend) —
   this exception covers HIGH-severity, build-time-only findings exclusively.
4. Tracked here for the next Next.js major-version evaluation cycle.

### Decision

**ACCEPTED RISK** — 0 CRITICAL, 2 HIGH with confirmed non-reachability and no
available non-breaking fix. Re-evaluate when Next.js 16 stabilizes far enough
for a scoped, tested migration, or if this application ever adds a feature that
processes externally-supplied CSS (at which point this exception is void and
must be re-reviewed immediately).
