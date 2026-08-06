# Good Testing Reference Implementation
## AI NEET Exam App

---

# Purpose

This document defines the canonical testing approach for the AI NEET Exam App.

It provides guidance for writing reliable, maintainable, deterministic, and production-grade tests.

Repository implementation is the source of truth.

Every new feature should include appropriate automated tests.

---

# Testing Philosophy

Every test should be

✓ Independent

✓ Repeatable

✓ Deterministic

✓ Fast

✓ Readable

✓ Focused

✓ Maintainable

✓ CI-friendly

Tests should verify observable behavior rather than implementation details.

---

# Testing Pyramid

                End-to-End
             Integration Tests
               Unit Tests

Prioritize unit tests.

Use integration tests to verify collaboration.

Reserve end-to-end tests for critical user journeys.

---

# Test Folder Structure

apps/

backend/

tests/

unit/

integration/

fixtures/

factories/

mocks/

frontend/

src/

tests/

components/

pages/

hooks/

utils/

Keep test structure aligned with production code.

---

# Unit Testing

Use unit tests for

✓ Business logic

✓ Service layer

✓ Utility functions

✓ Validators

✓ Domain rules

Mock external dependencies.

Never access the real database in unit tests.

---

# Integration Testing

Verify interaction between

Router

↓

Service

↓

Repository

↓

Database

Use a dedicated test database.

Never use production data.

---

# API Testing

Every endpoint should verify

✓ Success response

✓ Authentication

✓ Authorization

✓ Validation errors

✓ Business rule failures

✓ Pagination

✓ Filtering

✓ Sorting

✓ Search

✓ Error responses

Use FastAPI TestClient or AsyncClient as appropriate.

---

# Frontend Testing

Use React Testing Library.

Test

✓ Rendering

✓ User interaction

✓ Forms

✓ Navigation

✓ Loading states

✓ Empty states

✓ Error states

✓ Accessibility

Avoid testing implementation details.

---

# AI Testing

Mock AI providers.

Verify

✓ Prompt construction

✓ Input validation

✓ Output parsing

✓ Retry behavior

✓ Timeout handling

✓ Fallback logic

Never call live AI services during automated tests.

---

# Database Testing

Use isolated databases.

Verify

✓ CRUD operations

✓ Relationships

✓ Constraints

✓ Transactions

✓ Rollbacks

✓ Migrations

Clean up data after each test.

---

# Fixtures

Use fixtures for

Database sessions

Users

Questions

Exams

Bookmarks

Authentication tokens

AI responses

Fixtures should be reusable and deterministic.

---

# Factories

Generate realistic test data.

Prefer factories over manually creating objects.

Avoid duplicated setup code.

---

# Mocking

Mock only external dependencies such as

AI providers

Email services

SMS services

Payment gateways

Cloud storage

Time-dependent operations

Do not mock internal business logic unnecessarily.

---

# Assertions

Assertions should verify

Expected output

Side effects

Database changes

Error conditions

Permission enforcement

Avoid excessive assertions in a single test.

---

# Edge Cases

Test

Empty input

Invalid input

Boundary values

Large datasets

Duplicate data

Expired tokens

Permission failures

Concurrent operations

---

# Error Handling

Verify

Correct exceptions

Correct HTTP status codes

User-friendly error messages

No internal implementation leakage

No stack traces exposed

---

# Performance Testing

Measure

API latency

Search performance

Database query efficiency

Memory usage (where practical)

Avoid introducing performance regressions.

---

# Accessibility Testing

Verify

Keyboard navigation

Screen reader compatibility

ARIA attributes

Color contrast (where automated tools are available)

Semantic HTML

---

# Security Testing

Verify

Authentication

Authorization

Input validation

SQL injection protection

XSS prevention

Rate limiting (where applicable)

Sensitive data handling

---

# CI/CD Requirements

Every Pull Request should execute

✓ Backend unit tests

✓ Backend integration tests

✓ Frontend tests

✓ Linting

✓ Type checking

✓ Build verification

The CI pipeline should fail if critical tests fail.

---

# Code Coverage

Prioritize coverage for

Business rules

Authentication

Authorization

AI workflows

Exam workflows

Scoring

Bookmarking

Progress tracking

Coverage percentage is not the primary goal.

Meaningful coverage is.

---

# Test Review Checklist

Reviewers should verify

✓ Tests are readable

✓ Tests are deterministic

✓ Appropriate fixtures used

✓ External services mocked

✓ Edge cases covered

✓ Regression scenarios included

✓ No flaky tests

✓ CI compatibility maintained

---

# Common Anti-Patterns

Never

❌ Depend on test execution order

❌ Share mutable state between tests

❌ Use production services

❌ Hardcode environment-specific values

❌ Sleep to wait for async operations

❌ Ignore cleanup

❌ Over-mock internal logic

❌ Write brittle assertions

---

# Example Test Workflow

Requirement

↓

Feature Specification

↓

Implementation

↓

Unit Tests

↓

Integration Tests

↓

API Tests

↓

Frontend Tests

↓

Regression Tests

↓

CI Pipeline

↓

Code Review

↓

Merge

---

# Cursor Instructions

When writing tests

1. Inspect the repository.
2. Reuse existing fixtures and factories.
3. Follow the testing pyramid.
4. Mock only external dependencies.
5. Cover success and failure scenarios.
6. Test edge cases.
7. Verify accessibility where applicable.
8. Ensure tests are deterministic.
9. Confirm CI compatibility.
10. Update documentation if testing strategy changes.

Never write tests that depend on execution order or external services.

---

# Final Principle

Tests are executable documentation.

A well-designed test suite provides confidence that the application behaves correctly today and continues to behave correctly as the codebase evolves.

Every test in the AI NEET Exam App should be reliable, maintainable, and focused on protecting business value rather than merely increasing coverage metrics.