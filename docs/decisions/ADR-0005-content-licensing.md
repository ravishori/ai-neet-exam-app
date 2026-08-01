# ADR-0005: Content sourcing — NCERT-aligned and original only

## Status
Accepted

## Decision
Phase 1 content comes only from:
- NCERT-derived concepts, explanations, and diagrams (original wording)
- Content authored in-house
- Publicly available scientific facts
- Official NEET syllabus structure
- Previous-year questions only where legally permissible and reviewed

Explicitly **not ingested** without a signed license: Aakash, Allen,
Physics Wallah, Unacademy, or any other copyrighted coaching material.

## Why
NCERT (government-published) is comparatively safe to build on with
attribution; coaching-institute material is not automatically reusable and
carries real legal exposure if ingested wholesale.

## Consequences
No bulk-import pipeline for third-party question banks in v1. Content
volume grows only as fast as the editorial team (or AI Question Generator,
human-reviewed) can produce it — this is a known constraint on how much
syllabus coverage is possible before launch, not an oversight.
