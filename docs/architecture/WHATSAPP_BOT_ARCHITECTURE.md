# Trinetra NEET WhatsApp Bot — Architecture

Status: DRAFT FOR IMPLEMENTATION
Date: 2026-09-30

## 1. Architecture Decision
Use the official Meta WhatsApp Business Platform Cloud API directly.

Do not introduce Twilio, Gupshup, 360dialog or another WhatsApp BSP for the MVP.

## 2. System Flow
Student WhatsApp
  -> Meta WhatsApp Cloud API
  -> FastAPI HTTPS Webhook
  -> signature validation
  -> idempotency
  -> WhatsApp identity resolution
  -> WhatsAppOrchestrator
  -> existing learning services
  -> existing AIGateway when AI is required
  -> WhatsApp response

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

No duplicate learning engine.

## 4. New Module
apps/backend/app/modules/whatsapp/

    api/
        whatsapp_webhook_router.py
    services/
        whatsapp_webhook_service.py
        whatsapp_sender.py
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
        webhook.py
    tests/

## 5. New Database Tables
Maximum: 3.

### whatsapp.identities
Map external WhatsApp identity to Trinetra user.

Concepts:
id, user_id, wa_user_id, phone_e164, status, consent_at, language,
last_seen_at, created_at, updated_at.

Unique:
user_id, wa_user_id, phone_e164.

### whatsapp.messages
Persist inbound/outbound message metadata and support idempotency.

Concepts:
id, whatsapp_identity_id, wa_message_id, direction, message_type, text,
intent, provider_timestamp, processing_status, error_code, created_at.

Required:
UNIQUE(wa_message_id).

### whatsapp.study_sessions
Maintain short-lived WhatsApp learning state.

Concepts:
id, whatsapp_identity_id, session_type, status, assessment_id, attempt_id,
current_question_id, current_position, context_json, started_at,
expires_at, completed_at.

## 6. Do NOT Create
- whatsapp_questions
- whatsapp_attempts
- whatsapp_answers
- whatsapp_mastery
- whatsapp_recommendations
- whatsapp_flashcards
- duplicate AI provider clients
- duplicate assessment engine

## 7. Public Routes
Only:
GET /api/v1/whatsapp/webhook
POST /api/v1/whatsapp/webhook

GET = Meta webhook verification.
POST = inbound WhatsApp events.

## 8. Redis
Use existing Redis for:
- rate limiting
- one-time linking codes
- temporary state
- idempotency locks
- session expiry
- abuse/cost protection

PostgreSQL remains durable source of truth.

## 9. AI Rules
All AI calls go through existing AIGateway.

Never instantiate a separate AI provider client in the WhatsApp module.

Prefer deterministic processing for commands, quiz answers, navigation,
progress retrieval and flashcards.

## 10. Security Baseline
MVP must include:
- HTTPS
- Meta webhook verification
- X-Hub-Signature-256 validation
- raw-body signature verification
- secret redaction
- account authorization
- Redis rate limiting
- webhook idempotency

## 11. Data Principle
WhatsApp is an integration layer.
Academic truth remains in existing Trinetra schemas.

## 12. Future Channels
Web, WhatsApp and future mobile clients should consume the same learning
services/API contracts. WhatsApp must not own learning logic.
