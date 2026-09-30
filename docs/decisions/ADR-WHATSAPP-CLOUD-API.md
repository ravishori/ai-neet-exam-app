# ADR: Direct Meta WhatsApp Cloud API

Status: ACCEPTED
Date: 2026-09-30
Decision: Use Meta WhatsApp Business Platform Cloud API directly.

## Context
Trinetra NEET Prep needs a WhatsApp learning channel.

Candidates:
- Meta WhatsApp Cloud API
- Twilio WhatsApp
- Gupshup
- 360dialog
- other BSPs

The existing application already has FastAPI, PostgreSQL, Redis,
identity/authentication, assessment, tutor, knowledge, mastery,
recommendations, CMS and AIGateway.

## Decision
Use Meta WhatsApp Business Platform Cloud API directly with the existing
Trinetra FastAPI backend.

Do not add a WhatsApp BSP for the MVP.

## Rationale
1. Avoid unnecessary intermediary infrastructure.
2. Avoid third-party API/message markup where not required.
3. Maintain direct control over webhook/message processing.
4. Reuse existing FastAPI, PostgreSQL and Redis.
5. Reuse existing Trinetra learning services.
6. Isolate provider-specific code in one module.
7. Preserve ability to change provider later if necessary.

## Cost Principle
Meta controls WhatsApp Business Platform pricing.
Third-party providers may add their own fees.

Twilio currently publishes a per-message WhatsApp handling fee in addition
to applicable Meta fees.

Do not hard-code current Meta pricing into application logic.

## Security Decision
The integration must use:
- webhook verification
- X-Hub-Signature-256 validation
- secure secret storage
- idempotency
- rate limiting

## Architecture Decision
WhatsApp is a channel adapter.

It does not own:
- assessment logic
- question bank
- scoring
- mastery
- recommendations
- flashcards
- AI provider routing

## Consequences
Positive:
- lower architectural complexity
- lower provider dependency
- direct Meta integration
- reusable Trinetra learning engine
- easier Web/Mobile/WhatsApp convergence

Negative:
- Trinetra owns WhatsApp integration code
- Meta Business configuration is our responsibility
- webhook/security integration is our responsibility
- Meta policy/pricing changes must be monitored

## Revisit Conditions
Reconsider a BSP if:
- Meta onboarding becomes a material operational blocker
- required enterprise features are unavailable
- multi-provider routing becomes necessary
- operational/support requirements justify the additional cost
- WhatsApp scale materially changes the economics

Until then, direct Meta Cloud API remains the chosen architecture.

## References
Primary:
Meta WhatsApp Business Platform documentation and pricing.

Secondary:
Twilio WhatsApp Pricing, for provider-cost comparison.

Pricing and platform policies are external and must be rechecked before
production launch.
