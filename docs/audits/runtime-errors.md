# Runtime Errors Audit Report

**Scope:** Production bug reports for specific page/endpoint failures.

## F-12 — `/admin/content/{id}` generic error screen (Fixed locally — uncommitted, not production-verified)

**Reported:** production page
`https://neet.trinetralab.net/admin/content/7fb11a6b-9295-40e7-b85c-146c...`
shows a generic Next.js error boundary ("Something went wrong — We couldn't
load this page right now.") instead of the content-item detail view.

**Root cause (Independently reproduced locally, not just hypothesized):**
A QUESTION content item whose stored `content_versions.body["options"]` is
JSON `null` (rather than merely absent — e.g. from a legacy/bypassed
ingestion path that writes `body` directly without going through the
create-API's Pydantic validation) crashes the frontend. Python's
`dict.get(key, default)` only substitutes the default when the key is
**absent**; when the key exists with value `null`, it returns `None`
regardless of the default. So `editorial_review_service.py:861` (pre-fix)
serialized `question.options = None`, and
`apps/web/src/app/admin/content/[itemId]/page.tsx:185` (pre-fix) called
`question.options.map(...)` unconditionally, throwing
`TypeError: Cannot read properties of undefined (reading 'map')`.

**Reproduction method:** created a QUESTION item via the normal API, then
force-set `body["options"] = null` directly in the local dev DB (simulating
the malformed-ingestion case), hit `/review-packet`, confirmed the response
returned `options: null` pre-fix. On the frontend, confirmed (by temporarily
reverting the fix) that the component test threw the exact same `TypeError`
at the exact `question.options.map` line — matching the production symptom
precisely, not just a plausible guess.

**Fix (Implemented, Tested — uncommitted):**
- `app/modules/cms/services/editorial_review_service.py` — `body.get("options") or []` (coalesces a stored `null` the same as a missing key).
- `apps/web/src/app/admin/content/[itemId]/page.tsx` — `question.options ?? []` plus a "No options recorded for this item." message instead of crashing; also split the item-fetch error state into distinct 404 / 401-403 / generic-with-retry states (previously non-404 errors silently rendered nothing).
- New tests: `apps/backend/tests/test_editorial_review.py::test_review_packet_handles_question_with_null_options` (fails without the fix, passes with it); `apps/web/src/app/admin/content/[itemId]/page.test.tsx` (new file, 8 tests: loading/404/403/500-retry/normal/`options: null`/`options: undefined`/`options: []`).

**Test results (re-verified independently in this review pass, not just trusted from the implementing agent):**
```
pytest tests/test_content_factory_p5.py tests/test_batch_a_acquisition.py tests/test_batch_a_pilot.py tests/test_editorial_review.py -v
→ 21 passed, 0 failed, 0 skipped
```
```
npx vitest run src/app/admin
→ 10 test files, 65 tests, 65 passed, 0 failed
```
```
npx tsc --noEmit (apps/web, full project)
→ clean, 0 errors
```

**Related finding, also fixed in this review pass (same `dict.get(key, [])`
pattern found and hardened at 3 more call sites, confirmed via grep — not a
guess):**
- `app/modules/cms/api/cms_router.py:178` (`_question_summary`, student-facing browse view)
- `app/modules/cms/services/search_service.py:100` (`_to_public_result`, public search)
- `app/modules/cms/services/content_factory_human_review_service.py:457` (fully unguarded `body.get("options")`, no default at all)

All three changed to `body.get("options") or []`. **Coverage gap found and
reported, not fixed:** `search_service.py`'s `_to_public_result` has **no
existing test file at all** — grepped `tests/` and `app/modules/cms/tests/`
for any reference to `search_service`/`_to_public_result`, found none. The
other two are covered indirectly via `test_content_factory_p5.py`
(21/21 passing above, includes this file's code path).

**Status: Fixed and verified locally. NOT production-verified** — requires
deploy before the exact reported production URL can be re-checked. Per
`docs/audits/README.md`'s evidence-tier rule, do not cite this as
production-verified until that happens.

**Next steps for production verification (not done, requires deploy):**
1. Deploy both the backend and frontend fixes.
2. Visit the exact reported URL and confirm it renders (question+options, or "No options recorded for this item.") instead of the error boundary.
3. If it still fails, capture the `GET /content-items/{id}/review-packet` response body for that exact ID — would indicate a different null field, not this one.

**Scope boundary honored:** stayed within `apps/web/src/app/admin/content/`
and `app/modules/cms/`; did not touch `app/modules/identity/` or
`app/modules/commerce/` (confirmed via `git status` — those files carry only
the other concurrent audits' changes).
