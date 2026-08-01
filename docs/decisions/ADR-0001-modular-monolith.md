# ADR-0001: Modular monolith, not microservices

## Status
Accepted

## Context
Early brainstorming (BRD.docx) proposed independent microservices per
domain (Identity, Learning, Assessment, AI, …). Later sections of the same
document reverse this explicitly, and the concrete Sprint 0–2 specs all
assume one deployable backend.

## Decision
One FastAPI application. Modules (`identity`, `academic`, `cms`,
`assessment`, `ai`, …) are internal packages with hard boundaries
(`api/services/repositories/models`), not separate deployables.

## Why
- One team, one deploy target — microservices overhead (service discovery,
  distributed tracing, network calls between what could be function calls)
  has no payoff at this scale.
- Module boundaries are preserved in code, so extraction into a real
  microservice later is a refactor, not a rewrite.

## Consequences
- Shared database, shared process — a bug in one module can affect
  request latency for others. Mitigated by keeping modules internally
  decoupled (repository pattern, no cross-module ORM joins).
- Revisit only if a specific module needs independent scaling that the
  monolith genuinely can't provide.
