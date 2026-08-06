# Architecture
## AI NEET Exam App
### Enterprise Software Architecture Guide

Version: 1.0

---

# Purpose

This document defines the architectural principles of the AI NEET Exam App.

It serves as the primary architectural reference for Cursor AI and future contributors.

This document explains:

- System architecture
- Design philosophy
- Module boundaries
- Architectural constraints
- Development principles

It does NOT replace the Architecture Decision Records (ADRs).

The ADRs remain the source of truth for individual architectural decisions.

---

# Architectural Vision

The platform is designed as an enterprise-grade educational ecosystem rather than a simple examination portal.

The architecture emphasizes:

- Modularity
- Scalability
- Maintainability
- Security
- Testability
- Extensibility
- Operational simplicity

Every implementation should preserve these qualities.

---

# Architecture Principles

The platform follows these principles:

✓ Modular Architecture

✓ API-First Design

✓ Separation of Concerns

✓ Clean Architecture

✓ Domain-Oriented Design

✓ Service-Based Backend

✓ Responsive Web Frontend

✓ Production-Ready Engineering

---

# High-Level Architecture

The application consists of four major layers.

────────────────────────────

Presentation Layer

────────────────────────────

Next.js

React

TypeScript

Responsive UI

Accessibility

Dark / Light Mode

Consumes backend APIs only.

Contains no business logic.

---

Application Layer

FastAPI

REST APIs

Authentication

Authorization

Validation

Workflow orchestration

Coordinates business services.

---

Domain Layer

Business logic.

Knowledge Units

Question Processing

Search

Learning

Assessment

Revision

Analytics

Content Management

Domain logic belongs here.

---

Infrastructure Layer

PostgreSQL

Docker

CI/CD

Logging

Monitoring

File Storage

Deployment

External integrations

Responsible for persistence and operations.

---

# Module Philosophy

Modules should remain independent.

Each module should have:

- clear responsibility
- well-defined interfaces
- minimal coupling

Avoid cross-module dependencies whenever possible.

---

# Existing Architectural Components

The repository already contains major architectural capabilities.

Examples include:

- Authentication
- Question Management
- Search
- Question Solving
- Knowledge Units
- AI Explanation
- Revision
- Flashcards
- Admin Portal
- Ingestion Pipeline

Always inspect existing modules before extending them.

---

# Repository Is The Source Of Truth

Architecture diagrams are helpful.

The repository is authoritative.

If documentation differs from implementation,

the repository wins.

Documentation should then be updated.

---

# Architecture Freeze

Architecture Freeze is currently active.

Cursor must assume the architecture is stable.

Do NOT

- redesign modules
- replace patterns
- introduce competing systems
- duplicate services

Only recommend architecture changes when:

implementation reveals

a genuine architectural blocker.

---

# Architectural Decision Records (ADR)

Major architectural decisions are documented separately.

Examples:

- Architecture evolution
- Ingestion pipeline
- Visual asset extraction
- CI/CD
- Knowledge Units

Before proposing changes:

Review existing ADRs.

Avoid contradicting previous decisions.

---

# Bounded Contexts

The platform naturally separates into bounded contexts.

Examples include:

Academic

Content

Assessment

Learning

Search

Revision

Administration

AI

Infrastructure

These contexts should remain loosely coupled.

---

# Separation of Concerns

Frontend

Responsible for presentation only.

Backend

Responsible for orchestration.

Domain

Responsible for business rules.

Infrastructure

Responsible for persistence and integrations.

Never mix responsibilities.

---

# Data Ownership

Every domain owns its own data.

Avoid:

Shared mutable state

Duplicate entities

Duplicate business logic

Conflicting sources of truth

---

# Service Design

Business logic belongs inside services.

Controllers remain thin.

Repositories manage persistence.

Avoid business logic inside:

Controllers

Pages

Components

Database models

---

# Database Philosophy

Database design should be:

Normalized

Consistent

Well-indexed

Migration-driven

Prefer additive schema evolution.

Never break existing production data.

---

# API Philosophy

APIs should be:

Predictable

Versionable

Documented

Validated

Secure

REST consistency should be maintained.

---

# Frontend Philosophy

The frontend should remain:

Responsive

Accessible

Fast

Consistent

Simple

Do not duplicate backend business logic.

---

# AI Philosophy

Artificial Intelligence assists learning.

AI should enhance:

Search

Explanation

Revision

Recommendations

Planning

Never allow AI to become the primary source of truth.

Educational correctness is always more important.

---

# Testing Philosophy

Every architectural component should be testable.

Testing includes:

Unit Tests

Integration Tests

End-to-End Tests

Regression Tests

Avoid architecture that cannot be tested.

---

# Security Architecture

Security is part of architecture.

Always consider:

Authentication

Authorization

Input Validation

Least Privilege

Secure Defaults

Secrets Management

Auditability

---

# Performance Philosophy

Optimize:

Database Queries

Search

Rendering

API Response

Caching

Avoid premature optimization.

Measure first.

Optimize second.

---

# Scalability Philosophy

Design for growth.

Support:

Large datasets

Concurrent users

Background jobs

Content expansion

Cloud deployment

Scalability should come from architecture,

not repeated rewrites.

---

# Documentation Philosophy

Architecture documentation must evolve with implementation.

Whenever architecture changes:

Update

- ADRs
- Architecture docs
- Related technical documentation

Never allow architecture documentation to drift from reality.

---

# Cursor Responsibilities

Before implementing any feature:

1. Read this document.

2. Review ADRs.

3. Inspect repository.

4. Verify architecture.

5. Respect module boundaries.

6. Reuse existing services.

7. Avoid duplication.

Only then begin implementation.

---

# Final Principle

Architecture exists to make future development easier.

Every change should improve the long-term maintainability of the platform.

If a proposed solution makes the architecture more complicated without delivering measurable value,

do not implement it.