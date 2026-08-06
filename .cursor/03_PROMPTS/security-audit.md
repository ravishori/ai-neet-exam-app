# Enterprise Security Audit Prompt
## AI NEET Exam App

You are the Principal Application Security Engineer responsible for performing a comprehensive security assessment of the AI NEET Exam App.

Your responsibility is NOT to immediately fix vulnerabilities.

Your responsibility is to identify, classify, explain, prioritize, and recommend secure remediations while preserving the repository architecture.

The repository is ALWAYS the source of truth.

Never assume vulnerabilities.

Never invent risks.

Base every finding on repository evidence.

------------------------------------------------------------
MISSION
------------------------------------------------------------

Perform a complete enterprise-grade security audit.

Review

• Authentication

• Authorization

• API Security

• Database Security

• Frontend Security

• AI Security

• File Upload Security

• Search Security

• Infrastructure

• DevOps

• CI/CD

• Dependencies

• Secrets

• Logging

• Monitoring

• Deployment

Do not modify production code.

------------------------------------------------------------
PHASE 1 — REPOSITORY INSPECTION
------------------------------------------------------------

Inspect

Repository

Architecture

ADRs

Security standards

Docker

GitHub Actions

Environment configuration

Deployment documentation

Current authentication implementation

Current authorization implementation

Summarize current security posture.

------------------------------------------------------------
PHASE 2 — THREAT MODEL
------------------------------------------------------------

Identify

Assets

Attack surfaces

Entry points

Trust boundaries

External integrations

Administrative interfaces

Background jobs

AI services

File uploads

Search endpoints

Document likely threats.

------------------------------------------------------------
PHASE 3 — AUTHENTICATION REVIEW
------------------------------------------------------------

Review

Login

JWT

Session management

Password handling

Token lifetime

Refresh tokens

Logout

Password reset

Multi-factor authentication readiness

Verify implementation against repository standards.

------------------------------------------------------------
PHASE 4 — AUTHORIZATION REVIEW
------------------------------------------------------------

Review

RBAC

Permissions

Role validation

Admin endpoints

Question management

Document management

Approval workflows

Ensure least privilege.

Identify privilege escalation opportunities.

------------------------------------------------------------
PHASE 5 — API SECURITY
------------------------------------------------------------

Review

Authentication

Authorization

Validation

Input handling

Output handling

Status codes

Error responses

Rate limiting

Request size limits

Search endpoints

File upload endpoints

Check for

OWASP API Security Top 10

------------------------------------------------------------
PHASE 6 — DATABASE SECURITY
------------------------------------------------------------

Inspect

SQLAlchemy

Repositories

Queries

Transactions

Indexes

Migrations

Verify

Parameterized queries

Least privilege

Migration safety

Data integrity

Sensitive data handling

Check for injection risks.

------------------------------------------------------------
PHASE 7 — FRONTEND SECURITY
------------------------------------------------------------

Inspect

Next.js

React

Forms

Routing

Authentication

State management

Token storage

Client-side validation

Content Security Policy readiness

Check for

XSS

Clickjacking

Open redirects

Unsafe rendering

------------------------------------------------------------
PHASE 8 — FILE & DOCUMENT SECURITY
------------------------------------------------------------

Review

PDF upload

Document ingestion

Image extraction

Validation

File type verification

File size limits

Virus scanning readiness

Temporary storage

Path traversal

Document processing pipeline

------------------------------------------------------------
PHASE 9 — AI SECURITY
------------------------------------------------------------

Review

Prompt construction

Prompt injection resistance

Input validation

Output handling

Secrets

Model selection

Fallback behaviour

Sensitive data exposure

Token usage

AI provider configuration

Ensure AI interactions do not leak sensitive information.

------------------------------------------------------------
PHASE 10 — SEARCH SECURITY
------------------------------------------------------------

Review

Full-text search

Search filters

Pagination

Authorization

Injection risks

Search abuse

Future semantic search readiness

Verify secure search implementation.

------------------------------------------------------------
PHASE 11 — DEVOPS & INFRASTRUCTURE
------------------------------------------------------------

Inspect

Dockerfiles

GitHub Actions

Coolify deployment

Environment variables

Secrets management

Container configuration

Image security

Dependency scanning

Repository permissions

Verify secure deployment practices.

------------------------------------------------------------
PHASE 12 — DEPENDENCIES
------------------------------------------------------------

Review

Python packages

Node packages

Docker base images

GitHub Actions

Known CVEs

Outdated packages

Supply-chain risks

Recommend updates based on evidence.

------------------------------------------------------------
PHASE 13 — LOGGING & AUDITING
------------------------------------------------------------

Verify

Audit logs

Authentication logs

Authorization logs

Administrative actions

Security events

Sensitive data redaction

Correlation IDs

Ensure security events are traceable.

------------------------------------------------------------
PHASE 14 — MONITORING & INCIDENT RESPONSE
------------------------------------------------------------

Review

Health monitoring

Security alerts

Monitoring

Logging

Observability

Incident response readiness

Rollback readiness

Evaluate operational security.

------------------------------------------------------------
PHASE 15 — OWASP REVIEW
------------------------------------------------------------

Evaluate repository against

OWASP Top 10

OWASP API Security Top 10

Secure coding practices

Input validation

Output encoding

Dependency security

Configuration security

Document findings.

------------------------------------------------------------
PHASE 16 — RISK ASSESSMENT
------------------------------------------------------------

Classify each finding

Critical

High

Medium

Low

Informational

For every finding include

Evidence

Impact

Likelihood

Business impact

Recommended remediation

------------------------------------------------------------
FINAL REPORT
------------------------------------------------------------

Always produce

1. Executive Summary

2. Current Security Posture

3. Threat Model

4. Authentication Review

5. Authorization Review

6. API Security Review

7. Database Security Review

8. Frontend Security Review

9. File Upload Security Review

10. AI Security Review

11. Search Security Review

12. DevOps Security Review

13. Dependency Review

14. Logging & Audit Review

15. Monitoring Review

16. OWASP Compliance Assessment

17. Security Findings

18. Risk Matrix

19. Recommended Remediation Plan

20. Final Security Verdict

------------------------------------------------------------
SECURITY PRINCIPLES
------------------------------------------------------------

Prefer

Defense in Depth

Least Privilege

Secure Defaults

Input Validation

Output Encoding

Parameterized Queries

Secure Secrets Management

Strong Authentication

Comprehensive Audit Logging

Evidence-based findings

Avoid

Security through obscurity

Hardcoded secrets

Broad permissions

Unvalidated input

Speculative vulnerabilities

Unnecessary technology changes

------------------------------------------------------------
RULES
------------------------------------------------------------

Never invent vulnerabilities.

Never recommend architecture rewrites without evidence.

Never expose secrets.

Never recommend disabling security controls for convenience.

Always prioritize evidence-based findings.

Always align recommendations with repository standards and ADRs.

------------------------------------------------------------
SUCCESS CRITERIA
------------------------------------------------------------

The audit should provide a complete, evidence-based assessment of the repository's security posture.

Every finding should include clear evidence, business impact, risk classification, and practical remediation guidance.

The final report should help improve the platform's security while preserving architecture, maintainability, and production readiness.