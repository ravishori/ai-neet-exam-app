# Trinetra NEET WhatsApp Bot — Architecture

Status: DRAFT FOR IMPLEMENTATION
Date: 2026-09-30
Provider decision: see
[ADR-WHATSAPP-PROVIDER-ABSTRACTION.md](../decisions/ADR-WHATSAPP-PROVIDER-ABSTRACTION.md)
(supersedes [ADR-WHATSAPP-CLOUD-API.md](../decisions/ADR-WHATSAPP-CLOUD-API.md))

## 1. Architecture Decision

WhatsApp integration is built behind a **provider adapter boundary**.
**Twilio WhatsApp is the initial provider.** The core/domain architecture
is provider-agnostic: a future provider (Meta Cloud API, 360dialog,
Gupshup, or another BSP) is added as a new adapter implementing the same
interface, with zero changes to domain services, the database schema, or
the NEET orchestrator. See the ADR above for the full rationale and
migration strategy.

## 2. System Flow

```
Student WhatsApp
  -> Twilio WhatsApp (initial provider)
  -> Provider Adapter (providers/twilio/)
  -> signature/request validation (provider-specific)
  -> Canonical WhatsApp Message/Webhook Model (provider-neutral)
  -> idempotency
  -> WhatsApp identity resolution
  -> WhatsApp Domain Services
  -> NEET Orchestrator (WhatsAppOrchestrator)
  -> existing learning services (Assessment/Tutor/Flashcards/Revision/
     Progress/Mastery)
  -> existing AIGateway when AI is required
  -> Provider Adapter (outbound send)
  -> WhatsApp response
```

The **Provider Adapter** step is the only layer that changes if the
provider changes. Everything below "Canonical WhatsApp Message/Webhook
Model" in this flow is identical regardless of which provider delivered
the message.

## 3. Existing Infrastructure

- Python
- FastAPI
- SQLAlchemy 2.x async
- Alembic
- PostgreSQL
- Redis
- identity/users
- assessment
- tutor
- knowledge
- mastery
- recommendations
- flashcards/CMS
- study planner
- AI Gateway

No duplicate learning engine. No duplicate AI provider client.

## 4. New Module

```
apps/backend/app/modules/whatsapp/

    api/
        whatsapp_webhook_router.py     # stable GET/POST route, provider-independent

    providers/
        base.py                        # Provider interface: send_text,
                                        # parse_inbound, validate_webhook
        twilio/
            client.py                  # Twilio SDK usage, outbound send
            webhook.py                 # Twilio request-signature validation
            schemas.py                 # Twilio-specific webhook payload shapes

    services/
        whatsapp_webhook_service.py    # orchestrates: validate -> parse ->
                                        # idempotency -> persist -> delegate
        whatsapp_sender.py             # calls the configured provider adapter's
                                        # send_text — no provider SDK usage here
        whatsapp_identity_service.py
        whatsapp_orchestrator.py
        whatsapp_intent_service.py
        whatsapp_message_service.py

    repositories/
        whatsapp_repository.py

    models/
        whatsapp_identity.py
        whatsapp_message.py
        whatsapp_study_session.py

    schemas/
        webhook.py                     # canonical (provider-neutral) inbound/
                                        # outbound message shapes

    tests/
```

**Layering rule**: only `providers/<name>/` may import or reference a
provider's SDK, webhook payload shape, or provider-specific header names.
`services/`, `repositories/`, `models/`, and `api/` depend only on
`providers/base.py`'s interface and the canonical schemas in `schemas/`.

## 5. New Database Tables

Maximum: 3. All columns are **provider-neutral** — no table or column is
named after a Twilio-specific or Meta-specific concept.

### whatsapp.identities
Map an external WhatsApp identity (via whichever provider delivered it)
to a Trinetra user.

Concepts:
`id, user_id, provider, external_user_id, phone_e164, status, consent_at,
language, last_seen_at, created_at, updated_at`.

- `provider` — discriminator (`"twilio"` today), never hard-coded
  elsewhere as an assumption.
- `external_user_id` — the provider's own identifier for the WhatsApp
  user, where the provider exposes one distinct from the phone number.
  Nullable — not every provider necessarily has a concept distinct from
  the phone number itself.
- `phone_e164` — the actual WhatsApp number. Provider-independent (a
  phone number is a channel fact, not a provider concept), so this is
  the one identity field that survives a provider switch unchanged.

Unique: `(provider, external_user_id)` where `external_user_id` is set;
`phone_e164`.

### whatsapp.messages
Persist inbound/outbound message metadata and support idempotency,
regardless of provider.

Concepts:
`id, whatsapp_identity_id, provider, provider_message_id, direction,
message_type, text, intent, provider_timestamp, processing_status,
error_code, created_at`.

- `provider` — which provider delivered/sent this message.
- `provider_message_id` — the provider's own message identifier (Twilio:
  `MessageSid`; stored generically, never as a column literally named
  after Twilio or Meta).

Required:
`UNIQUE(provider, provider_message_id)` — durable idempotency guarantee,
independent of which provider redelivers.

### whatsapp.study_sessions
Maintain short-lived WhatsApp learning state. Already provider-neutral —
a study session belongs to a `whatsapp_identity`, not to a provider
directly.

Concepts:
`id, whatsapp_identity_id, session_type, status, assessment_id,
attempt_id, current_question_id, current_position, context_json,
started_at, expires_at, completed_at`.

## 6. Do NOT Create

- whatsapp_questions
- whatsapp_attempts
- whatsapp_answers
- whatsapp_mastery
- whatsapp_recommendations
- whatsapp_flashcards
- duplicate AI provider clients
- duplicate assessment engine
- core tables or columns named after Twilio-specific concepts
  (`twilio_message_sid`, `MessageSid`, `SmsStatus`) or Meta-specific
  concepts (`wa_id`, `messaging_product`) — use `provider` /
  `provider_message_id` / `external_user_id` instead

## 7. Public Routes

Only, and unchanged regardless of provider:
```
GET  /api/v1/whatsapp/webhook
POST /api/v1/whatsapp/webhook
```

GET/POST semantics are defined at the canonical/application layer (see
Integration Spec §3 "Canonical Application Contract"). What each provider
requires to satisfy that contract (Twilio's request-validation scheme,
Meta's `hub.challenge` verification handshake if added later) is resolved
entirely inside that provider's adapter, never in the router itself.

## 8. Redis

Use existing Redis for:
- rate limiting
- one-time linking codes
- temporary state
- idempotency locks
- session expiry
- abuse/cost protection

PostgreSQL remains durable source of truth. None of this changes with
provider — it operates on the canonical model, not provider-specific data.

## 9. AI Rules

All AI calls go through existing AIGateway.

Never instantiate a separate AI provider client in the WhatsApp module.
(Note: "provider" here means an AI model provider — OpenAI/Gemini/etc. —
a distinct concept from the WhatsApp messaging provider, Twilio, covered
by this document. The two are unrelated and must not be conflated in code
or naming.)

Prefer deterministic processing for commands, quiz answers, navigation,
progress retrieval and flashcards.

## 10. Security Baseline

MVP must include:
- HTTPS
- inbound webhook authenticity validation (provider-specific mechanism,
  behind the adapter — Twilio: `X-Twilio-Signature` request validation)
- raw-request signature/validation, not re-serialized-JSON validation
- secret redaction (provider credentials, never logged)
- account authorization
- Redis rate limiting
- webhook idempotency

## 11. Data Principle

WhatsApp is an integration layer, and the messaging provider (Twilio
today) is itself just one interchangeable piece of that integration
layer. Academic truth remains in existing Trinetra schemas.

## 12. Future Channels

Web, WhatsApp and future mobile clients should consume the same learning
services/API contracts. WhatsApp must not own learning logic. Within
WhatsApp itself, no single messaging provider owns the integration logic
either — that's what the provider adapter boundary in §4 exists to
guarantee.
