# ADR-0014: AI Gateway implementation — one module, graceful no-key fallback

## Status
Accepted

## Context
ADR-0004 froze the shape (thin provider abstraction, Claude only, four
agents: Tutor, Question Generator, Study Planner, Evaluator). This ADR
covers the concrete implementation choices ADR-0004 left open.

## Decision

**Location**: `app/modules/ai/`, not a top-level `app/ai/` sibling to
`app/modules/`. The BRD's EBTS spec puts AI at the top level since "no
educational content is stored there" — true, but it still has its own
API endpoints, a request-log table, and a study-plan table, which is
exactly the shape every other module already has. A second top-level
convention for one module isn't worth it; internal separation
(`gateway/`, `prompts/`, `services/`) achieves the same isolation.

**Provider abstraction**: `AIProvider` ABC with one method,
`generate(system_prompt, user_prompt, max_tokens) -> AIResponse`.
`ClaudeProvider` wraps the `anthropic` SDK. `FallbackProvider` returns a
clearly-labeled deterministic response when `ANTHROPIC_API_KEY` is empty
— matching the pattern already used elsewhere in this workspace (e.g.
NEETExamPrepAPP's `ai_service.py`) so every agent is fully testable
end-to-end with zero API cost, and "goes live" the moment a real key is
set — no code change required.

**Cost tracking from day one** (per ADR-0004): every gateway call writes
one row to `ai.ai_requests` — agent type, model, token counts, an
estimated cost, latency, and success/failure. Estimated cost uses
hardcoded per-model per-token rates (approximate, not billing-grade);
good enough for the observability ADR-0004 asked for, not good enough to
reconcile against an actual Anthropic invoice.

**Question Generator never bypasses ECAEP**: it calls the same
`ContentWorkflowService.create_item()` from Sprint 3, producing a
`DRAFT` content item attributed to the requesting admin. It goes through
`submit → review → publish` like any human-authored question — "always
human-reviewed before publish" from ADR-0004 is enforced structurally,
not by convention.

**Evaluator replaces the Sprint 3 stub in place**: `run_ai_check()` in
`app/modules/cms/services/ai_check_service.py` keeps its exact signature
and report shape, but now delegates to the real Evaluator agent instead
of returning `{"status": "skipped", ...}`. Nothing else in ECAEP changes.

**Study Planner reads real signal, doesn't invent it**: weak concepts
come from the student's actual `attempt_answers` (concepts where
`is_correct = false`), not a placeholder. No separate "AI memory" or
learning-profile table — that's still deferred per ADR-0007.

## Consequences
Without a real `ANTHROPIC_API_KEY`, every agent still runs and every
downstream flow (ECAEP review, question drafts, study plans) is fully
exercisable — verification in this sprint runs in fallback mode.
Swapping in a second provider (OpenAI, Gemini) later is a new
`AIProvider` subclass plus a config switch, per ADR-0004.
