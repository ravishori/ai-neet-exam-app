# Code Review Standards
## AI NEET Exam App
### Enterprise Code Review Guide

Version: 1.0

---

# Purpose

This document defines the mandatory code review process for every implementation in the AI NEET Exam App.

Every change must undergo a self-review before it is considered complete.

Code review is not about finding mistakes.

It is about ensuring:

- Quality
- Maintainability
- Security
- Performance
- Readability
- Production readiness

---

# Golden Rule

Never consider code complete simply because it works.

Correct code is not necessarily good code.

Every implementation should be reviewed before completion.

---

# Review Philosophy

Review the implementation as if you are a Senior Staff Engineer reviewing a production Pull Request.

Ask:

- Would I confidently approve this?
- Would I deploy this to production?
- Would another engineer understand this in six months?

---

# Review Order

Review in this order

1. Requirements

2. Repository Consistency

3. Architecture

4. Business Logic

5. API

6. Database

7. Frontend

8. Testing

9. Security

10. Performance

11. Accessibility

12. Documentation

13. Git

---

# Step 1 — Requirements Review

Verify

✓ Original requirements satisfied

✓ Acceptance criteria met

✓ Edge cases handled

✓ Failure scenarios considered

Do not add speculative functionality.

---

# Step 2 — Repository Review

Confirm

Repository inspected before implementation.

No duplicate functionality introduced.

Existing services reused.

Existing components reused.

Architecture respected.

---

# Step 3 — Architecture Review

Verify

Module boundaries respected.

No unnecessary abstractions.

No duplicated services.

No architectural regressions.

No circular dependencies.

Architecture Freeze respected.

---

# Step 4 — Business Logic Review

Business rules belong inside services.

Verify

Business logic is not inside

Controllers

React Components

Pages

Database Models

Utility Classes

Logic should be cohesive.

---

# Step 5 — API Review

Verify

REST consistency

Validation

Error responses

Status codes

Authentication

Authorization

API documentation

Backward compatibility

---

# Step 6 — Database Review

Review

Schema changes

Relationships

Indexes

Constraints

Migrations

Naming

Queries

Never allow breaking schema changes without migrations.

---

# Step 7 — Frontend Review

Verify

Responsive

Accessible

Consistent

Dark Mode

Light Mode

Loading states

Empty states

Error handling

Component reuse

Avoid duplicated UI.

---

# Step 8 — Testing Review

Confirm

Unit Tests

Integration Tests

Regression Tests

Manual verification (if appropriate)

Review test quality

not just quantity.

---

# Step 9 — Security Review

Verify

Authentication

Authorization

Input validation

Output encoding

SQL Injection

XSS

CSRF

Rate Limiting

Secrets

Least Privilege

Sensitive data handling

---

# Step 10 — Performance Review

Review

Database queries

Indexes

Pagination

Caching

Bundle size

Rendering

Network requests

Background processing

Optimize only where evidence exists.

---

# Step 11 — Accessibility Review

Verify

Semantic HTML

Keyboard navigation

Screen reader compatibility

Focus management

Labels

Contrast

ARIA usage

Accessibility is mandatory.

---

# Step 12 — Documentation Review

Review whether implementation requires updates to

README

API documentation

Architecture documentation

Deployment documentation

ADRs

Release notes

Keep documentation synchronized.

---

# Step 13 — Git Review

Verify

Logical commits

Meaningful commit messages

Clean Git history

Only intended files staged

No temporary files committed

No secrets committed

---

# Code Quality Checklist

Review for

✓ Readability

✓ Maintainability

✓ Simplicity

✓ Consistency

✓ Reuse

✓ Naming

✓ Error handling

✓ Logging

✓ Validation

✓ Documentation

✓ Testability

---

# Common Review Questions

Can this code be simplified?

Is there duplicate logic?

Can an existing service be reused?

Does this follow repository standards?

Is the naming clear?

Is error handling sufficient?

Is the implementation secure?

Is the implementation testable?

Would another engineer understand this quickly?

---

# Review Outcomes

Approve

Implementation is production ready.

Approve with Minor Suggestions

Non-blocking improvements identified.

Request Changes

Blocking issues identified.

Do not approve until resolved.

---

# Definition of Done

A task is complete only when

✓ Requirements satisfied

✓ Architecture respected

✓ Tests passing

✓ Documentation updated

✓ Security reviewed

✓ Performance reviewed

✓ Accessibility verified

✓ Git history clean

✓ Ready for production

---

# Cursor Instructions

Before completing any engineering task

Perform a complete self-review using this document.

If any review item fails

Fix it before considering the task complete.

---

# Final Principle

Every review should leave the repository in a better state than before.

Code review is the final quality gate before production.