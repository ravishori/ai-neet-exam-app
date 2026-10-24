# Findings Register

Every open finding across all modules, one row each. This is the
cross-cutting view; the module reports have full evidence/reproduction detail
per finding. Update this whenever a module report's findings change.

Severity: **P0** (user-facing breakage or data risk right now) · **P1**
(significant gap, not immediately catastrophic) · **P2** (worth fixing, low
urgency).

| ID | Severity | Module | Finding | Status | Report |
|---|---|---|---|---|---|
| F-01 | P0 | Payments | Production Railway `ai-neet-exam-app` service missing `RAZORPAY_KEY_ID` — order creation currently fails (503) | Open — fix requires user to set the Railway variable; documented steps provided, not executed | [payments.md](payments.md) |
| F-02 | P0 | Payments | No webhook existed for Razorpay (now implemented, uncommitted) — a client that never completes `/verify` (closed tab, crash) left a captured payment with no entitlement, no recovery path | Fixed in working tree, not committed/deployed — needs `RAZORPAY_WEBHOOK_SECRET` set + real webhook URL configured in Razorpay dashboard before it's live | [payments.md](payments.md) |
| F-03 | P0 | PYQ / Deploy | PYQ Answer Review feature (`cef1f42`) is merged to `main` but **not deployed** to production — live `openapi.json` has zero `pyq-answer-review` paths | Open — needs a Railway redeploy of `main`, then migration `d2e3f4a5b6c7` applied, then `pyq.answer_review` permission seeded | [pyq-answer-quality.md](pyq-answer-quality.md) |
| F-04 | P1 | Admin/Security | No admin-initiated password-reset endpoint existed for resetting *another* user's password (self-service reset/change existed; admin-on-behalf-of-another-user did not) | Fixed in working tree, not committed — new endpoint reuses existing reset-token machinery, 26/26 new+existing tests passing | [admin-security.md](admin-security.md) |
| F-05 | P1 | Admin/Security | Zero privileged accounts (incl. the one SUPER_ADMIN) have MFA enabled; hard enforcement would lock everyone out if flipped on today | Mitigated — soft `mfa_setup_required` login flag shipped (uncommitted); hard enforcement deliberately deferred, staged plan documented | [admin-security.md](admin-security.md) |
| F-06 | P1 | Admin/Security | No tool exists to reset an EXISTING admin's own password if they lose email access — `scripts/bootstrap_super_admin.py` is a no-op for an already-provisioned SUPER_ADMIN | Open — no safe automated path yet; manual one-off script would be required per-incident, not pre-built | [admin-security.md](admin-security.md) |
| F-07 | P1 | PYQ | No bulk answer-correction/import endpoint exists — the admin review feature is one-question-at-a-time by design | Designed (preview/commit two-endpoint spec), not implemented | [pyq-answer-quality.md](pyq-answer-quality.md) |
| F-08 | P1 | Payments | Missing cross-user order-ownership test and webhook-driven-entitlement test (implementation was already correct; tests were the gap) | Fixed — both tests added and passing | [payments.md](payments.md) |
| F-09 | P1 | Backups | No evidence a real backup of production existed prior to this session | Fixed — `database/backups/prod_railway_20261022_042819Z.dump` taken and validated this session (17.8MB, `pg_restore --list` exit 0) | [admin-security.md](admin-security.md) (ops note) |
| F-10 | P2 | Payments | `commerce.orders.razorpay_order_id` had no index — full table scan on every webhook delivery | Fixed — index migration `d4f5a6b7c8d9` added, local-verified | [payments.md](payments.md) |
| F-11 | P2 | CI | `Backend/Tests` and `Enterprise Security Checks` fail on recent CI runs | Confirmed pre-existing/unrelated to this session's changes, root-caused individually (missing CI fixtures, stale fake-settings fixtures, frontend npm lockfile CVEs tracked by Dependabot PRs #82-87, 2 genuine pre-existing parser bugs) | See CI investigation notes folded into payments.md/pyq-answer-quality.md context |
| F-12 | **P0** | Runtime | `/admin/content/{id}` production page shows a generic error screen for any QUESTION item with `options: null` in its stored body | Fixed locally (editorial_review_service.py + frontend null-guard + distinct error states), 21 backend + 65 frontend tests passing, **not committed, not production-verified** — requires deploy to confirm against the exact reported URL | [runtime-errors.md](runtime-errors.md) |
| F-13 | P1 | CMS | Same `body.get("options", [])`/unguarded-null pattern as F-12 found at 3 more call sites (`cms_router.py` student browse, `search_service.py` public search, `content_factory_human_review_service.py`) | Fixed — all 3 hardened to `body.get("options") or []`. `search_service.py`'s `_to_public_result` has **no existing test coverage at all** — flagged, not fixed, this audit | [runtime-errors.md](runtime-errors.md), [pyq-answer-quality.md](pyq-answer-quality.md) |
| F-14 | P1 | PYQ | `pyq_answer_review.py`'s `get_question_review_detail` serialized `row.raw_options` into the API response without the `or {}` guard used at every other call site in the same file — would have sent `options: null` to the frontend, which indexed it unguarded (`detail.options[label]`) | Fixed — backend `or {}` guard + frontend `?.[label]` optional-chaining added, 37/37 existing tests still pass | [pyq-answer-quality.md](pyq-answer-quality.md) |

## Resolved this session (kept for traceability, not re-audited unless flagged STALE)

- Pillow 12.3.0 → 13.0.0 (11 real CVEs, confirmed against PyPI's own vulnerability feed) — committed (`f3b77a6`).
- Bandit B608 false-positive (6 findings) — documented with `# nosec` + rationale — committed (`4ba291c`).
- Bandit B310 real gap (URL trust boundary in `hf_dataset_adapter.py`) — fixed with a runtime scheme/host check, not just suppressed — committed (`76e3bf5`).
- Stale test fixture (`validation_status='VALIDATED'` should be `'PASSED'`) causing 4 false Gemini-backfill test failures — fixed, committed (`af4f82f`).
- Two stale hardcoded counts in PYQ topic-mapping tests (128→204, 6→8) after 5 undocumented-in-test expansion rounds — fixed, uncommitted test-only change.
- Category-A skipif guards added for NCERT-corpus/fact-pack-dependent tests that have no guard, confirmed these assets are intentionally git-ignored/local-only — uncommitted test-only change.
