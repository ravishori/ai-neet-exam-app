# Git Workflow
## AI NEET Exam App
### Enterprise Git Workflow

Version: 1.0

---

# Purpose

This document defines the Git workflow for the AI NEET Exam App.

Every change committed to the repository should follow these standards.

The objectives are:

- Clean commit history
- Easy code reviews
- Safe deployments
- Simple rollbacks
- High traceability

Git history should tell the story of the project.

---

# Core Philosophy

Git is not only version control.

Git is documentation.

Every commit should explain:

- What changed
- Why it changed
- Scope of the change

---

# Repository Inspection First

Before making changes

Inspect:

- Current branch
- Current status
- Existing commits
- Open work
- Related documentation

Commands

git status

git branch

git log --oneline --graph --decorate -20

Never commit without understanding repository state.

---

# Branch Strategy

Unless the repository adopts GitFlow or another branching model,

follow a simple feature branch workflow.

Examples

feature/question-browser

feature/mock-exam

feature/flashcards

bugfix/search-ranking

hotfix/login-timeout

docs/api-update

refactor/search-service

---

# One Feature Per Branch

A branch should solve one problem.

Avoid mixing:

Feature

Bug Fix

Refactor

Documentation

Deployment

into one branch.

---

# Commit Philosophy

Commits should be

Small

Focused

Logical

Independent

Reviewable

Every commit should have one clear purpose.

---

# Before Every Commit

Review

git diff

git diff --staged

git status

Verify

Only intended files are staged.

Never commit unrelated changes.

---

# Commit Message Format

Use imperative mood.

Examples

Add AI explanation endpoint

Improve question search ranking

Fix authentication timeout

Update deployment documentation

Avoid

updates

misc changes

fix

temp

final

latest

---

# Preferred Commit Types

feat:

New feature

fix:

Bug fix

refactor:

Code improvement without behavior change

docs:

Documentation

test:

Testing

perf:

Performance

build:

Build configuration

ci:

CI/CD

chore:

Maintenance

Example

feat: add adaptive practice sessions

---

# Staging Strategy

Stage only related files.

Never use

git add .

without verifying changes.

Prefer

git add path/to/file

Review staged files before commit.

---

# Documentation Rule

Whenever implementation changes

consider whether

README

API Docs

Architecture Docs

Deployment Docs

ADRs

need updates.

Documentation is part of the change.

---

# Database Changes

If database schema changes

include

Migration

Documentation

Tests

Never commit schema changes without migrations.

---

# Pull Request Standards

Every Pull Request should include

Summary

Motivation

Files Changed

Testing Performed

Known Limitations

Documentation Updated

Screenshots (if UI)

Migration Notes (if applicable)

Rollback Considerations (if applicable)

---

# Code Review

Before requesting review

Self-review

Check

Correctness

Readability

Maintainability

Security

Performance

Accessibility

Test Coverage

Regression Risk

---

# Squashing

Squash

WIP

temporary

debug

fixup

commits

before merging.

Final history should remain clean.

---

# Merge Strategy

Prefer

Squash Merge

or

Rebase Merge

if repository policy allows.

Avoid unnecessary merge commits.

---

# Tags

Use Git tags for releases.

Example

v1.0.0

v1.1.0

v2.0.0-beta

Document release notes.

---

# Rollback

Every significant change should be reversible.

Avoid commits that mix unrelated work.

Logical commits simplify rollback.

---

# Sensitive Data

Never commit

Passwords

Secrets

API Keys

Certificates

Private Keys

Database Dumps

Personal Data

Use environment variables.

---

# Generated Files

Do not commit

Temporary files

Cache

Logs

Build artifacts

IDE settings unless intentionally shared

Follow .gitignore.

---

# ADR Alignment

If implementation requires a major architectural decision

Create or update the appropriate ADR.

Do not silently change architecture.

---

# CI/CD

Before merging

Verify

Tests passing

Lint passing

Type checking passing

Build successful

CI green

Never merge broken builds.

---

# Release Readiness

Before release verify

Tests

Documentation

Deployment

Rollback

Monitoring

Version

Tag

Release Notes

---

# Cursor Instructions

For every engineering task

1. Inspect Git status.

2. Review existing branch.

3. Stage only intended files.

4. Create logical commits.

5. Verify repository cleanliness.

6. Recommend the next logical commit if work remains.

---

# Definition of Done

Git work is complete only when

✓ Clean working tree

✓ Logical commits

✓ Meaningful commit messages

✓ Documentation updated

✓ Tests passing

✓ Ready for review

---

# Final Principle

A future engineer should understand the project's evolution by reading Git history alone.

Every commit should improve the repository's history, not make it harder to understand.