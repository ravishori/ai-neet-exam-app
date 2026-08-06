# Good API Reference Implementation
## AI NEET Exam App

---

# Purpose

This document defines the canonical REST API implementation pattern for the AI NEET Exam App.

It serves as the reference implementation that Cursor should imitate whenever creating or modifying APIs.

Repository implementation is the source of truth.

Consistency is more important than personal coding style.

---

# API Design Principles

Every API should be

✓ RESTful

✓ Predictable

✓ Stateless

✓ Secure

✓ Versioned

✓ Documented

✓ Tested

✓ Observable

✓ Backward compatible whenever practical

---

# Standard Architecture

Client

↓

FastAPI Router

↓

Authentication

↓

Authorization

↓

Request Validation

↓

Service Layer

↓

Repository Layer

↓

SQLAlchemy ORM

↓

PostgreSQL

Never bypass the Service Layer.

Business logic belongs in services.

Database access belongs in repositories.

---

# Folder Structure

apps/backend/app/

api/

services/

repositories/

schemas/

models/

core/

dependencies/

tests/

Maintain this separation of responsibilities.

---

# API Lifecycle

Every endpoint should follow this sequence

1. Receive request

2. Authenticate user

3. Authorize action

4. Validate request

5. Execute business logic

6. Call repository

7. Commit transaction if required

8. Return typed response

9. Log important events

10. Handle errors consistently

---

# Routing Guidelines

Use

/api/v1/

Examples

GET /api/v1/questions

GET /api/v1/questions/{id}

POST /api/v1/questions

PUT /api/v1/questions/{id}

PATCH /api/v1/questions/{id}

DELETE /api/v1/questions/{id}

Never expose internal implementation details in URLs.

Use plural resource names.

---

# Request Models

Use dedicated Pydantic models.

Separate

CreateRequest

UpdateRequest

SearchRequest

ResponseModel

Never expose ORM models directly.

---

# Response Models

Always return typed responses.

Include

Success responses

Validation errors

Authentication errors

Authorization errors

Unexpected errors

Avoid returning raw dictionaries.

---

# Authentication

Use repository authentication framework.

Protect endpoints appropriately.

Never duplicate authentication logic.

Never trust client identity.

---

# Authorization

Authorization belongs after authentication.

Verify

Role

Ownership

Permissions

Least privilege

Never rely on frontend authorization.

---

# Validation

Validate

Required fields

Ranges

Enums

Business rules

File uploads

Never trust client input.

Validation belongs in Pydantic models and service layer.

---

# Business Logic

Business logic belongs in services.

Examples

Question generation

Bookmark management

Exam submission

Progress calculation

AI explanation generation

Never place business logic inside routers.

---

# Repository Pattern

Repositories

Read data

Write data

Handle ORM

No business logic.

Repositories should be reusable.

---

# Transactions

Use transactions for write operations.

Avoid partial writes.

Rollback on failure.

---

# Error Handling

Return consistent HTTP status codes.

Examples

200 OK

201 Created

204 No Content

400 Bad Request

401 Unauthorized

403 Forbidden

404 Not Found

409 Conflict

422 Validation Error

500 Internal Server Error

Never expose stack traces.

---

# Logging

Log

Authentication failures

Authorization failures

Administrative actions

Business events

Unexpected exceptions

Never log

Passwords

JWTs

Secrets

Sensitive personal information

---

# Pagination

Collections should support

Page

Page Size

Sorting

Filtering

Search

Large datasets should never be returned without pagination.

---

# Search

Search endpoints should support

Filtering

Sorting

Pagination

Full-text search

Future semantic search compatibility

Avoid duplicate search implementations.

---

# AI Integration

AI calls should

Validate input

Use approved provider abstraction

Handle timeouts

Support fallback behaviour

Never expose API keys

Never place prompt templates inside routers

---

# Dependency Injection

Use FastAPI dependency injection.

Avoid global state.

Inject

Current User

Services

Repositories

Configuration

Database session

---

# Async Best Practices

Use async only where appropriate.

Avoid blocking I/O.

Avoid synchronous database operations inside async routes.

Keep async chains consistent.

---

# Security

Review

Authentication

Authorization

OWASP API Top 10

Rate limiting

Input validation

Output encoding

Audit logging

Secrets management

---

# Performance

Prefer

Indexes

Pagination

Small payloads

Efficient queries

Caching where justified

Streaming for large responses

Avoid

N+1 queries

Duplicate queries

Repeated calculations

Premature optimization

---

# Documentation

Every endpoint should include

Summary

Description

Tags

Request model

Response model

Error responses

Authentication requirements

OpenAPI documentation should remain complete.

---

# Testing Expectations

Every endpoint should have

Unit tests

Integration tests

Authentication tests

Authorization tests

Validation tests

Regression tests

Edge-case tests

Mock external AI providers where applicable.

---

# Example API Flow

HTTP Request

↓

FastAPI Router

↓

Authentication

↓

Authorization

↓

Request Validation

↓

Service Layer

↓

Repository

↓

Database

↓

Response Model

↓

HTTP Response

---

# Code Review Expectations

Reviewers should verify

✓ Repository inspected

✓ Existing API reused where possible

✓ REST conventions followed

✓ Typed request models

✓ Typed response models

✓ Authentication verified

✓ Authorization verified

✓ Validation complete

✓ Business logic in services

✓ Repository pattern respected

✓ Tests added

✓ OpenAPI updated

✓ Documentation updated

---

# Common Anti-Patterns

Never

❌ Place SQL in routers

❌ Place business logic in routers

❌ Return ORM models directly

❌ Duplicate endpoints

❌ Hardcode secrets

❌ Skip validation

❌ Ignore authorization

❌ Return inconsistent responses

❌ Break REST conventions

❌ Bypass repository pattern

---

# Cursor Instructions

When implementing or modifying an API

1. Inspect the repository.
2. Search for existing endpoints.
3. Reuse services and repositories.
4. Preserve architecture.
5. Follow REST conventions.
6. Use typed request and response models.
7. Keep business logic in services.
8. Keep persistence in repositories.
9. Add tests.
10. Update OpenAPI documentation.

Never redesign architecture without an ADR.

---

# Final Principle

A well-designed API is predictable, secure, maintainable, testable, and consistent.

Every API in the AI NEET Exam App should look as though it was written by the same engineering team, regardless of whether it was authored by a human developer or generated with AI.

Consistency is a feature.