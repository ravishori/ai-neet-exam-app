# ADR-0018: Sprint 9 scope — Commerce, Admin, Hardening, Deploy

## Status
Accepted

## Context
SP9 bundles four different areas into one final sprint — deliberately,
per the roadmap's own grouping, this is the wrap-up sprint that closes
the originally-scoped 9-sprint roadmap, not four separate feature
sprints. Each area gets a tight, concrete scope below rather than being
built out to BRD-enterprise depth.

## 1. Commerce (Razorpay) — ADR-0006 follow-through

**One-time purchase only. No subscriptions, no recurring billing.** A
single fixed-price "Premium" purchase per ADR-0006 (Razorpay directly,
no gateway abstraction). Recurring billing (cycles, dunning, plan
upgrades/downgrades) is real subscription-commerce complexity — BRD
scope, not this sprint's.

**No fake-payment fallback — this is the one place in the whole
project that deliberately breaks the pattern ADR-0014 established for
AI.** The AI Gateway simulates a response when no API key is
configured because text generation is safe to fake and clearly labeled
as such. Payment is different: simulating a "payment succeeded"
response, even labeled as dev-mode, teaches the codebase (and anyone
reading it) that a fake success path exists in a financial flow. That
risk isn't worth the convenience. Without `RAZORPAY_KEY_ID` /
`RAZORPAY_KEY_SECRET` configured, order creation returns a clear
`PAYMENT_GATEWAY_NOT_CONFIGURED` error — no order is created, nothing
is marked paid, and the frontend shows an honest "payment isn't
configured yet" notice instead of a broken checkout button.

**What ships and how it's verified without live credentials:**
- `commerce.orders` (id, user_id, amount_inr, status:
  CREATED/PAID/FAILED, razorpay_order_id, razorpay_payment_id,
  razorpay_signature, created_at) in the schema ADR-0001 already
  reserved for this. This table is the sole source of truth for premium
  status — no `is_premium` flag duplicated onto `identity.users`.
  Whether a user is premium is "does a PAID order exist for this
  user_id", computed live (same reasoning as ADR-0015/0017: don't
  duplicate state that's cheap to derive), and it keeps the write
  boundary clean — the `commerce` module never writes into `identity`'s
  table, it only owns its own.
- `RazorpayProvider` wraps the real `razorpay` SDK (`orders.create`,
  and signature verification via HMAC-SHA256 exactly as Razorpay's
  webhook docs specify) — real integration code, not a stub.
- Signature verification is a pure function
  (`verify_payment_signature(order_id, payment_id, signature, secret)`)
  independent of any network call, so it's fully unit-testable with a
  fixture secret and a signature computed the same way Razorpay
  computes it — this proves the verification logic is correct without
  needing live credentials or a real payment.
- `POST /api/v1/commerce/orders` (create), `POST
  /api/v1/commerce/orders/{id}/verify` (verify signature, mark PAID),
  and `GET /api/v1/commerce/status` (does the caller have a PAID
  order).
- End-to-end verification in this sprint covers: (a) order creation
  correctly refuses when no key is configured — the guard rail itself
  is the thing being proven, not a payment; (b) the signature-
  verification unit tests; (c) a service-level test that a validly-
  signed payload marks the order PAID and `GET /status` reflects it.
  Verifying an actual Razorpay checkout redirect requires a real
  test-mode key pair, which isn't available in this environment —
  that's a follow-up once a key is added, same caveat ADR-0014 already
  carries for real Claude calls.

**No feature is paywalled behind premium status in this sprint.** The
point of this sprint's commerce work is a working payment rail, not a
paywall product decision — deciding what's free vs. premium is a
business call for the user to make once the payment plumbing exists,
not something to bake in silently as a side effect of building the
plumbing.

## 2. Admin — user role/status management

`/admin/users` (built in Sprint 1) has been read-only this whole time —
it lists users and their roles but has no way to change either. The
backend has the same gap: `UserUpdateRequest` (used by both the
self-service `/users/me` and the admin `/users/{id}` PATCH) only
covers profile fields, not `status` or `role_codes`.

**Fix**: a separate `AdminUserUpdateRequest` schema (status + optional
role_codes list) used only by the already-`users.manage`-gated
`PATCH /users/{id}` route — `/users/me` keeps the narrower
self-service schema so a user can never grant themselves roles or
reactivate their own suspended account through the self-service path.
`RoleRepository.replace_roles(user_id, role_codes)` does a full
diff-and-sync (add missing, remove extra) in one call. `status` reuses
the `active`/anything-else convention `get_current_user` already
enforces (`dependencies.py:41`) — no new status enum, no migration
needed.

Frontend: `/admin/users` gets a role multi-select and a status toggle
per row, calling the extended PATCH endpoint. Nothing else about user
management (bulk actions, audit log of admin changes, impersonation)
is in scope.

**Bug found while verifying this**: `AuthService.authenticate()`
checked `locked_until` (brute-force lockout) but never checked
`status` — a suspended user could still log in and get a fresh token,
only getting blocked on their *next* request via `get_current_user`.
Fixed by rejecting login for any non-`active` status with
`ACCOUNT_SUSPENDED`, checked in the same place as the existing
`locked_until` check (before password verification, matching that
existing precedent).

## 3. Hardening

Two concrete, verifiable items, not a general security audit:

- **Rate limiting** on `/auth/login`, `/auth/register`, `/auth/refresh`
  — a fixed-window counter in Redis (already a dependency, already
  connected in `main.py`), keyed on client IP + path. No new
  dependency (considered `slowapi`; a ~15-line Redis `INCR`+`EXPIRE`
  does the same job for three routes without adding a library).
- **Security headers** middleware: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy` disabling camera/mic/geolocation (nothing in
  this app needs them). Applied to every response next to the existing
  `RequestContextMiddleware`.

Anything broader (dependency vulnerability scanning, pen-testing,
secrets-rotation tooling, WAF) is ops/process work outside a single
sprint of application code.

## 4. Deploy

SP0 already produced dev-parity Dockerfiles and
`infrastructure/docker/docker-compose.yml` (bind mounts, `--reload`,
baked-in dev credentials). This sprint adds what's missing for an
actual Coolify/Hetzner deployment per ADR-0006:

- `infrastructure/docker/docker-compose.prod.yml` — no bind mounts, no
  `--reload`, `restart: unless-stopped`, credentials from environment
  only (no baked-in defaults).
- Backend Dockerfile: run as a non-root user (currently runs as root).
- `docs/deploy/RUNBOOK.md` — required environment variables (with
  which ones must be real secrets vs. safe defaults), the Alembic
  migration step, and what "done" looks like post-deploy (`/health`,
  `/ready`).

No actual deployment happens in this sprint — there's no live
Hetzner VPS or Coolify instance reachable from this environment. This
produces the artifacts a real deploy would use; running them against a
real server is a follow-up outside this sandbox, exactly like the
"real Claude" and "real Razorpay" caveats above.

## Consequences
Commerce ships as working, honest infrastructure with an explicit gap
(no live-credential verification) rather than a simulated demo. Admin
gets the one capability that was actually missing rather than a full
admin-console rebuild. Hardening is two targeted defenses, not a
audit. Deploy produces real artifacts without pretending a deployment
happened that didn't.
