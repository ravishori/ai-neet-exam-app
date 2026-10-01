# WhatsApp M1 — Production Verification

**Baseline commit:** `dc5cf2791a433ee39984966cfd340d442abcef55`
**Verification date:** 2026-10-01

This document records the real, end-to-end production verification of the
WhatsApp M1 inbound webhook pipeline, performed against a live Twilio
WhatsApp message (not a simulated/local test).

## What was verified

A genuine inbound WhatsApp message was sent from an authorized test phone
to the production Twilio WhatsApp sender, and the full pipeline — Twilio
delivery, production webhook receipt, signature validation, identity and
message persistence, and the TwiML response — was confirmed directly
against Twilio's own API, Railway's production logs, and the production
database.

| Item | Value |
|---|---|
| Test message body | `INBOUND-PROD-TEST-20261001` |
| Twilio Message SID | `SM4d3056e80bf717404054185ecc0d7a2e` |
| Direction | `inbound` |
| From | `whatsapp:+919987671916` |
| To | `whatsapp:+18655188663` |
| Webhook HTTP response | `200` |
| Twilio signature validation | PASS |
| `whatsapp.identities` persistence | PASS |
| `whatsapp.messages` persistence | PASS |
| Application exception | NONE |
| Twilio error 12300 ("Invalid Content-Type") | NONE |
| Webhook response | `text/xml`, empty TwiML (`<?xml version="1.0" encoding="UTF-8"?><Response></Response>`) |
| Automatic reply | Intentionally NOT implemented in M1 — none expected, none sent |

### Scope of this verification

This confirms the **M1 inbound webhook pipeline only**:

- Twilio → production webhook (`POST /api/v1/whatsapp/webhook`) transport
- Twilio request-signature validation (F-01 fix, reverse-proxy-aware)
- Canonical inbound message parsing
- Identity resolution/persistence (`whatsapp.identities`)
- Message persistence with idempotency (`whatsapp.messages`,
  `UNIQUE(provider, provider_message_id)`)
- The webhook's TwiML/XML response format (resolves Twilio error 12300)

### Explicitly out of scope / unverified by this document

The following are **not** covered by this verification and have no
production evidence of working, because M1 does not implement them:

- Automatic/outbound replies to inbound messages
- `whatsapp.study_sessions` creation from the inbound webhook path
- Any outbound orchestration (quiz, tutor, assessment, revision, or other
  student-facing WhatsApp workflows)
- Delivery/status callbacks (no status-callback endpoint exists in the
  repository — confirmed `STATUS_CALLBACK_IMPLEMENTATION = NOT_IMPLEMENTED`
  during the production audit that preceded this verification)

## Baseline Freeze

This document freezes the verified-working state of the WhatsApp M1
inbound pipeline at commit `dc5cf2791a433ee39984966cfd340d442abcef55`.

Any future change to this pipeline — the webhook route, signature
validation, identity/message persistence, the provider adapter, or the
response format — requires a new implementation, regression test, and
production verification cycle before being considered production-ready
again. This document's PASS results apply only to the exact commit above;
they do not carry forward automatically to later changes.
