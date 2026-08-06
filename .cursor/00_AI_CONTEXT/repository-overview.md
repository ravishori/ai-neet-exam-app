\# Repository Overview

\## AI NEET Exam App

\### Enterprise Repository Navigation Guide



Version: 1.0



\---



\# Purpose



This document provides an overview of the repository structure and explains the purpose of each major directory.



It is intended to help Cursor AI and contributors quickly understand where functionality belongs.



This document is a navigation guide.



It does NOT replace implementation documentation or Architecture Decision Records (ADRs).



\---



\# Repository Philosophy



The repository should remain:



\- Organized

\- Predictable

\- Modular

\- Scalable

\- Easy to navigate



Each directory should have a clearly defined responsibility.



Avoid mixing unrelated concerns.



\---



\# Repository Root



The repository contains multiple logical areas.



Typical top-level directories include:



\- apps/

\- packages/

\- docs/

\- infrastructure/

\- scripts/

\- tests/

\- .github/

\- .cursor/



Always inspect the actual repository before assuming a directory exists.



The repository itself is the source of truth.



\---



\# apps/



Purpose



Contains deployable applications.



Examples



\- Frontend (Next.js)

\- Backend (FastAPI)

\- Future Admin Applications

\- Worker Services



Rules



Applications should not duplicate business logic.



Shared functionality should be extracted into reusable packages where appropriate.



\---



\# packages/



Purpose



Contains reusable libraries shared across applications.



Examples



\- UI components

\- Shared types

\- Utilities

\- Domain models

\- SDKs



Rules



Packages should remain framework-independent whenever practical.



Avoid application-specific business logic here.



\---



\# docs/



Purpose



Project documentation.



Examples



\- ADRs

\- Deployment Guides

\- API Documentation

\- Architecture Documents

\- Development Guides



Rules



Documentation must evolve together with implementation.



Never allow documentation to become outdated.



\---



\# infrastructure/



Purpose



Infrastructure configuration.



Examples



\- Docker

\- Reverse Proxy

\- Deployment

\- Cloud Configuration

\- Infrastructure as Code



Rules



Infrastructure changes should be version controlled.



\---



\# scripts/



Purpose



Development and operational scripts.



Examples



\- Data import

\- Database maintenance

\- Build utilities

\- Migration helpers

\- Deployment scripts



Rules



Scripts should be idempotent whenever possible.



\---



\# tests/



Purpose



Testing infrastructure.



Examples



\- Unit Tests

\- Integration Tests

\- End-to-End Tests

\- Fixtures

\- Test Utilities



Rules



Tests should mirror application structure where practical.



\---



\# .github/



Purpose



Repository automation.



Examples



\- GitHub Actions

\- CI/CD

\- Issue Templates

\- Pull Request Templates

\- Dependabot



\---



\# .cursor/



Purpose



AI Engineering Workspace.



Contains:



\- Project Context

\- Engineering Rules

\- Technical Standards

\- Prompts

\- Templates

\- Checklists

\- Examples

\- Engineering Decisions



Cursor should consult this workspace before implementation.



\---



\# Module Ownership



Every module should have:



A single responsibility.



Clear ownership.



Minimal dependencies.



Well-defined interfaces.



Avoid circular dependencies.



\---



\# Dependency Direction



Dependencies should flow inward.



Presentation



↓



Application



↓



Domain



↓



Infrastructure



Lower-level layers should never depend on higher-level layers.



\---



\# Naming Conventions



Directories



\- lowercase

\- descriptive

\- consistent



Files



\- meaningful names

\- predictable location



Avoid abbreviations unless widely understood.



\---



\# New Feature Placement



Before creating a new directory:



1\. Inspect the existing repository.



2\. Determine whether an appropriate location already exists.



3\. Extend existing modules whenever practical.



4\. Avoid creating unnecessary folders.



\---



\# Repository Evolution



The repository should evolve gradually.



Avoid large reorganizations.



Prefer incremental improvements.



Maintain backward compatibility whenever possible.



\---



\# Documentation Expectations



Whenever a major directory changes:



Update this document.



Repository documentation should accurately reflect implementation.



\---



\# Cursor Responsibilities



Before implementing any feature:



1\. Read README.md



2\. Read CURSOR\_RULES.md



3\. Read project-context.md



4\. Read architecture.md



5\. Read repository-overview.md



6\. Inspect the repository



7\. Verify existing implementation



Only then begin development.



\---



\# Final Principle



The repository should remain understandable to a new engineer joining the project.



Good organization reduces bugs, improves maintainability, and accelerates development.



Every change should leave the repository easier to navigate than before.

