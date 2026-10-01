# WhatsApp M2-A — Secure Account Linking

Implements the account-linking requirement from
[docs/product/WHATSAPP_BOT_PRD.md](../product/WHATSAPP_BOT_PRD.md) §6
("Never automatically link an existing account solely because the
WhatsApp phone number matches. Use a secure one-time linking flow with
expiry, one-time use, unlinking and blocked identity handling.").

## End-to-end lifecycle (as actually implemented)

```
1. Authenticated NEET user (web/app session) calls
   POST /api/v1/whatsapp/link/request.
2. Backend generates an 8-character, high-entropy, cryptographically
   secure code (secrets.choice over a 32-symbol alphabet, excluding
   visually ambiguous characters). Any still-pending codes for the same
   user are invalidated first.
3. Backend stores only the SHA-256 hash of the code, bound to the
   requesting user_id, with a 10-minute expiry.
4. The plaintext code is returned exactly once, in the generation
   response, to the already-authenticated caller.
5. The user sends that code as a plain WhatsApp message to the Twilio
   number. M1's existing, frozen webhook (whatsapp_webhook_router.py /
   whatsapp_webhook_service.py) validates the Twilio signature, applies
   rate limiting and idempotency, and persists the message exactly as it
   did before M2-A — unchanged.
6. After the webhook's response has already been sent (FastAPI
   BackgroundTasks), and only for a newly-persisted, non-duplicate
   message, whatsapp_webhook_router.py dispatches
   dispatch_link_code_verification_in_background(whatsapp_identity_id,
   message_text) — see "Integration point" below.
7. That background task recognizes a code-shaped message
   (looks_like_link_code — a shape check only, grants nothing by itself),
   opens its own database session, and calls
   WhatsAppLinkCodeService.verify_and_link.
8. On a valid, unexpired, unconsumed, phone-rate-limit-respecting match:
   the identity link is attempted atomically (UPDATE ... WHERE user_id IS
   NULL ... RETURNING) and, if won, the code is atomically consumed
   (UPDATE ... WHERE consumed_at IS NULL ... RETURNING) — resolving to
   LINKED, ALREADY_LINKED (identity already correctly linked), or
   CONFLICT (identity linked to a different user; never overwritten).
   See "Concurrency" below for the exact mechanics.
```

## Integration point

FastAPI's `BackgroundTasks`, dispatched from `whatsapp_webhook_router.py`
— the same primitive this codebase already uses for exactly this kind of
"act after persistence, decoupled from the request/response" case (see
`apps/backend/app/modules/ingestion/api/ingestion_router.py`'s
`_run_pipeline_in_background`). The router's `whatsapp_webhook_receive`
handler gained a `background_tasks: BackgroundTasks` parameter and a
2-line dispatch call; `WhatsAppWebhookService.handle_inbound`'s
`WebhookProcessResult` dataclass gained two optional, additive fields
(`whatsapp_identity_id`, `message_text`) so the already-computed identity
and message are available to that dispatch, populated only on the
newly-persisted, non-duplicate, non-rate-limited path.

No linking/verification logic was added to either file — both edits are
pure data-plumbing (a parameter, a 2-field dataclass extension, a 2-line
dispatch). All verification logic lives in
`whatsapp_link_code_service.py`. `whatsapp_webhook_router.py`'s TwiML
response, and `whatsapp_webhook_service.py`'s signature/rate-limit/
idempotency/persistence behavior, are byte-for-byte unchanged for every
input they handled before — re-verified by running M1's own 43 tests
unmodified after this change (see the M2-A implementation report for
results). Because `BackgroundTasks` run strictly after the response is
sent, the dispatched task can structurally never affect that response.

## Security properties

| Property | Implementation |
|---|---|
| Never link by phone match alone | `WhatsAppLinkCodeService.verify_and_link` is the only code path that ever sets `WhatsAppIdentity.user_id`; nothing compares `phone_e164` to `mobile_e164` anywhere in the module |
| Code entropy | 8 chars from a 32-symbol alphabet (`secrets.choice`), ≈40 bits |
| Hashed storage only | `code_hash` (SHA-256 via the existing `hash_opaque_token`); plaintext never persisted or logged |
| Expiry | 10 minutes (`CODE_TTL_MINUTES`) |
| Single-use | Atomic `UPDATE ... WHERE consumed_at IS NULL ... RETURNING` (see "Concurrency" below) |
| Verification throttling | Rate-limited **per WhatsApp phone number** — `check_rate_limit("ratelimit:whatsapp_link_verify:{phone_e164}", limit=5, window_seconds=300, fail_closed=False)`, the same primitive M1's own webhook already uses for inbound-message throttling. This replaced an earlier revision that incremented every active code's attempt counter on any unmatched guess, which could let one phone lock out an unrelated user's pending code — see "Attempt-attribution fix" below |
| Per-code attempts/max_attempts | Still present on `whatsapp.link_codes` and still checked in `find_candidates_for_verification` (`attempts < max_attempts`), but — because there is no session binding an unauthenticated guess to one specific code — this counter is **not incremented** by the current implementation; the phone-scoped rate limit above is the active throttle. The column remains as a structural ceiling for a future per-code attribution mechanism, not a currently-enforced-by-increment control. Documented here explicitly so this isn't overclaimed. |
| Replay rejected | A consumed code is excluded from `find_candidates_for_verification` |
| Generation rate limiting | `rate_limit_per_user("whatsapp_link_request", limit=5, window_seconds=300)` on the authenticated request endpoint |
| Conflicting existing link | `CONFLICT` outcome; `WhatsAppIdentity.user_id` is never overwritten |
| Existing correct link | `ALREADY_LINKED` outcome; idempotent, the code is still consumed (hygiene) but no relink occurs |
| Blocked identity | Checked first, before any code comparison or rate-limit check; `BLOCKED` outcome |
| Enumeration resistance | Wrong code, expired code, rate-limited guess, and race-lost code all collapse to the same `INVALID_CODE` outcome — no distinguishing signal |
| Unlink authorization | Only the linked user, or an explicitly admin-flagged caller (`SUPER_ADMIN` role, checked at the router), via `POST /api/v1/whatsapp/link/unlink` |
| Unlink enumeration resistance | `POST /api/v1/whatsapp/link/unlink` returns the exact same `403 WHATSAPP_UNLINK_FORBIDDEN` response — same status code, same error code, same message — whether the submitted phone number has no `WhatsAppIdentity` at all, or has one not owned by the caller. The router never distinguishes these two cases (no 404 path exists); an authenticated caller cannot use this endpoint to learn whether a given phone number has ever messaged the bot. Proven by `test_http_unlink_enumeration_safe_responses_are_identical`. |
| Deleted/soft-deleted users | `UserRepository.get_by_id` already excludes `deleted_at IS NOT NULL` rows; a code whose user has since been deleted resolves to `INVALID_CODE` |
| Pending-code invalidation on unlink | `WhatsAppLinkCodeService.unlink` calls `invalidate_pending_for_user` for the identity's linked user in the same transaction as clearing `WhatsAppIdentity.user_id`, before committing. A code generated before an unlink — even if still unexpired — can no longer redeem afterward, against this or any other identity. Proven by `test_unlink_invalidates_pending_codes_for_that_user`. |

## Attempt-attribution fix

An earlier revision of `verify_and_link` incremented the attempt counter
on **every** currently-active candidate code when a guess matched none of
them, reasoning that an unauthenticated guess can't be attributed to one
specific code. That had real cross-user impact: one phone's bad guesses
could contribute to locking out an unrelated user's still-valid pending
code. This has been replaced with rate-limiting verification attempts
**per WhatsApp phone number** — the actual unauthenticated boundary —
using the existing `check_rate_limit` primitive. A non-matching guess no
longer mutates any code row at all; `test_unrelated_pending_codes_not_locked_by_another_phones_guesses`
in `test_whatsapp_link_code.py` proves this directly: phone A exhausting
its own rate limit has zero effect on phone B's independent code.

## Concurrency

Two separate state transitions are each made atomic by a conditional SQL
`UPDATE ... RETURNING` rather than a plain read-then-write:

**Code consumption:**

```sql
UPDATE whatsapp.link_codes
SET consumed_at = now(), whatsapp_identity_id = :identity_id
WHERE id = :code_id AND consumed_at IS NULL
RETURNING id
```

Two simultaneous verification attempts for the same code can never both
succeed — the `WHERE consumed_at IS NULL` guard means only one `UPDATE`
affects a row; the loser sees zero rows returned and treats it as
`INVALID_CODE` (or, if the identity is already correctly linked by the
winner, `ALREADY_LINKED`). Proven by
`test_concurrent_double_verification_links_exactly_once`.

**Identity linking** (`WhatsAppLinkCodeService._try_atomic_link`):

```sql
UPDATE whatsapp.identities
SET user_id = :user_id
WHERE id = :identity_id AND user_id IS NULL
RETURNING id
```

An earlier revision set `WhatsAppIdentity.user_id` as a plain ORM
attribute assignment, decided from an in-memory read — two concurrent
`verify_and_link` calls for the same still-unlinked identity (e.g. two
different valid codes belonging to two different users, both targeting
the same phone number at once) could both observe "unlinked" and both
attempt to claim it, with whichever committed last silently winning. The
atomic conditional `UPDATE` above closes that window: `verify_and_link`
attempts this update *before* consuming the matched code (so a losing
call never burns its code), and if it loses, re-reads the identity's
now-current `user_id` to resolve `ALREADY_LINKED` (same user) or
`CONFLICT` (different user) rather than assuming either. Proven by
`test_two_different_valid_codes_concurrently_resolve_to_one_winner`,
which asserts exactly one `LINKED` outcome, a `CONFLICT` for the other,
and that the losing call's own code remains unconsumed.

**Test limitation:** both concurrency tests above drive their "concurrent"
`verify_and_link` calls via `asyncio.gather` against a single shared
`db_session` — i.e. one underlying database connection/transaction, not
two genuinely separate Postgres transactions racing against each other.
This proves the WHERE-guarded update logic is correct when two calls are
interleaved on one connection, which is necessary but not sufficient to
demonstrate behavior under true cross-transaction row-lock contention (the
scenario that actually occurs in production, where each
`dispatch_link_code_verification_in_background` call opens its own
independent `AsyncSessionLocal()`). The atomic `UPDATE ... WHERE ...
RETURNING` pattern itself is standard, well-established SQL semantics —
the same pattern this codebase already relies on elsewhere (M1's own
`WhatsAppRepository.get_or_create_identity`) — so this is a gap in test
depth, not a known or suspected defect in the fix. No test in this suite
claims to have verified true cross-transaction concurrency, and this
document does not claim that either.

## M1 boundary

`whatsapp_webhook_router.py` and `whatsapp_webhook_service.py` each
received a small, additive edit to carry the dispatch (see "Integration
point" above) — no other M1 file (`providers/twilio/`,
`whatsapp_repository.py`, `whatsapp_identity_service.py`) was touched,
and `test_whatsapp_m1.py` was not modified. All 43 of M1's own tests pass
unchanged, confirming the webhook's observable behavior (signature
validation, rate limiting, idempotency, persistence, TwiML response) is
identical to before this change for every case those tests cover.

## Operational caveats

- **Verification throttling degrades silently during a Redis outage.**
  `check_rate_limit` is called with `fail_closed=False` for the per-phone
  verification throttle (matching M1's own established convention for
  this message-processing path, as opposed to auth_router.py's
  interactive-HTTP OTP endpoints). If Redis is unreachable, the count-based
  per-phone limit is not enforced at all for that period — the only
  remaining defense is the code's own ≈40 bits of entropy, which is
  considered an acceptable trade-off given a 10-minute expiry window, but
  is a real, intentional reduction in defense-in-depth during an outage,
  not a theoretical one.
- **`BackgroundTasks` has no durable retry.** The link-code verification
  dispatch (`dispatch_link_code_verification_in_background`) runs via
  FastAPI's in-process `BackgroundTasks`, the same primitive
  `ingestion_router.py` already uses in this codebase. It has no queue,
  no persistence, and no retry: if the backend process restarts or
  crashes between "webhook response sent" and "background verification
  completed," that verification attempt is silently lost and the user
  must resend their code. This is considered proportionate for the
  current scale and traffic volume, not a defect, but is a real
  reliability gap worth knowing before relying on this path for
  higher-stakes or higher-volume flows later.

## Out of scope for M2-A

MCQ interaction, study-session persistence/state machine, broader
conversation orchestration, outbound messaging/templates, and status
callbacks — all remain unimplemented, as in the M1 baseline.
