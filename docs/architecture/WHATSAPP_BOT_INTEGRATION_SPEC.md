# Trinetra NEET WhatsApp Bot — Integration Specification

Status: DRAFT FOR IMPLEMENTATION
Date: 2026-09-30
Provider decision: see
[ADR-WHATSAPP-PROVIDER-ABSTRACTION.md](../decisions/ADR-WHATSAPP-PROVIDER-ABSTRACTION.md)

This document is split into three layers, matching the codebase's own
`providers/base.py` (canonical) vs `providers/twilio/` (Twilio-specific)
split (see `WHATSAPP_BOT_ARCHITECTURE.md` §4). Read §1 first regardless of
which provider you're integrating; read §2 only if you're working inside
the Twilio adapter specifically.

---

## PART 1 — Canonical Application Contract (provider-independent)

This part describes what the `whatsapp` module guarantees regardless of
which provider is configured. Nothing here changes when the provider
changes.

### 1.1 Provider Interface

`apps/backend/app/modules/whatsapp/providers/base.py` defines the
contract every provider adapter implements:

- `send_text(to: str, body: str) -> ProviderSendResult` — send a text
  message; returns a provider-agnostic result (success/failure, the
  provider's own message id captured as `provider_message_id`, not a
  provider-specific field name).
- `parse_inbound(raw_request) -> CanonicalInboundMessage` — turn a
  validated provider-specific webhook payload into the canonical
  internal message shape below. All provider-specific field names and
  payload quirks are resolved here.
- `validate_webhook(raw_request) -> bool` — authenticate that an inbound
  webhook call genuinely came from the configured provider. The
  signature is identical across providers; the implementation is not.

### 1.2 Canonical Inbound Message Model

Provider-neutral fields the rest of the application actually consumes
(`schemas/webhook.py`):

- `provider` — which provider delivered this (`"twilio"` today).
- `provider_message_id` — the provider's own message identifier, stored
  generically (never a column/field literally named after a specific
  provider).
- `external_user_id` — the provider's identifier for the WhatsApp user,
  if the provider exposes one distinct from the phone number.
- `phone_e164` — the WhatsApp phone number. Provider-independent.
- `direction`, `message_type`, `text`, `provider_timestamp`.

Domain services, the orchestrator, and persistence operate exclusively on
this canonical shape. See `WHATSAPP_BOT_ARCHITECTURE.md` §5 for the
corresponding provider-neutral database columns.

### 1.3 Public Webhook Route

Stable regardless of provider:
```
GET  /api/v1/whatsapp/webhook
POST /api/v1/whatsapp/webhook
```

**GET** — used by providers that require a verification handshake before
activating a webhook (Meta's `hub.mode`/`hub.verify_token`/`hub.challenge`
pattern is the canonical example; Twilio's webhook configuration does not
require this handshake, so under Twilio the GET method exists for
contract stability and provider portability but is not exercised as part
of Twilio's own activation flow). Whether GET verification does anything
meaningful is provider-defined behavior inside the adapter, not an
application-layer assumption.

**POST** — the request flow, entirely provider-independent from step 2
onward:
1. Provider adapter's `validate_webhook(raw_request)` authenticates the
   request using the raw request (never a re-serialized/re-parsed
   version — see §1.4).
2. Provider adapter's `parse_inbound(raw_request)` produces a
   `CanonicalInboundMessage`.
3. Idempotency check on `(provider, provider_message_id)`.
4. Identity resolution (`whatsapp.identities`, keyed by `(provider,
   external_user_id)` or `phone_e164`).
5. Intent resolution.
6. Delegation to the existing Trinetra service the intent maps to.
7. Persist the processing result.
8. Send a response via the provider adapter's `send_text`.

### 1.4 Authenticity Validation Principle

Every provider adapter's `validate_webhook` must validate against the
**exact raw inbound request** (raw body and/or raw form-encoded
parameters and URL, per that provider's own documented scheme) — never
against a value re-serialized from an already-parsed payload. This
principle is provider-independent even though the concrete mechanism
(HMAC algorithm, what's signed, which header) is provider-specific. An
unauthenticated request must never reach step 2 above.

### 1.5 Idempotency

`(provider, provider_message_id)` must be unique at the database level
(`whatsapp.messages`). A redelivered event for an already-processed
`(provider, provider_message_id)` pair must not re-execute the learning
action, create a duplicate message row, or create a duplicate study
session, regardless of which provider redelivered it or why.

### 1.6 Identity

External identity is `(provider, external_user_id)` and/or `phone_e164`.
Internal identity is the existing `identity.users.id`.

**Never auto-link** a WhatsApp identity to an existing Trinetra account
solely because a phone number matches, regardless of provider. Linking
flow (§1.7) is identical regardless of which provider carried the LINK
request.

### 1.7 Account Linking

1. Student requests LINK (via whichever provider delivered the message).
2. Backend generates a cryptographically secure one-time code.
3. Store code in Redis with short expiry.
4. Student authenticates to the Trinetra web account.
5. Student submits the code.
6. Validate the code.
7. Link the WhatsApp identity (`(provider, external_user_id)` /
   `phone_e164`) to `identity.users.id`.
8. Invalidate the code.
9. Send confirmation via the provider adapter.

Support expiry, one-time use, invalid code, already-linked identity,
unlink, and blocked state — all provider-independent.

### 1.8 Intent Mapping

Minimum, provider-independent:
`HI, HELP, LINK, QUIZ, QUIZ_ANSWER, FLASHCARDS, REVISION, PROGRESS,
RECOMMEND, STUDY_PLAN, TUTOR`.

Unknown input → controlled help/menu response.

### 1.9 Quiz / Flashcard / Revision / Progress / Tutor Flows

Identical to the original spec, entirely provider-independent — the
provider only carries the text in and the text out:

- **Quiz**: `QUIZ -> existing AssessmentService -> existing attempt ->
  question -> A/B/C/D -> existing answer/scoring -> existing mastery
  update -> explanation -> next question.` No WhatsApp-specific
  attempt/answer records, and no provider-specific ones either.
- **Flashcards**: existing published/certified flashcard content.
- **Revision**: existing mastery/revision/recommendation services.
- **Progress**: existing student progress/assessment/mastery data.
- **Tutor**: `WhatsApp -> WhatsAppOrchestrator -> TutorService ->
  KnowledgeService -> AIGateway -> configured AI provider -> WhatsApp`
  (the AI provider here is an unrelated concept from the WhatsApp
  messaging provider — see `WHATSAPP_BOT_ARCHITECTURE.md` §9).

### 1.10 Message Types

MVP: text only. Future: interactive buttons, lists, templates, images,
documents, audio — whichever of these a given provider actually supports
is that provider's own adapter's concern; the canonical model does not
assume a specific provider's capability set.

### 1.11 Conversation Window

Design around WhatsApp's own message-category and customer-service-window
rules (these are WhatsApp Business Platform policy, not provider-specific
— they apply whether the message transits through Twilio or Meta
directly). Do not assume arbitrary outbound messages outside the service
window. Proactive notifications are future functionality requiring
appropriate template/consent handling.

### 1.12 Rate Limiting & Cost Control

Use existing Redis. Rate-limit inbound messages, account linking
attempts, and expensive AI requests — provider-independent, since the
canonical model is what's being rate-limited, not provider-specific
payloads.

Do not call AI for deterministic operations. All AI requests use the
existing AIGateway for centralized cost/token/latency accounting.

### 1.13 Failure Behaviour

MVP fallback, regardless of provider or failure cause:
> "Sorry, I couldn't complete that request right now. Please try again."

Never expose stack traces, SQL errors, provider credentials (Twilio auth
token or any future provider's equivalent), or internal details.

### 1.14 Configuration Principle

WhatsApp provider pricing and policy are external business rules
regardless of provider. Do not hard-code current pricing into application
logic — Twilio publishes its own WhatsApp handling fee in addition to
Meta's underlying conversation-based pricing; both are subject to change
independently of this codebase.

`WHATSAPP_PROVIDER` selects the active adapter. Provider-specific
credentials are namespaced per provider (Twilio's under `TWILIO_*`) so
adding a future provider's config never requires touching Twilio's.

### 1.15 Source of Truth

The configured messaging provider (Twilio today) is the communication
transport only. Trinetra remains the source of truth for users,
questions, assessments, attempts, answers, mastery, recommendations,
flashcards, and AI routing — unaffected by which provider is configured.

---

## PART 2 — Provider Adapter Contract (Twilio-specific)

This part is specific to the Twilio adapter
(`apps/backend/app/modules/whatsapp/providers/twilio/`). A future Meta or
other-provider adapter would have its own equivalent §2, not this one.

### 2.1 Provider

Twilio WhatsApp (Twilio Programmable Messaging for WhatsApp).
Integration: Twilio's REST API for outbound sends, Twilio webhook for
inbound messages.

### 2.2 Twilio-Specific Environment Variables

```
WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_FROM        # the Twilio WhatsApp-enabled sender number, E.164
```

These live alongside — not instead of — a provider-neutral
`WHATSAPP_PROVIDER` selector. A future provider adds its own
similarly-namespaced variables without touching these. Secrets follow the
existing project secret/config conventions (`app/core/config.py`'s
established `str = ""`-default, never-hard-coded, never-logged pattern —
see `twilio_account_sid`/`twilio_auth_token` already present there for
the mobile-OTP integration, which this WhatsApp integration's Twilio
adapter is a sibling of, not a duplicate — confirm at implementation time
whether the existing `twilio_account_sid`/`twilio_auth_token` fields can
be reused directly if this is the same Twilio account/credentials, or
whether WhatsApp needs its own distinct Twilio subaccount credentials).

### 2.3 Twilio Webhook Request Validation

Twilio signs each webhook request with `X-Twilio-Signature`, computed as
an HMAC-SHA1 over the full request URL concatenated with its sorted
POST parameters, keyed with `TWILIO_AUTH_TOKEN`. Validate using Twilio's
own published request-validation algorithm (implemented by Twilio's
official SDK as `RequestValidator`, or an equivalent constant-time
reimplementation) — never construct this validation from a re-serialized
or re-encoded version of the payload; validate against the exact raw
inbound request data, per the canonical principle in §1.4.

Invalid or missing signatures must be rejected before step 2 of the flow
in §1.3 — the parsed payload must never be trusted first and validated
second.

### 2.4 Twilio Inbound Webhook Shape

Twilio delivers inbound WhatsApp messages as `application/x-www-form-
urlencoded` POST parameters (not JSON), including at minimum a message
SID, the sender's WhatsApp-prefixed number (`whatsapp:+91XXXXXXXXXX`
form), the destination number, and the message body. The Twilio adapter's
`parse_inbound` is responsible for:
- Stripping the `whatsapp:` prefix to produce a bare `phone_e164`.
- Mapping Twilio's message SID to the canonical `provider_message_id`.
- Producing a `CanonicalInboundMessage` (§1.2) with `provider="twilio"`.

No Twilio-specific field name (message SID's own field name, the
`whatsapp:`-prefixed form, Twilio's delivery-status callback field
names) may leak past this adapter into `services/`, `repositories/`, or
`models/`.

### 2.5 Twilio Outbound Send

`providers/twilio/client.py` wraps Twilio's REST API (via Twilio's
official SDK or a direct authenticated HTTPS call) to send a WhatsApp
text message from `TWILIO_WHATSAPP_FROM` to the target `phone_e164`
(re-adding the `whatsapp:` prefix Twilio's API requires, entirely inside
this adapter). Returns a `ProviderSendResult` (§1.1) — callers outside
the adapter never see Twilio's own response shape.

### 2.6 Twilio Error Handling

Twilio API errors (4xx client errors, 5xx provider errors, network
timeouts) are caught inside `providers/twilio/client.py` and translated
to the same structured, provider-agnostic error shape
`whatsapp_sender.py` (§1, canonical layer) expects from any provider —
callers of `send_text` never need to know they're specifically handling
a Twilio error versus a future provider's error.

### 2.7 Message Types Twilio Supports (MVP scope)

MVP: text only, per §1.10. Twilio also supports WhatsApp templates,
media messages, and interactive content — none are implemented in this
MVP regardless of Twilio's own capability, per the product scope
exclusions in `WHATSAPP_BOT_PRD.md`.

---

## Future Providers

Adding a second provider (e.g. Meta Cloud API) means writing a new
`providers/meta/` package satisfying Part 1's `base.py` contract and
writing that provider's own "Part 2"-equivalent document — it does not
mean rewriting this document's Part 1, and it does not mean touching
`services/`, `repositories/`, `models/`, or the orchestrator. See
`ADR-WHATSAPP-PROVIDER-ABSTRACTION.md`'s "Migration strategy to another
provider" section for the full checklist.
