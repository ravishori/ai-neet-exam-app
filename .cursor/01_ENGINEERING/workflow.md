# Development Workflow
## AI NEET Exam App
### Standard Engineering Workflow

Version: 1.0

---

# Purpose

This document defines the mandatory workflow for every engineering task performed in this repository.

The objective is to ensure that every implementation is:

- Evidence-based
- Incremental
- Fully tested
- Production ready

This workflow applies to:

- New Features
- Bug Fixes
- Refactoring
- Performance Improvements
- Security Enhancements
- Documentation Updates

---

# Golden Rule

Never write code first.

Always understand the repository first.

Repository evidence always overrides assumptions.

---

# Phase 1 — Understand the Request

Read the complete request carefully.

Identify

- Business objective
- User problem
- Expected outcome
- Constraints
- Acceptance criteria

If anything is ambiguous

STOP

Ask questions.

Never guess.

---

# Phase 2 — Repository Inspection

Before writing code

Inspect the repository.

Search for

- Existing implementation
- APIs
- Services
- Components
- Hooks
- Utilities
- Database models
- Migrations
- Tests
- Documentation
- ADRs

Produce a short Repository Inspection Report.

---

# Phase 3 — Feature Classification

Determine whether the requested feature is

✅ Already Implemented

✅ Partially Implemented

✅ Missing

---

# Already Implemented

STOP.

Do not write code.

Explain

- where it exists
- relevant files
- existing APIs
- existing UI

Recommend improvements only.

---

# Partially Implemented

Create a Gap Analysis.

Identify missing

Backend

Frontend

API

Database

Validation

Tests

Documentation

Accessibility

Security

Performance

Implement only missing pieces.

---

# Missing

Prepare a short implementation plan.

Wait for approval if required.

---

# Phase 4 — Product Design

Before implementation

Document

User Story

Acceptance Criteria

Success Criteria

Edge Cases

Failure Scenarios

UX Considerations

---

# Phase 5 — Technical Design

Review

Database

API

Backend

Frontend

Security

Performance

Reuse existing architecture.

Avoid introducing new patterns unnecessarily.

---

# Phase 6 — Implementation

Implement one complete vertical slice.

Include

✓ Database (if required)

✓ FastAPI Backend

✓ API

✓ Business Logic

✓ Next.js Frontend

✓ Validation

✓ Error Handling

✓ Loading States

✓ Empty States

✓ Responsive UI

✓ Accessibility

✓ Documentation

---

# Phase 7 — Testing

Run

Backend Tests

Frontend Tests

Lint

Type Checking

Regression Tests

If any test fails

STOP

Fix the issue.

Re-run tests.

---

# Phase 8 — Documentation

Review

Developer Docs

API Docs

Deployment Docs

Architecture Docs

Update any documentation affected by implementation.

---

# Phase 9 — Security Review

Review

Authentication

Authorization

Input Validation

SQL Injection

XSS

CSRF

Secrets

Rate Limiting

Sensitive Data Handling

Document findings.

---

# Phase 10 — Performance Review

Review

Database Queries

Indexes

Caching

Pagination

Lazy Loading

Bundle Size

API Response Time

Optimize only if evidence supports it.

---

# Phase 11 — Git Preparation

Review staged files.

Ensure only intended files are included.

Split work into logical commits.

For every commit provide

Summary

Files Included

Reason

Commit Message

---

# Phase 12 — Final Engineering Review

Verify

✓ No duplicate code

✓ No dead code

✓ Tests passing

✓ Documentation updated

✓ Accessibility verified

✓ Security reviewed

✓ Performance reviewed

✓ Repository deployable

---

# Completion Checklist

A feature is complete only when

✓ Repository inspected

✓ Requirements understood

✓ Existing implementation verified

✓ Backend complete

✓ Frontend complete

✓ Tests passing

✓ Documentation updated

✓ Security reviewed

✓ Performance reviewed

✓ Ready for production

---

# Continuous Improvement

After every completed task

1. Review repository status

2. Update documentation

3. Recommend the next highest-priority feature

4. Explain why

5. Wait for approval

Never automatically begin another feature.

---

# Workflow Summary

Understand Request

↓

Repository Inspection

↓

Feature Classification

↓

Gap Analysis

↓

Product Design

↓

Technical Design

↓

Implementation

↓

Testing

↓

Documentation

↓

Security Review

↓

Performance Review

↓

Git Commits

↓

Final Review

↓

Next Feature Recommendation

---

# Cursor Instructions

Every engineering task must follow this workflow.

Do not skip phases.

If repository evidence contradicts assumptions,

trust the repository.

---

# Final Principle

A disciplined engineering process produces better software than writing code quickly.

Every completed task should leave the repository cleaner, safer, and easier to maintain.