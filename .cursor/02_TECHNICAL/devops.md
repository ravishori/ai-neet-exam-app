# DevOps Standards
## AI NEET Exam App
### Enterprise DevOps Engineering Guide

Version: 1.0

---

# Purpose

This document defines the DevOps standards for the AI NEET Exam App.

The objectives are

- Reliable deployments
- Automated testing
- Infrastructure consistency
- Repeatable builds
- Secure delivery
- Fast recovery
- Production readiness

DevOps is a continuous engineering practice rather than a deployment phase.

---

# DevOps Philosophy

Every commit should be capable of progressing toward production.

Automation should replace manual work whenever practical.

Prefer

Repeatability

Automation

Observability

Reliability

Security

---

# Repository First

Before modifying infrastructure

Inspect

Docker

GitHub Actions

Deployment scripts

Environment configuration

CI workflows

Existing documentation

Existing ADRs

Never duplicate deployment pipelines.

---

# Current Platform

Frontend

Next.js

Backend

FastAPI

Database

PostgreSQL

ORM

SQLAlchemy

Migration

Alembic

Containers

Docker

CI/CD

GitHub Actions

Deployment

Coolify

Operating System

Linux

Repository implementation is the source of truth.

---

# Infrastructure Principles

Infrastructure should be

Version controlled

Repeatable

Automated

Secure

Recoverable

Never depend on undocumented manual steps.

---

# Container Standards

Use Docker for all deployable services.

Containers should

Be reproducible

Use minimal base images

Avoid unnecessary packages

Run one primary process

Support health checks

Avoid privileged containers.

---

# Docker Standards

Use

Multi-stage builds

Layer caching

Pinned base images

Minimal runtime images

Avoid

Root users

Large images

Development tools in production images

Unused packages

---

# Environment Configuration

Use

Environment variables

Separate configuration per environment

Never commit

Passwords

Secrets

Tokens

Certificates

Private keys

Production credentials

---

# Environments

Recommended environments

Development

Testing

Staging

Production

Configuration should remain isolated.

---

# CI/CD Philosophy

Every Pull Request should verify

Build

Lint

Type checking

Backend tests

Frontend tests

Security scans

Docker build

Repository should remain deployable.

---

# GitHub Actions

Repository currently uses GitHub Actions.

Typical pipeline

Checkout

↓

Install dependencies

↓

Lint

↓

Type checking

↓

Backend tests

↓

Frontend tests

↓

Security scanning

↓

Docker build

↓

Deployment trigger

---

# Security Scanning

Current tooling

CodeQL

Dependabot

gitleaks

pip-audit

npm audit

Trivy

Review findings regularly.

Do not ignore critical vulnerabilities.

---

# Dependency Management

Review

Python packages

Node packages

Docker base images

GitHub Actions

Update dependencies through controlled Pull Requests.

---

# Database Operations

Database changes require

Alembic migration

Migration testing

Rollback consideration

Documentation updates

Never modify production schema manually.

---

# Deployment

Deployments should

Be automated

Be repeatable

Be documented

Be reversible

Current deployment platform

Coolify

Avoid manual production deployments where automation exists.

---

# Rollback Strategy

Every deployment should support rollback.

Maintain

Tagged releases

Version history

Database migration strategy

Rollback documentation

Rollback should be tested periodically.

---

# Health Checks

Applications should expose health endpoints.

Verify

Application availability

Database connectivity

Dependencies

Health checks should support deployment automation.

---

# Logging

Centralize logs where practical.

Log

Application startup

Errors

Warnings

Background jobs

Administrative events

Never log secrets.

---

# Monitoring

Monitor

Application uptime

API latency

Database health

Memory

CPU

Disk usage

Background jobs

Security events

Monitoring should provide actionable information.

---

# Backups

Backups should include

Database

Uploaded content (where applicable)

Configuration

Document

Frequency

Retention

Recovery procedure

Recovery should be periodically tested.

---

# Disaster Recovery

Document procedures for

Infrastructure failure

Database corruption

Deployment failure

Configuration loss

Recovery objectives should be defined.

---

# Release Process

Every release should include

Passing CI

Passing tests

Security review

Documentation updates

Version update

Release notes

Deployment verification

---

# Infrastructure Security

Review

Firewall

HTTPS

Certificates

Secrets

Least privilege

Container security

Dependency vulnerabilities

---

# Performance

Review

Container size

Build duration

Deployment duration

Application startup

Resource usage

Optimize based on evidence.

---

# Documentation

Keep updated

Deployment Guide

Runbook

Rollback Guide

CI/CD documentation

Architecture documentation

ADRs

---

# DevOps Checklist

Before deployment verify

✓ Build succeeds

✓ Backend tests pass

✓ Frontend tests pass

✓ Lint passes

✓ Type checking passes

✓ Security scans reviewed

✓ Docker image builds

✓ Migrations validated

✓ Documentation updated

✓ Rollback available

---

# Cursor Instructions

Before modifying infrastructure

1. Inspect existing workflows.

2. Inspect Docker configuration.

3. Review deployment documentation.

4. Reuse existing infrastructure.

5. Avoid introducing new deployment tools without ADR approval.

6. Validate builds locally where practical.

7. Update documentation.

---

# Definition of Done

DevOps work is complete only when

✓ Infrastructure reviewed

✓ CI passing

✓ Tests passing

✓ Security reviewed

✓ Deployment documented

✓ Rollback documented

✓ Repository deployable

---

# Repository Tooling

Current DevOps Toolchain

Frontend
- Next.js

Backend
- FastAPI

Database
- PostgreSQL

ORM
- SQLAlchemy

Migration
- Alembic

Containers
- Docker

CI/CD
- GitHub Actions

Deployment
- Coolify

Security
- CodeQL
- Trivy
- gitleaks
- pip-audit
- npm audit
- Dependabot

Testing
- pytest
- Vitest
- React Testing Library

Code Quality
- Ruff
- ESLint
- TypeScript

---

# Future Considerations

Potential future enhancements

- Kubernetes
- Horizontal autoscaling
- Distributed caching
- CDN integration
- Multi-region deployments
- Object storage
- Centralized observability

These require repository evidence and ADR approval before implementation.

---

# Final Principle

DevOps exists to deliver reliable software safely and repeatedly.

Every deployment should be predictable, observable, secure, and reversible.