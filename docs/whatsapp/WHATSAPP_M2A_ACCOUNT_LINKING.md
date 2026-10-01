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
   the matched code row and the target identity row are both locked
   (SELECT ... FOR UPDATE) for the remainder of the decision, the code is
   consumed, and the identity is linked — together, within that locked
   section — resolving to LINKED, ALREADY_LINKED (identity already
   correctly linked), or CONFLICT (identity linked to a different user;
   never overwritten). See "Concurrency" below for the exact mechanics.
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
| Single-use | Enforced via paired `SELECT ... FOR UPDATE` row locks on the code and target identity, held for the full decision — one valid code can establish exactly one identity link, even under genuine concurrent transactions (see "Concurrency" below) |
| Rollback safety | The code-consumption and identity-linking writes happen inside one transaction, committed once by the caller; an exception anywhere in between rolls back both together — never a partial state where the code is burned but no identity was linked. Proven by `test_failure_mid_link_rolls_back_without_burning_the_code`. |
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

### History: two successive fixes

**Fix 1 (identity-row race):** an early revision set `WhatsAppIdentity.user_id`
as a plain ORM attribute assignment decided from an in-memory read — two
concurrent `verify_and_link` calls for the same still-unlinked identity
(two different valid codes belonging to two different users, both
targeting the same phone number at once) could both observe "unlinked"
and both attempt to claim it. This was first closed with a conditional
`UPDATE whatsapp.identities SET user_id = :user_id WHERE id = :identity_id
AND user_id IS NULL RETURNING id`, attempted *before* consuming the
matched code so a losing call never burned its code.

**Fix 2 (single-use-code race, this revision):** that first fix was
per-identity only. It did not prevent the *same code* from being
redeemed via two *different* WhatsApp identities concurrently: each
identity's atomic link check only looked at its own row, so both could
independently win their own identity-link *before* either checked
whether the code itself had already been claimed — `try_consume`'s
boolean result was discarded entirely. One valid code could therefore
link two different WhatsApp identities, a single-use-code violation.

### Current mechanism: paired row locks, not independent compare-and-swaps

`verify_and_link` now locks **both** the matched code row and the target
identity row with `SELECT ... FOR UPDATE`, in a fixed order (identity,
then code) used consistently by every caller of this pattern, including
`unlink`. All of the decision (blocked/expiry/already-linked/conflict)
and both writes (consuming the code, linking the identity) happen inside
that single locked section of one transaction, which only commits once,
in the caller (`dispatch_link_code_verification_in_background` or the
HTTP router):

```sql
-- lock order: identity first, then the matched code
SELECT id FROM whatsapp.identities WHERE id = :identity_id FOR UPDATE;
SELECT * FROM whatsapp.link_codes WHERE id = :code_id FOR UPDATE;
-- re-validate code + identity state under lock, then:
UPDATE whatsapp.link_codes SET consumed_at = now(), whatsapp_identity_id = :identity_id
  WHERE id = :code_id AND consumed_at IS NULL;
UPDATE whatsapp.identities SET user_id = :user_id WHERE id = :identity_id AND user_id IS NULL;
```

A consistent lock order (identity always before code) across every call
site is what makes this deadlock-free regardless of which identity/code
pair is involved — see `verify_and_link`'s and `unlink`'s docstrings for
the full reasoning.

This closes both races at once:
- **Two different codes, same identity** — the identity-row lock means
  whichever call acquires it first fully decides and writes before the
  other can even read the identity's state.
- **Same code, two different identities** — the code-row lock means only
  the call that locks the code first may consume it; the loser
  re-validates the code's state under its own lock afterward and
  correctly finds it already consumed, never linking.

A `CONFLICT` outcome never mutates either row — the code remains fully
valid for the same user to redeem against a different identity (or the
same one, after an unlink).

### Test coverage

Three tests use genuinely independent PostgreSQL sessions/transactions
(separate `AsyncSession` objects, each on its own connection to the test
database, each committing its own transaction) — not the shared-session
`asyncio.gather` pattern used for simpler single-row tests elsewhere in
this file:

- `test_same_code_redeemed_by_two_identities_under_independent_transactions`
  — the exact Fix 2 scenario: one code, two different identities, two
  real concurrent transactions. Asserts exactly one `LINKED`, the other
  `INVALID_CODE`, and that the code is consumed exactly once.
- `test_two_different_codes_same_identity_under_independent_transactions`
  — the Fix 1 scenario, re-proven under genuine transaction concurrency
  (its predecessor, which used a shared session, was removed — see
  inline comment in the test file explaining why `SELECT ... FOR UPDATE`
  cannot meaningfully be exercised by two calls sharing one transaction,
  since a transaction never blocks on its own lock).
- `test_conflict_under_independent_transactions_never_burns_the_code` —
  confirms a `CONFLICT` under real cross-transaction contention leaves
  the code fully unconsumed.

Additionally, `test_failure_mid_link_rolls_back_without_burning_the_code`
proves rollback safety: an exception injected between code consumption
and identity linking (via the real `dispatch_link_code_verification_in_background`
path, whose own `async with AsyncSessionLocal()` block performs the
rollback) leaves *both* the code unconsumed and the identity unlinked —
confirming the two writes are never partially applied — and that the
code remains genuinely redeemable afterward.

One remaining same-transaction `asyncio.gather` test,
`test_concurrent_double_verification_links_exactly_once` (same code,
same identity, shared session), exercises statement-interleaving
correctness but is not a substitute for genuine cross-transaction proof
— the three independent-session tests above are what establishes that.

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
