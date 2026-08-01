# ADR-0010: Product name — Trinetra AI Learning OS (TALOS)

## Status
Accepted

## Context
BRD.docx refers to the product as "AI Learning OS" throughout and never
once as "Trinetra." TALOS.docx (a later artifact) and the build
instruction both settle on "Trinetra AI Learning OS (TALOS)."

## Decision
Canonical name everywhere: **Trinetra AI Learning OS**, abbreviated
**TALOS**. Package scope: `@trinetra/*` (once `packages/` has real
content). Repository/database identifiers use `trinetra_*` (database:
`trinetra_db`, roles: `trinetra_app` / `trinetra_migration` /
`trinetra_readonly`) — no further renaming once Sprint 0 ships.

## Consequences
Any reference to "AI Learning OS" without "Trinetra" found in new code or
docs going forward is a naming bug, not an alternate acceptable name.
