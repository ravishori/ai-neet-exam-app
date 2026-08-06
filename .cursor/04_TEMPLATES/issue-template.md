# Engineering Issue Template
## AI NEET Exam App

---

# Issue Information

**Issue ID:** ISSUE-XXXX

**Title:**

**Type:**

- Bug
- Feature Request
- Enhancement
- Performance
- Security
- Technical Debt
- Documentation
- Infrastructure
- Research
- Spike

**Priority:**

- Critical
- High
- Medium
- Low

**Severity:**

- Critical
- Major
- Minor
- Trivial

**Status:**

- New
- Triaged
- Approved
- In Progress
- Blocked
- In Review
- Testing
- Completed
- Closed

**Reported By:**

**Assigned To:**

**Reviewer:**

**Date Created:**

**Target Release:**

---

# 1. Executive Summary

Provide a concise description of the issue.

Answer

• What is the problem?

• Why does it matter?

• Who is affected?

Maximum 10 sentences.

---

# 2. Repository Inspection

Before any implementation

Inspect

Repository

Existing implementation

Existing APIs

Existing Components

Existing Services

Database

Tests

ADRs

Documentation

Determine

Does this already exist?

Can existing implementation be reused?

Are similar issues already solved?

Avoid duplicate work.

---

# 3. Business Context

Describe

Business need

Affected users

Business value

Operational impact

---

# 4. Problem Statement

Describe

Current behaviour

Expected behaviour

Observed behaviour

Frequency

Environment

Reproduction conditions

---

# 5. Scope

Included

-

-

-

Excluded

-

-

-

---

# 6. User Impact

Affected Users

Students

Teachers

Administrators

Reviewers

Content Managers

System Administrators

Describe user impact.

---

# 7. Reproduction Steps (Bug Only)

Step 1

Step 2

Step 3

Expected Result

Actual Result

Attach

Logs

Screenshots

Videos

API responses

Stack traces

If not a bug

State

"Not Applicable"

---

# 8. Root Cause Analysis

If known

Describe

Root cause

Contributing factors

Dependencies

Architecture impact

Otherwise

State

"Requires Investigation"

---

# 9. Proposed Solution

Describe

Recommended approach

Alternative approaches

Trade-offs

Repository reuse

Architecture impact

Do not redesign architecture without ADR.

---

# 10. Repository Impact

Affected

Backend

Frontend

Database

API

Search

AI

Document ingestion

Admin Portal

Deployment

CI/CD

Monitoring

Logging

Observability

---

# 11. Database Impact

Document

Tables

Indexes

Relationships

Constraints

Migrations

Rollback

If none

State

"No database changes."

---

# 12. API Impact

Document

Endpoints

Authentication

Authorization

Validation

Pagination

Filtering

Sorting

Search

OpenAPI updates

If none

State

"No API changes."

---

# 13. Frontend Impact

Document

Pages

Components

Layouts

Dialogs

Forms

Navigation

Accessibility

Responsive behaviour

Dark mode

If none

State

"No frontend changes."

---

# 14. Security Considerations

Review

Authentication

Authorization

Input validation

OWASP

Secrets

Audit logging

Sensitive data

Rate limiting

---

# 15. Performance Considerations

Review

Database

Indexes

Queries

Search

Caching

Rendering

Bundle size

Background jobs

Memory

CPU

Expected impact

---

# 16. Testing Requirements

Unit Tests

Integration Tests

API Tests

Frontend Tests

Regression Tests

Performance Tests

Security Tests

Accessibility Tests

Reuse existing fixtures.

---

# 17. Documentation Requirements

Update

README

Architecture

API

Deployment

Developer Guide

User Guide

Release Notes

ADRs

---

# 18. Risks

Technical

Security

Performance

Migration

Operational

Business

Rank

Critical

High

Medium

Low

---

# 19. Dependencies

Related Issues

Feature Specifications

ADRs

Pull Requests

External Services

Infrastructure

Third-party APIs

---

# 20. Acceptance Criteria

Issue is complete when

✓ Repository inspected

✓ Existing implementation reviewed

✓ Solution approved

✓ Tests passing

✓ Documentation updated

✓ Security reviewed

✓ Performance reviewed

✓ Accessibility verified

✓ Deployment reviewed

---

# 21. References

Repository files

Issues

Feature Specifications

ADRs

Pull Requests

Release Notes

Research

External Documentation

---

# Cursor Instructions

Before working on this issue

1. Inspect the repository.
2. Search for duplicate functionality.
3. Review ADRs.
4. Review existing APIs.
5. Review existing UI.
6. Reuse before creating.
7. Avoid architecture redesign.
8. Add tests.
9. Update documentation.
10. Verify implementation before closing.

---

# Issue Quality Checklist

✓ Repository inspected

✓ Existing implementation reviewed

✓ Scope defined

✓ User impact documented

✓ Solution proposed

✓ Security reviewed

✓ Performance reviewed

✓ Tests identified

✓ Documentation identified

✓ Risks assessed

✓ Acceptance criteria defined

---

# Final Principle

Every issue should be traceable from identification through implementation and release.

An issue should contain enough context for any engineer or AI assistant to understand the problem, evaluate the solution, implement the change, verify the result, and maintain long-term repository consistency without relying on assumptions.