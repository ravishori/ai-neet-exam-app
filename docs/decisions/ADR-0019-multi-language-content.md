# ADR-0019: Multi-language content — Hindi, content only, not UI

## Status
Accepted

## Context
ADR-0007 deferred "multi-language content" to Phase 2. The roadmap's
original 9 sprints (SP0–SP9) are now done. This is the first Phase 2
item taken up, per direct user request to pick one and scope it.

Two columns already exist for exactly this, unused since the sprint
that created them:
- `cms.content_items.language` (String(10), default `"en"`) — every
  content item has had a language column since ECAEP shipped (SP3),
  but nothing has ever filtered by it, and no content in any language
  but English has ever been authored.
- `identity.users.preferred_language` (String(10), default `"en"`) —
  present since Sprint 1, accepted by `PATCH /users/me`, but never
  returned by any response schema and never read by anything.

This ADR wires up what was already reserved rather than adding new
columns.

## Decision

**Content is multi-language. The UI is not.** "Multi-language content"
means a concept note or question can exist in Hindi as well as
English — the thing a NEET student actually reads to learn. It does
not mean translating button labels, nav links, or page chrome
("Dashboard", "Practice", "Save changes"). Full UI i18n is a
substantially larger, separate effort (a translation-key system across
every component) that ADR-0007's "multi-language content" phrase did
not ask for and this ADR does not expand into.

**The academic hierarchy's names stay English-only.** Subject/Chapter/
Topic/Concept `name` columns are single strings, not translated tables.
Translating curriculum structure is a data-model expansion (a
translations table or per-row language columns four levels deep) that
buys little on its own — the value is in the content *under* a concept,
which this ADR does address, not in whether the concept is labeled
"Ohm's Law" or "ओम का नियम" in a breadcrumb.

**`preferred_language` becomes the default content filter**, exposed
via `UserResponse` (previously missing — it was accepted on write,
never returned on read) and editable through the Settings page, which
has been a placeholder since Sprint 1. `GET
/cms/concepts/{concept_id}/published` gains an optional `language`
query param; when omitted, it defaults server-side to the
authenticated user's `preferred_language` rather than requiring every
caller to remember to pass it.

**Fallback to English when nothing's translated yet, not an empty
page.** Content coverage will be partial for a long time — translating
every concept note and question is real ongoing work, not a one-time
migration. If a concept has no content in the requested language, the
endpoint returns the English versions instead with a flag
(`language_fallback: true`) so the frontend can show a small "showing
English — Hindi not available yet" notice rather than either an empty
page or silently mislabeling English content as translated.

**Hindi content is authored manually through the existing ECAEP
workflow, not AI-generated.** The Question Generator agent (ADR-0014)
stays English-only for now — verifying AI-generated Hindi content
would need a real `ANTHROPIC_API_KEY` (fallback mode only ever
produces the same placeholder English string), so it's not something
this sandbox can verify. The admin "New content" form gets a language
dropdown so a human author can create a Hindi item directly; it goes
through the same draft → submit → review → publish pipeline as any
other content, per ADR-0009.

**One concept seeded fully, not scattered coverage.** Per the same
"seed one chapter completely before scaling" precedent from ECAEP
(SP3), this ADR seeds real Hindi content for exactly one concept
(Ohm's Law) — a CONCEPT_NOTE and a QUESTION, pushed through the real
API end to end — to prove the pipeline, not to claim broad Hindi
coverage.

## Consequences
A student whose `preferred_language` is `hi` sees Hindi content
wherever it exists and English elsewhere, with a visible signal when
falling back — never a silent mix presented as if fully translated.
Adding a third language later is additive (another value in the same
`language` column, another dropdown option) — this ADR's design doesn't
special-case "en vs hi", it's language-agnostic by construction.
