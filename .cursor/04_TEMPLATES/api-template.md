# API Specification Template
## AI NEET Exam App

---

# API Information

**API ID:** API-XXXX

**API Name:**

**Version:** v1

**Status:**
- Draft
- Proposed
- Approved
- Implemented
- Deprecated

**Owner:**

**Reviewer:**

**Date:**

---

# 1. Executive Summary

Describe the purpose of this API.

Answer

• What problem does it solve?

• Which users or systems consume it?

• Why is it required?

Maximum 10 sentences.

---

# 2. Repository Review

Before implementing

Inspect

Existing endpoints

Existing routers

Services

Repositories

Database

Tests

OpenAPI

ADRs

Determine

Existing reusable implementation

Endpoints to reuse

Duplicate functionality

Repository standards

---

# 3. Business Context

Describe

Business need

Affected users

Related feature

Dependencies

Scope

---

# 4. Endpoint Information

HTTP Method

GET

POST

PUT

PATCH

DELETE

Route

/api/v1/...

Example

GET /api/v1/questions

---

# 5. Authentication

Authentication Required

Yes / No

Authentication Type

JWT

OAuth

API Key

Session

None

---

# 6. Authorization

Required Roles

Student

Teacher

Reviewer

Administrator

Super Admin

Document permissions.

---

# 7. Request Parameters

Document

Path Parameters

Query Parameters

Headers

Body

For every parameter include

Name

Type

Required

Validation

Default Value

Example

Description

---

# 8. Request Body

Provide schema.

Document

Fields

Types

Validation

Required fields

Constraints

Examples

---

# 9. Response

Document

Status Code

Response Body

Example

Success Response

Failure Response

Validation Errors

Authorization Errors

Unexpected Errors

---

# 10. Error Responses

Examples

400

401

403

404

409

422

429

500

For every error include

Meaning

Cause

Recommended client action

---

# 11. Validation Rules

Document

Required fields

Length limits

Ranges

Formats

Enums

Business validation

Cross-field validation

Avoid undocumented validation.

---

# 12. Database Impact

Inspect repository.

Document

Tables

Indexes

Relationships

Queries

Repositories

Migrations

Rollback impact

If no database changes

State

"No database changes."

---

# 13. Service Layer

Document

Business service

Repository

Dependencies

Validation

Logging

Caching

Background jobs

Reuse existing services whenever possible.

---

# 14. Performance

Expected request rate

Expected latency

Caching

Pagination

Filtering

Sorting

Compression

Streaming

Document performance expectations.

---

# 15. Search Support

If applicable

Document

Full-text search

Ranking

Pagination

Filtering

Future semantic search compatibility

If not applicable

State

"No search support."

---

# 16. AI Impact

If applicable

Document

LLM

Prompt generation

Knowledge Units

Embeddings

AI provider

Caching

Fallback

If none

State

"No AI impact."

---

# 17. Security Review

Authentication

Authorization

Input validation

Output encoding

Rate limiting

OWASP

Secrets

Sensitive data

Audit logging

File uploads

Review security implications.

---

# 18. Logging

Log

Request ID

Correlation ID

Errors

Audit events

Warnings

Avoid logging secrets.

---

# 19. Monitoring

Health

Latency

Error Rate

Request Count

Slow Requests

Success Rate

Metrics

Alerts

---

# 20. Testing

Document

Unit Tests

Integration Tests

API Tests

Regression Tests

Security Tests

Performance Tests

Mock requirements

Reuse existing fixtures.

---

# 21. Documentation

Update

OpenAPI

Swagger

README

Developer Guide

Architecture

Release Notes

ADRs (if applicable)

---

# 22. Deployment Impact

Docker

GitHub Actions

Environment Variables

Database Migration

Monitoring

Rollback

Coolify

Health Checks

---

# 23. Risks

Technical

Security

Performance

Operational

Migration

Business

Rank

Critical

High

Medium

Low

---

# 24. Acceptance Criteria

API is complete when

✓ Repository inspected

✓ Existing endpoints reviewed

✓ Authentication implemented

✓ Authorization implemented

✓ Validation complete

✓ Tests passing

✓ Documentation updated

✓ Monitoring added

✓ Logging verified

✓ Performance acceptable

---

# 25. Examples

Example Request

```http
GET /api/v1/questions?page=1&pageSize=20
Authorization: Bearer <JWT>
```

Example Success Response

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 0
}
```

Example Error

```json
{
  "error": "Unauthorized"
}
```

---

# 26. References

Repository files

Related ADRs

Feature Specification

Issues

Pull Requests

External documentation

---

# Cursor Instructions

Before implementing an API

1. Inspect the repository.
2. Search for similar endpoints.
3. Reuse existing routers and services.
4. Avoid duplicate APIs.
5. Follow REST conventions.
6. Review security implications.
7. Add comprehensive tests.
8. Update OpenAPI documentation.
9. Document performance expectations.
10. Verify backward compatibility.

---

# API Quality Checklist

✓ Repository inspected

✓ Existing endpoints reviewed

✓ REST compliant

✓ Authentication verified

✓ Authorization verified

✓ Validation documented

✓ Database impact reviewed

✓ Tests added

✓ Security reviewed

✓ Performance reviewed

✓ Documentation updated

✓ Monitoring considered

---

# Final Principle

Every API should be designed before implementation.

The API should integrate naturally with the repository, preserve architectural consistency, follow REST best practices, and provide a secure, performant, well-documented interface for both internal and external consumers.

Repository implementation remains the ultimate source of truth.