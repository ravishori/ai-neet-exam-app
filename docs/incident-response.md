# Incident response — auth / security (TALOS)

## Severity classes

| Class | Examples | First response |
|-------|----------|----------------|
| Sev-1 | Suspected credential stuffing, mass account lockouts, refresh-token reuse storms | Rate-limit / WAF; rotate `JWT_SECRET` only with planned session kill; notify ops |
| Sev-2 | SMTP outage blocking resets; Redis outage causing fail-closed 429s on recovery | Fail closed is preferred over open abuse; restore Redis/SMTP |
| Sev-3 | Single-user account compromise report | Force password reset; revoke refresh tokens; disable TOTP if attacker-controlled |

## Secret handling

- Never paste passwords, OTP codes, TOTP secrets, or raw JWT into tickets or chat.
- Use Error ID / `traceId` from API envelopes when correlating logs.
- Rotate `ENCRYPTION_KEY` only with a documented re-encrypt plan (invalidates stored TOTP secrets).

## Alert emails

Critical unhandled exceptions may email `ALERT_EMAIL` with route + Error ID only (no stack/PII/secrets). Deduped via Redis (`alert:dedupe:*`).

## Contacts / runbooks

Maintain operator contacts outside this repo. After any Sev-1, update `docs/security-audit.md` with residual risk.
