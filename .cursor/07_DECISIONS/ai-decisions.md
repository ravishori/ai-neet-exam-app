# AI Engineering Decisions
## AI NEET Exam App

Version: 1.0

Status: Active

Last Updated:

Owner: Engineering Team

---

# Purpose

This document records the long-term engineering decisions for the AI NEET Exam App.

Its purpose is to preserve architectural consistency, avoid repeated design debates, and provide clear guidance for both human developers and AI coding assistants.

Repository implementation is the ultimate source of truth.

If repository implementation conflicts with this document, investigate before changing either.

---

# Decision-Making Principles

When multiple implementation approaches are possible, prioritize:

1. Repository consistency
2. Simplicity
3. Maintainability
4. Testability
5. Security
6. Performance
7. Scalability
8. Developer productivity

Do not introduce complexity without measurable benefit.

---

# Architecture Decisions

## Decision: Layered Architecture

Status

Accepted

Reason

Provides clear separation of concerns.

Application Layers

Client

↓

API Router

↓

Service Layer

↓

Repository Layer

↓

Database

Rules

Business logic belongs in Services.

Persistence belongs in Repositories.

Routers remain thin.

Never bypass the Service Layer.

---

## Decision: Repository Pattern

Status

Accepted

Reason

Improves maintainability, testing, and database abstraction.

Repositories

Read

Write

Query

Persist

Repositories never contain business logic.

---

## Decision: Service Layer

Status

Accepted

Reason

Centralizes business rules.

Responsibilities

Business logic

Validation

Workflow orchestration

Transactions

External integrations

Services never return HTTP responses.

---

## Decision: FastAPI

Status

Accepted

Reason

Modern async framework

Automatic OpenAPI generation

Excellent typing support

Dependency Injection

Strong ecosystem

Do not replace FastAPI without a formal ADR.

---

## Decision: PostgreSQL

Status

Accepted

Reason

Reliable

ACID compliant

Excellent indexing

JSON support

Scalable

Production ready

Future migrations should continue targeting PostgreSQL.

---

## Decision: SQLAlchemy ORM

Status

Accepted

Reason

Strong ORM ecosystem

Alembic integration

Database abstraction

Maintainability

Avoid raw SQL unless profiling demonstrates necessity.

---

## Decision: Alembic

Status

Accepted

Reason

Version-controlled schema migrations.

All schema changes must use Alembic.

Never modify production migrations after release.

---

# Frontend Decisions

## Decision: Next.js

Status

Accepted

Reason

Modern React framework

Performance

Routing

SEO

Developer experience

Future frontend work should follow Next.js conventions.

---

## Decision: TypeScript

Status

Mandatory

Reason

Type safety

Maintainability

Tooling

Avoid using "any".

Explicit typing is preferred.

---

## Decision: Tailwind CSS

Status

Accepted

Reason

Reusable design system

Rapid development

Consistency

Avoid inline CSS unless absolutely necessary.

---

## Decision: React Query

Status

Accepted

Reason

Server state management

Caching

Automatic refetching

Optimistic updates

Avoid custom caching unless justified.

---

## Decision: React Hook Form

Status

Accepted

Reason

Performance

Validation

Accessibility

Forms should use project validation standards.

---

# AI Platform Decisions

## Decision: AI Provider Abstraction

Status

Mandatory

Reason

Avoid vendor lock-in.

Application code should depend on an abstraction layer rather than a specific AI provider.

Providers should be replaceable.

---

## Decision: Knowledge Units

Status

Accepted

Reason

Versioned educational content.

Knowledge Units are the smallest reusable learning asset.

Future learning features should build upon Knowledge Units.

---

## Decision: Prompt Templates

Status

Mandatory

Reason

Prompt logic should remain centralized.

Never embed prompts inside routers or UI components.

---

## Decision: AI Calls

Status

Accepted

Rules

Validate input

Retry safely

Support fallback

Log failures

Protect API keys

Never expose provider credentials.

---

# Security Decisions

Authentication

JWT

Authorization

Role-Based Access Control (RBAC)

Validation

Server-side mandatory

Secrets

Environment variables only

Logging

No sensitive data

OWASP review required

Security takes precedence over convenience.

---

# Database Decisions

Naming

Consistent

Explicit

Descriptive

Indexes

Only where justified

Constraints

Prefer database constraints in addition to application validation.

Migrations

Small

Reviewable

Reversible

---

# API Decisions

REST-first

Versioned

Typed requests

Typed responses

Consistent error handling

OpenAPI maintained

Backward compatibility preferred

Never expose ORM models directly.

---

# Frontend Decisions

Accessibility

WCAG 2.2 AA

Responsive design

Mandatory

Dark Mode

Supported

Loading

Required

Error states

Required

Empty states

Required

---

# Testing Decisions

Testing Pyramid

Unit

↓

Integration

↓

End-to-End

Mock only external services.

Do not mock core business logic.

CI must execute automated tests.

---

# DevOps Decisions

Docker

Mandatory

GitHub Actions

Mandatory

Environment variables

Documented

Health checks

Required

Rollback

Documented

Monitoring

Required

---

# Cursor Decisions

Cursor must

Inspect repository before implementation

Search for reusable code

Avoid duplication

Respect ADRs

Update documentation

Add tests

Preserve architecture

Cursor must never

Invent architecture

Duplicate business logic

Ignore repository conventions

Modify unrelated modules

Claim implementation without repository evidence

---

# Decision Review Process

Every major engineering decision should include

Decision

Reason

Alternatives considered

Trade-offs

Status

Date

Owner

Related ADR

---

# Deprecated Decisions

Record superseded decisions here.

Never delete historical architectural decisions.

---

# Future Review

Review this document when

Technology stack changes

Architecture changes

Major refactoring

Database migration

AI provider replacement

Security architecture changes

---

# Cursor Instructions

Before implementing any feature

1. Inspect the repository.
2. Review this document.
3. Review ADRs.
4. Preserve existing architecture.
5. Reuse existing implementation.
6. Avoid unnecessary abstraction.
7. Add tests.
8. Update documentation.
9. Record new long-term decisions here when appropriate.
10. Never contradict repository implementation without an approved ADR.

---

# Final Principle

Architecture is a long-term asset.

Consistency is more valuable than novelty.

Every engineering decision should make the AI NEET Exam App easier to understand, easier to maintain, easier to test, and easier to evolve.

Human developers and AI assistants should make decisions using the same engineering principles so the repository continues to feel like it was built by one cohesive team.