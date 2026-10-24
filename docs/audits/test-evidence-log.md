# Test Evidence Log

Append-only. One entry per test command actually run during an audit. Never
estimate counts — if you didn't run it, don't log a result for it. Newest
entries at the bottom.

---

**2026-10-21/22/24 session** — multiple audits, commands below in
chronological order of execution.

```
pytest tests/test_pyq_answer_review.py app/modules/cms/tests/test_content_bodies.py -v
→ 60 passed, 0 failed, 0 skipped (re-run at multiple points this session, consistent)
```

```
pytest tests/test_pyq_gemini_backfill.py -v
→ 8 passed, 0 failed, 0 skipped (after fixing the stale 'VALIDATED'→'PASSED' fixture value)
```

```
pytest app/modules/cms/tests/test_mcq_factory_external_acquisition.py -v
→ 20 passed, 0 failed, 0 skipped (17 existing + 3 new default_http_get trust-boundary guard tests)
```

```
bandit app/modules/cms/mcq_factory_groq/external_sources/hf_dataset_adapter.py
→ 0 issues identified, 1 suppressed (B310, now backed by a real runtime check, not just a comment)
```

```
bandit app/modules/cms/pyq/pyq_answer_review.py
→ 0 issues identified, 6 suppressed (B608, verified false-positive — hardcoded predicate constants only, never request-derived SQL)
```

```
pip-audit -r apps/backend/requirements.txt -r apps/backend/requirements-dev.txt
→ No known vulnerabilities found (after Pillow 12.3.0 → 13.0.0; confirmed again in real CI, not just locally)
```

```
pytest app/modules/cms/tests/test_neet_syllabus_driven_generation.py -v
→ 13 passed, 0 failed, 0 skipped
pytest app/modules/cms/tests/test_mcq_factory_groq_topic_mapping_fix.py -v
→ 8 passed, 0 failed, 0 skipped (after fixing stale 128/6 → 204/8 counts and reusing load_all_hand_curated_facts())
```

```
pytest app/modules/commerce/ tests/test_commerce_and_language.py -v
→ 18 passed, 0 failed, 0 skipped (8 pre-existing signature/order tests + 8 new webhook tests + 2 new review-added tests: cross-user ownership, webhook-driven entitlement)
```

```
bandit app/modules/commerce/ -r
→ 39 Low (all B101 assert-in-tests, expected), 0 Medium, 0 High
```

```
pytest tests/test_admin_password_reset_and_mfa_gate.py tests/test_forgot_reset_password.py tests/test_mfa_recovery_csrf_alerts.py -v
→ 26 passed, 0 failed, 0 skipped
```

```
pg_restore --list database/backups/prod_railway_20261022_042819Z.dump
→ exit 0, 568 TOC entries, dbname: railway, format CUSTOM — archive valid
```

---

**2026-10-24 — comprehensive review of all uncommitted changes (this entry)**

```
pytest tests/test_content_factory_p5.py tests/test_batch_a_acquisition.py tests/test_batch_a_pilot.py tests/test_editorial_review.py -v
→ 21 passed, 0 failed, 0 skipped (admin/content null-options fix, F-12)
```

```
npx vitest run src/app/admin  (apps/web)
→ 10 test files, 65 passed, 0 failed
```

```
npx tsc --noEmit  (apps/web, full project)
→ clean, 0 errors
```

```
alembic downgrade -2 && alembic upgrade head  (apps/backend, local dev DB)
→ clean cycle: d4f5a6b7c8d9 -> c7d8e9f0a1b2 -> d2e3f4a5b6c7 (down), then back up to d4f5a6b7c8d9 (head). Single unambiguous head confirmed both times.
```

```
pytest tests/test_pyq_answer_review.py app/modules/cms/tests/test_content_bodies.py app/modules/commerce/ tests/test_commerce_and_language.py tests/test_admin_password_reset_and_mfa_gate.py tests/test_forgot_reset_password.py tests/test_mfa_recovery_csrf_alerts.py tests/test_editorial_review.py tests/test_content_factory_p5.py -v
→ 114 passed, 0 failed, 0 skipped — combined run across every module touched by concurrent agents this session, confirms zero cross-agent regression
```

```
bandit app/modules/cms/ app/modules/commerce/ app/modules/identity/ -r -f json
→ 1222 Low (expected, mostly B101 assert-in-tests), 1 Medium (B108, apps/backend/app/modules/cms/tests/test_mcq_p2_3_pre_human_audit.py:212 — confirmed pre-existing via `git status`, not touched by any session agent), 0 High
```

(Append new entries below this line in future sessions — do not edit entries above.)
