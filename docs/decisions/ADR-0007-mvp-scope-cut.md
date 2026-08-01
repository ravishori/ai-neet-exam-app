# ADR-0007: MVP scope — what's cut from the BRD's vision, and why

## Status
Accepted

## Context
The BRD's vision includes ~280 tables, 700-1,000 APIs, a 4-layer competency
model (Concept → Learning Objective → Competency → Micro-Competency,
~21,000 micro-competencies for NEET alone), a full Enterprise Knowledge
Graph, a Student Digital Twin, multi-tenancy from v1, and a 12+ agent AI
orchestrator. The same document repeatedly acknowledges this shouldn't all
be built before an MVP, but never performs the cut itself.

## Decision
Deferred to Phase 2/3, not built in v1:
- Knowledge Graph / Enterprise Domain Ontology
- Micro-Competency layer (v1 uses a flat Concept → mastery score model)
- Student Digital Twin
- Multi-tenancy (organizations table reserved, not wired in)
- 12-agent AI orchestrator (v1 ships 4 agents — see ADR-0004)
- Multi-language content
- Native mobile apps (web-first, PWA-capable)
- Voice tutor, AI-generated video, live classes, parent/institution portals

## Why
None of these are load-bearing for validating "AI-first NEET platform with
real students." They're real Phase 2 ideas, kept as backlog rather than
scope, so the MVP has a finish line.

## Consequences
The ~45-60 table range the BRD itself calls its own "Phase 1 MVP" target
is the actual target here, not the 280-table enterprise vision.
