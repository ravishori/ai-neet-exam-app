# Known Limitations Register
## AI NEET Exam App

Version: 1.0

Status: Active

Last Updated:

Owner: Engineering Team

---

# Purpose

This document records all known limitations of the AI NEET Exam App.

A limitation is a current technical, operational, business, infrastructure, regulatory, or third-party constraint that affects the system.

Unlike technical debt, a limitation may not currently have a practical solution.

Repository implementation remains the source of truth.

---

# Definition

Known limitations include

✓ Platform limitations

✓ Infrastructure constraints

✓ Third-party service limitations

✓ AI provider limitations

✓ Browser limitations

✓ Mobile limitations

✓ Performance constraints

✓ Security constraints

✓ Product scope limitations

✓ Regulatory limitations

Do not confuse limitations with bugs.

---

# Categories

## Architecture

Examples

• Current architectural constraints

• Monolithic deployment limitations

• Scaling boundaries

---

## Backend

Examples

• API rate limits

• Long-running operations

• Background processing limits

---

## Frontend

Examples

• Browser compatibility

• Offline support

• Client-side storage limitations

---

## Database

Examples

• PostgreSQL limitations

• Query performance boundaries

• Maximum dataset assumptions

---

## AI Platform

Examples

• Token limits

• Context window limits

• AI provider quotas

• Embedding size limits

• Model availability

---

## Search

Examples

• Ranking limitations

• Semantic search maturity

• Indexing latency

---

## Infrastructure

Examples

• VPS capacity

• Storage

• Bandwidth

• Memory

• CPU

---

## Security

Examples

• External authentication dependency

• Third-party certificate constraints

• Vendor-managed identity systems

---

## Deployment

Examples

• Coolify capabilities

• Docker host limitations

• Rolling deployment constraints

---

# Limitation Entry Template

---

## Limitation ID

LIMIT-XXXX

### Title

Short descriptive title.

### Category

Architecture

Backend

Frontend

Database

AI Platform

Infrastructure

Deployment

Security

Performance

Search

Browser

Mobile

Third-Party

Other

---

### Status

Active

Under Review

Resolved

Accepted

Superseded

---

### Severity

Critical

High

Medium

Low

---

### Description

Describe

What the limitation is

Why it exists

Current behaviour

---

### Root Cause

Examples

Technology limitation

Business decision

Infrastructure capacity

Third-party restriction

Regulatory requirement

Hardware limitation

Cost constraint

---

### Affected Areas

Examples

Backend

Frontend

AI

Database

Search

Authentication

Deployment

Analytics

Admin Portal

Student Portal

---

### Business Impact

Describe

User experience

Operational impact

Development impact

Maintenance impact

---

### Technical Impact

Examples

Performance

Scalability

Reliability

Availability

Maintainability

Security

Developer productivity

---

### Current Workaround

Describe

Existing mitigation

Manual process

Alternative implementation

Operational procedure

If none

State

"No workaround currently available."

---

### Recommended Future Solution

Describe

Possible long-term approach

Alternative technologies

Infrastructure improvements

Architecture evolution

Do not assume implementation is currently feasible.

---

### Dependencies

Examples

Infrastructure

Cloud provider

AI provider

Database

Third-party APIs

Budget

Legal approval

---

### Target Review

Examples

Quarterly

Next major release

Infrastructure upgrade

Future roadmap

Backlog

---

### Related References

ADR

Feature Specification

Issue

Pull Request

Release Notes

Documentation

---

# Current Known Limitations

Document all active limitations here.

Each limitation should have its own section using the template above.

---

# Review Schedule

Review limitations

Every major release

Quarterly architecture review

Infrastructure upgrades

AI provider changes

Database upgrades

Browser support updates

---

# Resolution Workflow

Identify Limitation

↓

Document

↓

Assess Impact

↓

Determine Workaround

↓

Monitor

↓

Review

↓

Resolve (if feasible)

↓

Update Documentation

---

# Acceptance Rules

A limitation may be accepted when

✓ Clearly documented

✓ Business impact understood

✓ Technical impact assessed

✓ Workaround documented (if available)

✓ Future review planned

Undocumented limitations are unacceptable.

---

# Metrics

Track

Total active limitations

Critical limitations

High-impact limitations

Resolved limitations

Limitations by category

Review frequency

---

# Code Review Expectations

Reviewers should verify

✓ New limitations documented

✓ Existing limitations respected

✓ No implementation conflicts

✓ Workarounds applied correctly

✓ Documentation updated

---

# Cursor Instructions

When implementing new features

1. Review this document.
2. Respect documented limitations.
3. Do not propose solutions that violate active constraints.
4. Prefer existing workarounds where appropriate.
5. If a new limitation is discovered:
   - Document it.
   - Assess its impact.
   - Record any workaround.
   - Schedule future review.
6. Revisit limitations only when architecture, infrastructure, or business priorities change.

---

# Common Anti-Patterns

Never

❌ Ignore documented limitations

❌ Assume unlimited AI tokens

❌ Assume infinite infrastructure capacity

❌ Ignore browser compatibility constraints

❌ Ignore third-party API quotas

❌ Design features that exceed documented limits

❌ Remove limitations without verification

---

# Example Entry

## Limitation ID

LIMIT-0001

### Title

AI provider context window limitation

### Category

AI Platform

### Status

Active

### Severity

Medium

### Description

The current AI provider has a maximum context window that restricts the amount of source material processed in a single request.

### Root Cause

Third-party model limitation.

### Business Impact

Large documents may require chunking.

### Technical Impact

Additional preprocessing required.

### Current Workaround

Split documents into Knowledge Units before AI processing.

### Recommended Future Solution

Support providers with larger context windows and intelligent context selection.

### Target Review

Next major AI platform review.

---

# Final Principle

Known limitations are engineering constraints—not failures.

Documenting them enables informed decision-making, realistic planning, and consistent implementation.

Every limitation should have a clear description, measurable impact, an identified workaround (if possible), and a scheduled review to determine whether it still applies.