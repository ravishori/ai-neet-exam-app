# Audit Documentation Index

This directory is the permanent, living record of every audit, investigation,
fix, and test run performed on this repository by an AI agent or a human
operator. It exists so that no audit ever starts from zero — before auditing
anything, **read the relevant report below first**, reuse what's still valid,
and investigate only what has changed or what the existing report flags as
unverified/STALE.

This index itself must be updated whenever a linked report changes
materially (new findings, a status flip, a new audit date) — see
`findings-register.md` for the cross-cutting open-issues view, and
`system-inventory.md` for what currently exists in the codebase.

## How to use this system (for agents and humans)

1. **Before a new audit**: read this README, then the specific module report
   below, then `findings-register.md` for that module's open items. Treat any
   finding older than ~2 weeks or predating a relevant code change as
   candidate-STALE — re-verify it rather than repeating it as fact.
2. **During the audit**: record scope, date, status per finding, severity,
   exact file:line, reproduction steps, exact commands run, actual results
   (never estimated), limitations, and next actions — in the relevant report
   below, not in a new ad-hoc file.
3. **After the audit**: update the module report, then update
   `findings-register.md` and this README's "Last updated" lines if the
   module's overall status changed. Do this automatically, without the user
   having to ask — see `CLAUDE.md`'s "Audit documentation protocol" section.
4. **Evidence tiers** — every finding/claim must be labeled one of:
   - **Implemented** — code exists (cite file:line).
   - **Tested** — a test file exists and was actually run this audit (cite
     exact command + exact pass/fail/skip counts).
   - **Independently verified** — a *different* audit/reviewer than the one
     who implemented it confirmed the behavior by re-reading code or re-running
     tests, not trusting the implementer's own report.
   - **Sandbox-tested** — exercised against a real sandbox/test-mode external
     system (e.g. a payment gateway's test mode), not just mocks.
   - **Production-verified** — confirmed against live production via a
     read-only check (e.g. a live HTTP probe, a read-only DB query, or
     Railway's own deployment metadata) — cite the exact command/output.
   - **STALE** — was one of the above, but enough time or enough relevant
     code change has passed that it needs re-confirmation before being relied
     on again.

## Module reports

| Report | Scope | Status (as of last audit) | Last updated |
|---|---|---|---|
| [admin-security.md](admin-security.md) | Admin/SUPER_ADMIN accounts, password reset/recovery, MFA, audit logging | Partially implemented — admin-initiated reset shipped (uncommitted), MFA soft-gate shipped (uncommitted), hard MFA enforcement intentionally deferred | 2026-10-24 |
| [payments.md](payments.md) | Razorpay order creation, signature verification, webhook, entitlement | Partially implemented — webhook + reconciliation shipped (uncommitted), production `RAZORPAY_KEY_ID` missing, sandbox E2E not attempted | 2026-10-24 |
| [pyq-answer-quality.md](pyq-answer-quality.md) | PYQ answer-pending cohort, admin answer-review feature, structural data quality | Feature implemented + merged to `main`, **not yet deployed to production**; bulk-correction designed but not implemented | 2026-10-24 |
| [runtime-errors.md](runtime-errors.md) | Production bug reports (e.g. admin/content page crash) | Fixed locally, uncommitted, not production-verified — root cause reproduced, fix tested (21 backend + 65 frontend tests) | 2026-10-24 |

## Cross-cutting documents

- [findings-register.md](findings-register.md) — every open finding across all modules, one row each, with severity and status, so nothing is tracked in only one place.
- [system-inventory.md](system-inventory.md) — what exists in this codebase right now (modules, routers, migrations, feature flags), refreshed whenever a new audit touches a part of it, so later audits know what's already there without re-deriving it from scratch.
- [test-evidence-log.md](test-evidence-log.md) — append-only chronological log of every test command actually run during an audit and its exact result, across all modules. The module reports summarize; this log has the raw entries.

## Relationship to pre-existing documentation

This repository already has an extensive, older set of audit/quality documents
(`docs/quality/*`, `docs/audits/*` content-factory reports, `docs/PRODUCTION_READINESS.md`,
`docs/COMPREHENSIVE_PROJECT_AUDIT.md`, etc.) covering MCQ-generation pilots,
content-factory work, and earlier production-readiness passes. **Those are
preserved as-is** — this new system does not replace, move, or edit them. It
is the home for audits going forward, and the module reports above link out to
the most relevant pre-existing documents for historical continuity rather than
duplicating their content.
