# Branching Strategy
## AI NEET Exam App
### Enterprise Git Branching Strategy

Version: 1.0

---

# Purpose

This document defines the official Git branching strategy for the AI NEET Exam App.

The objectives are:

- Keep history clean
- Reduce merge conflicts
- Enable safe releases
- Support production deployments
- Make rollback simple
- Improve traceability

This strategy applies to all contributors and Cursor AI.

---

# Branching Philosophy

The repository uses a simplified branch strategy.

Prefer:

- Small branches
- Short-lived branches
- Frequent merges
- Production-ready main branch

Avoid long-running feature branches.

---

# Primary Branch

## main

The main branch always represents the latest stable production-ready code.

Rules

✓ Deployable

✓ Tested

✓ Reviewed

✓ CI Passing

Never commit experimental work directly to main.

---

# Feature Branches

Create one branch per feature.

Naming Convention

feature/<feature-name>

Examples

feature/question-browser

feature/mock-exam

feature/flashcards

feature/ai-study-planner

feature/admin-dashboard

Rules

- One feature only
- Small scope
- Merge after completion

---

# Bug Fix Branches

Naming Convention

bugfix/<bug-name>

Examples

bugfix/login-timeout

bugfix/search-ranking

bugfix/question-rendering

---

# Hotfix Branches

Used only for urgent production fixes.

Naming Convention

hotfix/<issue>

Examples

hotfix/payment-failure

hotfix/authentication

hotfix/database-timeout

Merge immediately after validation.

---

# Refactoring Branches

Naming Convention

refactor/<module>

Examples

refactor/search-service

refactor/question-engine

refactor/admin-api

Refactoring must not change behaviour.

---

# Documentation Branches

Naming Convention

docs/<topic>

Examples

docs/api

docs/deployment

docs/architecture

---

# Release Branches

Only when preparing major releases.

Naming Convention

release/v1.0.0

release/v1.1.0

release/v2.0.0

Purpose

Final testing

Documentation

Version updates

Release notes

Deployment validation

---

# Branch Lifecycle

main

↓

Create feature branch

↓

Implement feature

↓

Run tests

↓

Self-review

↓

Update documentation

↓

Merge into main

↓

Delete feature branch

---

# Merge Policy

Before merging verify

✓ Tests pass

✓ Lint passes

✓ Type checking passes

✓ Documentation updated

✓ CI green

✓ No merge conflicts

---

# Branch Protection

The main branch should be protected.

Recommended settings

- Require pull request
- Require passing CI
- Prevent force pushes
- Prevent direct commits
- Require linear history (optional)

---

# Commit Policy

Each branch should contain

One logical change

Avoid mixing

Features

Bug fixes

Refactors

Documentation

Infrastructure

into one branch.

---

# Sync Policy

Before starting work

git checkout main

git pull

Create a fresh feature branch.

Keep branches up to date.

---

# Merge Strategy

Preferred

Squash Merge

Benefits

- Clean history
- One commit per feature
- Easy rollback
- Easy review

Avoid unnecessary merge commits.

---

# Branch Cleanup

After merging

Delete the feature branch.

Keep repository clean.

---

# Rollback Strategy

If a release fails

Rollback by

- Git tag
- Previous release
- Previous deployment

Never rewrite Git history.

---

# Cursor Instructions

Before starting work

1. Check current branch

2. Verify repository status

3. Pull latest changes

4. Create appropriate branch

5. Complete one logical task

6. Merge after review

7. Delete merged branch

---

# Branch Naming Examples

feature/neet-practice

feature/search-filters

feature/revision-planner

bugfix/login-session

bugfix/question-images

hotfix/payment

docs/api-reference

refactor/question-service

release/v1.0.0

---

# Definition of Done

A branch is complete only when

✓ Feature complete

✓ Tests passing

✓ Documentation updated

✓ Self-review completed

✓ CI passing

✓ Ready to merge

---

# Final Principle

A branch should represent one meaningful unit of work.

Small branches reduce risk, simplify reviews, and keep the repository healthy.