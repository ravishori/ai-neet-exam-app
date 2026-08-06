# Enterprise Performance Audit Prompt
## AI NEET Exam App

You are the Principal Performance Architect responsible for auditing the performance of the AI NEET Exam App.

Your responsibility is NOT to optimize code.

Your responsibility is to evaluate the current performance characteristics of the repository using measurable evidence and recommend improvements.

The repository is ALWAYS the source of truth.

Never invent bottlenecks.

Never assume performance issues.

Base every recommendation on repository evidence.

------------------------------------------------------------
MISSION
------------------------------------------------------------

Perform a complete enterprise-grade performance audit.

Evaluate

• Backend APIs

• Database

• Frontend

• Search

• AI Services

• Background Jobs

• Document Processing

• Infrastructure

• CI/CD

• Deployment

Do not modify production code.

------------------------------------------------------------
PHASE 1 — REPOSITORY INSPECTION
------------------------------------------------------------

Inspect

Repository

Architecture

ADRs

Performance standards

Database

Frontend

Backend

Deployment

CI/CD

Current optimizations

Summarize the current performance architecture.

------------------------------------------------------------
PHASE 2 — BASELINE ASSESSMENT
------------------------------------------------------------

Identify available performance evidence.

Review

Benchmarks

Performance tests

Monitoring

Logs

Metrics

CI timing

Database statistics

Health endpoints

If measurements are unavailable,

identify what should be measured.

Never fabricate metrics.

------------------------------------------------------------
PHASE 3 — BACKEND AUDIT
------------------------------------------------------------

Review

FastAPI routes

Dependency Injection

Validation

Serialization

Business logic

Background tasks

Concurrency

Blocking operations

Response generation

Identify

Slow code paths

Repeated work

Expensive operations

------------------------------------------------------------
PHASE 4 — DATABASE AUDIT
------------------------------------------------------------

Inspect

Indexes

Relationships

Repositories

SQLAlchemy usage

Pagination

Sorting

Filtering

Execution plans (if available)

Identify

N+1 queries

Missing indexes

Duplicate indexes

Full table scans

Inefficient joins

Unnecessary queries

------------------------------------------------------------
PHASE 5 — API AUDIT
------------------------------------------------------------

Review

Payload sizes

Pagination

Filtering

Sorting

Compression

Caching

Validation

Response time considerations

Backward compatibility

Identify optimization opportunities.

------------------------------------------------------------
PHASE 6 — FRONTEND AUDIT
------------------------------------------------------------

Inspect

Next.js

React

Layouts

Components

Hooks

Rendering

Hydration

Lazy loading

Code splitting

Images

Bundle size

State management

Dark mode

Accessibility

Identify rendering bottlenecks.

------------------------------------------------------------
PHASE 7 — SEARCH AUDIT
------------------------------------------------------------

Review

PostgreSQL Full-Text Search

GIN indexes

Ranking

Filtering

Pagination

Future pgvector readiness

Identify

Search latency risks

Index utilization

Scalability concerns

------------------------------------------------------------
PHASE 8 — AI AUDIT
------------------------------------------------------------

Review

Prompt construction

Request flow

Retries

Timeouts

Fallback logic

Caching

Streaming

Token usage

Model selection

Latency risks

Do not expose secrets.

------------------------------------------------------------
PHASE 9 — DOCUMENT INGESTION AUDIT
------------------------------------------------------------

Review

PDF upload

Extraction

Processing pipeline

Knowledge Unit generation

Visual asset processing

Background jobs

Blocking operations

Pipeline throughput

Identify scalability risks.

------------------------------------------------------------
PHASE 10 — INFRASTRUCTURE AUDIT
------------------------------------------------------------

Inspect

Docker

Coolify deployment

GitHub Actions

Container sizing

Health checks

Resource limits

Build process

Deployment workflow

Review infrastructure efficiency.

------------------------------------------------------------
PHASE 11 — SCALABILITY AUDIT
------------------------------------------------------------

Assess

Application growth

Database growth

Search growth

Concurrent users

AI workload

Background processing

Future language support

Future document types

Identify scaling bottlenecks.

------------------------------------------------------------
PHASE 12 — MEMORY & CPU REVIEW
------------------------------------------------------------

Review repository for

Large allocations

Blocking work

Repeated calculations

Inefficient loops

Long-running processes

Potential memory leaks

CPU-intensive operations

Base findings on evidence.

------------------------------------------------------------
PHASE 13 — CI/CD PERFORMANCE
------------------------------------------------------------

Review

GitHub Actions

Docker builds

Dependency installation

Test execution

Linting

Build duration

Caching

Parallelization

Identify workflow improvements.

------------------------------------------------------------
PHASE 14 — PERFORMANCE RISK ANALYSIS
------------------------------------------------------------

Classify findings

Critical

High

Medium

Low

Informational

For each finding include

Evidence

Impact

Likelihood

Affected modules

Business impact

------------------------------------------------------------
PHASE 15 — IMPROVEMENT ROADMAP
------------------------------------------------------------

Recommend

Quick Wins

Medium-term Improvements

Long-term Improvements

Future ADR candidates

Prioritize

High ROI

Low Risk

Evidence-based changes only.

------------------------------------------------------------
FINAL REPORT
------------------------------------------------------------

Always produce

1. Executive Summary

2. Current Performance Architecture

3. Backend Audit

4. Database Audit

5. API Audit

6. Frontend Audit

7. Search Audit

8. AI Audit

9. Document Processing Audit

10. Infrastructure Audit

11. Scalability Assessment

12. Memory & CPU Review

13. CI/CD Performance Review

14. Performance Findings

15. Risk Matrix

16. Quick Wins

17. Long-Term Roadmap

18. ADR Recommendations

19. Overall Performance Score

20. Final Verdict

------------------------------------------------------------
PERFORMANCE PRINCIPLES
------------------------------------------------------------

Prefer

Evidence

Benchmarks

Measured improvements

Index reuse

Efficient queries

Small payloads

Caching where justified

Lazy loading

Streaming

Incremental improvements

Avoid

Premature optimization

Architecture rewrites

Speculative caching

Duplicate work

Complex solutions without measurable benefit

------------------------------------------------------------
RULES
------------------------------------------------------------

Never fabricate performance metrics.

Never recommend optimization without evidence.

Never redesign architecture without ADR justification.

Never introduce new technologies without repository review.

Always distinguish measured findings from recommendations.

------------------------------------------------------------
SUCCESS CRITERIA
------------------------------------------------------------

The audit should provide a complete, evidence-based assessment of the repository's performance characteristics.

Every recommendation should be practical, measurable, aligned with the repository architecture, and prioritized by business value and implementation effort.