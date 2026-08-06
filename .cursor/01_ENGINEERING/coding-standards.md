# Coding Standards
## AI NEET Exam App
### Enterprise Coding Standards

Version: 1.0

---

# Purpose

This document defines the coding standards for the AI NEET Exam App.

Every line of code written in this repository should follow these standards.

The objective is to produce software that is:

- Readable
- Maintainable
- Secure
- Testable
- Consistent
- Production Ready

---

# General Principles

Always prioritize

- Correctness
- Readability
- Simplicity
- Maintainability

Never optimize for writing less code.

Optimize for writing understandable code.

---

# Software Engineering Principles

Every implementation should follow:

✓ SOLID

✓ DRY (Don't Repeat Yourself)

✓ KISS (Keep It Simple)

✓ YAGNI (You Aren't Gonna Need It)

✓ Separation of Concerns

✓ Single Responsibility Principle

✓ Dependency Injection where appropriate

Avoid unnecessary abstractions.

---

# Repository First

Before creating any file:

Search the repository.

Reuse existing implementations whenever practical.

Never duplicate

- Services
- Components
- Hooks
- Utilities
- Validators
- Database models

---

# Python Standards

Use

Python 3.x

PEP8

Type hints

Docstrings for public functions

Meaningful variable names

Prefer

Small focused functions.

Avoid

Huge functions.

Deep nesting.

Global mutable state.

---

# FastAPI Standards

Business logic belongs inside services.

Controllers should:

- validate
- authorize
- orchestrate

Controllers should NOT contain business logic.

Use dependency injection.

Keep endpoints RESTful.

Return consistent response models.

---

# Database Standards

Use PostgreSQL.

Schema changes must use migrations.

Never modify production tables manually.

Prefer additive migrations.

Index frequently queried columns.

Avoid duplicate entities.

Respect foreign key relationships.

---

# SQL Standards

Use parameterized queries.

Never concatenate SQL strings.

Prefer ORM unless raw SQL provides measurable benefit.

Optimize queries using evidence.

---

# React Standards

Use functional components.

Prefer composition over inheritance.

Keep components focused.

Separate:

UI

Business logic

State

Network calls

Avoid oversized components.

---

# Next.js Standards

Use App Router conventions already adopted by the repository.

Keep pages thin.

Move reusable logic into components or hooks.

Optimize images.

Support responsive layouts.

---

# TypeScript Standards

Avoid any.

Prefer strict typing.

Use interfaces or type aliases consistently.

Keep types close to where they are used unless shared.

Enable compile-time safety.

---

# Component Standards

Each component should have:

Single responsibility

Clear props

Predictable behavior

Minimal side effects

Reusable design

---

# State Management

Prefer local state when sufficient.

Avoid unnecessary global state.

Reuse existing state management patterns already present in the repository.

---

# Error Handling

Never silently ignore errors.

Provide meaningful error messages.

Log unexpected failures.

Return appropriate HTTP status codes.

Show user-friendly messages in the UI.

---

# Logging

Log

Important business events

Warnings

Errors

Unexpected behavior

Avoid logging

Passwords

Secrets

Tokens

Sensitive personal data

---

# Validation

Validate:

API input

Forms

Database constraints

Uploaded files

Never trust client input.

---

# Security

Always consider

Authentication

Authorization

Least privilege

Input validation

Output encoding

Secure defaults

Protect sensitive data.

---

# Performance

Optimize

Database queries

Rendering

Search

Pagination

Bundle size

API response time

Measure before optimizing.

---

# Accessibility

Support

Keyboard navigation

Screen readers

Semantic HTML

Color contrast

Focus visibility

Accessible forms

Accessibility is mandatory.

---

# Naming Standards

Classes

PascalCase

Example

QuestionService

PracticeSession

KnowledgeUnit

---

Functions

camelCase

Example

searchQuestions()

createSession()

publishDocument()

---

Variables

camelCase

Example

questionId

studentScore

chapterName

---

Constants

UPPER_SNAKE_CASE

Example

DEFAULT_TIMEOUT

MAX_UPLOAD_SIZE

API_VERSION

---

Files

Use descriptive names.

Examples

question_service.py

practice-session.tsx

search-api.ts

Avoid

temp.py

new.ts

misc.js

---

Folders

Use

lowercase

kebab-case where appropriate

Avoid abbreviations unless already established.

---

Comments

Write comments explaining

WHY

not

WHAT

Code should explain WHAT.

Comments explain WHY.

---

Documentation

Every public API should be documented.

Complex algorithms should include implementation notes.

Keep documentation synchronized with code.

---

Testing

Every new feature should include appropriate tests.

Tests should be:

Readable

Independent

Repeatable

Fast

Avoid flaky tests.

---

Git

Keep commits focused.

One logical change per commit whenever practical.

Use meaningful commit messages.

Avoid "misc updates".

---

Code Review Checklist

Before completing work verify:

✓ Readability

✓ Correctness

✓ Security

✓ Performance

✓ Test Coverage

✓ Accessibility

✓ Documentation

✓ No duplicate logic

✓ No dead code

---

Definition of Done

Code is complete only when

✓ Requirements satisfied

✓ Repository standards followed

✓ Tests passing

✓ Documentation updated

✓ Security reviewed

✓ Performance reviewed

✓ Accessibility verified

✓ Ready for production

---

Cursor Instructions

Before generating code

Review this document.

Ensure every implementation follows these standards.

If existing repository standards differ,

follow the repository.

Do not invent a new coding style.

---

Final Principle

Every line of code should make the repository easier to understand, easier to maintain, and safer to evolve.

Write code that another engineer can confidently extend years from now.