# API Guidelines
## AI NEET Exam App
### Enterprise REST API Standards

Version: 1.0

---

# Purpose

This document defines the official API standards for the AI NEET Exam App.

Every API should be:

- Consistent
- Secure
- Versionable
- Well documented
- Testable
- Backward compatible

The repository is the source of truth.

Always inspect existing APIs before creating new ones.

---

# API Philosophy

The platform follows an API-first architecture.

Frontend applications communicate only through backend APIs.

Business logic belongs inside backend services.

APIs should orchestrate business logic rather than contain it.

---

# Repository First

Before creating a new endpoint

Inspect

- Existing routers
- Existing services
- Existing schemas
- Existing repositories
- Existing OpenAPI documentation
- Existing tests

Reuse existing APIs whenever practical.

Never duplicate endpoints.

---

# REST Principles

Use REST conventions consistently.

Resources should be represented as nouns.

Good

/questions

/practice-sessions

/mock-exams

/concepts

/documents

Bad

/getQuestions

/createQuestion

/deleteQuestion

/searchQuestionByKeyword

Use HTTP methods instead.

---

# HTTP Methods

GET

Read data

POST

Create resources

PUT

Replace an existing resource

PATCH

Partial update

DELETE

Remove a resource

Avoid using POST for updates unless justified.

---

# URL Design

Use lowercase.

Use hyphens where needed.

Examples

/api/questions

/api/questions/{id}

/api/practice-sessions

/api/search

Avoid

CamelCase

MixedCase

Verb-based URLs

---

# Resource Relationships

Examples

/questions/{id}

/questions/{id}/explanations

/chapters/{id}/topics

/topics/{id}/concepts

Keep nesting shallow.

Avoid deeply nested routes.

---

# API Versioning

Current approach

Repository implementation

Future recommendation

/api/v1/

If versioning becomes necessary,

introduce it through an ADR.

Avoid unnecessary version proliferation.

---

# Request Validation

Use Pydantic models.

Validate

Required fields

Formats

Ranges

Enums

Business constraints

Never trust client input.

Reject invalid requests with clear errors.

---

# Response Standards

Every response should be predictable.

Success

{
    "success": true,
    "data": { ... }
}

Error

{
    "success": false,
    "error": {
        "code": "...",
        "message": "...",
        "details": [...]
    }
}

Maintain consistency across endpoints.

---

# HTTP Status Codes

200

OK

201

Created

204

No Content

400

Bad Request

401

Unauthorized

403

Forbidden

404

Not Found

409

Conflict

422

Validation Error

429

Too Many Requests

500

Internal Server Error

Use the correct status code.

Avoid returning HTTP 200 for errors.

---

# Pagination

Large collections must support pagination.

Preferred parameters

?page=

&page_size=

or repository convention.

Return

Current page

Page size

Total records

Total pages

Never return unbounded datasets.

---

# Filtering

Support filtering where appropriate.

Examples

subject

chapter

difficulty

year

question_type

status

Filters should be optional.

---

# Sorting

Support sorting.

Examples

sort_by

sort_order

Use consistent parameter names.

---

# Search

Use dedicated search endpoints where appropriate.

Examples

/queries/search

/questions/search

Avoid overloading list endpoints with excessive search logic.

Leverage existing PostgreSQL full-text search implementation.

---

# Authentication

Authentication should be handled centrally.

Avoid custom authentication logic inside individual endpoints.

Support repository authentication mechanism.

Never expose sensitive information.

---

# Authorization

Authorization belongs in the service layer or middleware.

Verify

Roles

Permissions

Ownership

Least privilege

Never trust client claims.

---

# Error Handling

Return structured errors.

Include

Error code

Human-readable message

Relevant validation details

Avoid exposing internal implementation details.

Never return stack traces to clients.

---

# Idempotency

GET

PUT

DELETE

should be idempotent.

POST generally creates new resources.

Document exceptions.

---

# File Uploads

Validate

Content type

Size

Extension

Virus scanning (future)

Store files securely.

Never trust filenames from clients.

---

# Background Operations

Long-running tasks should return immediately.

Provide

Job identifier

Status endpoint

Progress (where appropriate)

Avoid blocking HTTP requests.

---

# Rate Limiting

Protect endpoints against abuse.

Examples

Authentication

Search

AI endpoints

File uploads

Document repository strategy.

---

# Logging

Log

Request identifiers

Warnings

Errors

Audit events

Never log

Passwords

Tokens

Secrets

Personally sensitive information

---

# API Documentation

Every endpoint should include

Summary

Description

Parameters

Request schema

Response schema

Status codes

Examples

Use FastAPI OpenAPI generation.

Keep documentation synchronized.

---

# Testing

Every API should have

Unit tests

Integration tests

Validation tests

Authorization tests

Regression tests

Test success and failure scenarios.

---

# Backward Compatibility

Avoid breaking existing clients.

Prefer

Additive changes

Optional fields

New endpoints

If a breaking change is unavoidable,

document it

and create an ADR if architectural.

---

# Security Checklist

Verify

Authentication

Authorization

Validation

Input sanitization

Output encoding

Rate limiting

Secure defaults

Audit logging

Least privilege

---

# Performance Checklist

Review

Database queries

Indexes

Pagination

Caching

Payload size

N+1 queries

Large joins

Optimize based on evidence.

---

# Cursor Instructions

Before creating an API

1. Inspect existing routes.

2. Inspect services.

3. Inspect schemas.

4. Reuse existing endpoints where practical.

5. Validate requests.

6. Return consistent responses.

7. Add tests.

8. Update OpenAPI documentation.

9. Review security.

10. Review performance.

Never create duplicate APIs.

---

# Definition of Done

An API implementation is complete only when

✓ Repository inspected

✓ Endpoint follows REST principles

✓ Validation implemented

✓ Authentication reviewed

✓ Authorization reviewed

✓ Tests passing

✓ Documentation updated

✓ Security reviewed

✓ Performance reviewed

✓ Backward compatibility preserved

---

# Final Principle

APIs are long-term contracts with clients.

Design them carefully.

A well-designed API should remain stable, predictable, and easy to evolve without breaking existing integrations.