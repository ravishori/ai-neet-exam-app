# Security Standards
## AI NEET Exam App
### Enterprise Security Engineering Guide

Version: 1.0

---

# Purpose

This document defines the security standards for the AI NEET Exam App.

Security is not a separate phase.

Security is part of every engineering decision.

Every feature must be designed, implemented, tested, and reviewed with security in mind.

---

# Security Philosophy

The platform handles

- Student accounts
- Educational content
- Administrative functions
- AI-generated content
- Uploaded documents
- Practice history
- Analytics

Security must protect

- Confidentiality
- Integrity
- Availability

Never sacrifice security for convenience.

---

# Security Principles

Follow

✓ Least Privilege

✓ Defense in Depth

✓ Secure by Default

✓ Fail Securely

✓ Zero Trust

✓ Principle of Minimum Exposure

---

# Repository First

Before implementing security-related changes

Inspect

Existing authentication

Authorization

Middleware

Configuration

Environment variables

Existing security tests

Existing ADRs

Reuse existing security patterns.

Never introduce competing authentication mechanisms.

---

# Authentication

Authentication must be centralized.

Never implement custom authentication inside controllers or components.

Support repository authentication mechanism.

Verify

Identity

Session validity

Token validity

Expiration

Revocation

---

# Authorization

Authorization is mandatory.

Verify

Roles

Permissions

Ownership

Access level

Examples

Student

Administrator

Reviewer

Publisher

Never trust client-side role information.

Always verify permissions on the server.

---

# Password Security

Passwords must

Never be stored in plain text.

Use strong password hashing.

Never log passwords.

Never return passwords.

Never expose password reset tokens.

---

# Session Management

Sessions should

Expire appropriately.

Support logout.

Invalidate expired sessions.

Rotate tokens when required.

Prevent session fixation.

---

# Input Validation

Validate all external input.

Examples

Forms

API requests

Headers

Query parameters

File uploads

JSON payloads

Never trust client input.

---

# Output Encoding

Encode output appropriately.

Prevent

Cross-Site Scripting (XSS)

Injection attacks

Unsafe HTML rendering

Avoid rendering untrusted HTML.

---

# SQL Injection

Always use

SQLAlchemy ORM

Parameterized queries

Never concatenate SQL.

Never build SQL strings from user input.

---

# Cross-Site Scripting (XSS)

Avoid

Unsafe HTML rendering

Unescaped user content

Inline JavaScript

Sanitize rich text if supported.

---

# Cross-Site Request Forgery (CSRF)

Protect state-changing operations.

Use repository security strategy.

Review cookie configuration.

Review authentication mechanism.

---

# File Upload Security

Validate

File type

File size

Extension

Content type

Reject unsupported formats.

Never trust file names.

Store uploads securely.

Future

Virus scanning

Quarantine

Content inspection

---

# Secrets Management

Secrets must never be committed.

Use

Environment variables

Secret management systems

Production secrets must not appear in

Repository

Logs

Error messages

Tests

Documentation

---

# API Security

Every endpoint should review

Authentication

Authorization

Validation

Rate limiting

Input sanitization

Error responses

Avoid exposing implementation details.

---

# Rate Limiting

Protect

Authentication

Search

AI endpoints

Document uploads

Admin endpoints

Prevent abuse.

---

# Logging

Log

Authentication failures

Authorization failures

Security warnings

Administrative actions

Unexpected behaviour

Never log

Passwords

Secrets

Tokens

Sensitive personal data

---

# Audit Trail

Administrative actions should be auditable.

Examples

User creation

Role changes

Document publication

Content approval

Deletion

Configuration changes

---

# Dependency Security

Review dependencies regularly.

Use

Dependabot

pip-audit

npm audit

CodeQL

Update vulnerable packages promptly.

---

# Infrastructure Security

Production should use

HTTPS

Secure headers

Restricted ports

Firewall

Least privilege

Regular updates

Avoid exposing internal services.

---

# Database Security

Use

Least privilege accounts

Parameterized queries

Encrypted connections

Backups

Access control

Never expose database credentials.

---

# AI Security

Validate

AI prompts

AI output

Uploaded content

Prevent

Prompt injection

Sensitive information leakage

Unsafe output

AI-generated content should be reviewable.

---

# Data Privacy

Protect

Student information

Progress history

Bookmarks

Notes

Analytics

Follow applicable privacy regulations.

Collect only required information.

---

# Error Handling

Error messages should

Help users

Avoid revealing implementation details

Never expose

Stack traces

SQL

Secrets

Internal paths

Production configuration

---

# Security Testing

Every security-sensitive feature should include

Authentication tests

Authorization tests

Validation tests

Permission tests

Regression tests

Review OWASP Top 10 where applicable.

---

# Security Review Checklist

Before merging verify

✓ Authentication reviewed

✓ Authorization reviewed

✓ Input validation

✓ Output encoding

✓ SQL Injection protection

✓ XSS protection

✓ CSRF review

✓ Secrets protected

✓ Logging reviewed

✓ Rate limiting considered

✓ Dependency scan clean

---

# Incident Response

If a security issue is discovered

1. Assess impact

2. Protect users

3. Contain the issue

4. Fix root cause

5. Add regression tests

6. Update documentation

7. Record lessons learned

---

# Cursor Instructions

Before implementing any feature

1. Review authentication.

2. Review authorization.

3. Validate every input.

4. Protect sensitive information.

5. Review logging.

6. Review dependencies.

7. Add security tests where appropriate.

Security review is mandatory.

---

# Definition of Done

Security work is complete only when

✓ Authentication verified

✓ Authorization verified

✓ Validation implemented

✓ Sensitive data protected

✓ Security tests passing

✓ Documentation updated

✓ Repository remains secure

---

# Final Principle

Security is everyone's responsibility.

The safest code is code that assumes nothing, validates everything, exposes the minimum necessary information, and fails securely.