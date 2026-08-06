# Security Validation Checklist
## AI NEET Exam App

---

# Purpose

This checklist defines the mandatory security verification steps before approving any feature, bug fix, API, deployment, or release.

Security is everyone's responsibility.

Repository implementation is the source of truth.

No implementation should be approved without completing all applicable security checks.

---

# 1. Repository Inspection

☐ Repository inspected

☐ Existing security implementation reviewed

☐ Existing authentication reviewed

☐ Existing authorization reviewed

☐ Existing middleware reviewed

☐ Existing validation reviewed

☐ Existing audit logging reviewed

☐ Existing security tests reviewed

☐ Existing ADRs reviewed

☐ No duplicate security implementation introduced

---

# 2. Authentication

☐ Authentication required where appropriate

☐ JWT validation verified

☐ Token expiration verified

☐ Refresh token behaviour verified (if applicable)

☐ Logout invalidation reviewed

☐ Session handling secure

☐ Unauthorized access blocked

☐ Authentication bypass impossible

---

# 3. Authorization

☐ RBAC verified

☐ Least privilege applied

☐ Role validation implemented

☐ Admin-only endpoints protected

☐ Resource ownership enforced

☐ Privilege escalation prevented

☐ Permission checks tested

☐ Authorization failures return correct responses

---

# 4. Input Validation

☐ Server-side validation implemented

☐ Client validation supplements server validation

☐ Required fields validated

☐ Length constraints validated

☐ Enum validation implemented

☐ File validation implemented

☐ Invalid requests rejected

☐ No trust placed in client input

---

# 5. Output Protection

☐ Sensitive fields excluded

☐ Internal errors hidden

☐ Stack traces not exposed

☐ Response data minimized

☐ Proper HTTP status codes returned

☐ Error messages safe

☐ Sensitive metadata removed

---

# 6. Database Security

☐ Parameterized queries used

☐ ORM used correctly

☐ SQL injection prevented

☐ Database permissions reviewed

☐ Sensitive columns protected

☐ Migrations reviewed

☐ Backup strategy considered

☐ Rollback verified

---

# 7. API Security

☐ REST endpoints protected

☐ Authentication enforced

☐ Authorization enforced

☐ Input validation complete

☐ Output validation complete

☐ Pagination limits enforced

☐ Search endpoints protected

☐ Rate limiting reviewed

☐ OpenAPI documentation updated

---

# 8. File Upload Security

☐ File type validated

☐ MIME type verified

☐ File size limits enforced

☐ Filename sanitized

☐ Storage location secure

☐ Path traversal prevented

☐ Malware scanning considered

☐ Temporary files cleaned

If not applicable

☐ No file upload functionality

---

# 9. Frontend Security

☐ XSS prevention reviewed

☐ Unsafe HTML rendering avoided

☐ Secure routing verified

☐ Token storage secure

☐ Sensitive data not stored in browser unnecessarily

☐ CSRF considerations reviewed (if applicable)

☐ Clickjacking protections considered

---

# 10. AI Platform Security

☐ Prompt injection risk reviewed

☐ AI input validated

☐ AI output reviewed

☐ Sensitive data masked

☐ Prompt templates protected

☐ AI provider credentials protected

☐ Token usage reviewed

☐ Fallback behaviour secure

If not applicable

☐ No AI impact

---

# 11. Secrets Management

☐ No hardcoded secrets

☐ Environment variables used

☐ API keys protected

☐ Database credentials protected

☐ JWT secrets protected

☐ Production configuration reviewed

☐ Git history checked for secrets

---

# 12. Dependency Security

☐ Dependencies reviewed

☐ Known vulnerabilities checked

☐ Security advisories reviewed

☐ Docker base images reviewed

☐ GitHub Actions reviewed

☐ Third-party libraries justified

---

# 13. Logging & Auditing

☐ Authentication events logged

☐ Authorization failures logged

☐ Administrative actions logged

☐ Errors logged safely

☐ Sensitive data excluded from logs

☐ Correlation IDs present

☐ Audit trail complete

---

# 14. Monitoring

☐ Security monitoring enabled

☐ Alerts configured (where applicable)

☐ Health checks reviewed

☐ Incident response documented

☐ Rollback strategy available

☐ Operational monitoring verified

---

# 15. OWASP Review

☐ Broken Access Control

☐ Cryptographic Failures

☐ Injection

☐ Insecure Design

☐ Security Misconfiguration

☐ Vulnerable Components

☐ Authentication Failures

☐ Data Integrity

☐ Logging & Monitoring

☐ SSRF (where applicable)

---

# 16. Testing

☐ Authentication tests

☐ Authorization tests

☐ Validation tests

☐ Security regression tests

☐ API security tests

☐ File upload tests

☐ Permission tests

☐ Existing tests still pass

---

# 17. Documentation

☐ Security documentation updated

☐ API documentation updated

☐ Deployment guide updated

☐ ADR updated (if required)

☐ Release notes updated

☐ Known risks documented

---

# 18. Final Security Validation

☐ No Critical vulnerabilities

☐ No High vulnerabilities

☐ Medium risks accepted or mitigated

☐ Repository deployable

☐ Security review completed

☐ Security approval granted

---

# Security Status

Feature:

Reviewer:

Date:

Result

☐ Approved

☐ Approved with Conditions

☐ Requires Remediation

☐ Blocked

Comments

____________________________________________________

____________________________________________________

____________________________________________________

---

# Cursor Instructions

Before approving security

1. Inspect repository.
2. Review existing security implementation.
3. Verify authentication.
4. Verify authorization.
5. Review OWASP risks.
6. Review dependencies.
7. Verify logging.
8. Verify monitoring.
9. Execute security tests.
10. Document remaining risks.

Never approve security without evidence.

---

# Security Quality Checklist

✓ Repository inspected

✓ Authentication verified

✓ Authorization verified

✓ Validation complete

✓ Secrets protected

✓ OWASP reviewed

✓ Dependencies reviewed

✓ Logging verified

✓ Monitoring reviewed

✓ Security tests passing

✓ Documentation updated

---

# Final Principle

Security is a continuous engineering responsibility, not a one-time task.

Every feature, API, deployment, and release should demonstrate evidence-based security validation before approval.

The objective is to reduce risk while preserving repository architecture, maintainability, and operational stability.