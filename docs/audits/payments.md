# Payments (Razorpay) Audit Report

**Scope:** Checkout → order creation → payment verification → webhook →
transaction persistence → entitlement activation.

## Current status (2026-10-24)

Overall: **Partially verified.** Core verify-path implementation is sound and
well-tested. Webhook + reconciliation gap is now fixed in the working tree
(uncommitted). Production has a real, confirmed misconfiguration blocking
order creation today. **Sandbox/live E2E has never been attempted** — nothing
in this report should be read as proof the full user-facing lifecycle works
end to end against the real Razorpay API.

## Files involved

- `app/modules/commerce/api/commerce_router.py` — `POST /orders`, `POST /orders/{id}/verify`, `GET /status`, new `POST /webhooks/razorpay`
- `app/modules/commerce/services/commerce_service.py` — order/verify/webhook logic
- `app/modules/commerce/gateway/razorpay_client.py` — Razorpay HTTP client, checkout-signature verification, new webhook-signature verification
- `app/modules/commerce/models/order.py`, new `models/webhook_event.py`
- `app/modules/commerce/repositories/order_repository.py`
- `alembic/versions/b6accd4cd83f_commerce_module_orders.py` (existing), new `c7d8e9f0a1b2_commerce_webhook_events.py`, new `d4f5a6b7c8d9_commerce_orders_razorpay_order_id_index.py`
- Tests: `tests/test_commerce_and_language.py`, `app/modules/commerce/tests/test_razorpay_signature.py`, new `app/modules/commerce/tests/test_razorpay_webhook.py`
- Frontend: `apps/web/src/features/commerce/api.ts`, `apps/web/src/components/go-premium-card.tsx`
- Docs: `docs/deploy/RUNBOOK.md` — "Razorpay webhook (H6)" section

## Lifecycle trace (Implemented, Independently verified by a second review pass)

1. **Order creation** (`commerce_service.py:~29-55`): amount is a hardcoded
   server-side constant (`PREMIUM_PRICE_INR = 499.00`) — never read from
   client input.
2. **Verification** (`commerce_service.py:~57-84`): HMAC-SHA256(`order_id|payment_id`,
   `key_secret`) via `hmac.compare_digest` — matches Razorpay's documented
   checkout-verification algorithm. Ownership check present (line ~62).
   Idempotent re-verify of an already-PAID order. Invalid signature → `FAILED`.
3. **Webhook** (new, `commerce_router.py`): signature check (`X-Razorpay-Signature`
   against `RAZORPAY_WEBHOOK_SECRET`, computed over the **raw** request body,
   captured via `await request.body()` before any JSON parse) is the FIRST
   gate — confirmed by a second, independent review pass reading the actual
   route code line-by-line, not trusting the implementer's own summary.
   Dedup: `commerce.webhook_events` unique `provider_event_id` (sourced from
   the `x-razorpay-event-id` header, confirmed against Razorpay's real docs),
   written via `INSERT ... ON CONFLICT DO NOTHING` — race-safe, not
   rollback-based. Dedup insert + order state transition happen in **one**
   commit (`commerce_service.py:~112-134`).
4. **Entitlement**: `OrderRepository.has_paid_order` — any `status == "PAID"`
   order for the user. Confirmed this flips true via the webhook path alone
   (no `/verify` call needed) — this is the core reconciliation guarantee,
   proven by test `test_webhook_driven_paid_order_activates_entitlement`.

## F-01 — Production missing `RAZORPAY_KEY_ID` (Production-verified, Open)

Confirmed via `railway variables --service ai-neet-exam-app --kv | cut -d'=' -f1`
(names only, no values printed, no values ever will be) on 2026-10-22/23:
`RAZORPAY_KEY_SECRET` present, `RAZORPAY_KEY_ID` **absent**. `create_razorpay_order`
requires both — order creation currently fails with 503 `PAYMENT_GATEWAY_NOT_CONFIGURED`
in production right now. **This is independent of the webhook work below** —
it blocks the pre-existing checkout flow regardless of anything else in this report.

**Remediation (not executed — requires the user's own Razorpay dashboard value):**
```
railway variables --service ai-neet-exam-app --set "RAZORPAY_KEY_ID=<value from your Razorpay dashboard>"
```
I cannot and should not see or transmit the actual key value — retrieve it
from your own Razorpay dashboard and run this yourself, or authorize me to
run it with the value supplied through a channel outside this transcript.

## F-02 — No webhook existed (Implemented, Tested — uncommitted)

See lifecycle trace above. Before this session: zero webhook code existed;
a client that never completed `/verify` left the order `CREATED` forever with
no recovery path. Now fixed, pending the approvals below before it's live.

## F-08 — Missing tests (Fixed)

A second, independent review pass (not the implementing agent) added:
- `test_verify_rejects_order_belonging_to_another_user` — real second FK-valid
  user, confirms 404 and the order left untouched.
- `test_webhook_driven_paid_order_activates_entitlement` — proves entitlement
  activation via the webhook path alone.

## F-10 — Missing index (Fixed)

`commerce.orders.razorpay_order_id` had no index — every webhook delivery was
a full table scan. Fixed via migration `d4f5a6b7c8d9` (parent `c7d8e9f0a1b2`),
mirrored on the ORM model. Verified locally: `alembic upgrade head` →
`downgrade -1` → `upgrade head` cycle, single unambiguous head
(`alembic heads` → one result) both times.

## Test results (re-run by the independent review pass, not just trusted)

```
pytest app/modules/commerce/ tests/test_commerce_and_language.py -v
→ 18 passed, 0 failed, 0 skipped
```
```
bandit app/modules/commerce/ -r
→ 39 Low (all B101 assert-in-tests, expected in pytest files), 0 Medium, 0 High
```

## Readiness summary

| Area | Status |
|---|---|
| Implementation | Verify-path: complete. Webhook: complete (uncommitted). |
| Automated tests | 18/18 passing, including the previously-missing ownership and webhook-entitlement cases |
| **Sandbox E2E** | **Not attempted.** No live/sandbox Razorpay call has been made in any audit this session. Nothing above proves the real integration works against Razorpay's actual API. |
| Production configuration | `RAZORPAY_KEY_ID` confirmed absent (names-only check); `RAZORPAY_WEBHOOK_SECRET` not yet set anywhere |
| Merchant/settlement | Cannot verify from code or read-only access |

## Required approvals (none taken)

1. Set `RAZORPAY_KEY_ID` in Railway (user supplies the value from their own dashboard).
2. Set `RAZORPAY_WEBHOOK_SECRET` in Railway + configure the real webhook URL (`https://api.neet.trinetralab.net/api/v1/commerce/webhooks/razorpay`) in Razorpay's dashboard.
3. Run `alembic upgrade head` against production (2 pending migrations: `c7d8e9f0a1b2`, `d4f5a6b7c8d9`) — take a fresh backup first (see `admin-security.md`'s backup note; the one taken 2026-10-22 will be STALE by the time this runs).
4. Commit and review the uncommitted commerce-module working-tree changes.
5. Only after 1-4: attempt an actual Razorpay sandbox/test-mode transaction to get real E2E evidence — this report must not be cited as E2E proof until that happens.
