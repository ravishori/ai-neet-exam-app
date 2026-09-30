# ADR: WhatsApp provider abstraction — Twilio as initial provider

Status: ACCEPTED
Date: 2026-09-30
Supersedes: ADR-WHATSAPP-CLOUD-API.md
Decision: WhatsApp integration is built behind a provider adapter boundary.
Twilio WhatsApp is the initial provider implementation. The core/domain
architecture is provider-agnostic and portable to Meta Cloud API,
360dialog, Gupshup, or any future provider without touching learning
services.

## Context

ADR-WHATSAPP-CLOUD-API.md originally decided to integrate the Meta
WhatsApp Business Platform Cloud API directly, with no BSP (Business
Solution Provider) intermediary, reasoning that direct integration avoids
unnecessary infrastructure and third-party markup.

That reasoning about avoiding *unnecessary* intermediary complexity still
holds in principle, but the starting provider has changed: **Twilio is
now the initial WhatsApp provider**, not direct Meta Cloud API access.
This is a provider choice, not a reversal of the underlying engineering
judgment — the risk the original ADR was actually guarding against was
building `whatsapp` module code so entangled with one provider's SDK,
webhook shape, and signature scheme that switching providers later would
mean rewriting the module rather than swapping an adapter. That risk
exists identically whether the first provider is Meta or Twilio, and
this ADR is what actually addresses it: a provider abstraction boundary,
so the choice of Twilio today does not lock the architecture to Twilio
tomorrow.

## Decision

**WhatsApp integration is structured in four layers**, per the
architecture document's system flow:

```
Student
  -> WhatsApp
  -> Provider Adapter          (Twilio today; Meta/360dialog/Gupshup later)
  -> Canonical WhatsApp Message/Webhook Model
  -> WhatsApp Domain Services
  -> NEET Orchestrator
  -> existing Assessment/Tutor/Flashcards/Revision/Progress/Mastery services
```

**Twilio WhatsApp is the initial provider**, integrated through a provider
adapter under `apps/backend/app/modules/whatsapp/providers/`:

```
providers/
    base.py              # Provider interface — send_text, parse_inbound,
                          # validate_webhook
    twilio/
        client.py        # Twilio SDK usage, outbound send
        webhook.py        # Twilio request-signature validation
        schemas.py        # Twilio-specific webhook payload shapes
```

**The provider interface (`providers/base.py`) is the only contract the
domain services depend on.** Conceptually:
- `send_text(to, body) -> ProviderSendResult` — send a text message,
  return a provider-agnostic result (success/failure, provider message id).
- `parse_inbound(raw_request) -> CanonicalInboundMessage` — turn a
  provider-specific webhook payload into the canonical internal message
  shape (see below). All provider-specific field names, payload shapes,
  and quirks are resolved here and nowhere else.
- `validate_webhook(raw_request) -> bool` — authenticate that an inbound
  webhook call genuinely came from the configured provider, using
  whatever mechanism that provider uses (Twilio: `X-Twilio-Signature`
  header validation via Twilio's own `RequestValidator`, HMAC-SHA1 over
  the request URL and POST parameters, per Twilio's published request-
  validation scheme; Meta, if added later: `X-Hub-Signature-256`,
  HMAC-SHA256 over the raw body). **This method's signature is the same
  regardless of provider — only its implementation differs.**

**A canonical internal message model is provider-neutral.** No domain
service, repository, or database column is named after a Twilio-specific
concept (`MessageSid`, `From`/`To` in Twilio's E.164-with-`whatsapp:`-
prefix form, `SmsStatus`) or a Meta-specific concept (`wa_id`,
`messaging_product`, Meta's nested `entry[].changes[].value.messages[]`
shape). Persistence uses:
- `provider` — which provider handled this identity/message (`"twilio"`
  today; a discriminator column, not a hard-coded assumption).
- `provider_message_id` — the provider's own message identifier
  (Twilio's `MessageSid` today), stored generically.
- `external_user_id` — the provider's identifier for the WhatsApp user,
  where the provider exposes one distinct from the phone number.
- `phone_e164` — the actual WhatsApp phone number. This is **not**
  provider-specific (a phone number is a channel-level fact, not a
  Twilio or Meta concept), so it is the one identity field that survives
  a provider switch unchanged.

**The application webhook route is stable and provider-independent**:
`GET /api/v1/whatsapp/webhook` and `POST /api/v1/whatsapp/webhook` do not
change name, path, or existence when the provider changes. Only the
provider adapter selected by configuration changes what happens inside
the request.

**Configuration selects the active provider.** A `WHATSAPP_PROVIDER`
setting (e.g. `"twilio"`) picks which adapter is instantiated;
provider-specific credentials (Twilio: `TWILIO_ACCOUNT_SID`,
`TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`) are namespaced separately
from any future provider's own credentials, so adding a second provider's
config never requires renaming or removing the first provider's.

## Migration strategy to another provider

Adding or switching to a new provider (e.g. Meta Cloud API) requires:
1. A new `providers/<name>/` package implementing the same `base.py`
   interface (`send_text`, `parse_inbound`, `validate_webhook`).
2. New provider-specific settings, namespaced under that provider's own
   prefix (e.g. `WHATSAPP_META_*`), added alongside — not replacing —
   Twilio's.
3. A configuration change (`WHATSAPP_PROVIDER=meta`) to select it.
4. **Zero changes** to `whatsapp` domain services, the NEET orchestrator,
   the database schema, or any downstream learning service — the
   canonical message model and provider-neutral persistence columns
   already accommodate a different `provider` value without a migration.

This is the concrete test of whether the abstraction actually held: if
switching providers ever requires touching `services/`, `repositories/`,
`models/`, or the orchestrator, the boundary has leaked and should be
treated as a defect against this ADR, not accepted as normal.

## Consequences

Positive:
- Twilio can be adopted now without a later rewrite if the provider
  changes.
- Core learning/domain code has zero Twilio (or Meta) import, naming, or
  payload-shape dependency.
- Multiple providers could in principle run side-by-side (e.g. during a
  migration window) since `provider` is a per-row discriminator, not a
  global assumption.
- Testing the domain/orchestrator layer needs only a fake provider
  adapter implementing the same interface — no real Twilio/Meta
  credentials or sandbox required for those tests.

Trade-offs:
- More upfront structure than calling a provider SDK directly from the
  webhook router — an extra interface and adapter layer for what is,
  today, a single provider.
- The canonical message model must be kept genuinely provider-neutral in
  practice, not just in the interface signature — a future provider with
  a materially different message model (e.g. rich interactive replies)
  may still require canonical-model extension, not just a new adapter.
- Provider-specific webhook authentication mechanisms differ enough
  (Twilio's per-request HMAC-SHA1 over URL+params vs. Meta's
  HMAC-SHA256 over the raw body) that `validate_webhook` cannot be a
  thin shared helper — each adapter owns its own correct implementation.

## Security considerations

- Webhook authenticity validation (`validate_webhook`) is mandatory
  before any inbound payload is parsed or trusted, regardless of
  provider — this requirement is provider-agnostic even though its
  mechanism isn't.
- Twilio credentials (`TWILIO_AUTH_TOKEN`, used both for outbound API
  calls and inbound signature validation) follow the same
  never-hard-code, never-log, environment-variable-only convention as
  every other secret in this codebase (see `app/core/config.py`'s
  existing `twilio_*`/`*_api_key` fields for the established pattern).
- The provider adapter boundary also serves as a security boundary:
  provider-specific request parsing (where injection/parsing bugs are
  most likely to live, given they handle attacker-reachable webhook
  input) is isolated to `providers/<name>/`, not spread across domain
  services.

## Testing implications

- **Domain/orchestrator tests** use a fake/stub provider adapter (same
  interface, canned responses) — no live Twilio account, sandbox, or
  network call required, and these tests do not change when a provider
  is added or swapped.
- **Provider adapter tests** (Twilio-specific) cover: valid/invalid/
  missing `X-Twilio-Signature`, canonical-model parsing of a real Twilio
  inbound webhook payload shape, and outbound `send_text` success/error
  handling against Twilio's API — these tests are provider-specific and
  live under `providers/twilio/`'s own test coverage, not mixed into
  domain service tests.
- **Router-level tests** confirm the stable `GET`/`POST
  /api/v1/whatsapp/webhook` contract (status codes, verification
  behavior) without needing to know which provider is configured.

## Revisit conditions

Reconsider this abstraction (not the provider choice) if:
- Only one provider is ever realistically expected and the interface
  layer is pure overhead with no portability being exercised.
- A provider's message model is different enough that the canonical
  model can't represent it without leaking provider concepts back into
  domain services anyway.

Reconsider the **provider choice** (Twilio vs. direct Meta vs. another
BSP) independently of this abstraction, using the same cost/support/
operational criteria ADR-WHATSAPP-CLOUD-API.md already established —
that evaluation is unaffected by which adapter implements the interface.

## References

Primary: this repository's `docs/architecture/WHATSAPP_BOT_ARCHITECTURE.md`
and `docs/architecture/WHATSAPP_BOT_INTEGRATION_SPEC.md` (both revised
alongside this ADR to reflect the provider boundary).

Secondary: ADR-WHATSAPP-CLOUD-API.md (superseded by this ADR for the
specific "which provider first" decision; its security/idempotency/
rate-limiting/architecture-ownership principles are unaffected and still
apply).
