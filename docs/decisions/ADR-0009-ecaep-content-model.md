# ADR-0009: Two-table content model (ECAEP), not a 40-table CMS

## Status
Accepted

## Decision
Every content type (concept note, question, flashcard, diagram, video
reference, formula sheet) is a `content_items` row with a type-specific
JSONB body, versioned via `content_versions`. One editorial workflow for
all types: `DRAFT → AI_CHECKED → IN_REVIEW → (APPROVED|CHANGES_REQUESTED)
→ PUBLISHED → ARCHIVED`.

Full spec: `docs/architecture/ecaep.md`.

## Why
The BRD's Content Domain proposed ~40 tables, one per type, each with a
90-150 field metadata profile — the right shape for a large content team,
the wrong shape for the team that exists today. A polymorphic two-table
model gets version history, review gates, and an AI-assist pass without
forty schemas to maintain.

## Consequences
Adding a seventh content type is a new Pydantic schema for the JSONB body,
not a migration. Rich per-type querying (e.g. "all questions with
difficulty=hard") goes through JSONB operators / generated columns rather
than dedicated typed columns — acceptable at MVP content volume.
