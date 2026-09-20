# Payments Readiness Audit — Phase 0 (Read-Only)

**Companion JSON:** `payments_readiness_audit.json` · **Date:** 2026-09-12  
**Do not create payment accounts or keys in this phase.**

## Overall

**PARTIALLY IMPLEMENTED** — Razorpay server order + client HMAC verify exist; production money path is **not** complete without webhooks/reconciliation.

| Capability | Status |
|------------|--------|
| Razorpay module | **IMPLEMENTED** (`apps/backend/app/modules/commerce/`) |
| Server-side order create | **IMPLEMENTED** |
| Fail-closed if keys missing | **IMPLEMENTED** (503) |
| Client verify signature | **IMPLEMENTED** (`verify_payment_signature`) |
| CSRF + rate limit on commerce | **IMPLEMENTED** |
| Stripe | **MISSING** |
| Webhook endpoint | **MISSING** |
| Idempotent webhook handling | **MISSING** |
| Refunds | **MISSING** |
| Automated reconciliation | **MISSING** |
| Subscription expiry jobs | **UNVERIFIED / thin** |

## Data that may be stored (expected)

Order/payment IDs, amounts, currency, status, gateway metadata — **not** PAN/CVV. Confirm schema does not persist card data (remediation task if any leak found).

## Required controls before live payments (design only)

1. Razorpay webhooks with signature verification  
2. Idempotent state machine (created → paid → failed → refunded)  
3. Entitlement grant only after verified paid state  
4. Duplicate webhook / replay protection  
5. Reconciliation against Razorpay settlements  
6. Audit trail of entitlement changes  
7. PCI scope minimization (hosted checkout only)

## Mandatory stop

No payment APIs called; no credentials created.
