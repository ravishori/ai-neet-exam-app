# Technology Stack
## AI NEET Exam App
### Official Technology Stack & Engineering Standards

Version: 1.0

---

# Purpose

This document defines the official technology stack used throughout the AI NEET Exam App.

It serves as the single technical reference for Cursor AI and contributors.

Before introducing any new library, framework, or infrastructure component:

1. Inspect the repository.
2. Verify whether the capability already exists.
3. Reuse existing technologies whenever practical.
4. Avoid unnecessary dependencies.

Repository implementation always takes precedence over this document.

---

# Architecture Overview

Architecture Style

- Modular Monolith
- API-First
- Service-Oriented Backend
- Clean Architecture Principles
- Domain-Oriented Design
- Repository Pattern
- Dependency Injection

Current status

Production-oriented architecture.

Architecture Freeze is active.

---

# Frontend

Framework

Next.js

Language

TypeScript

UI Library

React

Routing

Next.js App Router

Styling

Repository Design System

Responsive Design

Desktop

Tablet

Mobile

Theme

Light Mode

Dark Mode

Accessibility

WCAG-oriented implementation

Testing

Vitest

React Testing Library

Linting

ESLint

Formatting

Repository standard

Do not introduce alternative frontend frameworks.

Do not introduce Flutter.

Do not introduce Angular.

Do not introduce Vue.

---

# Backend

Framework

FastAPI

Language

Python

Architecture

Layered

Services

Repositories

Dependency Injection

Validation

Pydantic

Authentication

Repository implementation

Authorization

Role-based access where implemented

Background Processing

FastAPI BackgroundTasks

Avoid introducing Celery unless justified by an ADR.

---

# Database

Database

PostgreSQL

Migration Tool

Alembic

Database Access

SQLAlchemy

Repository Pattern

Preferred

Normalization

Preferred

Indexes

Required for frequently queried fields

Never bypass migrations.

Never modify production schema manually.

---

# Search

Current

PostgreSQL Full-Text Search

GIN Indexes

Repository implementation

Future

pgvector (planned)

Semantic Search

AI-assisted Retrieval

These require a future ADR before implementation.

---

# Artificial Intelligence

Current AI capabilities

Question explanations

Content generation support

Knowledge Unit generation

Ingestion assistance

Future

Adaptive learning

Semantic recommendations

Knowledge Graph reasoning

AI tutoring

Only introduce new AI providers after repository review.

Keep AI provider abstraction centralized.

---

# Document Intelligence

Supported

PDF ingestion

Knowledge extraction

Visual asset extraction

Question extraction

Explanation extraction

Current architecture follows the existing ingestion pipeline.

Avoid introducing alternative document processing frameworks without ADR approval.

---

# API Standards

Architecture

REST

Validation

Pydantic

Error Responses

Consistent JSON

Authentication

Repository implementation

Versioning

Repository convention

Do not mix REST with GraphQL without ADR approval.

---

# Security

Authentication

Repository implementation

Authorization

Role-based

Password Storage

Secure hashing

Secrets

Environment Variables

HTTPS

Production deployments

Input Validation

Mandatory

Output Encoding

Mandatory

Never hardcode secrets.

Never commit credentials.

---

# File Storage

Current

Repository implementation

Local storage where configured

Future

Object Storage

Azure Blob

AWS S3

Google Cloud Storage

Requires ADR before implementation.

---

# Testing

Backend

pytest

Frontend

Vitest

React Testing Library

Quality

Regression Tests

Integration Tests

Unit Tests

Repository currently maintains a high level of automated coverage.

New features should include corresponding tests.

---

# Quality Tools

Python

ruff

Type Checking

TypeScript compiler

Frontend

ESLint

CI

GitHub Actions

Security

pip-audit

CodeQL

gitleaks

Dependabot

These tools should remain part of the development workflow.

---

# DevOps

Containerization

Docker

CI/CD

GitHub Actions

Deployment

Coolify

Target Infrastructure

Linux

Production VPS

Current deployment documentation is located under docs/deploy.

---

# Monitoring

Current

Application logging

Health checks

CI validation

Future

Metrics

Tracing

Advanced monitoring

Requires ADR before implementation.

---

# Configuration

Environment variables

Required

Secrets

Never committed

Configuration

Environment-specific

Use .env files only for local development.

---

# Dependencies

Before adding a dependency

Verify

Existing repository capability

Maintenance quality

Community support

Security

License

Long-term support

Avoid dependency duplication.

---

# Repository Preferences

Preferred

FastAPI

Next.js

TypeScript

PostgreSQL

Docker

GitHub Actions

Pytest

Vitest

Alembic

SQLAlchemy

Pydantic

ruff

Avoid replacing these technologies unless justified by a new ADR.

---

# Technology Evaluation Process

Before adopting any new technology

Repository inspection

↓

Existing capability review

↓

Alternative evaluation

↓

Prototype (if required)

↓

ADR (if architectural)

↓

Approval

↓

Implementation

Never adopt technology because it is fashionable.

Adopt technology only when it provides measurable value.

---

# Cursor Instructions

Before writing code

1. Review this document.

2. Verify repository implementation.

3. Reuse existing technologies.

4. Avoid introducing unnecessary frameworks.

5. Respect Architecture Freeze.

6. Recommend an ADR if a new technology changes architecture.

---

# Final Principle

Technology is a means to deliver reliable educational software.

Choose stability, maintainability, and long-term support over novelty.

The repository should remain consistent, understandable, and production-ready for many years.