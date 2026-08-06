# Repository Inspection Guide
## AI NEET Exam App
### Mandatory Pre-Implementation Workflow

Version: 1.0

---

# Purpose

Repository inspection is the most important engineering activity before implementing any change.

The objective is to understand the current implementation before proposing new code.

Never assume functionality is missing.

The repository is the only source of truth.

---

# Golden Rule

Never write code first.

Always inspect the repository first.

Evidence always overrides assumptions.

---

# Primary Objectives

Repository inspection should answer:

1. Does this feature already exist?

2. Is it partially implemented?

3. Can existing code be extended?

4. What architecture already exists?

5. What APIs already exist?

6. What database structures already exist?

7. What tests already exist?

8. What documentation already exists?

Only after answering these questions should implementation begin.

---

# Phase 1 — Understand the Request

Before inspecting the repository,

understand the request.

Identify

Business Goal

User Story

Expected Behaviour

Constraints

Acceptance Criteria

Unknowns

If requirements are unclear,

ask questions before inspecting.

---

# Phase 2 — Search Existing Features

Search for

Pages

Components

Services

Repositories

Models

Hooks

Utilities

Routes

Tests

Documentation

ADRs

Examples

Question Browser

Practice Session

Search

Mock Exam

Flashcards

Bookmarks

Revision

Admin Portal

Authentication

If functionality exists,

record where it exists.

---

# Phase 3 — Backend Inspection

Inspect

FastAPI Routes

Services

Repositories

Models

DTOs

Validators

Background Jobs

Authentication

Authorization

Configuration

Logging

Determine

Existing endpoints

Business logic

Reusable services

Dependencies

---

# Phase 4 — Frontend Inspection

Inspect

Pages

Layouts

Components

Hooks

Utilities

Providers

Theme

Routing

Forms

Tables

Dialogs

Navigation

Determine

Existing UI

Reusable components

Existing workflows

State management

---

# Phase 5 — Database Inspection

Inspect

Tables

Relationships

Indexes

Constraints

Migrations

Seed Data

Determine

Existing entities

Reusable schema

Normalization

Migration history

---

# Phase 6 — API Inspection

Inspect

REST Endpoints

Authentication

Validation

Error Responses

Pagination

Filtering

Sorting

Search

Versioning

Avoid creating duplicate endpoints.

---

# Phase 7 — Testing Inspection

Inspect

Backend Tests

Frontend Tests

Integration Tests

Regression Tests

Fixtures

Mocks

Coverage

Determine

Existing behaviour verification.

---

# Phase 8 — Documentation Inspection

Inspect

README

Architecture

ADRs

Deployment

API Documentation

Engineering Docs

Technical Standards

Determine

Existing decisions

Known limitations

Future plans

---

# Phase 9 — Dependency Inspection

Inspect

Python packages

Node packages

Docker

CI/CD

Shared packages

Environment configuration

Determine

Existing capabilities

Avoid introducing unnecessary libraries.

---

# Phase 10 — Feature Classification

Every request must be classified.

---

## Category 1

Already Implemented

Evidence

Repository contains complete implementation.

Action

STOP.

Do not write code.

Provide

Existing files

Existing APIs

Existing UI

Explain behaviour.

Recommend improvements only.

---

## Category 2

Partially Implemented

Evidence

Feature exists but is incomplete.

Action

Produce a Gap Analysis.

Document

Missing Backend

Missing Frontend

Missing API

Missing Tests

Missing Documentation

Missing Security

Missing Performance

Implement ONLY missing pieces.

---

## Category 3

Missing

Evidence

Repository contains no implementation.

Action

Prepare implementation plan.

Wait for approval if required.

Then implement.

---

# Repository Inspection Report

Before implementation produce

## Feature Requested

...

---

## Existing Implementation

...

---

## Files Found

...

---

## APIs Found

...

---

## Database Objects

...

---

## Tests Found

...

---

## Documentation Found

...

---

## Classification

Already Implemented

or

Partially Implemented

or

Missing

---

## Recommendation

...

---

# Duplicate Prevention

Never create

Duplicate APIs

Duplicate Components

Duplicate Services

Duplicate Tables

Duplicate Utilities

Duplicate Business Logic

Duplicate Validation

Extend existing implementation whenever practical.

---

# Architecture Verification

Verify

Architecture Freeze

Existing module boundaries

Dependency direction

ADRs

Service ownership

Never silently redesign architecture.

---

# Reuse Checklist

Before creating new

Service

Repository

Component

Hook

Utility

Migration

Validator

Search whether one already exists.

Prefer extension over duplication.

---

# Questions Cursor Should Ask

Before implementation

Does this already exist?

Can this be extended?

What is reusable?

What architecture already exists?

What ADR applies?

What tests already exist?

Will this duplicate anything?

Can this be implemented as a vertical slice?

---

# Inspection Deliverables

Every repository inspection should produce

✓ Repository Inspection Summary

✓ Feature Classification

✓ Gap Analysis (if required)

✓ Recommended Implementation Plan

Only then begin implementation.

---

# Cursor Instructions

Every engineering task must begin with repository inspection.

Never skip this document.

Never generate implementation before completing repository inspection.

---

# Final Principle

Understanding the repository is more valuable than writing code quickly.

The best implementation is often extending existing work rather than creating something new.