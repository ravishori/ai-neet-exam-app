# PYQ Answer Quality & Admin Review Audit Report

**Scope:** `NEET_PYQ_OFFICIAL` answer-pending cohort structural quality,
the Admin PYQ Answer Review feature, and its deployment status.

## Current status (2026-10-24)

Overall: **Feature implemented and merged to `main`; NOT yet deployed to
production.** The underlying data-quality findings are stable (re-confirmed,
no drift). Bulk correction is designed but not implemented.

## Live cohort counts (Production-verified, re-queried 2026-10-24 — not the earlier 8,928 by assumption, confirmed by live re-query showing identical numbers, i.e. no drift)

| State | Count |
|---|---|
| `ANSWER_PENDING` | 8,928 |
| `ANSWER_VERIFIED` | 3,081 |
| `ANSWER_CONFLICT` | 387 |

**Pending by subject:** Chemistry 1,056 · Physics 1,049 · Zoology 1,034 · Botany 1,018 · unset/null 4,771.
**Pending by exam year:** 2020: 2,094 · 2021: 4,157 · 2023: 2,150 · 2024: 524 · 2025: 3.
**Structural eligibility** (via the real production classifier `pyq_option_eligibility.py`, run against a bulk dump, not re-derived SQL logic): `FOUR_VALID_OPTIONS` 7,682 (ready for review right now) · `MISSING_OPTION` 1,148 · `MALFORMED_OPTIONS` 70 · `DUPLICATE_OPTIONS` 27 · `REQUIRES_MANUAL_REVIEW` 1.

This breakdown is also recorded in full historical detail (with methodology
and precedence rules) in `docs/content-factory/PYQ_ANSWER_KEY_STATUS.md` —
read that file's multiple dated sections for the complete audit trail; this
report summarizes current state, that file is the historical ledger.

## The Admin PYQ Answer Review feature (commit `cef1f42`, on `main`)

Built this session: migration `d2e3f4a5b6c7` (adds `reviewer_user_id`/`reviewed_at`/
`evidence_source_type`/`evidence_locator` to `pyq.answer_assertions`), permission
`pyq.answer_review`, service `app/modules/cms/pyq/pyq_answer_review.py` +
`pyq_option_eligibility.py`, router `pyq_answer_review_router.py`, frontend
`apps/web/src/app/admin/pyq-answer-review/`.

### Gap table against required functionality

| Capability | Status | Evidence |
|---|---|---|
| Answer entry | Implemented | `pyq_answer_review.py:307-487` `save_answer_review`, router `:73-108` |
| Answer verification | Implemented | writes `VERIFIED`, transitions `ANSWER_VERIFIED`/`ANSWER_CONFLICT` (`:429,474`) |
| Audit history | Implemented | `AuditService(db).log(...)` after save (`router:92-104`) and skip (`:119-126`) |
| Filters/pagination/progress counts | Implemented | `list_review_queue` (`:142-204`), `get_queue_counts` (`:81-139`), router query params (`:33-50`) |
| Never mark AI-generated answers verified | Confirmed | zero LLM/AI-gateway imports anywhere in `pyq_answer_review.py` |
| Idempotent retry / conflict routing | Implemented, Tested | second reviewer picking a different option routes to `ANSWER_CONFLICT`+`DISPUTED`, never silently overwrites; identical retry with a stale `expected_state` is a safe no-op (fixed this session — idempotency check now runs before the staleness check) |
| **Bulk import/correction** (preview, validation, duplicate detection, transaction safety, rollback) | **Missing** — confirmed, not assumed. No bulk endpoint exists anywhere in the router. | — |

### F-07 — Bulk correction design (not implemented)

Two endpoints under the existing router prefix:
- `POST /pyq-answer-review/bulk/preview` — validates every row (reusing
  `save_answer_review`'s own validation + `classify_option_structure` for
  eligibility + existing-assertion lookup for duplicate detection), makes
  **zero writes**, returns a per-row verdict (`will_save` / `idempotent_noop`
  / `conflict` / `rejected:<reason>`).
- `POST /pyq-answer-review/bulk/commit` — same payload, calls the existing
  single-question `save_answer_review()` once per row, each in its own
  transaction (so one bad row never rolls back the whole batch), one audit
  log entry per row (or one batched entry referencing all affected question
  IDs). **No new migration needed** — reuses the exact same write path as the
  single-question flow, just looped.

Not implemented this session — specified precisely enough to implement in a
follow-up, per the instruction to prioritize correctness over rushing.

## F-03 — Feature merged but not deployed (Production-verified, Open)

Confirmed via two independent signals: (1) live `openapi.json` (180 paths)
has zero `pyq-answer-review` paths, (2) Railway's own deployment metadata
(`railway status --json`) shows the active production deployment's commit
hash (`677724a...`) is a confirmed ancestor of `cef1f42`, 9 commits behind.
Also confirmed via direct read-only SQL: production `alembic_version` =
`62aa0447d463` ≠ local head `d2e3f4a5b6c7`; the 4 new `answer_assertions`
columns = 0/4 present; `pyq.answer_review` permission = does not exist in
production at all.

**This means: nobody can currently use this feature in production, even
though it is fully merged, tested, and browser-verified in a local
environment.** It is not "ready" in any production sense until deployed.

## Test results

```
pytest tests/test_pyq_answer_review.py app/modules/cms/tests/test_content_bodies.py -v
→ 60 passed, 0 failed, 0 skipped (re-confirmed 2026-10-24, consistent across multiple re-runs this session)
```

## Control-character validation hardening (separate, related fix)

38 `ANSWER_PENDING` rows had embedded Unicode `Cc` control characters (e.g.
`U+0001`, `U+0004`) in `raw_stem`, corrupting otherwise-valid-looking
questions. Fixed by adding a shared validator in
`app/modules/cms/schemas/content_bodies.py` rejecting any `Cc` character
except `\t\n\r`, while explicitly preserving scientific notation, chemical
formulas, Greek letters, and arrows (tested against the real corrupted
examples, not synthetic ones). This re-classified 38 rows from
`FOUR_VALID_OPTIONS` into `MALFORMED_OPTIONS`, reflected in the cohort counts
above.

## Required approvals (none taken)

1. Deploy `main` to production (brings the whole feature + the 5 pending migrations, including `d2e3f4a5b6c7`, live).
2. Run the identity seed against production to grant `pyq.answer_review`.
3. Decide whether to implement the bulk-correction design in F-07 above as a follow-up.
