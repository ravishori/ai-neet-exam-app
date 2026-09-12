# Security test plan — TALOS

## Automated (CI / local)

| Area | How |
|------|-----|
| Log redaction | `tests/test_security_wave_a.py` |
| IntegrityError mapping | same |
| Forgot-password rate limit fail-closed | same |
| Auth login/lockout/refresh | `tests/test_auth.py` |
| OTP hash verify / abuse | `tests/test_security_wave_c.py` |
| TOTP enroll + MFA login step-up | same |
| Change-password arg order | same |
| Dropdown Menu.Group | `apps/web` vitest `dropdown-menu.test.tsx` |

Commands:

```bash
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_security_wave_a.py tests/test_security_wave_c.py tests/test_auth.py -q

cd apps/web
npm test -- --run src/components/ui/dropdown-menu.test.tsx
```

## Manual / staging

1. SMTP: configure `SMTP_*` + `WEB_APP_URL`; request password reset; confirm delivery; confirm production logs omit tokens.
2. `ALERT_EMAIL`: force a 500 path in staging; confirm alert email + Redis dedupe (no second mail within cooldown).
3. TOTP: enroll with authenticator; logout; login requires MFA; recovery code works once.
4. OTP: request email OTP; verify; confirm wrong codes lock after max attempts; confirm API never returns plaintext OTP.
5. Headers: check `X-Content-Type-Options`, prod HSTS, correlation `X-Request-Id` round-trip.
6. Do **not** claim GREEN readiness until SMTP + ENCRYPTION_KEY + alert path verified in the target environment.

## Out of scope this wave

- Full PostgreSQL RLS enforcement (see `docs/database-security.md`).
- SMS OTP gateway.
- Blind Next.js major upgrade.
