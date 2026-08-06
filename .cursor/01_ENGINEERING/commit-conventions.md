# Commit Conventions
## AI NEET Exam App
### Enterprise Git Commit Standards

Version: 1.0

---

# Purpose

This document defines the official commit conventions for the AI NEET Exam App.

Every commit should communicate:

- What changed
- Why it changed
- Scope of the change
- Impact on the repository

A clean commit history improves:

- Code Reviews
- Debugging
- Releases
- Rollbacks
- Collaboration
- Documentation

---

# Core Principles

Every commit should be:

✓ Small

✓ Focused

✓ Logical

✓ Reviewable

✓ Reversible

One commit should solve one problem.

---

# Golden Rule

Never mix unrelated work into the same commit.

Avoid combining:

- Features
- Bug fixes
- Refactoring
- Documentation
- Infrastructure
- Tests

unless they are inseparable.

---

# Commit Message Format

Use the following structure.

<type>: <short summary>

Examples

feat: add adaptive practice sessions

fix: resolve question image loading

docs: update deployment guide

test: add search service tests

refactor: simplify authentication service

ci: add GitHub Actions deployment

---

# Allowed Commit Types

## feat

New functionality.

Examples

feat: add mock exam generator

feat: implement AI explanations

---

## fix

Bug fixes.

Examples

fix: correct search pagination

fix: resolve login timeout

---

## refactor

Code improvements without behaviour changes.

Examples

refactor: simplify revision service

refactor: extract reusable search helper

---

## docs

Documentation only.

Examples

docs: update architecture guide

docs: improve API examples

---

## test

Testing improvements.

Examples

test: add repository integration tests

test: increase search coverage

---

## perf

Performance improvements.

Examples

perf: optimize search queries

perf: reduce dashboard loading time

---

## ci

Continuous Integration / Deployment.

Examples

ci: add deployment workflow

ci: improve security scan

---

## build

Build configuration.

Examples

build: upgrade Docker image

build: update dependency versions

---

## chore

Repository maintenance.

Examples

chore: remove unused assets

chore: reorganize documentation

---

# Commit Summary Rules

The summary should:

✓ Start with a verb

✓ Be concise

✓ Explain the change

Good

feat: add flashcard generation

Bad

updates

misc fixes

latest

done

---

# Commit Body (Optional)

Use when additional context is useful.

Example

feat: add adaptive revision planner

- Introduce revision scheduling service
- Add REST endpoint
- Implement UI integration
- Add unit tests
- Update documentation

---

# Breaking Changes

If a commit introduces a breaking change

Document it clearly.

Example

BREAKING CHANGE:

Renamed QuestionService API endpoints.

Migration required.

---

# Documentation Rule

If implementation changes

Review whether these require updates:

README

Architecture

API

Deployment

ADRs

Release Notes

Documentation changes should be committed together with the implementation whenever practical.

---

# Testing Rule

Before committing verify:

✓ Backend tests pass

✓ Frontend tests pass

✓ Lint passes

✓ Type checking passes

✓ Manual verification completed (if required)

Never commit failing code.

---

# Review Before Commit

Run

git status

git diff

git diff --staged

Verify

Only intended files are staged.

No temporary files included.

No secrets included.

---

# Commit Size

Preferred

50–300 lines changed

Acceptable

Up to ~600 lines if the change represents one logical unit.

Large commits should be split whenever practical.

---

# What Should Never Be Committed

Passwords

API Keys

Secrets

Private Keys

Database Dumps

Temporary Files

Build Artifacts

IDE Cache

Debug Output

Personal Notes

---

# Commit Checklist

Before committing verify

✓ Repository inspected

✓ One logical purpose

✓ Correct commit type

✓ Clear summary

✓ Tests passing

✓ Documentation updated

✓ Security reviewed

✓ No secrets

✓ Only intended files staged

---

# Examples

Feature

feat: add chapter performance dashboard

Bug Fix

fix: prevent duplicate bookmark creation

Refactor

refactor: simplify question search service

Documentation

docs: update CI/CD guide

Testing

test: improve authentication coverage

Performance

perf: optimize PostgreSQL indexes

CI/CD

ci: add production deployment pipeline

Maintenance

chore: remove deprecated utilities

---

# Cursor Instructions

Before every commit

1. Review staged files.

2. Confirm one logical change.

3. Select the correct commit type.

4. Write a clear summary.

5. Suggest splitting commits if unrelated changes are staged.

6. Verify repository cleanliness.

---

# Final Principle

A commit should explain its purpose without requiring the reviewer to inspect every changed file.

Good commit history is long-term project documentation.