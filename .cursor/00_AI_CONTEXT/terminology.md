# Terminology Standards
## AI NEET Exam App
### Repository Language & Naming Guide

Version: 1.0

---

# Purpose

This document defines the official terminology standards for the AI NEET Exam App.

The goal is to ensure that:

- Cursor AI
- Developers
- Documentation
- APIs
- Database
- UI
- Tests

all use consistent language.

Repository terminology should never become inconsistent.

---

# Single Source of Truth

Every concept should have exactly one preferred name.

Avoid creating synonyms.

Example

✓ Question

✗ MCQ

✗ Item

✗ Problem

Unless referring to an external standard, always use the preferred repository term.

---

# Educational Terminology

Use

Subject

Chapter

Topic

Concept

Knowledge Unit

Question

Option

Explanation

Revision

Practice

Mock Test

Flashcard

Bookmark

Study Session

Performance

Analytics

Never invent alternative names.

---

# AI Terminology

Preferred terms

AI Explanation

AI Recommendation

Knowledge Graph

Knowledge Unit

Embedding

Semantic Search

Document Intelligence

Visual Asset

Ingestion Pipeline

Avoid ambiguous names.

---

# Repository Terminology

Always use

Repository

Module

Service

API

Component

Migration

ADR

Feature

Bug Fix

Pull Request

Commit

Release

Deployment

---

# User Terminology

Preferred

Student

Administrator

Reviewer

Publisher

Instructor

Avoid

End User

Consumer

Client

Unless required by external integrations.

---

# Database Terminology

Use

Table

Column

Row

Entity

Relationship

Migration

Primary Key

Foreign Key

Index

Constraint

Transaction

Avoid inconsistent alternatives.

---

# API Terminology

Use

Endpoint

Request

Response

Payload

Validation

Authentication

Authorization

Status Code

Avoid mixing REST and RPC terminology.

---

# Frontend Terminology

Preferred

Page

Layout

Component

Modal

Dialog

Drawer

Card

Table

Form

Button

Input

Badge

Toast

Tooltip

Navigation

Sidebar

Header

Footer

---

# Backend Terminology

Preferred

Service

Repository

Controller

Dependency

Middleware

Validator

Schema

DTO

Business Logic

Domain Logic

Avoid inconsistent naming.

---

# Testing Terminology

Preferred

Unit Test

Integration Test

End-to-End Test

Regression Test

Fixture

Mock

Test Suite

Coverage

---

# Security Terminology

Preferred

Authentication

Authorization

Role

Permission

Least Privilege

Rate Limiting

Secret

Token

Encryption

Hashing

Audit Log

---

# DevOps Terminology

Preferred

Build

Pipeline

Workflow

Deployment

Release

Rollback

Container

Image

Environment

Health Check

Monitoring

Logging

Observability

---

# Naming Conventions

Classes

PascalCase

Example

QuestionService

KnowledgeUnit

PracticeSession

---

Interfaces

PascalCase

Prefix only if repository convention already requires it.

Avoid unnecessary prefixes.

---

Functions

camelCase

Example

createQuestion()

searchQuestions()

publishDocument()

---

Variables

camelCase

Example

questionId

chapterName

studentScore

---

Constants

UPPER_SNAKE_CASE

Example

MAX_UPLOAD_SIZE

DEFAULT_TIMEOUT

API_VERSION

---

Files

Use descriptive names.

Examples

question-service.py

question_repository.py

practice-session.tsx

Avoid

temp.py

new.py

utils2.py

---

Directories

Use

lowercase

kebab-case when appropriate

Avoid

MixedCase

Random abbreviations

---

Database

Tables

snake_case

Columns

snake_case

Indexes

Descriptive names

Migration names should describe the change.

---

API Routes

Use nouns.

Examples

/questions

/concepts

/practice-sessions

Avoid verbs in route names where REST conventions already provide the action.

---

Documentation

Use complete sentences.

Avoid unexplained abbreviations.

Prefer clarity over brevity.

---

Commit Messages

Use imperative mood.

Examples

Add practice session filtering

Improve search indexing

Fix question pagination

Avoid

misc changes

updates

fixed stuff

---

Comments

Write comments explaining

WHY

not

WHAT

Good code should already explain what it does.

---

Abbreviations

Allowed

API

ADR

AI

CI/CD

OCR

PDF

UI

UX

UUID

SQL

HTTP

JSON

JWT

Avoid creating new abbreviations unless they become widely used in the repository.

---

Consistency Rules

If a term exists in:

Database

API

Backend

Frontend

Documentation

Tests

Use the SAME name everywhere.

Avoid introducing synonyms.

---

Adding New Terms

Before introducing a new long-term project term:

1. Verify it does not already exist.

2. Check glossary.md.

3. Check ADRs.

4. Update glossary.md if necessary.

5. Update terminology.md if naming guidance is required.

---

Cursor Instructions

Before creating:

Entities

Tables

APIs

Components

Services

Pages

Verify terminology consistency across the repository.

Never invent alternative names for existing concepts.

---

Final Principle

Consistency is more valuable than creativity.

The same concept should always have the same name throughout the repository.

A consistent vocabulary makes the platform easier to build, maintain, document, and understand.