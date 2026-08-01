# ADR-0004: AI Gateway from day one, single provider (Claude) behind it

## Status
Accepted

## Context
The review's first pass recommended deferring the AI Gateway abstraction
until a second provider was actually needed, to avoid premature
abstraction. CTO review pushed back: the abstraction is ~300-500 lines and
prevents vendor lock-in permanently, so building it now is cheap insurance,
not speculative generality.

## Decision
Build a thin `AIProvider` interface in `apps/backend/app/ai/providers/`
from Sprint 5 onward. Wire exactly one implementation (Claude) behind it.
Adding OpenAI/Gemini later is a new class + a config change, not an
architecture change.

## Agents (v1 — four, not twelve)
1. **Tutor** — explains concepts, cites source content
2. **Question Generator** — drafts practice MCQs, always human-reviewed
   before publish (never auto-publishes)
3. **Study Planner** — daily/weekly plan from target score + exam date
4. **Evaluator** — reviews AI- and human-authored content for quality
   before it clears editorial review (see ECAEP, ADR-0009)

Mentor, Diagram Agent, Digital Twin, and a 12-agent orchestrator are
explicitly deferred — see ADR-0007.

## Consequences
Cost tracking and prompt versioning are built into the Gateway from the
start (see `docs/architecture/roadmap.md`, Sprint 5), not retrofitted after
a cost surprise.
