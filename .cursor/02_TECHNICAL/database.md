# Database Standards
## AI NEET Exam App
### Enterprise Database Design & Development Guide

Version: 1.0

---

# Purpose

This document defines the database standards for the AI NEET Exam App.

It explains how database changes should be designed, implemented, reviewed, tested, and deployed.

The objectives are:

- Data Integrity
- Performance
- Scalability
- Maintainability
- Backward Compatibility
- Production Safety

The repository is the source of truth.

Always inspect the existing schema before making changes.

---

# Database Platform

Official Database

PostgreSQL

ORM

SQLAlchemy

Migration Tool

Alembic

Pattern

Repository Pattern

Database changes must always be migration-driven.

Never modify production databases manually.

---

# Database Philosophy

The database is a long-term asset.

Schema evolution should be:

- Incremental
- Predictable
- Reversible
- Well documented

Avoid disruptive schema redesign.

---

# Repository First

Before creating

Table

Column

Index

Constraint

Relationship

Migration

Inspect

Existing Models

Existing Migrations

Existing Relationships

Existing Queries

Existing Indexes

Never duplicate existing structures.

---

# Schema Design Principles

Prefer

Normalized design

Clear relationships

Meaningful names

Primary keys

Foreign keys

Indexes

Audit fields

Avoid

Duplicate entities

Repeated data

Business logic inside the database

Premature denormalization

---

# Naming Standards

Tables

snake_case

Examples

questions

subjects

chapters

topics

concepts

practice_sessions

knowledge_units

---

Columns

snake_case

Examples

question_id

created_at

updated_at

chapter_id

difficulty_level

---

Primary Keys

id

or

entity_id

Follow existing repository conventions.

---

Foreign Keys

<entity>_id

Examples

subject_id

chapter_id

concept_id

student_id

---

Indexes

Meaningful names.

Examples

idx_questions_subject

idx_question_year

idx_practice_session_student

---

Constraints

Use descriptive names.

Examples

fk_questions_subject

uq_question_code

ck_difficulty

---

Relationships

Prefer explicit foreign keys.

Avoid implicit relationships.

Document cascade behaviour.

---

# Data Types

Use appropriate PostgreSQL types.

Examples

UUID

INTEGER

BIGINT

TEXT

VARCHAR

BOOLEAN

TIMESTAMP

JSONB (only when justified)

NUMERIC

Avoid generic TEXT when a more specific type improves validation.

---

# Audit Fields

Every long-lived entity should include

created_at

updated_at

Optionally

created_by

updated_by

deleted_at (if soft delete is used)

Maintain consistency across entities.

---

# Soft Delete Policy

Prefer soft deletes only where recovery or audit history is required.

Avoid unnecessary soft deletes.

If implemented

Filter deleted records consistently.

---

# Migrations

Every schema change must have an Alembic migration.

Migration rules

- One logical change per migration
- Descriptive migration message
- Reversible where practical
- Reviewed before deployment

Never edit historical migrations already applied in production.

---

# Indexing

Create indexes for

Foreign keys

Search fields

Frequently filtered columns

Frequently sorted columns

Unique constraints

Avoid unnecessary indexes.

Every index increases write cost.

Measure before adding.

---

# Query Standards

Prefer SQLAlchemy ORM.

Use raw SQL only when

Performance

Database-specific functionality

Complex reporting

justifies it.

Always parameterize queries.

Never concatenate SQL strings.

---

# Transactions

Use transactions for operations that modify multiple related records.

Ensure

Atomicity

Consistency

Rollback on failure

Avoid long-running transactions.

---

# Relationships

Prefer explicit relationships.

Examples

Subject

↓

Chapter

↓

Topic

↓

Concept

↓

Question

Maintain referential integrity.

---

# JSONB Usage

Use JSONB only for

Flexible metadata

Configuration

Rarely queried attributes

Do NOT replace relational design with JSONB.

---

# Search

Current

PostgreSQL Full-Text Search

GIN Indexes

Future

pgvector

Semantic Search

Requires ADR approval before implementation.

---

# Performance

Review

Execution Plans

Indexes

Joins

Sorting

Pagination

Filtering

Avoid

SELECT *

N+1 Queries

Unbounded queries

Full table scans on large datasets

---

# Pagination

Always paginate large result sets.

Avoid returning entire tables.

Support

Limit

Offset

Cursor pagination where appropriate

---

# Constraints

Use database constraints whenever possible.

Examples

NOT NULL

UNIQUE

CHECK

FOREIGN KEY

Database integrity should not depend solely on application code.

---

# Seed Data

Reference data

Subjects

Chapters

Topics

Difficulty Levels

Question Types

should be version controlled where practical.

---

# Data Integrity

Always protect

Academic content

Student progress

Bookmarks

Notes

Practice history

Revision history

Analytics

Never compromise educational data.

---

# Security

Validate input.

Use parameterized queries.

Never expose internal IDs unnecessarily.

Protect sensitive data.

Least privilege for database users.

Never store secrets in database tables.

---

# Testing

Every migration should be tested.

Verify

Schema creation

Upgrade

Downgrade (where supported)

Indexes

Constraints

Relationships

Application compatibility

---

# Documentation

Database changes should update

ER Diagram (if maintained)

Architecture docs

Migration notes

Relevant ADRs

API documentation (if impacted)

Keep documentation synchronized.

---

# Future Growth

The database should support future capabilities such as

Adaptive Learning

Knowledge Graph

AI Recommendations

Flashcards

Revision Planning

Document Intelligence

Visual Assets

Analytics

without requiring disruptive redesign.

---

# Cursor Instructions

Before making database changes

1. Inspect existing schema.

2. Inspect existing migrations.

3. Verify relationships.

4. Check indexes.

5. Check repository conventions.

6. Prefer extending existing entities.

7. Create migration.

8. Add tests.

9. Update documentation.

Never introduce schema changes without repository evidence.

---

# Definition of Done

Database work is complete only when

✓ Schema reviewed

✓ Existing models inspected

✓ Migration created

✓ Migration tested

✓ Relationships verified

✓ Indexes reviewed

✓ Documentation updated

✓ Repository remains deployable

---

# Final Principle

The database is one of the most stable parts of the platform.

Schema changes should be deliberate, reversible, and well documented.

Good database design reduces future engineering effort and supports long-term scalability.