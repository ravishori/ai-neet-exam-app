# Pull Request Template
## AI NEET Exam App

---

# Pull Request Information

**PR Title:**

**PR Number:**

**Feature / Bug ID:**

**Branch:**

**Target Branch:**

**Author:**

**Reviewer(s):**

**Date:**

---

# 1. Executive Summary

Provide a concise summary.

Answer

• What is changing?

• Why is it changing?

• What problem does it solve?

Maximum 10 sentences.

---

# 2. Related Work

Link related artifacts.

Feature Specification

ADR(s)

Issue(s)

Bug Report(s)

Previous PR(s)

Sprint

Release

---

# 3. Repository Inspection

Before implementation

Inspect

Repository

Existing implementation

Existing APIs

Existing Components

Existing Services

Existing Tests

Existing ADRs

Document

What was reused

What was modified

What remains unchanged

---

# 4. Scope of Changes

## Added

-

-

-

## Modified

-

-

-

## Removed

-

-

-

Clearly describe all repository changes.

---

# 5. Architecture Review

Verify

Repository architecture preserved

Layer boundaries respected

Module responsibilities maintained

ADR compliance verified

Dependency direction unchanged

If architecture changed

Reference ADR.

---

# 6. Database Impact

Document

Tables affected

Indexes

Relationships

Repositories

Alembic migrations

Rollback considerations

If none

State

"No database changes."

---

# 7. API Impact

Document

New endpoints

Modified endpoints

Deprecated endpoints

Authentication

Authorization

Validation

OpenAPI updates

Backward compatibility

If none

State

"No API changes."

---

# 8. Frontend Impact

Document

Pages

Layouts

Components

Dialogs

Forms

Tables

Navigation

Dark Mode

Accessibility

Responsive design

Reuse existing components whenever possible.

---

# 9. AI Impact

Document

Prompt changes

AI services

Knowledge Units

Embeddings

Search

LLM integration

Caching

Fallback behaviour

If none

State

"No AI impact."

---

# 10. Security Review

Verify

Authentication

Authorization

Validation

Secrets

OWASP considerations

Input sanitization

Output encoding

Rate limiting

Audit logging

Document findings.

---

# 11. Performance Review

Review

Database

Indexes

Queries

Caching

Rendering

Bundle size

Search

Background jobs

Memory

CPU

Expected performance impact.

---

# 12. Accessibility Review

Verify

Keyboard navigation

ARIA

Focus management

Semantic HTML

Responsive layout

Dark Mode

WCAG AA

Document accessibility impact.

---

# 13. Testing

Document

Unit Tests

Integration Tests

API Tests

Frontend Tests

Regression Tests

Security Tests

Performance Tests

Accessibility Tests

Include

Number of tests

Pass/Fail

Coverage impact

---

# 14. Documentation

Updated

README

Architecture

API

Deployment

Release Notes

ADRs

Developer Guide

User Guide

If none

State

"No documentation updates."

---

# 15. Deployment Impact

Review

Docker

GitHub Actions

Environment Variables

Database Migration

Coolify

Monitoring

Logging

Observability

Rollback

Health Checks

If none

State

"No deployment impact."

---

# 16. Risks

Technical

Business

Security

Performance

Operational

Migration

Rank

Critical

High

Medium

Low

---

# 17. Rollback Plan

Describe

Rollback steps

Database rollback

Deployment rollback

Recovery validation

Monitoring after rollback

---

# 18. Validation Results

Verify

✓ Build passes

✓ Lint passes

✓ Type checking passes

✓ Backend tests pass

✓ Frontend tests pass

✓ CI/CD passes

✓ Deployment verified (if applicable)

Document evidence.

---

# 19. Reviewer Checklist

Architecture

☐ Repository inspected

☐ ADR compliant

☐ No duplicate implementation

Backend

☐ Services reviewed

☐ APIs reviewed

☐ Validation reviewed

Database

☐ Schema reviewed

☐ Migrations reviewed

Frontend

☐ UI reviewed

☐ Accessibility reviewed

☐ Responsive verified

Security

☐ Authentication

☐ Authorization

☐ Input validation

☐ Secrets

Performance

☐ Queries

☐ Rendering

☐ Search

Testing

☐ Unit

☐ Integration

☐ Regression

Documentation

☐ Updated

Deployment

☐ Rollback verified

☐ Monitoring verified

---

# 20. Merge Readiness

Status

☐ Ready to Merge

☐ Ready with Minor Changes

☐ Requires Major Changes

☐ Blocked

Explain decision.

---

# References

Repository files

Feature Specification

ADR(s)

Issue(s)

Pull Request(s)

Release Notes

Documentation

---

# Cursor Instructions

Before generating a Pull Request

1. Inspect repository.

2. Review Feature Specification.

3. Review ADRs.

4. Review implementation.

5. Verify tests.

6. Verify documentation.

7. Review security.

8. Review performance.

9. Review accessibility.

10. Confirm deployment readiness.

Never claim merge readiness without evidence.

---

# Pull Request Quality Checklist

✓ Repository inspected

✓ Existing implementation reviewed

✓ Architecture preserved

✓ ADRs reviewed

✓ Database reviewed

✓ APIs reviewed

✓ Frontend reviewed

✓ Security reviewed

✓ Performance reviewed

✓ Accessibility reviewed

✓ Tests passing

✓ Documentation updated

✓ Deployment reviewed

✓ Rollback documented

---

# Final Principle

Every Pull Request should explain not only *what* changed, but *why* it changed, *how* it was validated, and *what impact* it has on the repository.

A reviewer should be able to approve or reject the change based solely on this document, without making assumptions.