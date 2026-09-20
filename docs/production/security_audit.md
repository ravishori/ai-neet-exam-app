# Security Audit — Phase 0 (Read-Only)

**Verdict contribution:** AMBER within overall platform AMBER  
**Branch:** `phase2-question-bank` · **Date:** 2026-09-12  
**Companion JSON:** `security_audit.json`

## Summary matrix

| Control | Status | Evidence |
|---------|--------|----------|
| SQL injection (request path) | **IMPLEMENTED** | Parameterized `sqlalchemy.text()`; ORM elsewhere (`cms/repositories/search_repository.py`, ingestion) |
| XSS | **PARTIALLY IMPLEMENTED** | `markdown-renderer.tsx` (no `rehype-raw`); `question-panel.tsx` SVG `data:` URI; **no Next CSP** |
| CSRF | **PARTIALLY IMPLEMENTED** | `verify_csrf` on mutations; **`/logout` without CSRF** |
| CORS | **PARTIALLY IMPLEMENTED** | Explicit origins + credentials; `allow_methods/headers=["*"]` |
| Authentication | **IMPLEMENTED** | Argon2, HTTP-only cookies, refresh rotation, lockout, MFA API |
| Authorization / IDOR | **PARTIALLY IMPLEMENTED** | RBAC + attempt ownership; CMS ownership uneven |
| Input validation | **IMPLEMENTED** | Pydantic v2 schemas on routers |
| File upload | **IMPLEMENTED** | PDF magic/size/path jail; CSV sandbox |
| SSRF | **IMPLEMENTED** | Fixed provider URLs only (AI/Razorpay) |
| Command injection | **IMPLEMENTED** | No `shell=True` in `app/` |
| Secrets | **PARTIALLY IMPLEMENTED** | `.env` gitignored; prod vault **UNVERIFIED** |
| Security headers (API) | **IMPLEMENTED** | `SecurityHeadersMiddleware` |
| Security headers (Web) | **MISSING** | No Next.js CSP/headers config found |
| Rate limiting | **PARTIALLY IMPLEMENTED** | Redis; login/register fail-open |
| Exception leakage | **IMPLEMENTED** | Generic envelope + `errorId` |
| AI / content trust | **PARTIALLY / IMPLEMENTED** | Factory gates PARTIAL; ECAEP publish **IMPLEMENTED** |
| DB RLS | **PARTIALLY IMPLEMENTED** | `docs/database-security.md`; runtime typically owner role |

## P0 security blockers

1. Prove production HTTPS + Secure cookies  
2. Next.js CSP / security headers  
3. SMTP + alert path  
4. Auth rate-limit policy under Redis outage  
5. Secrets inventory / rotation  
6. DB least-privilege decision  
7. Logout CSRF (or document accepted risk)  
8. SVG/AI markdown XSS threat model + CSP  

## Tests present (do not equal “fixed in prod”)

- `apps/backend/tests/test_security_wave_a.py`  
- `apps/backend/tests/test_security_wave_c.py`  
- `apps/backend/tests/test_auth.py`  
- Commerce signature tests  

## Mandatory stop

No remediations implemented in this phase.
