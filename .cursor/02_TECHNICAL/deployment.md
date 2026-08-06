# Deployment Guide
## AI NEET Exam App
### Enterprise Deployment Runbook

Version: 1.0

---

# Purpose

This document defines the official deployment process for the AI NEET Exam App.

Deployment should always be

- Repeatable
- Automated
- Tested
- Documented
- Secure
- Reversible

Repository implementation is the source of truth.

---

# Deployment Philosophy

Deployments should never rely on undocumented manual steps.

Every deployment should be

Repeatable

Observable

Recoverable

Predictable

Production Ready

Automation should always be preferred.

---

# Repository First

Before deploying

Inspect

Docker configuration

GitHub Actions

Deployment documentation

Environment configuration

Migration history

Current application version

Never bypass existing deployment processes.

---

# Current Deployment Stack

Frontend

Next.js

Backend

FastAPI

Database

PostgreSQL

Migration

Alembic

Containerization

Docker

CI/CD

GitHub Actions

Deployment Platform

Coolify

Infrastructure

Linux VPS

---

# Deployment Environments

Supported environments

Development

Testing

Staging

Production

Each environment should have

Independent configuration

Independent database

Separate secrets

Environment-specific variables

---

# Pre-Deployment Checklist

Before deployment verify

✓ Repository clean

✓ Correct branch

✓ Latest changes pulled

✓ Tests passing

✓ Lint passing

✓ Type checking passing

✓ Docker builds successfully

✓ Security scans reviewed

✓ Documentation updated

✓ Release notes prepared

Do not deploy failing builds.

---

# Version Verification

Verify

Application version

Git commit

Git tag

Release notes

Migration status

Deployment should always be traceable.

---

# Environment Variables

Configuration should come only from

Environment variables

Never hardcode

Passwords

Secrets

API keys

Tokens

Certificates

Database credentials

Validate required variables before deployment.

---

# Database Migration

Migration process

1. Backup database

2. Review pending migrations

3. Execute Alembic migration

4. Validate schema

5. Verify application startup

Never manually modify production schema.

---

# Build Process

Backend

Build Docker image

Run tests

Verify image

Frontend

Build production bundle

Verify build

Run frontend tests

Build failures must stop deployment.

---

# Docker Standards

Verify

Dockerfile

Container health

Image size

Multi-stage builds

Runtime user

Container should be reproducible.

---

# Deployment Workflow

Developer

↓

Push changes

↓

GitHub Actions

↓

Lint

↓

Type Check

↓

Backend Tests

↓

Frontend Tests

↓

Security Scans

↓

Docker Build

↓

Image Publish

↓

Coolify Deployment

↓

Health Check

↓

Deployment Complete

---

# Health Checks

After deployment verify

Application available

API responding

Database connected

Authentication working

Search working

Question retrieval working

Admin portal available

Document ingestion available (if applicable)

Health endpoint responding

Deployment is not complete until health checks pass.

---

# Smoke Tests

Execute basic validation

Login

Question Browser

Search

Practice Session

Admin Login

Question Viewer

AI Explanation (if enabled)

Document Upload (if enabled)

Verify critical workflows.

---

# Post-Deployment Verification

Review

Logs

Database

CPU

Memory

Application health

Background jobs

Security alerts

Verify there are no unexpected errors.

---

# Rollback Strategy

Rollback should be documented before deployment.

Rollback options

Previous Docker image

Previous Git tag

Previous deployment

Database rollback (if supported)

Rollback should be tested periodically.

---

# Deployment Failure

If deployment fails

1. Stop rollout

2. Preserve logs

3. Identify failure

4. Roll back if necessary

5. Verify system health

6. Document incident

Never continue a partially failed deployment.

---

# Backup Strategy

Before production deployment

Backup

Database

Uploaded documents

Configuration

Critical assets

Verify backup integrity periodically.

---

# Security Verification

Confirm

HTTPS enabled

Secrets loaded correctly

Authentication working

Authorization working

No debug endpoints exposed

No development configuration enabled

---

# Performance Verification

Review

Application startup time

API response time

Memory usage

CPU usage

Database response

Container health

Investigate significant regressions.

---

# Monitoring

Verify monitoring is active.

Review

Health checks

Application logs

Deployment logs

Background tasks

Security events

Performance metrics

---

# Release Documentation

Every deployment should update

Release Notes

Deployment Log

Version

Changelog

Relevant ADRs (if applicable)

Repository documentation

---

# Disaster Recovery

Document recovery procedures for

Deployment failure

Database corruption

Configuration errors

Container failure

Infrastructure outage

Recovery procedures should be tested.

---

# Cursor Instructions

Before deployment

1. Inspect repository state.

2. Verify deployment configuration.

3. Validate environment variables.

4. Run tests.

5. Build containers.

6. Verify migrations.

7. Deploy through approved pipeline.

8. Execute health checks.

9. Update documentation.

Never recommend manual production changes that bypass the deployment process.

---

# Deployment Checklist

Before deployment

✓ Repository clean

✓ Correct branch

✓ Tests passing

✓ Docker builds

✓ Migrations reviewed

✓ Environment variables validated

✓ Security reviewed

✓ Documentation updated

After deployment

✓ Health checks

✓ Smoke tests

✓ Logs reviewed

✓ Monitoring active

✓ Performance verified

✓ Deployment recorded

---

# Known Repository Standards

Current deployment platform

- Docker
- GitHub Actions
- Coolify
- PostgreSQL
- Alembic
- Linux VPS

Deployment should remain compatible with the repository's Architecture Freeze.

Any major deployment architecture change requires a new ADR.

---

# Definition of Done

Deployment is complete only when

✓ Application deployed

✓ Health checks pass

✓ Smoke tests pass

✓ Logs clean

✓ Monitoring active

✓ Documentation updated

✓ Rollback available

✓ Production stable

---

# Final Principle

A successful deployment is not merely code reaching production.

A successful deployment is a verified, observable, secure, and recoverable production release that maintains service availability and protects student data.