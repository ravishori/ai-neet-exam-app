# Good FastAPI Service Reference Implementation
## AI NEET Exam App

---

# Purpose

This document defines the canonical Service Layer implementation for the AI NEET Exam App.

It explains how business logic should be organized, how services interact with repositories, and how Cursor should structure all new service classes.

The repository implementation is always the source of truth.

Business logic belongs in services.

Services should never contain HTTP concerns or database implementation details.

---

# Service Layer Responsibilities

A service is responsible for

✓ Business rules

✓ Domain validation

✓ Workflow orchestration

✓ Transaction coordination

✓ Calling repositories

✓ Calling AI services

✓ Calling external services

✓ Logging business events

✓ Raising domain-specific exceptions

Services should NOT

✗ Handle HTTP requests

✗ Define API routes

✗ Execute SQL directly

✗ Know UI details

✗ Return HTTP responses

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

Every request should pass through the service layer.

---

# Folder Structure

apps/backend/app/

services/

question_service.py

user_service.py

bookmark_service.py

exam_service.py

admin_service.py

ai_service.py

Repositories should remain separate.

---

# Dependency Injection

Services should receive dependencies through FastAPI's dependency injection.

Typical dependencies

• Repository

• Database session

• Configuration

• AI Gateway

• Search service

• Logger

Never instantiate repositories directly inside services.

---

# Business Logic

Business logic belongs only here.

Examples

Generate AI explanations

Submit exams

Calculate scores

Bookmark questions

Generate analytics

Update progress

Publish question bank

Never place these in routers.

---

# Validation Strategy

Validation occurs in three layers

1.

Pydantic

Request validation

2.

Service

Business rule validation

3.

Repository

Database integrity

Example

Pydantic

✓ Email format

Service

✓ User already exists

Repository

✓ Unique constraint

---

# Repository Interaction

Services call repositories.

Repositories never call services.

Services may coordinate multiple repositories.

Example

QuestionRepository

↓

BookmarkRepository

↓

ProgressRepository

↓

AnalyticsRepository

Repositories remain persistence-only.

---

# Transaction Management

Write operations should be transactional.

Examples

Create Question

Submit Exam

Publish Question Bank

Create User

If one operation fails

Rollback

Never leave partial writes.

---

# Read Operations

Read operations should

Reuse repositories

Support pagination

Support filtering

Support sorting

Support search

Avoid duplicate queries

Avoid unnecessary joins

---

# Async Best Practices

Use async consistently.

Avoid

Blocking I/O

Mixing sync and async unnecessarily

Long-running synchronous work

Move expensive processing into background tasks where appropriate.

---

# Exception Handling

Services raise domain exceptions.

Routers convert exceptions into HTTP responses.

Example

QuestionNotFoundError

DuplicateUserError

PermissionDeniedError

InvalidExamSubmissionError

Never raise HTTPException inside services unless repository conventions require it.

---

# Logging

Services log

Business events

Administrative actions

Warnings

Unexpected failures

Examples

Question published

Exam submitted

Bookmark created

AI explanation generated

Never log

Passwords

JWTs

Secrets

Sensitive personal information

---

# Security

Service layer enforces

Authorization

Ownership

Business permissions

Repository should never decide permissions.

Example

Student owns bookmark

Administrator may publish content

Reviewer may approve questions

---

# AI Integration

AI services should be abstracted.

Service layer should

Prepare prompt input

Validate data

Call provider abstraction

Handle retries

Handle timeout

Handle fallback

Never place prompts inside routers.

Never expose provider credentials.

---

# Search Integration

Service layer coordinates

Search

Filtering

Ranking

Embeddings

Knowledge Units

Future semantic search

Search implementation should remain replaceable.

---

# Performance

Prefer

Repository reuse

Bulk operations

Indexes

Caching where justified

Small payloads

Streaming where appropriate

Avoid

N+1 queries

Repeated calculations

Duplicate repository calls

Premature optimization

---

# Testing Expectations

Every service should have

✓ Unit tests

✓ Integration tests

✓ Mocked external dependencies

✓ Failure path tests

✓ Validation tests

✓ Permission tests

Business logic should be independently testable.

---

# Service Lifecycle

Request

↓

Router

↓

Authentication

↓

Authorization

↓

Validation

↓

Service

↓

Repositories

↓

Database

↓

Result

↓

Router

↓

Response Model

---

# Code Review Expectations

Reviewers should verify

✓ Business logic belongs in service

✓ No SQL in service

✓ Repository reused

✓ Dependency Injection used

✓ Validation complete

✓ Transactions correct

✓ Logging appropriate

✓ Security enforced

✓ AI integration abstracted

✓ Tests added

---

# Common Anti-Patterns

Never

❌ Put SQL in services

❌ Put HTTP logic in services

❌ Instantiate repositories manually

❌ Duplicate business logic

❌ Skip validation

❌ Skip transactions

❌ Log secrets

❌ Call AI providers directly from routers

❌ Mix presentation with domain logic

---

# Cursor Instructions

When creating or modifying a service

1. Inspect the repository.
2. Search for an existing service.
3. Reuse repositories.
4. Keep business logic in the service.
5. Use dependency injection.
6. Validate business rules.
7. Coordinate transactions.
8. Raise domain exceptions.
9. Add comprehensive tests.
10. Update documentation if behavior changes.

Never redesign architecture without an approved ADR.

---

# Final Principle

The Service Layer is the heart of the application's business logic.

A well-designed service is reusable, testable, secure, transaction-safe, and independent of HTTP or database implementation details.

Every service in the AI NEET Exam App should follow a consistent structure so that any developer—or AI assistant—can understand, maintain, and extend it with confidence.