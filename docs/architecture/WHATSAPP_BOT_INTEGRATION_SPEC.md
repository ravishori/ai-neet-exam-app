# Trinetra NEET WhatsApp Bot — Integration Specification

Status: DRAFT FOR IMPLEMENTATION
Date: 2026-09-30

## 1. Provider
Meta WhatsApp Business Platform Cloud API.
Integration: direct HTTPS API + webhook.
No Twilio/BSP dependency for MVP.

## 2. Environment Variables
WHATSAPP_ACCESS_TOKEN
WHATSAPP_BUSINESS_ACCOUNT_ID
WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_VERIFY_TOKEN
WHATSAPP_APP_SECRET
WHATSAPP_GRAPH_API_VERSION

Secrets must follow existing project secret/config conventions.

## 3. Webhook Verification
GET /api/v1/whatsapp/webhook

Expected:
- hub.mode
- hub.verify_token
- hub.challenge

Verify mode/token and return challenge on success.

## 4. Webhook Signature
POST /api/v1/whatsapp/webhook

Validate X-Hub-Signature-256 before trusting/processing the payload.

Use:
- raw request body
- WHATSAPP_APP_SECRET
- HMAC SHA-256
- constant-time comparison

Invalid signatures must not be processed.

## 5. Event Processing
Meta webhook
 -> signature validation
 -> event parsing
 -> message ID extraction
 -> idempotency check
 -> identity resolution
 -> intent resolution
 -> existing Trinetra service
 -> persist processing result
 -> send WhatsApp response

## 6. Idempotency
wa_message_id must be unique.
Already terminally processed events must not execute the learning action again.

## 7. Identity
External:
- wa_user_id
- phone_e164

Internal:
- existing identity.users.id

Do not auto-link solely by phone number.

## 8. Account Linking
1. Student requests LINK.
2. Backend generates cryptographically secure one-time code.
3. Store code in Redis with short expiry.
4. Student authenticates to Trinetra web account.
5. Student submits code.
6. Validate code.
7. Link WhatsApp identity.
8. Invalidate code.
9. Send confirmation.

Support expiry, one-time use, invalid code, already-linked identity,
unlink and blocked state.

## 9. Intent Mapping
Minimum:
HI
HELP
LINK
QUIZ
QUIZ_ANSWER
FLASHCARDS
REVISION
PROGRESS
RECOMMEND
STUDY_PLAN
TUTOR

Unknown input -> controlled help/menu response.

## 10. Quiz Flow
QUIZ
 -> existing AssessmentService
 -> existing attempt
 -> question
 -> A/B/C/D
 -> existing answer/scoring
 -> existing mastery update
 -> explanation
 -> next question

No WhatsApp-specific attempt/answer records.

## 11. Flashcard Flow
Use existing published/certified flashcard content.

## 12. Revision Flow
Use existing mastery/revision/recommendation services.

## 13. Progress Flow
Use existing student progress/assessment/mastery data.

## 14. Tutor Flow
WhatsApp -> WhatsAppOrchestrator -> TutorService -> KnowledgeService
-> AIGateway -> configured provider -> WhatsApp.

## 15. Outbound Messaging
Use Meta Cloud API.
Use:
- WHATSAPP_PHONE_NUMBER_ID
- WHATSAPP_ACCESS_TOKEN
- WHATSAPP_GRAPH_API_VERSION

Keep provider-specific HTTP code isolated.

## 16. Message Types
MVP: text only.
Future: interactive buttons, lists, templates, images, documents, audio.

## 17. Conversation Window
Design around current WhatsApp message-category and customer-service-window
rules. Do not assume arbitrary outbound messages outside the service window.

Proactive notifications are future functionality requiring appropriate
template/consent handling.

## 18. Rate Limiting
Use existing Redis.
Rate-limit:
- inbound messages
- account linking attempts
- expensive AI requests

## 19. Cost Control
Do not call AI for deterministic operations.
All AI requests use existing AIGateway for centralized cost/token/latency
accounting.

## 20. Failure Behaviour
MVP fallback:
"Sorry, I couldn't complete that request right now. Please try again."

Never expose stack traces, SQL errors, provider credentials or internal details.

Comprehensive exception/observability is a later hardening phase.

## 21. Configuration Principle
WhatsApp provider pricing and policy are external business rules.
Do not hard-code message prices into application logic.

## 22. Source of Truth
Meta = communication provider.
Trinetra = source of truth for users, questions, assessments, attempts,
answers, mastery, recommendations, flashcards and AI routing.
